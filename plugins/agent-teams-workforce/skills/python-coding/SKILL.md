---
name: python-coding
description: The owner's Python coding rules — PEP 8 and PEP 257 style, naming and constants, flat structure under a Cognitive Complexity of 7, idioms, typed-by-construction types with no Any, contracts and boundary validation, error handling, design, concurrency, and the lint, format, strict type and probe checks a change passes before it is finished. Use whenever writing, editing, refactoring, reviewing or testing Python code (.py files), operational tooling and scripts included.
user-invocable: true
---

# Python: typed-by-construction

Write Python as if the language were statically typed and the checker ran on every keystroke. Code is correct when written, so mypy and Ruff confirm it and never correct it. Type all Python by construction, operational tooling included.

These rules apply to every piece of Python an agent writes, changes or reviews. A reviewer judges Python code against them.

## How to read this skill

- Every rule has one form: the instruction, then the reason where one is given, then at most one example.
- An example is two labelled code blocks, "Instead of" and "Write". The "Instead of" block shows the habit the rule bans. An example illustrates its rule; the rule covers every case its text describes, not only the case shown.
- Examples are shortened. A function in an example has a one-line docstring and no precondition guards, unless the rule is about them. Code you write carries both in full.
- Two rules are marked **CRITICAL**. The mark flags a rule the owner emphasised. It does not relax any unmarked rule.
- A section name in parentheses, such as (Error handling), names the section that states that subject.

## Habits to replace on sight

Replace these five recurring habits on sight. Each row points to the section that states the rule in full.

| Do not | Do instead | Section |
|---|---|---|
| `except Exception:` or a bare `except:` | Specific exceptions, handled gracefully | Error handling |
| Deeply nested `if/else` blocks | Guard clauses and early returns | Structure and complexity |
| Hardcoded strings, paths, and magic numbers | Configuration constants, or `pathlib.Path` objects, at the top of the file | Naming and constants |
| Manual loops with `.append()` | Comprehensions or generator expressions | Structure and complexity |
| Cryptic variable names (`x`, `data`, `temp`) | Descriptive snake_case names that explain intent | Naming and constants |

## Style and docstrings

- Follow PEP 8 in all Python.
- Write all Python Pythonically.
- Document return values and failure modes.
- Follow PEP 257 in every docstring. Lay out the docstring in the Google-style `Args:`, `Returns:`, and `Raises:` sections. Those sections are the layout used within PEP 257's conventions, so the two are one standard.

  Instead of:

  ```python
  from pathlib import Path

  from pydantic import ValidationError


  def load_profile(profile_path: Path) -> StoredProfile:
      """Loads the profile."""
      with profile_path.open() as profile_file:
          profile_json: str = profile_file.read()
      try:
          return StoredProfile.model_validate_json(profile_json)
      except ValidationError as error:
          message: str = f"Loading the profile at {profile_path} failed"
          raise ValueError(message) from error
  ```

  Write:

  ```python
  from pathlib import Path

  from pydantic import ValidationError


  def load_profile(profile_path: Path) -> StoredProfile:
      """Load a user profile from a JSON file.

      Args:
          profile_path: Location of the profile file.

      Returns:
          The validated profile.

      Raises:
          ValueError: If the file does not hold a valid profile.
      """
      with profile_path.open() as profile_file:
          profile_json: str = profile_file.read()
      try:
          return StoredProfile.model_validate_json(profile_json)
      except ValidationError as error:
          message: str = f"Loading the profile at {profile_path} failed"
          raise ValueError(message) from error
  ```

## Naming and constants

- Name every variable in descriptive snake_case that explains its intent. Replace cryptic names such as `x`, `data`, and `temp`.

  Instead of:

  ```python
  data: list[int] = find_expired_user_ids(users)
  ```

  Write:

  ```python
  expired_user_ids: list[int] = find_expired_user_ids(users)
  ```

- Define strings, paths, and numbers that carry meaning as configuration constants at the top of the file. Define paths as `pathlib.Path` objects there. Replace hardcoded strings, hardcoded paths, and magic numbers in the body of the code with those names.

## Structure and complexity

