# Python implementation standard

- Type every parameter and return value. Use concrete types; do not use `Any`.
- Parse JSON files, subprocess output, environment variables and HTTP data into typed structures and validate them where they enter the process.
- Name the failed operation in errors and preserve the original cause. Handle failures explicitly; never swallow them or use bare `except`.
- Give our own writer and reader one exact contract. Reject contract drift instead of accepting either shape.
- Write docstrings required by the repository Ruff profile, including return values and raised errors.
- Run `ruff check`, `ruff format --check` and `mypy --strict` before reporting Python work complete.
- Tier 2 skips test suites, not typing, runtime boundary validation, docstrings or lint.
