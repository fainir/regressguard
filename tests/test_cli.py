"""End-to-end CLI wiring via the stub provider. Covers happy path + a failing case."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "eval_runner.cli", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    return result.returncode, result.stdout, result.stderr


def test_all_pass_against_stub(tmp_path):
    out = tmp_path / "report.json"
    code, _stdout, stderr = _run(
        [
            "--prompt", "{{input}}",
            "--cases", "examples/eval-cases.json",
            "--provider", "stub",
            "--stub-responses", "examples/stub-responses.json",
            "--out", str(out),
        ]
    )
    assert code == 0, stderr
    report = json.loads(out.read_text())
    assert report["pass"] == 4
    assert report["fail"] == 0
    assert len(report["cases"]) == 4
    for case in report["cases"]:
        assert case["passed"] is True
        for assertion in case["assertions"]:
            assert assertion["passed"] is True


def test_exit_code_1_when_case_fails(tmp_path):
    # Craft a case file where the stub response won't satisfy the assertion.
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(json.dumps({
        "version": "0",
        "cases": [
            {"input": "say hi", "assertions": [{"type": "exact", "value": "goodbye"}]}
        ],
    }))
    responses_file = tmp_path / "stub.json"
    responses_file.write_text(json.dumps({"say hi": "hello"}))

    code, _stdout, _stderr = _run(
        [
            "--prompt", "{{input}}",
            "--cases", str(cases_file),
            "--provider", "stub",
            "--stub-responses", str(responses_file),
        ]
    )
    assert code == 1


def test_missing_stub_responses_arg_errors():
    code, _stdout, stderr = _run(
        [
            "--prompt", "{{input}}",
            "--cases", "examples/eval-cases.json",
            "--provider", "stub",
        ]
    )
    assert code != 0
    assert "stub-responses" in stderr.lower() or "stub-responses" in stderr