- **CRITICAL:** Write every function as clean, idiomatic, flat Python with a Cognitive Complexity score of less than 7. Nested, high-cognitive-load structures are forbidden. The rules that follow in this section achieve it.
- Write zero nested loops or conditions. Nesting depth is at most 1 layer: no `if` inside a `for` or `while` loop, and no loop inside an `if`, unless it is absolutely unavoidable.
- Keep control flow flat with guard clauses; they are mandatory. Handle edge cases, errors, and empty states first and return immediately, so the core logic stays at the top level of the function. Replace deep nesting, where the entire main logic sits inside one massive `if` block or in deeply nested `if/else` blocks.

  Instead of:

  ```python
  from collections.abc import Sequence


  def average_score(scores: Sequence[float] | None) -> float | None:
      """Return the mean score, or None when there are no scores."""
      if scores is not None:
          if len(scores) > 0:
              score_total: float = sum(scores)
              return score_total / len(scores)
      return None
  ```

  Write:

  ```python
  from collections.abc import Sequence


  def average_score(scores: Sequence[float] | None) -> float | None:
      """Return the mean score, or None when there are no scores."""
      if not scores:  # Catch None and empty collections early
          return None
      score_total: float = sum(scores)
      return score_total / len(scores)
  ```

- Eliminate `else` blocks by validating conditions at the very beginning of the function. When a condition is invalid, return or raise immediately.

  Instead of:

  ```python
  def reciprocal(divisor: float) -> float | None:
      """Return one divided by the divisor, or None when it is not positive."""
      if divisor > 0:
          return 1 / divisor
      else:
          return None
  ```

  Write:

  ```python
  def reciprocal(divisor: float) -> float | None:
      """Return one divided by the divisor, or None when it is not positive."""
      if divisor <= 0:
          return None
      return 1 / divisor
  ```

- Build collections with list, dictionary, or set comprehensions in place of manual loop accumulation. For data processing (transformation, extraction, or filtering) a comprehension or a generator expression is mandatory. Replace a manual `for` loop with `.append()`.

  Instead of:

  ```python
  user_emails: list[str] = []
  for user in users:
      user_emails.append(user.email)
  ```

  Write:

  ```python
  user_emails: list[str] = [user.email for user in users]
  ```

- Use a generator expression for a large dataset whose full memory allocation is not needed immediately.
- Extract complex logic. When a function has to check several logical conditions together, move that evaluation, or the block that follows it, into its own small, dedicated helper function.

  Instead of:

  ```python
  if user.is_admin and user.is_active or user.is_owner:
      open_settings(user)
  ```

  Write:

  ```python
  def can_open_settings(user: User) -> bool:
      """Report whether the user may open the settings."""
      return user.is_admin and user.is_active or user.is_owner


  if can_open_settings(user):
      open_settings(user)
  ```

- Write code that reads as if a Principal Engineer who puts readability and linear scanning first wrote it. Rewrite, before delivering it, any function that cannot be read easily from top to bottom without jumping back and forth to track state.

## Idioms

- Combine consecutive or nested `if` statements with logical operators (`and`, `or`). Two simple conditions are combined with `and`/`or`; a longer mix of conditions is extracted into a named helper (Structure and complexity).

  Instead of:

  ```python
  if user.is_active:
      if user.has_verified_email:
          send_welcome_email(user)
  ```

  Write:

  ```python
  if user.is_active and user.has_verified_email:
      send_welcome_email(user)
  ```

- Test one value against several alternatives with membership in a collection (`in`).

  Instead of:

  ```python
  if status == Status.ACTIVE or status == Status.PENDING or status == Status.PAUSED:
      schedule_renewal(subscription)
  ```

  Write:

  ```python
  if status in {Status.ACTIVE, Status.PENDING, Status.PAUSED}:
      schedule_renewal(subscription)
  ```

- Use `dict.get()` for a lookup with a default. It is the fast built-in form.

  Instead of:

  ```python
  retry_limit: int = retry_limits[service_name] if service_name in retry_limits else default_retry_limit
  ```

  Write:

  ```python
  retry_limit: int = retry_limits.get(service_name, default_retry_limit)
  ```

- Use a set for membership lookups. A list is scanned on every lookup.

  Instead of:

  ```python
  allowed_user_ids: list[int] = load_allowed_user_ids()
  if user_id in allowed_user_ids:
      grant_access(user_id)
  ```

  Write:

  ```python
  allowed_user_ids: set[int] = set(load_allowed_user_ids())
  if user_id in allowed_user_ids:
      grant_access(user_id)
  ```

