"""The review of one repository's specification documents, and what follows a finding.

One reviewer session reads the documents against the implementation-level criteria. A finding
goes once to the author of the document it names. A finding an author disputes goes to the
decider, and a finding the decider upholds goes back to that author as a directive. A document
derived from one that changed is brought into agreement by its own author in the same pass.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from review_criteria import LEVEL_IMPLEMENTATION, load_criteria
from spec_review_contract import (
    RULING_FINDING_STANDS,
    SPEC_CORRECTION_SCHEMA_PATH,
    SPEC_DOCUMENTS,
    SPEC_REVIEW_SCHEMA_PATH,
    SPEC_RULING_SCHEMA_PATH,
    Dispute,
    Finding,
    RulingValue,
    SpecCorrection,
    SpecDocument,
    SpecReview,
    SpecRuling,
    validate_spec_correction,
    validate_spec_review,
    validate_spec_ruling,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agents import AgentRunner, strict_json
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import json_object, write_json
from orchestrator.core.models import AgentStep, StepError

_ARGUMENT_ERROR: Final[str] = "Arguments violate the spec_review input contract"

REVIEWER: Final[str] = "openapi-contract-reviewer"
DECIDER: Final[str] = "spec-decider"
CRITERIA_FILE: Final[str] = "skills/architecture-baseline/review-criteria.json"

REVIEW_RESULT: Final[str] = "Review of this repository's specification documents against the implementation criteria."
CORRECTION_RESULT: Final[str] = "Correction of this specification document for the spec review findings."
RULING_RESULT: Final[str] = "Ruling on each disputed spec review finding."
REVISION_RESULT: Final[str] = "Revision of this specification document to the directives of the ruling."

type Recorder = Callable[[tuple[str, ...], tuple[Path, ...]], None]


class SpecReviewOutcome(TypedDict):
    """What one repository's spec review came to; the file the flow records when the review is over.

    ``findings`` are the ids of the findings the review holds against an implementation-level
    criterion; ``dropped`` the ids it holds against anything else, which go no further.
    ``corrected`` and ``revised`` name the documents an author worked on again, after the review
    and after the ruling. ``disputed`` are the finding ids an author did not apply and ``upheld``
    those of them the decider ruled for.
    """

    review: str
    findings: list[str]
    dropped: list[str]
    corrected: list[SpecDocument]
    disputed: list[str]
    upheld: list[str]
    revised: list[SpecDocument]
    warnings: list[str]


@dataclass(frozen=True)
class ReviewedDocument:
    """One specification document: who wrote it, from what, and how it is checked."""

    kind: SpecDocument
    path: Path
    agent: str
    inputs: tuple[str, ...]
    check: Callable[[Path], object]
    derived_from: tuple[SpecDocument, ...] = ()

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate the fields before any session is started for the document.

        Raises:
            ValueError: The kind or a kind in ``derived_from`` is not a specification document.

        """
        check_type(self.path, Path)
        check_type(self.agent, str)
        check_type(self.inputs, tuple[str, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        check_type(self.check, Callable[[Path], object])
        if self.kind not in SPEC_DOCUMENTS or any(kind not in SPEC_DOCUMENTS for kind in self.derived_from):
            message: str = f"not a specification document kind: {self.kind!r} / {self.derived_from!r}"
            raise ValueError(message)


@dataclass(frozen=True)
class SpecReviewScope:
    """Everything one repository's spec review is handed.

    ``documents`` are in authoring order: a document comes after every document it is derived
    from. ``author_dirs`` are the directories an author session may read, as when it wrote.
    """

    stage: str
    slug: str
    work: Path
    trd: Path
    facts: Path
    criteria: Path
    documents: tuple[ReviewedDocument, ...]
    author_dirs: tuple[Path, ...]

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate the fields and the order of the documents.

        Raises:
            ValueError: A document kind is repeated, or a document precedes one it is derived from.

        """
        check_type(self.stage, str)
        check_type(self.slug, str)
        value: Path
        for value in (self.work, self.trd, self.facts, self.criteria):
            check_type(value, Path)
        check_type(
            self.documents,
            tuple[ReviewedDocument, ...],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        check_type(self.author_dirs, tuple[Path, ...], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        seen: list[SpecDocument] = []
        document: ReviewedDocument
        for document in self.documents:
            if document.kind in seen or any(kind not in seen for kind in document.derived_from):
                message: str = f"specification documents are repeated or out of authoring order at {document.kind!r}"
                raise ValueError(message)
            seen.append(document.kind)


@dataclass(frozen=True)
class _Seat:
    """Who runs one session of this step, reading which directories."""

    agent: str
    dirs: tuple[Path, ...]


@dataclass
class _Pass:
    """What one pass of author sessions did."""

    worked: list[SpecDocument]
    changed: set[SpecDocument]
    disputes: dict[str, Path]
    warnings: list[str]


class SpecReviewStep:
    """One repository's spec review, from the reviewer session to the recorded result."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(
        self,
        scope: SpecReviewScope,
        store: ArtifactStore,
        runner: AgentRunner,
        record: Recorder,
    ) -> None:
        """Bind the scope, the receipt store, the session runner and the receipt writer.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if (
            not isinstance(scope, SpecReviewScope)
            or not isinstance(store, ArtifactStore)
            or not isinstance(runner, AgentRunner)
            or not callable(record)
        ):
            raise TypeError(_ARGUMENT_ERROR)
        self.scope: SpecReviewScope = scope
        self.store: ArtifactStore = store
        self.runner: AgentRunner = runner
        self.record: Recorder = record
        self.ran: bool = False
        self.review_path: Path = scope.work / f"spec-{scope.slug}.review.json"
        self.ruling_path: Path = scope.work / f"spec-{scope.slug}.ruling.json"
        self.result_path: Path = scope.work / f"spec-{scope.slug}.review-outcome.json"

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def review_inputs(self) -> tuple[str, ...]:
        """Name the files the reviewer is handed: the documents, the TRD, the context and the criteria.

        Returns:
            The paths, the documents first, in authoring order.

        """
        return (
            *(str(document.path) for document in self.scope.documents),
            str(self.scope.trd),
            str(self.scope.facts),
            str(self.scope.criteria),
        )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self) -> SpecReviewOutcome:
        """Review the documents and carry every finding to its end, or reuse a recorded result.

        A recorded result is reused while the documents, the TRD, the context and the criteria
        are the bytes it was recorded against, so a review is not repeated for unchanged specs.
        A session that fails raises StepError from the runner and nothing is recorded.

        Returns:
            The result, as recorded in ``result_path``.

        """
        if self.store.reusable(self.review_inputs(), (self.result_path,)):
            return check_type(
                strict_json(self.result_path),
                SpecReviewOutcome,
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        self.ran = True
        review: SpecReview = self._review()
        allowed: frozenset[str] = frozenset(
            entry.id for entry in load_criteria(self.scope.criteria).at_level(LEVEL_IMPLEMENTATION)
        )
        findings: list[Finding] = [finding for finding in review["findings"] if finding["criterion"] in allowed]
        dropped: list[str] = [finding["id"] for finding in review["findings"] if finding["criterion"] not in allowed]
        warnings: list[str] = [
            f"spec review finding {identifier} names no implementation-level criterion and was dropped"
            for identifier in dropped
        ]
        ended: SpecReviewOutcome = {
            "review": str(self.review_path),
            "findings": [finding["id"] for finding in findings],
            "dropped": dropped,
            "corrected": [],
            "disputed": [],
            "upheld": [],
            "revised": [],
            "warnings": warnings,
        }
        if findings:
            corrections: _Pass = self._author_pass(findings, (self.review_path,), "correction", CORRECTION_RESULT)
            ended["corrected"] = corrections.worked
            ended["disputed"] = sorted(corrections.disputes)
            warnings.extend(corrections.warnings)
            upheld: list[Finding] = self._ruling(findings, corrections.disputes, warnings)
            ended["upheld"] = sorted({finding["id"] for finding in upheld})
            if upheld:
                revisions: _Pass = self._author_pass(
                    upheld,
                    (self.review_path, self.ruling_path),
                    "revision",
                    REVISION_RESULT,
                )
                ended["revised"] = revisions.worked
                warnings.extend(revisions.warnings)
                warnings.extend(
                    f"spec review finding {identifier} was disputed again after the ruling; the ruling stands"
                    for identifier in sorted(revisions.disputes)
                )
        return self._finish(ended)

    def _finish(self, ended: SpecReviewOutcome) -> SpecReviewOutcome:
        """Write and record the result: the one place this step's result becomes an artifact.

        Returns:
            The result written.

        """
        write_json(self.result_path, json_object(ended))
        self.record(self.review_inputs(), (self.result_path,))
        return ended

    def _session(self, name: str, seat: _Seat, inputs: tuple[str, ...], schema: Path, outcome: str) -> Path:
        """Run one session of this step and accept its JSON result under the given schema.

        Returns:
            The accepted result file, ``spec-<slug>.<name>.json`` in the work directory.

        """
        file_name: str = f"spec-{self.scope.slug}.{name}.json"
        return self.runner.run(
            AgentStep(
                stage=f"{self.scope.stage}:{name}",
                agent=seat.agent,
                inputs=inputs,
                output=self.scope.work / "candidates" / file_name,
                final=self.scope.work / file_name,
                validate=schema,
                outcome=outcome,
                add_dirs=(*seat.dirs, self.scope.criteria.parent),
            ),
        )

    def _review(self) -> SpecReview:
        """Run the one reviewer session for this repository.

        Returns:
            The review, validated.

        """
        seat: _Seat = _Seat(REVIEWER, (self.scope.work,))
        accepted: Path = self._session("review", seat, self.review_inputs(), SPEC_REVIEW_SCHEMA_PATH, REVIEW_RESULT)
        return validate_spec_review(strict_json(accepted), str(accepted))

    def _author_pass(self, findings: list[Finding], basis: tuple[Path, ...], name: str, outcome: str) -> _Pass:
        """Send each document's findings to its author, once, in authoring order.

        A document with no finding of its own is also worked on when a document it is derived
        from changed in this pass, so the set stays in agreement.

        Returns:
            The documents worked on, those whose bytes changed, each disputed finding id with
            the file that states the dispute, and the warnings raised.

        Raises:
            StepError: A document no longer passes its own check after its author worked on it.

        """
        done: _Pass = _Pass([], set(), {}, [])
        document: ReviewedDocument
        dispute: Dispute
        for document in self.scope.documents:
            own: set[str] = {finding["id"] for finding in findings if finding["document"] == document.kind}
            if not own and not done.changed.intersection(document.derived_from):
                continue
            stage: str = f"{document.kind}.{name}"
            before: str = check_type(self.store.module.sha256_file(document.path), str)
            accepted: Path = self._session(
                stage,
                _Seat(document.agent, self.scope.author_dirs),
                tuple(
                    dict.fromkeys((
                        *document.inputs,
                        str(self.scope.facts),
                        str(document.path),
                        *(str(path) for path in basis),
                    )),
                ),
                SPEC_CORRECTION_SCHEMA_PATH,
                outcome,
            )
            correction: SpecCorrection = validate_spec_correction(strict_json(accepted), str(accepted))
            try:
                document.check(document.path)
            except (OSError, ValueError) as exc:
                self.store.invalidate((document.path,))
                failed: str = f"{self.scope.stage}:{stage}"
                raise StepError(failed, OTHER_CAUSE, (str(document.path), str(exc))) from exc
            self.record(document.inputs, (document.path,))
            done.worked.append(document.kind)
            if check_type(self.store.module.sha256_file(document.path), str) != before:
                done.changed.add(document.kind)
            for dispute in correction["disputes"]:
                if dispute["findingId"] in own:
                    done.disputes[dispute["findingId"]] = accepted
                else:
                    done.warnings.append(
                        f"{document.agent} disputed {dispute['findingId']}, which is no finding on its document",
                    )
        return done

    def _ruling(self, findings: list[Finding], disputes: dict[str, Path], warnings: list[str]) -> list[Finding]:
        """Run the one decider session for every disputed finding of this repository.

        No dispute starts no session. A disputed finding the decider gives no ruling on leaves
        its document as the author left it, with a warning.

        Returns:
            The disputed findings the decider upheld.

        """
        if not disputes:
            return []
        accepted: Path = self._session(
            "ruling",
            _Seat(DECIDER, self.scope.author_dirs),
            (
                str(self.review_path),
                *dict.fromkeys(str(path) for path in disputes.values()),
                *(str(document.path) for document in self.scope.documents),
                str(self.scope.trd),
                str(self.scope.criteria),
            ),
            SPEC_RULING_SCHEMA_PATH,
            RULING_RESULT,
        )
        ruling: SpecRuling = validate_spec_ruling(strict_json(accepted), str(accepted))
        ruled: dict[str, RulingValue] = {
            entry["findingId"]: entry["ruling"] for entry in ruling["rulings"] if entry["findingId"] in disputes
        }
        warnings.extend(
            f"spec review finding {identifier} was disputed and not ruled on; its document stands"
            for identifier in sorted(set(disputes) - set(ruled))
        )
        return [finding for finding in findings if ruled.get(finding["id"]) == RULING_FINDING_STANDS]
