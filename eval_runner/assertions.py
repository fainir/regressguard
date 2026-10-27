"""Assertion runners for RegressGuard eval cases. Schema: README.md#case-file-format"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional


ASSERTION_TYPES = ("exact", "contains", "regex", "llm-judge")


@dataclass(frozen=True)
class AssertionResult:
    passed: bool
    detail: str


JudgeFn = Callable[[str], str]


def _stub_judge(_prompt: str) -> str:
    raise RuntimeError(
        "llm-judge assertion requires a judge_fn; none was supplied to run_assertion"
    )


def validate_assertion(assertion: dict) -> None:
    """Raise ValueError if `assertion` is malformed. Called up front so a bad case file fails fast."""
    if not isinstance(assertion, dict):
        raise ValueError(f"assertion must be a JSON object, got {type(assertion).__name__}")

    a_type = assertion.get("type")
    if a_type not in ASSERTION_TYPES:
        raise ValueError(f"unknown assertion type: {a_type!r} (expected one of {', '.join(ASSERTION_TYPES)})")

    value = assertion.get("value")
    if not isinstance(value, str):
        raise ValueError(f"{a_type} assertion needs a string 'value'")

    if a_type == "regex":
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"invalid regex {value!r}: {exc}") from None

    if a_type == "llm-judge" and not isinstance(assertion.get("judge_prompt"), str):
        raise ValueError("llm-judge assertion requires a string judge_prompt")


def _judge_verdict(judge_output: str) -> str:
    """First word of the first non-blank line, without markdown or punctuation, upper-cased."""
    for line in judge_output.splitlines():
        words = line.split()
        if words:
            return words[0].strip("*_`.:,!").upper()
    return ""


def run_assertion(
    assertion: dict,
    response: str,
    judge_fn: Optional[JudgeFn] = None,
) -> AssertionResult:
    """Apply one assertion to a model response.

    `assertion` matches the case schema in README.md.
    `judge_fn` is only consulted for llm-judge assertions.
    """
    validate_assertion(assertion)
    a_type = assertion["type"]
    value = assertion["value"]

    if a_type == "exact":
        passed = response.strip() == value.strip()
        return AssertionResult(passed, f"exact match ({passed})")

    if a_type == "contains":
        passed = value in response
        return AssertionResult(passed, f"substring {value!r} {'found' if passed else 'not found'}")

    if a_type == "regex":
        match = re.search(value, response)
        if match:
            return AssertionResult(True, f"regex matched: {match.group(0)!r}")
        return AssertionResult(False, f"regex {value!r} did not match")

    # llm-judge
    fn = judge_fn or _stub_judge
    rendered = assertion["judge_prompt"].replace("{{response}}", response)
    judge_output = fn(rendered) or ""
    verdict = _judge_verdict(judge_output)
    passed = verdict == "PASS"
    return AssertionResult(passed, f"judge verdict={verdict!r}")
