"""The code of every step a flow can plan, found by the step's script key or its agent name.

A flow module fills the registry when it is imported: ``@script_step("<key>")`` registers the
handler of the script steps whose ``script`` text is that key, and ``@agent_step("<agent>", ...)``
registers the launch builder of the steps those agents perform. The journal runner asks the
registry for the code of each step it runs; a step whose key or agent has none fails with a
structured error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from typeguard import CollectionCheckStrategy, typechecked

from .handback_contract import OTHER_CAUSE
from .journal_steps import AgentBuilder, ScriptHandler, stage_of
from .models import StepError

# isort: split
# journal_steps puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import Step


class Registry:
    """The code of every step a flow can plan: script handlers by key, launch builders by agent."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self) -> None:
        """Start with no handler and no builder."""
        self._scripts: dict[str, ScriptHandler] = {}
        self._agents: dict[str, AgentBuilder] = {}

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def script_step(self, key: str) -> Callable[[ScriptHandler], ScriptHandler]:
        """Register the handler of the script steps whose ``script`` text is ``key``.

        Returns:
            The decorator, which returns the handler unchanged.

        Raises:
            ValueError: ``key`` is blank or already has a handler.

        """
        if not key.strip() or key in self._scripts:
            message: str = f"the script step key {key!r} is blank or already has a handler"
            raise ValueError(message)

        def register(handler: ScriptHandler) -> ScriptHandler:
            self._scripts[key] = handler
            return handler

        return register

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def agent_step(self, *agents: str) -> Callable[[AgentBuilder], AgentBuilder]:
        """Register the launch builder of the steps these agents perform.

        Returns:
            The decorator, which returns the builder unchanged.

        Raises:
            ValueError: No agent is named, or one is blank or already has a builder.

        """
        if not agents or any(not name.strip() or name in self._agents for name in agents):
            message: str = f"the agent names {agents!r} are empty, blank or already have a builder"
            raise ValueError(message)

        def register(builder: AgentBuilder) -> AgentBuilder:
            name: str
            for name in agents:
                self._agents[name] = builder
            return builder

        return register

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def script(self, step: Step) -> ScriptHandler:
        """Find the handler of a script step.

        Returns:
            The handler registered for the step's ``script`` text.

        Raises:
            StepError: No handler is registered for it.

        """
        key: str = step.get("script", "")
        handler: ScriptHandler | None = self._scripts.get(key)
        if handler is None:
            raise StepError(
                stage_of(step),
                OTHER_CAUSE,
                (f"step {step['id']} ({step['description']}): no handler is registered for the script {key!r}",),
            )
        return handler

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def agent(self, step: Step) -> AgentBuilder:
        """Find the launch builder of an agent step.

        Returns:
            The builder registered for the step's ``agent`` name.

        Raises:
            StepError: No builder is registered for it.

        """
        name: str = step.get("agent", "")
        builder: AgentBuilder | None = self._agents.get(name)
        if builder is None:
            raise StepError(
                stage_of(step),
                OTHER_CAUSE,
                (f"step {step['id']} ({step['description']}): no launch builder is registered for agent {name!r}",),
            )
        return builder


REGISTRY: Final[Registry] = Registry()
"""The registry the flow modules fill when they are imported."""
script_step: Final = REGISTRY.script_step
agent_step: Final = REGISTRY.agent_step
