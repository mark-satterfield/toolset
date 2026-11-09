---
name: "tdd-guide"
description: "Test-driven development skill for writing unit tests, generating test fixtures and mocks, analyzing coverage gaps, and guiding red-green-refactor workflows across Jest, Pytest, JUnit, Vitest, and Mocha. Use when the user asks to write tests, improve test coverage, practice TDD, generate mocks or stubs, or mentions testing frameworks like Jest, pytest, or JUnit. Handles test generation from source code, coverage report parsing (LCOV/JSON/XML), quality scoring, and framework conversion for TypeScript, JavaScript, Python, and Java projects."
triggers:
  - generate tests
  - analyze coverage
  - TDD workflow
  - red green refactor
  - Jest tests
  - Pytest tests
  - JUnit tests
  - coverage report
---

# TDD Guide

Test-driven development skill for generating tests, analyzing coverage, and guiding red-green-refactor workflows across Jest, Pytest, JUnit, and Vitest.

---

## Workflows

### Generate Tests from Code

1. Provide source code (TypeScript, JavaScript, Python, Java)
2. Specify target framework (Jest, Pytest, JUnit, Vitest)
3. Run `test_generator.py` with requirements
4. Review generated test stubs
5. **Validation:** Tests compile and cover happy path, error cases, edge cases

### Analyze Coverage Gaps

1. Generate coverage report from test runner (`npm test -- --coverage`)
2. Run `coverage_analyzer.py` on LCOV/JSON/XML report
3. Review prioritized gaps (P0/P1/P2)
4. Generate missing tests for uncovered paths
5. **Validation:** Coverage meets target threshold (typically 80%+)

### TDD New Feature

1. Read the PRD, TRD, Story, specs and Task activity together. Review the repository's existing suite before choosing test work.
2. Review, update, refactor or add tests for required happy paths, negative cases, edge cases and boundaries. Tests are code and receive the same quality judgment as product code.
3. Run the whole suite and judge its quality. A failing suite can contain a poor test, a setup defect, an environment failure or missing product behavior; distinguish these before changing implementation.
4. Implement missing behavior and prerequisite dependencies. A suite that already passes needs no manufactured failure, sabotage or mutation demonstration.
5. Always review architecture conformance, code quality and best practices in the assigned scope. Improve code and tests where warranted, including when the suite already passes; a justified no-change result is valid.
6. Verify the whole suite after improvements. Keep required earlier behavior covered and restore a regressing refactor to its recorded Green snapshot.

### Python build contracts

The Python build records each command and its complete output directly. Agents perform reasoning and writing; no model session merely relays a command, parses an exit code or repeats a file.

Build agents receive a facts file and the current journal by path. The facts file's `accepted` section is resolved for you from the accepted journal artifacts: `requirements` points to the criteria, spec, data model, TRD, Story document and Tasks; `workspace` names the work tree and branches; `artifacts` lists the latest accepted artifact of every other name (the existing suite runs, baseline, reviews, earlier corrections) by reference only, each with the step and role that produced it, as a path or a `valueFile`: open one when your work needs it; `previousResult` is the result your own agent recorded on its last accepted step (null when it has none), never another specialist's result of the same name; `delta` lists what was accepted since you last ran (`deltaSince`), and is empty on your first run, when everything in `artifacts` is new to you; `unresolvedFindings` lists review findings not yet approved and reported test defects. The requirements, workspace, previous result, delta and findings carry small values inline and larger ones as a `valueFile`. Start from those pointers instead of searching the journal; open the journal only when you need full primary evidence they do not carry. A writer's summary never replaces the evidence a reviewer judges. Never treat a Task as the requirements document: it describes the implementation activity. Requirements and acceptance evidence also come from the PRD, TRD, Story, specs and architecture.

The shared result schemas are the `build-*.schema.json` files in `skills/pipeline-contracts/schemas/`. The launch names the exact schema to write; producers and consumers use that same contract. Specialist selection names bare roster roles in `agents`, without a plugin prefix.

