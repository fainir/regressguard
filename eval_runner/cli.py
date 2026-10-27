"""RegressGuard eval runner CLI. Runs a case file against a provider, applies assertions, prints JSON report.

Exit codes: 0 = every case passed, 1 = at least one case failed or errored, 2 = usage or config error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from eval_runner import __version__
from eval_runner.assertions import run_assertion, validate_assertion
from eval_runner.providers import DEFAULT_ANTHROPIC_MODEL, DEFAULT_TIMEOUT, Provider, build_provider


EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ERROR = 2


def validate_cases(cases: Any) -> list[dict[str, Any]]:
    """Raise ValueError naming the first bad case (1-based) so a typo fails the run instead of passing it."""
    if not isinstance(cases, list):
        raise ValueError("'cases' must be a list")
    if not cases:
        raise ValueError("no cases to run ('cases' is empty)")
    for n, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"case {n}: must be a JSON object")
        if not isinstance(case.get("input"), str):
            raise ValueError(f"case {n}: 'input' must be a string")
        assertions = case.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            raise ValueError(f"case {n}: 'assertions' must be a non-empty list")
        for m, assertion in enumerate(assertions, start=1):
            try:
                validate_assertion(assertion)
            except ValueError as exc:
                raise ValueError(f"case {n}, assertion {m}: {exc}") from None
    return cases


def load_cases(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        try:
            doc = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"case file {path!r} is not valid JSON: {exc}") from None
    cases = doc.get("cases") if isinstance(doc, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"case file {path!r} has no top-level 'cases' array")
    try:
        return validate_cases(cases)
    except ValueError as exc:
        raise ValueError(f"case file {path!r}: {exc}") from None


def render(template: str, input_value: str) -> str:
    return template.replace("{{input}}", input_value)


def make_judge_fn(provider: Provider):
    def judge(prompt: str) -> str:
        return provider.complete(prompt)

    return judge


def _error_report(input_value: str, response: str | None, exc: Exception) -> dict[str, Any]:
    return {
        "input": input_value,
        "response": response,
        "assertions": [],
        "passed": False,
        "error": f"{type(exc).__name__}: {exc}",
    }


def run_case(case: dict[str, Any], prompt_template: str, provider: Provider) -> dict[str, Any]:
    input_value = case["input"]
    rendered = render(prompt_template, input_value)
    try:
        response = provider.complete(rendered)
    except Exception as exc:
        return _error_report(input_value, None, exc)

    assertion_results: list[dict[str, Any]] = []
    all_passed = True
    try:
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
    except Exception as exc:
        # An llm-judge call can fail like any provider call; keep it scoped to this case.
        return _error_report(input_value, response, exc)

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


def summarize(report: dict[str, Any]) -> str:
    """Human-readable summary for CI logs (stderr), one line per failing case."""
    lines = []
    for n, case in enumerate(report["cases"], start=1):
        if case["passed"]:
            continue
        if "error" in case:
            reason = case["error"]
        else:
            reason = "; ".join(a["detail"] for a in case["assertions"] if not a["passed"])
        snippet = case["input"] if len(case["input"]) <= 60 else case["input"][:57] + "..."
        lines.append(f"FAIL case {n} ({snippet!r}): {reason}")
    lines.append(f"regressguard: {report['pass']} passed, {report['fail']} failed")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="regressguard",
        description="Run an eval suite against an LLM provider. Exit 0 if every case passes, 1 if any fails, 2 on config errors.",
    )
    p.add_argument("--prompt", required=True, help="Prompt template with '{{input}}' placeholder.")
    p.add_argument("--cases", required=True, help="Path to case file (JSON with a top-level 'cases' array).")
    p.add_argument("--provider", required=True, choices=["anthropic", "openai", "stub"])
    p.add_argument(
        "--model",
        help=f"Model id. Default for anthropic: {DEFAULT_ANTHROPIC_MODEL}. Required for openai. Ignored for stub.",
    )
    p.add_argument("--stub-responses", help="Path to canned-response JSON (required for --provider stub).")
    p.add_argument("--out", help="Write report JSON to this path (default: stdout).")
    p.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout in seconds for anthropic/openai (default: {DEFAULT_TIMEOUT:g}).",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds")
    try:
        cases = load_cases(args.cases)
    except (OSError, ValueError) as exc:
        print(f"regressguard: error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        provider = build_provider(args.provider, args.model, args.stub_responses, timeout=args.timeout)
    except Exception as exc:  # SDK constructors raise their own error types (e.g. missing API key)
        print(f"regressguard: error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    report = run_suite(args.prompt, cases, provider)
    output = json.dumps(report, indent=2)
    if args.out:
        try:
            Path(args.out).write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"regressguard: error: cannot write report: {exc}", file=sys.stderr)
            return EXIT_ERROR
    else:
        print(output)
    print(summarize(report), file=sys.stderr)
    return EXIT_OK if report["fail"] == 0 else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
