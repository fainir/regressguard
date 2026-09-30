"""Assertion runners for RegressGuard eval cases. Schema: .agent/eval-schema.md"""

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


def run_assertion(
    assertion: dict,
    response: str,
    judge_fn: Optional[JudgeFn] = None,
) -> AssertionResult:
    """Apply one assertion to a model response.

    `assertion` matches the schema in `.agent/eval-schema.md`.
    `judge_fn` is only consulted for llm-judge assertions.
    """
    a_type = assertion.get("type")
    if a_type not in ASSERTION_TYPES:
        raise ValueError(f"unknown assertion type: {a_type!r}")

    value = assertion.get("value")
    if not isinstance(value, str):
        raise ValueError("assertion.value must be a string")

    if a_type == "exact":
        passed = response.strip() == value.strip()
        return AssertionResult(passed, f"exact match ({passed})")

    if a_type == "contains":
        passed = value in response
        return AssertionResult(passed, f"substring {value!r} {'found' if passed else 'not found'}")

    if a_type == "regex":
        pattern = re.compile(value)
        match = pattern.search(response)
        if match:
            return AssertionResult(True, f"regex matched: {match.group(0)!r}")
        return AssertionResult(False, f"regex {value!r} did not match")

    # llm-judge
    judge_prompt = assertion.get("judge_prompt")
    if not isinstance(judge_prompt, str):
        raise ValueError("llm-judge assertion requires a string judge_prompt")
    fn = judge_fn or _stub_judge
    rendered = judge_prompt.replace("{{response}}", response)
    judge_output = fn(rendered)
    first_line = judge_output.splitlines()[0].strip() if judge_output else ""
    passed = first_line == "PASS"
    return AssertionResult(passed, f"judge first-line={first_line!r}")
