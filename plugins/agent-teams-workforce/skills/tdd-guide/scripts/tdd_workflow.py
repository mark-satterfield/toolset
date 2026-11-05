"""TDD workflow guidance module.

Provides step-by-step guidance through red-green-refactor cycles with validation.
"""

from enum import Enum

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class TDDPhase(Enum):
    """TDD cycle phases."""

    RED = "red"  # Review and extend the existing suite
    GREEN = "green"  # Make test pass
    REFACTOR = "refactor"  # Improve code


class WorkflowState(Enum):
    """Current state of TDD workflow."""

    INITIAL = "initial"
    TEST_WRITTEN = "test_written"
    TEST_FAILING = "test_failing"
    TEST_PASSING = "test_passing"
    CODE_REFACTORED = "code_refactored"


class TDDWorkflow:
    """Guide users through TDD red-green-refactor workflow."""

    def __init__(self) -> None:
        """Initialize TDD workflow guide."""
        self.current_phase = TDDPhase.RED
        self.state = WorkflowState.INITIAL
        self.history: list[dict[str, JsonValue]] = []

    def start_cycle(self, requirement: str) -> dict[str, JsonValue]:
        """Start a new TDD cycle.

        Args:
            requirement: User story or requirement to implement

        Returns:
            Guidance for RED phase

        """
        self.current_phase = TDDPhase.RED
        self.state = WorkflowState.INITIAL

        return {
            "phase": "RED",
            "instruction": "Review and extend the existing suite for the requirement",
            "requirement": requirement,
            "checklist": [
                "Write test that describes desired behavior",
                "Record actual suite outcomes; passing behavior may already satisfy the requirement",
                "Test name clearly describes what is being tested",
                "Test has clear arrange-act-assert structure",
            ],
            "tips": [
                "Focus on behavior, not implementation",
                "Start with simplest test case",
                "Test should be specific and focused",
            ],
        }

    def validate_red_phase(
        self,
        test_code: str,
        test_result: dict[str, JsonValue] | None = None,
    ) -> dict[str, JsonValue]:
        """Validate RED phase completion.

        Args:
            test_code: The test code written
            test_result: Test execution result (optional)

        Returns:
            Validation result and next steps

        """
        validations: list[dict[str, JsonValue]] = []

        # Check test exists
        if not test_code or not test_code.strip():
            validations.append({
                "valid": False,
                "message": "No test code provided",
            })
        else:
            validations.append({
                "valid": True,
                "message": "Test code provided",
            })

        # Check for assertions
        has_assertion = any(keyword in test_code.lower() for keyword in ["assert", "expect", "should"])
        validations.append({
            "valid": has_assertion,
            "message": "Contains assertions" if has_assertion else "Missing assertions",
        })

        # Check test result if provided
        status: JsonValue = test_result.get("status") if test_result else None
        failure_cause: JsonValue = test_result.get("failureCause") if test_result else None
        if test_result:
            accepted: bool = status == "passed" or (status == "failed" and failure_cause == "product")
            validations.append({
                "valid": accepted,
                "message": (
                    "Actual suite outcome reviewed"
                    if accepted
                    else "Review test quality and classify test, setup, environment or product failure "
                    "before implementation"
                ),
            })
        else:
            validations.append({"valid": False, "message": "Actual existing-suite outcome is required"})

        all_valid = all(v["valid"] for v in validations)

        if all_valid:
            passing: bool = status == "passed"
            self.state = WorkflowState.TEST_PASSING if passing else WorkflowState.TEST_FAILING
            self.current_phase = TDDPhase.REFACTOR if passing else TDDPhase.GREEN
            return {
                "phase_complete": True,
                "next_phase": self.current_phase.value.upper(),
                "validations": list(validations),
                "instruction": (
                    "Review architecture, code and test quality; improve relevant issues where warranted"
                    if passing
                    else "Implement the confirmed requirement defect, including required prerequisites"
                ),
            }
        return {
            "phase_complete": False,
            "current_phase": "RED",
            "validations": list(validations),
            "instruction": "Address validation issues before proceeding",
        }

    def validate_green_phase(
        self,
        implementation_code: str,
        test_result: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Validate GREEN phase completion.

        Args:
            implementation_code: The implementation code
            test_result: Test execution result

        Returns:
            Validation result and next steps

        """
        validations: list[dict[str, JsonValue]] = []

        # Check implementation exists
        if not implementation_code or not implementation_code.strip():
            validations.append({
                "valid": False,
                "message": "No implementation code provided",
            })
        else:
            validations.append({
                "valid": True,
                "message": "Implementation code provided",
            })

        # Check test now passes
        test_passed = test_result.get("status") == "passed"
        validations.append({
            "valid": test_passed,
            "message": "Test passes" if test_passed else "Test still failing",
        })

        all_valid = all(v["valid"] for v in validations)

        if all_valid:
            self.state = WorkflowState.TEST_PASSING
            self.current_phase = TDDPhase.REFACTOR
            return {
                "phase_complete": True,
                "next_phase": "REFACTOR",
                "validations": list(validations),
                "instruction": "Refactor code while keeping tests green",
                "refactoring_suggestions": ["Review architecture conformance, code and suite quality in context"],
            }
        return {
            "phase_complete": False,
            "current_phase": "GREEN",
            "validations": list(validations),
            "instruction": "Make the test pass before refactoring",
        }

    def validate_refactor_phase(
        self,
        original_code: str,
        refactored_code: str,
        test_result: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        """Validate REFACTOR phase completion.

        Args:
            original_code: Original implementation
            refactored_code: Refactored implementation
            test_result: Test execution result after refactoring

        Returns:
            Validation result and cycle completion status

        """
        validations: list[dict[str, JsonValue]] = []

        # Check tests still pass
        test_passed = test_result.get("status") == "passed"
        validations.append({
            "valid": test_passed,
            "message": "Tests still pass after refactoring" if test_passed else "Tests broken by refactoring",
        })

        # Review is required; a sound result does not require invented edits.
        code_changed = original_code != refactored_code
        quality_reviewed: bool = test_result.get("qualityReviewed") is True
        validations.append({
            "valid": quality_reviewed,
            "message": (
                ("Code refactored and quality reviewed" if code_changed else "Quality reviewed; no edit warranted")
                if quality_reviewed
                else "Architecture, code and test quality review must be recorded"
            ),
        })

        all_valid = all(v["valid"] for v in validations if v.get("valid") is not None)

        if all_valid:
            self.state = WorkflowState.CODE_REFACTORED
            self.history.append({
                "cycle_complete": True,
                "final_state": self.state.value,
            })
            return {
                "phase_complete": True,
                "cycle_complete": True,
                "validations": list(validations),
                "message": "TDD cycle complete! Ready for next requirement.",
                "next_steps": [
                    "Follow the active owner and repository instructions for commits",
                    "Start next TDD cycle with new requirement",
                    "Or add more test cases for current feature",
                ],
            }
        return {
            "phase_complete": False,
            "current_phase": "REFACTOR",
            "validations": list(validations),
            "instruction": "Ensure tests pass and architecture, code and suite quality review is recorded",
        }

    def generate_workflow_summary(self) -> str:
        """Generate summary of TDD workflow progress.

        Returns:
            Current phase, state and the suite-review workflow.

        """
        summary = [
            "# TDD Workflow Summary\n",
            f"Current Phase: {self.current_phase.value.upper()}",
            f"Current State: {self.state.value.replace('_', ' ').title()}",
            f"Completed Cycles: {len(self.history)}\n",
        ]

        summary.extend([
            "## TDD Cycle Steps:\n",
            "1. **RED**: Review and extend the existing suite",
            "   - Test describes desired behavior",
            "   - Record actual outcomes and classify failures; never manufacture failure\n",
            "2. **GREEN**: Make the test pass",
            "   - Write minimal code to pass test",
            "   - All tests should pass\n",
            "3. **REFACTOR**: Improve the code",
            "   - Clean up implementation",
            "   - Tests still pass",
            "   - Code is more maintainable\n",
        ])

        return "\n".join(summary)

    def get_phase_guidance(self, phase: TDDPhase | None = None) -> dict[str, JsonValue]:
        """Get detailed guidance for a specific phase.

        Args:
            phase: TDD phase (uses current if not specified)

        Returns:
            Detailed guidance dictionary

        """
        target_phase = phase or self.current_phase

        if target_phase == TDDPhase.RED:
            return {
                "phase": "RED",
                "goal": "Review and extend the existing suite for happy, negative, edge and boundary cases",
                "steps": [
                    "1. Read and understand the requirement",
                    "2. Think about expected behavior",
                    "3. Write test that verifies this behavior",
                    "4. Record the actual outcome in the existing suite context",
                    "5. Review test quality and classify product, test, setup or environment failures",
                ],
                "common_mistakes": [
                    "Assuming an immediate pass proves either complete coverage or a bad test",
                    "Test fails for wrong reason (syntax error)",
                    "Test is too broad or tests multiple things",
                ],
                "tips": [
                    "Start with simplest test case",
                    "One assertion per test (focused)",
                    "Test should read like specification",
                ],
            }

        if target_phase == TDDPhase.GREEN:
            return {
                "phase": "GREEN",
                "goal": "Make the test pass with minimal code",
                "steps": [
                    "1. Write simplest code that makes test pass",
                    "2. Run test and verify it passes",
                    "3. Run all tests to ensure no regression",
                    "4. Resist urge to add extra features",
                ],
                "common_mistakes": [
                    "Over-engineering solution",
                    "Adding features not covered by tests",
                    "Breaking existing tests",
                ],
                "tips": [
                    "Implement the actual requirement without test-specific hardcoding",
                    "Triangulate with more tests if needed",
                    "Keep implementation simple",
                ],
            }

        if target_phase == TDDPhase.REFACTOR:
            return {
                "phase": "REFACTOR",
                "goal": "Improve code quality while keeping tests green",
                "steps": [
                    "1. Identify code smells or duplication",
                    "2. Apply one refactoring at a time",
                    "3. Run tests after each change",
                    "4. Commit when satisfied with quality",
                ],
                "common_mistakes": [
                    "Changing behavior (breaking tests)",
                    "Refactoring too much at once",
                    "Skipping this phase",
                ],
                "tips": [
                    "Extract methods for better naming",
                    "Remove duplication",
                    "Improve variable names",
                    "Tests are safety net - use them!",
                ],
            }

        return {}
