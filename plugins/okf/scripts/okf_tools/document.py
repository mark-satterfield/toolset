# SPDX-License-Identifier: Apache-2.0
# Adapted from the OKF reference agent (Google Cloud Knowledge Catalog),
# licensed under Apache License 2.0:
# https://github.com/GoogleCloudPlatform/knowledge-catalog
# Modifications for the okf Claude Code plugin: validation is split into a
# spec floor (type only) and a stricter reference profile (type, title,
# description, timestamp). See NOTICE.md in this directory.
"""Canonical OKF concept document: parse, serialize, validate.

The OKF v0.1 spec makes `type` the *only* hard requirement. The reference
agent's own tooling additionally expects `title`, `description`, and
`timestamp`. We keep both bars available: `validate_spec()` enforces the
floor; `validate_profile()` enforces the stricter house style.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

# The OKF v0.1 conformance floor — the only field the spec mandates.
SPEC_REQUIRED_KEYS = ("type",)

# The stricter "reference profile" the OKF authors' agent writes to. Superset
# of the spec floor; missing any of these is a house-style problem, not a
# spec-conformance failure.
PROFILE_REQUIRED_KEYS = ("type", "title", "description", "timestamp")

# Recommended-but-optional fields we surface as warnings, never errors.
RECOMMENDED_KEYS = ("title", "description", "timestamp")

_FRONTMATTER_DELIM = "---"


class OKFDocumentError(ValueError):
    pass


@dataclass
class OKFDocument:
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @classmethod
    def parse(cls, text: str) -> "OKFDocument":
        lines = text.splitlines()
        if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
            return cls(frontmatter={}, body=text)

        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == _FRONTMATTER_DELIM:
                end_idx = i
                break
        if end_idx is None:
            raise OKFDocumentError("Unterminated YAML frontmatter block")

        fm_text = "\n".join(lines[1:end_idx])
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError as e:
            raise OKFDocumentError(f"Invalid YAML in frontmatter: {e}") from e
        if not isinstance(fm, dict):
            raise OKFDocumentError("Frontmatter must be a YAML mapping")

        body = "\n".join(lines[end_idx + 1:])
        if body.startswith("\n"):
            body = body[1:]
        return cls(frontmatter=fm, body=body)

    def serialize(self) -> str:
        fm_text = yaml.safe_dump(
            self.frontmatter, sort_keys=False, allow_unicode=True
        ).rstrip()
        body = self.body if self.body.endswith("\n") else self.body + "\n"
        return f"{_FRONTMATTER_DELIM}\n{fm_text}\n{_FRONTMATTER_DELIM}\n\n{body}"

    def missing(self, keys: tuple[str, ...]) -> list[str]:
        return [k for k in keys if not self.frontmatter.get(k)]

    def validate_spec(self) -> None:
        """Enforce the OKF v0.1 floor: a non-empty `type`."""
        missing = self.missing(SPEC_REQUIRED_KEYS)
        if missing:
            raise OKFDocumentError(
                f"Missing spec-required frontmatter keys: {', '.join(missing)}"
            )

    def validate_profile(self) -> None:
        """Enforce the stricter reference profile (type/title/description/timestamp)."""
        missing = self.missing(PROFILE_REQUIRED_KEYS)
        if missing:
            raise OKFDocumentError(
                f"Missing profile-required frontmatter keys: {', '.join(missing)}"
            )
