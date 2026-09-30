"""RegressGuard eval runner CLI. Runs a case file against a provider, applies assertions, prints JSON report."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from eval_runner.assertions import run_assertion
from eval_runner.providers import Provider, build_provider


def load_cases(path: str) -> list[dict[str, Any]]:
    with open(path) as f:
        doc = json.load(f)
    cases = doc.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"case file {path!r} has no top-level 'cases' array")
    return cases


def render(template: str, input_value: str) -> str:
    return template.replace("{{input}}", input_value)


def make_judge_fn(provider: Provider):
    def judge(prompt: str) -> str:
        return provider.complete(prompt)

    return judge


def run_case(case: dict[str, Any], prompt_template: str, provider: Provider) -> dict[str, Any]:
    input_value = case["input"]
    rendered = render(prompt_template, input_value)
    try:
        response = provider.complete(rendered)
    except Exception as exc:
        return {
            "input": input_value,
            "response": None,
            "assertions": [],
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    assertion_results: list[dict[str, Any]] = []
    all_passed = True
    for assertion in case.get("assertions", []):
        result = run_assertion(assertion, response, judge_fn=make_judge_fn(provider))
        assertion_results.append(
            {
                "type": assertion.get("type"),
                "value": assertion.get("value"),
                "passed": result.passed,
                "detail": result.detail,
            }
        )
        if not result.passed:
            all_passed = False

    return {
        "input": input_value,
        "response": response,
        "assertions": assertion_results,
        "passed": all_passed,
    }


def run_suite(prompt_template: str, cases: list[dict[str, Any]], provider: Provider) -> dict[str, Any]:
    case_reports = [run_case(c, prompt_template, provider) for c in cases]
    passed = sum(1 for r in case_reports if r["passed"])
    return {
        "pass": passed,
        "fail": len(case_reports) - passed,
        "cases": case_reports,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="eval-runner", description="Run an eval suite against an LLM provider.")
    p.add_argument("--prompt", required=True, help="Prompt template with '{{input}}' placeholder.")
    p.add_argument("--cases", required=True, help="Path to case file (see .agent/eval-schema.md).")
    p.add_argument("--provider", required=True, choices=["anthropic", "openai", "stub"])
    p.add_argument("--model", default="claude-haiku-4-5-20251001", help="Model id for anthropic/openai.")
    p.add_argument("--stub-responses", help="Path to canned-response JSON (required for --provider stub).")
    p.add_argument("--out", help="Write report JSON to this path (default: stdout).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    provider = build_provider(args.provider, args.model, args.stub_responses)
    cases = load_cases(args.cases)
    report = run_suite(args.prompt, cases, provider)
    output = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(output + "\n")
    else:
        print(output)
    return 0 if report["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
