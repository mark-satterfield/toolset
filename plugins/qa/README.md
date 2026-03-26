# QA

Validates plugins, skills, and slash commands for structural correctness and content quality.

## Install

```bash
claude plugin add mark-satterfield/qa
```

## What's Included

- **Commands**:
  - `/qa:validate` — validate skills, plugins, and commands
  - `/qa:test` — run test suites
  - `/qa:report` — generate quality reports
  - `/qa:plugin-audit` — audit plugin structure and metadata
- **Scripts**: `validate_skill.py`, `validate_plugin.py`, `validate_command.py`, `validate_marketplace.py`, `run_tests.py`, `generate_report.py`
- **Hook**: `validate-on-write.sh` — validates on file write

**Version**: 0.1.0

## License

MIT
