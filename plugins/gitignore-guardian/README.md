# Gitignore Guardian

Gitignore management, auditing, and protection. PreToolUse hooks block dangerous `.gitignore` modifications and `git add` of ignored files. Supports `@protect` annotations.

## Install

```bash
claude plugin add mark-satterfield/gitignore-guardian
```

## What's Included

- **Skill**: Auto-activating gitignore management and auditing
- **Hooks** (auto-registered):
  - `gitignore-guard.sh` — blocks `git add` of ignored files
  - `gitignore-edit-guard.sh` — blocks dangerous `.gitignore` edits
- **Script**: `gitignore_audit.py` — audits gitignore coverage and health

## License

MIT
