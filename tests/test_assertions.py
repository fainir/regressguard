"""Pass and fail path for every assertion type in eval_runner.assertions."""

import pytest

from eval_runner.assertions import AssertionResult, run_assertion


class TestExact:
    def test_pass_ignores_surrounding_whitespace(self):
        result = run_assertion({"type": "exact", "value": "ok"}, "  ok\n")
        assert result.passed is True

    def test_fail_on_mismatch(self):
        result = run_assertion({"type": "exact", "value": "ok"}, "okay")
        assert result.passed is False


class TestContains:
    def test_pass_case_sensitive_substring(self):
        result = run_assertion({"type": "contains", "value": "parameter"}, "Use parameterized queries.")
        assert result.passed is True

    def test_fail_when_absent(self):
        result = run_assertion({"type": "contains", "value": "banana"}, "Use parameterized queries.")
        assert result.passed is False


class TestRegex:
    def test_pass_when_pattern_matches(self):
        result = run_assertion(
            {"type": "regex", "value": r"\b\d{3}-\d{3}-\d{4}\b"},
            "Call me at 555-123-4567 tomorrow.",
        )
        assert result.passed is True
        assert "555-123-4567" in result.detail

    def test_fail_when_pattern_absent(self):
        result = run_assertion(
            {"type": "regex", "value": r"\b\d{3}-\d{3}-\d{4}\b"},
            "no phone number here",
        )
        assert result.passed is False


class TestLlmJudge:
    def test_pass_when_judge_returns_pass_on_first_line(self):
        def judge(prompt: str) -> str:
            assert "hamlet is a play" in prompt.lower()
            return "PASS\nBrief and accurate."

        result = run_assertion(
            {
                "type": "llm-judge",
                "value": "factual",
                "judge_prompt": "Grade this: {{response}}",
            },
            "Hamlet is a play by Shakespeare.",
            judge_fn=judge,
        )
        assert result.passed is True

    def test_fail_when_judge_returns_fail(self):
        result = run_assertion(
            {
                "type": "llm-judge",
                "value": "factual",
                "judge_prompt": "Grade: {{response}}",
            },
            "irrelevant",
            judge_fn=lambda _p: "FAIL\nOff-topic.",
        )
        assert result.passed is False

    def test_stub_judge_raises_when_no_judge_fn_supplied(self):
        with pytest.raises(RuntimeError):
            run_assertion(
                {
                    "type": "llm-judge",
                    "value": "factual",
                    "judge_prompt": "Grade: {{response}}",
                },
                "response text",
            )


class TestSchemaErrors:
    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            run_assertion({"type": "starts-with", "value": "hi"}, "hi there")

    def test_llm_judge_without_prompt_raises(self):
        with pytest.raises(ValueError):
            run_assertion({"type": "llm-judge", "value": "x"}, "resp", judge_fn=lambda _p: "PASS")


def test_assertion_result_is_frozen():
    result = AssertionResult(True, "ok")
    with pytest.raises(Exception):
        result.passed = False  # type: ignore[misc]
