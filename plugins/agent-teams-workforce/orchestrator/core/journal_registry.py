"""The code of every step a flow can plan, found by the step's script key or its agent name.

A flow module fills the registry when it is imported: ``@script_step("<key>")`` registers the
handler of the script steps whose ``script`` text is that key, and ``@agent_step("<agent>", ...)``
registers the launch builder of the steps those agents perform, and
``@any_agent_step(<names>)`` registers one launch builder for every other agent of a set: an agent
another module chose by name at run time, which no flow lists. The journal runner asks the
registry for the code of each step it runs; a step whose key or agent has none fails with a
structured error.

A flow that plans steps under a container while the run goes (not when the journal is created)
also registers the plans it makes there with ``plan_under``, so a journal written before a step
key was renamed can be replanned from the lane's current plan for that position.

A container a journal plans with no child steps is filled while the run goes, by a step that
plans steps under it or plans the steps that do. Its flow names the script keys and agents of
those steps with ``fills``, so a run whose empty container no step can fill any more fails before
its first step, not when it reaches the container.

A flow names with ``children_together`` the containers whose child containers do not depend on
each other (one per repository), so the runner runs those child containers at the same time.
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
from step_journal_contract import Step, StepPlan


class Registry:
    """The code of every step a flow can plan: script handlers by key, launch builders by agent."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self) -> None:
        """Start with no handler, no builder and no plan under a container."""
        self._scripts: dict[str, ScriptHandler] = {}
        self._agents: dict[str, AgentBuilder] = {}
        self._any_agent: tuple[frozenset[str], AgentBuilder] | None = None
        self._containers: dict[str, tuple[StepPlan, ...]] = {}
        self._fillers: dict[str, frozenset[str]] = {}
        self._together: set[str] = set()

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def plan_under(self, container: str, *plans: StepPlan) -> None:
        """Register the steps a flow plans under a container, in the order it plans them.

        Args:
            container: The description of the container step.
            plans: The plans, each with its description, purpose and script or agent.

        Raises:
            ValueError: ``container`` is blank, no plan is given, or the container already has plans.

        """
        if not container.strip() or not plans or container in self._containers:
            message: str = f"the container {container!r} is blank, has no plan or already has plans"
            raise ValueError(message)
        self._containers[container] = plans

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def plans_under(self, container: str) -> tuple[StepPlan, ...]:
        """Name the steps a flow plans under a container.

        Returns:
            The plans registered for the container's description; empty when none are.

        """
        return self._containers.get(container, ())

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def fills(self, container: str, *keys: str) -> None:
        """Register the script keys and agents of the steps that fill an empty container.

        A step fills the container when it plans steps under it, or plans the steps that do.

        Args:
            container: The description of the container step.
            keys: The script keys and agent names; added to those already registered.

        Raises:
            ValueError: ``container`` is blank, or no key is given or one is blank.

        """
        if not container.strip() or not keys or any(not key.strip() for key in keys):
            message: str = f"the container {container!r} or the keys {keys!r} that fill it are blank or missing"
            raise ValueError(message)
        self._fillers[container] = self._fillers.get(container, frozenset()) | frozenset(keys)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def fills_container(self, step: Step, container: str) -> bool:
        """Tell whether a step is one that fills a container.

        Returns:
            True when the step's script key or agent is registered as a filler of the container.

        """
        key: str | None = step.get("script") or step.get("agent")
        return key is not None and key in self._fillers.get(container, frozenset())

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def children_together(self, *containers: str) -> None:
        """Register containers whose child containers run at the same time.

        Args:
            containers: The descriptions of the container steps.

        Raises:
            ValueError: No container is named, or one is blank.

        """
        if not containers or any(not container.strip() for container in containers):
            message: str = f"the containers {containers!r} are empty or blank"
            raise ValueError(message)
        self._together.update(containers)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def runs_children_together(self, container: str) -> bool:
        """Tell whether a container's child containers run at the same time.

        Returns:
            True when the container's description is registered with ``children_together``.

        """
        return container in self._together

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def handles(self, step: Step | StepPlan) -> bool:
        """Tell whether the registry holds the code of a step or of a step plan.

        Returns:
            True when a handler is registered for its script key, or a launch builder for its
            agent; False for one with neither, or whose key or agent has none.

        """
        if "script" in step:
            return step["script"] in self._scripts
        if "agent" in step:
            return self._builder(step["agent"]) is not None
        return False

    def _builder(self, name: str) -> AgentBuilder | None:
        """Find the launch builder of one agent: its own, else the one for any agent of the set.

        Returns:
            The builder; None when the agent has none and is not in the set.

        """
        own: AgentBuilder | None = self._agents.get(name)
        if own is not None or self._any_agent is None:
            return own
        names: frozenset[str]
        builder: AgentBuilder
        names, builder = self._any_agent
        return builder if name in names else None

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
    def any_agent_step(self, agents: frozenset[str]) -> Callable[[AgentBuilder], AgentBuilder]:
        """Register one launch builder for every agent of a set that has no builder of its own.

        An agent registered with ``agent_step`` keeps its own builder, whenever it is registered.

        Returns:
            The decorator, which returns the builder unchanged.

        Raises:
            ValueError: The set is empty or holds a blank name, or a builder for any agent is
                already registered.

        """
        if not agents or any(not name.strip() for name in agents) or self._any_agent is not None:
            message: str = "the set of agents is empty, holds a blank name, or a builder for any agent exists"
            raise ValueError(message)

        def register(builder: AgentBuilder) -> AgentBuilder:
            self._any_agent = (agents, builder)
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
        builder: AgentBuilder | None = self._builder(name)
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
any_agent_step: Final = REGISTRY.any_agent_step
plan_under: Final = REGISTRY.plan_under
fills: Final = REGISTRY.fills
children_together: Final = REGISTRY.children_together