- Use `str.join()` to build a string from parts. It is the fast built-in form.

  Instead of:

  ```python
  report_text: str = ""
  for report_line in report_lines:
      report_text += report_line
  ```

  Write:

  ```python
  report_text: str = "".join(report_lines)
  ```

- Return an expression directly. A variable allocated only to be returned on the next line is redundant.

  Instead of:

  ```python
  from collections.abc import Sequence
  from decimal import Decimal


  def invoice_total(invoices: Sequence[Invoice]) -> Decimal:
      """Return the sum of the invoice amounts."""
      total_amount: Decimal = sum_amounts(invoices)
      return total_amount
  ```

  Write:

  ```python
  from collections.abc import Sequence
  from decimal import Decimal


  def invoice_total(invoices: Sequence[Invoice]) -> Decimal:
      """Return the sum of the invoice amounts."""
      return sum_amounts(invoices)
  ```

- Test a Boolean directly. Comparing a Boolean with `True` or `False` is redundant.

  Instead of:

  ```python
  if is_file_missing == True:
      create_report(report_path)
  if is_valid == False:
      reject_upload(upload)
  ```

  Write:

  ```python
  if is_file_missing:
      create_report(report_path)
  if not is_valid:
      reject_upload(upload)
  ```

- Manage every resource with a context manager (a `with` statement).
- Perform all I/O operations inside a context manager.
- Use built-in functions such as `any()`, `all()`, and `enumerate()` in place of a manually maintained flag or counter.

  Instead of:

  ```python
  has_admin: bool = False
  for user in users:
      has_admin = has_admin or user.is_admin
  ```

  Write:

  ```python
  has_admin: bool = any(user.is_admin for user in users)
  ```

## Types

- Annotate every parameter, return value, class attribute, and local variable. Inference is for the checker; annotations are for the reader.

  Instead of:

  ```python
  total = 0
  names = []
  ```

  Write:

  ```python
  total: int = 0
  names: list[str] = []
  ```

- Cover every public API and every function signature with strict type hints, with no exceptions.
- Declare the return type explicitly in every function signature, including a function that returns `None`. Never leave the return type for the type checker to infer.

  Instead of:

  ```python
  def save_log(log_lines: list[str], message: str):
      """Append the message to the log lines."""
      log_lines.append(message)
  ```

  Write:

  ```python
  def save_log(log_lines: list[str], message: str) -> None:
      """Append the message to the log lines."""
      log_lines.append(message)
  ```

- Use the most specific type that is known. Name the concrete class, `TypedDict`, dataclass, `Literal`, `Enum`, or `NewType` that describes the value.
- Never write `Any`. Replace it with the real type in every position, including `dict[str, Any]`, `*args: Any`, and `Callable[..., Any]`: write `dict[str, int]`, `*args: str`, `Callable[[int, str], bool]`.
- Write a value that is one of several known types as an explicit union (`X | Y`).

  Instead of:

  ```python
  from typing import Any


  def split_reply(reply: Any) -> Any:
      """Split a reply into its words."""
      return str(reply).split()
  ```

  Write:

  ```python
  def split_reply(reply: str | int) -> list[str]:
      """Split a reply into its words."""
      return str(reply).split()
  ```

- Use a generic instead of erasing the type. When a function processes several types and its input and output types are linked, a generic keeps them consistent where `Any` would strip the type away.

  Instead of:

  ```python
  from collections.abc import Sequence
  from typing import Any


  def first_item(items: Sequence[Any]) -> Any:
      """Return the first item."""
      return items[0]
  ```

  Write:

  ```python
  from collections.abc import Sequence


  def first_item[T](items: Sequence[T]) -> T:
      """Return the first item."""
      return items[0]
  ```

- Preserve every such relationship with type parameters, and with `ParamSpec` for a callable's parameters.
- Write the PEP 695 spelling of a generic: `def function_name[T: Base](value: T) -> T`. On a Python version before 3.12, write the `TypeVar` spelling.

  Instead of (on a Python version before 3.12):

  ```python
  from collections.abc import Sequence


  def first_item[T](items: Sequence[T]) -> T:
      """Return the first item."""
      return items[0]
  ```

  Write (on a Python version before 3.12):

  ```python
  from collections.abc import Sequence
  from typing import TypeVar

  T = TypeVar("T")


  def first_item(items: Sequence[T]) -> T:
      """Return the first item."""
      return items[0]
  ```