- Work to the verification methods the accepted `executionPolicy` in your facts names, and cite a whole-suite result the build executed on the tree you work on (its `evidenceKey` names that tree) instead of rerunning the same suite.
- Test specialists review the existing suite in context. Preserve legitimate earlier obligations while correcting poor tests. Report actual coverage, not just a test count or an exit code.
- Suite reviewers choose `pass` when the freshly executed sound suite passes, `test-repair` when tests or their setup do not correctly establish the contract, `implementation` when valid tests expose required product work, and `environment` when execution cannot establish either. Provide concrete evidence. Never diagnose a product defect from a nonzero exit alone.
- An environment judgment receives a bounded current-Task prerequisite diagnosis. Real producer Tasks and required build or deployment stages are validated before additive blockers are written. The consumer releases its build slot while those producers progress. Current readiness, the recorded whole-suite command, and an independent fresh assessment follow progression; an old accepted judgment is never replayed as new evidence. Missing producer work is a recorded pipeline work-authoring gap, never ad hoc parameter creation.
- Code reviewers assess the architecture and design as well as correctness, quality and best practices. Findings stay within the assigned behavior and its dependencies; do not invent unrelated cleanup.
- Implementers develop prerequisites that the assigned behavior needs, using the owning repositories and normal worktrees. Report test defects for test-author judgment; do not weaken tests to obtain Green. A dependency that exists only in an unpublished SkillSpoke library is reported for publication under the library rules.
- Refactoring always receives a review opportunity, including when behavior already exists. Improve warranted issues while preserving required behavior. Do not force a change solely to show that the phase ran. An accepted assessment of the current tree satisfies the opportunity without a new refactoring session.

---

## Examples

### Test Generation — Input → Output (Pytest)

**Input source function (`math_utils.py`):**
```python
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

**Command:**
```bash
python scripts/test_generator.py --input math_utils.py --framework pytest
```

**Generated test output (`test_math_utils.py`):**
```python
import pytest
from math_utils import divide


class TestDivide:
    def test_divide_positive_numbers(self):
        assert divide(10, 2) == 5.0

    def test_divide_negative_numerator(self):
        assert divide(-10, 2) == -5.0

    def test_divide_float_result(self):
        assert divide(1, 3) == pytest.approx(0.333, rel=1e-3)

    def test_divide_by_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(10, 0)

    def test_divide_zero_numerator(self):
        assert divide(0, 5) == 0.0
```

---

### Coverage Analysis — Sample P0/P1/P2 Output

**Command:**
```bash
python scripts/coverage_analyzer.py --report lcov.info --threshold 80
```

**Sample output:**
```
Coverage Report — Overall: 63% (threshold: 80%)

P0 — Critical gaps (uncovered error paths):
  auth/login.py:42-58   handle_expired_token()       0% covered
  payments/process.py:91-110  handle_payment_failure()   0% covered

P1 — High-value gaps (core logic branches):
  users/service.py:77   update_profile() — else branch  0% covered
  orders/cart.py:134    apply_discount() — zero-qty guard  0% covered

P2 — Low-risk gaps (utility / helper functions):
  utils/formatting.py:12  format_currency()            0% covered

Recommended: Generate tests for P0 items first to reach 80% threshold.
```

---

## Key Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| `test_generator.py` | Generate test cases from code/requirements | `python scripts/test_generator.py --input source.py --framework pytest` |
| `coverage_analyzer.py` | Parse and analyze coverage reports | `python scripts/coverage_analyzer.py --report lcov.info --threshold 80` |
| `tdd_workflow.py` | Guide red-green-refactor cycles | `python scripts/tdd_workflow.py --phase red --test test_auth.py` |
| `fixture_generator.py` | Generate test data and mocks | `python scripts/fixture_generator.py --entity User --count 5` |

Additional scripts: `framework_adapter.py` (convert between frameworks), `metrics_calculator.py` (quality metrics), `format_detector.py` (detect language/framework), `output_formatter.py` (CLI/desktop/CI output).

---

## Input Requirements

**For Test Generation:**
- Source code (file path or pasted content)
- Target framework (Jest, Pytest, JUnit, Vitest)
- Coverage scope (unit, integration, edge cases)

**For Coverage Analysis:**
- Coverage report file (LCOV, JSON, or XML format)
- Optional: Source code for context
- Optional: Target threshold percentage

**For TDD Workflow:**
- Feature requirements or user story
- Current phase (RED, GREEN, REFACTOR)
- Test code and implementation status

---

## Limitations

| Scope | Details |
|-------|---------|
| Unit test focus | Integration and E2E tests require different patterns |
| Static analysis | Cannot execute tests or measure runtime behavior |
| Language support | Best for TypeScript, JavaScript, Python, Java |
| Report formats | LCOV, JSON, XML only; other formats need conversion |
| Generated tests | Provide scaffolding; require human review for complex logic |

**When to use other tools:**
- E2E testing: Playwright, Cypress, Selenium
- Performance testing: k6, JMeter, Locust
- Security testing: OWASP ZAP, Burp Suite
