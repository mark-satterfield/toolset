# Python implementation standard

Python code must be typed by construction, including operational tooling.

- Explicitly annotate every parameter, return value, class attribute, and local variable. Use the most specific known concrete type, `TypedDict`, dataclass, `Literal`, enum, or `NewType`. Preserve relationships with type parameters and `ParamSpec`; use a `Protocol` or abstract base class for behavioral interfaces.
- Never use `Any`. Use `object` only for an unknowable value entering from I/O, and narrow it in that same function before passing it inward. Do not erase known producer types or hide gaps behind `cast`, broad callable signatures, suppressions, or permissive adapters.
- Accept the widest appropriate read-only interface (`Sequence`, `Mapping`, `Iterable`, or `Collection`) and return a narrow concrete type. Make optional values and `None` semantics precise. Use modern type aliases and generics, `Self`, `Final`, and `ClassVar` where appropriate for the actual runtime.
- Wrap third-party APIs at the edge. Parse external JSON, subprocess output, environment variables, and HTTP data into validated frozen dataclasses or Pydantic models before internal use. Own writers and readers share one exact contract; reject drift instead of accepting either shape.
- Check preconditions explicitly at every public function and module boundary with `if` and a descriptive `TypeError` or `ValueError`. Assertions and runtime type decorators do not replace these guards. Keep validated internal state typed and make illegal states unrepresentable. Handle unions and enums exhaustively with `assert_never` where appropriate.
- Preserve original error causes and name the failed operation. Handle failures explicitly; never swallow them or use bare `except`. Document return values and failure modes. Update every caller in the same change.
- Replace casts with narrowing. A truly unavoidable suppression names one specific rule and includes a one-line reason tied to a verified limitation.
- Deliver correct imports, docstrings, and types in the first draft. Before completion, run `ruff check`, `ruff format --check`, strict mypy with the repository's additional Any restrictions, and focused producer/consumer probes. A clean static check is not proof that runtime preconditions or real data contracts are correct.
- Tier 2 does not add test suites or coverage gates. Use a few focused pure checks; only the owner runs the pipeline.