- Carry a producer's known type through to its consumer. Never erase a known type. Fix a gap in the types; never hide it behind `cast`, a broad callable signature, a suppression, or a permissive adapter.
- Write `object` only for a value whose type is unknowable where it enters from outside (parsed JSON, `pickle`, third-party callbacks, an untyped third-party or legacy library's result).
- Narrow that `object` to a real type in the same function, then pass the narrowed value onward.
- Narrow a value already inside the program with `isinstance` or a `TypeGuard`. Data crossing a system boundary is narrowed by validating it with Pydantic (Contracts and validation).
- Require flexibility through abstraction: accept the widest appropriate read-only type (`Sequence`, `Mapping`, `Iterable`, `Collection`).
- Return the narrowest concrete type.
- Describe behavior with `Protocol` or an `ABC`.
- Define the required interface with `typing.Protocol`, and annotate the parameter with it, when a function accepts any object that has specific methods or attributes (structural typing, duck typing). `object` is not the type for that parameter.

  Instead of:

  ```python
  from collections.abc import Iterable


  def render_all(widgets: Iterable[object]) -> list[str]:
      """Render every widget."""
      return [widget.render() for widget in widgets]
  ```

  Write:

  ```python
  from collections.abc import Iterable
  from typing import Protocol


  class Renderable(Protocol):
      """An object that renders itself as text."""

      def render(self) -> str:
          """Return the rendered text."""
          ...


  def render_all(widgets: Iterable[Renderable]) -> list[str]:
      """Render every widget."""
      return [widget.render() for widget in widgets]
  ```

- Use modern syntax: `list[str]`, `X | None`, `type Alias = ...`, PEP 695 generics, `Self`, `Final`, `ClassVar`, each where appropriate for the actual runtime.
- Wrap third-party APIs at the edge. Wrap untyped third-party results there in a typed function or a `Protocol`, so untyped values never travel inward.
- Resolve type errors by fixing the code.
- Write a suppression only when it is truly unavoidable, as `# type: ignore[specific-code]` or `# noqa: RULE`. Name one specific rule and give a one-line reason tied to a verified limitation.
- Replace `cast` with narrowing.

## Contracts and validation

- State each function's contract in its signature: inputs, outputs, `None` as explicit `T | None`, and failures as documented exception types in the docstring.
- Make optional values and `None` semantics precise.
- Enforce preconditions at runtime on every public function and every module boundary with explicit `if ...: raise TypeError/ValueError(...)` carrying a descriptive message.
- Use `raise` rather than `assert` for these guards, because `assert` disappears under `-O`. Assertions and runtime type decorators do not replace the guards.
- Validate data crossing a system boundary (files, JSON, HTTP, environment, subprocess output, queue messages, database rows) with Pydantic at the boundary. Parse it into a Pydantic model before internal use.
- Model internal domain objects as frozen dataclasses.
- Pass only validated, typed objects to internal code. Keep validated internal state typed.
- Share one exact contract between the writers and readers you own. Reject drift instead of accepting either shape.
- Make illegal states unrepresentable: prefer `Enum`/`Literal` over strings, frozen dataclasses over dicts, and `NewType` over bare `str`/`int` identifiers.
- Model every structured domain object and data payload concretely, as a `dataclass`, a Pydantic model, or a `NamedTuple`. Never represent one with a generic `dict` or `Any`. Where the two rules above on system boundaries and internal domain objects apply, they choose the form: a Pydantic model at a system boundary, a frozen dataclass for an internal domain object.

  Instead of:

  ```python
  def contact_line(user: dict[str, str]) -> str:
      """Format a user's name and email address."""
      return f"{user['username']} <{user['email']}>"
  ```

  Write:

  ```python
  from dataclasses import dataclass
  from typing import NewType

  UserId = NewType("UserId", int)


  @dataclass(frozen=True)
  class UserProfile:
      """A registered user."""

      user_id: UserId
      username: str
      email: str


  def contact_line(user: UserProfile) -> str:
      """Format a user's name and email address."""
      return f"{user.username} <{user.email}>"
  ```

- Close every `match`/`if` chain over a union or enum with `assert_never(value)`, so a new variant fails the type check. `assert_never` is a function call, not an `assert` statement, so the rule against `assert` does not cover it. In an `if` chain each branch returns and `assert_never(value)` follows the chain at the top level, so the chain needs no `else`.
- Keep callers and callees consistent: when changing a signature, update every call site and the tests in the same change.

## Error handling

- **CRITICAL:** Never swallow an exception. Handle failures explicitly.
- Catch specific exception types (for example `ValueError`, `KeyError`); this is mandatory. Handle each one gracefully. Never write `except Exception:` or a bare `except:`.
- Preserve the original error cause and name the failed operation.

## Design

- Follow DRY: state each piece of logic or knowledge once, and have every other place call or reference it.
- Follow YAGNI: build what the current requirement needs, and add a capability when a real requirement calls for it.
- Follow KISS: choose the simplest design that meets the requirement, readable without explanation.
- Prioritize composition over inheritance: give a class the collaborators it needs as attributes, and describe shared behavior with a `Protocol`.
- Write no global variables. Pass state explicitly, as parameters and return values.
- Expose an attribute through `@property` in place of explicit getter and setter methods.

  Instead of:

  ```python
  class Account:
      """A customer account."""

      def __init__(self, owner_name: str) -> None:
          """Store the owner's name."""
          self._owner_name: str = owner_name

      def get_owner_name(self) -> str:
          """Return the owner's name."""
          return self._owner_name

      def set_owner_name(self, owner_name: str) -> None:
          """Replace the owner's name."""
          self._owner_name = owner_name
  ```

  Write:

  ```python
  class Account:
      """A customer account."""

      def __init__(self, owner_name: str) -> None:
          """Store the owner's name."""
          self._owner_name: str = owner_name

      @property
      def owner_name(self) -> str:
          """Return the owner's name."""
          return self._owner_name

      @owner_name.setter
      def owner_name(self, owner_name: str) -> None:
          """Replace the owner's name."""
          self._owner_name = owner_name
  ```

## Concurrency

- Use `asyncio` where appropriate: for I/O-bound work that runs concurrently.
- Run awaitables together with `asyncio.gather`, start background work with `asyncio.create_task`, and manage async resources with async context managers (`async with`).
- Keep synchronous code synchronous. The `asyncio` rule is no reason to make it async.

## Tooling and completion checks

- Satisfy the tooling while writing. Target `mypy --strict` and the project's Ruff config.
- Write code cleanly enough to pass Flake8, Ruff, and MyPy with zero warnings or errors on the first attempt.
- Treat laziness, an unhandled edge case, or messy formatting as a failed task.
- Deliver correct imports, docstrings, and types in the first draft: imports sorted, unused names removed, line length within config, and docstrings present as Ruff requires.
- Know the lint profile a file falls under before writing it. In the SkillSpoke repository, Python lints under the strict Ruff profile in `pyproject.toml`:
  - Service and library code: the full profile — type annotations, docstrings with `Returns:` and `Raises:`, no `print`, exception classes.
  - `ops/**/*.py`: the full profile, including annotations and docstrings. Diagnostics use `logging`; real CLI output uses `sys.stdout.write`.
  - `.claude/skills/**/scripts/*.py`: the existing skill-script exceptions apply; annotations and docstrings remain required.
- Before finishing, run these on the files changed and report zero diagnostics. Run them before attempting the commit: discovering lint debt at the pre-commit gate is the failure, not the gate itself.
  - `ruff check`
  - `ruff format --check`
  - strict mypy with the repository's additional `Any` restrictions
  - the generators' `--check`, when a schema or shared block changed
- A clean static check is not proof that runtime preconditions or real data contracts are correct. Probe the changed producer and its consumer once with realistic input: import the changed module and call the changed function or entry point.
- For tier 2 tooling (the machinery that builds SkillSpoke, as the root `AGENTS.md` "Code quality" section defines it), that probe is the sanity check. It is a throwaway, scoped to what changed: it is not kept, committed, wired into a hook, or run again by a later step. No test or check suite exists for tier 2 tooling and none is written; the owner's pipeline run is the test.
