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


def _write_cases(tmp_path, cases) -> str:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"cases": cases}))
    return str(path)


def _write_stub(tmp_path, responses) -> str:
    path = tmp_path / "stub.json"
    path.write_text(json.dumps(responses))
    return str(path)


def test_quickstart_example_passes():
    code, stdout, stderr = _run(
        [
            "--prompt", "{{input}}",
            "--cases", "examples/quickstart-cases.json",
            "--provider", "stub",
            "--stub-responses", "examples/quickstart-stub-responses.json",
        ]
    )
    assert code == 0, stderr
    report = json.loads(stdout)
    assert (report["pass"], report["fail"]) == (3, 0)


def test_summary_line_goes_to_stderr_and_stdout_stays_json(tmp_path):
    cases = _write_cases(tmp_path, [
        {"input": "say hi", "assertions": [{"type": "exact", "value": "hello"}]},
        {"input": "say bye", "assertions": [{"type": "exact", "value": "goodbye"}]},
    ])
    stub = _write_stub(tmp_path, {"say hi": "hello", "say bye": "later"})
    code, stdout, stderr = _run(
        ["--prompt", "{{input}}", "--cases", cases, "--provider", "stub", "--stub-responses", stub]
    )
    assert code == 1
    json.loads(stdout)  # stdout is still a parseable report
    assert "1 passed, 1 failed" in stderr
    assert "say bye" in stderr


def test_case_without_assertions_is_a_config_error_not_a_pass(tmp_path):
    # A typo like "assertion" used to make the case pass with zero checks.
    cases = _write_cases(tmp_path, [{"input": "say hi", "assertion": [{"type": "exact", "value": "x"}]}])
    stub = _write_stub(tmp_path, {"say hi": "hello"})
    code, stdout, stderr = _run(
        ["--prompt", "{{input}}", "--cases", cases, "--provider", "stub", "--stub-responses", stub]
    )
    assert code == 2
    assert stdout == ""
    assert "case 1" in stderr and "assertions" in stderr
    assert "Traceback" not in stderr


@pytest.mark.parametrize(
    "cases, needle",
    [
        ([], "no cases"),
        ([{"assertions": [{"type": "exact", "value": "x"}]}], "input"),
        ([{"input": 3, "assertions": [{"type": "exact", "value": "x"}]}], "input"),
        ([{"input": "a", "assertions": [{"type": "starts-with", "value": "x"}]}], "unknown assertion type"),
        ([{"input": "a", "assertions": [{"type": "regex", "value": "("}]}], "invalid regex"),
        ([{"input": "a", "assertions": [{"type": "llm-judge", "value": "x"}]}], "judge_prompt"),
    ],
)
def test_invalid_case_file_exits_2_with_message(tmp_path, cases, needle):
    path = _write_cases(tmp_path, cases)
    stub = _write_stub(tmp_path, {"a": "a"})
    code, _stdout, stderr = _run(
        ["--prompt", "{{input}}", "--cases", path, "--provider", "stub", "--stub-responses", stub]
    )
    assert code == 2, stderr
    assert needle in stderr
    assert "Traceback" not in stderr


def test_missing_cases_file_exits_2(tmp_path):
    stub = _write_stub(tmp_path, {})
    code, _stdout, stderr = _run(
        ["--prompt", "{{input}}", "--cases", str(tmp_path / "nope.json"), "--provider", "stub", "--stub-responses", stub]
    )
    assert code == 2
    assert "nope.json" in stderr
    assert "Traceback" not in stderr


def test_malformed_cases_json_exits_2(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text("{ not json")
    stub = _write_stub(tmp_path, {})
    code, _stdout, stderr = _run(
        ["--prompt", "{{input}}", "--cases", str(path), "--provider", "stub", "--stub-responses", stub]
    )
    assert code == 2
    assert "not valid JSON" in stderr


def test_openai_without_model_exits_2():
    # Used to silently send the Claude default model id to OpenAI.
    code, _stdout, stderr = _run(
        ["--prompt", "{{input}}", "--cases", "examples/quickstart-cases.json", "--provider", "openai"]
    )
    assert code == 2
    assert "--model" in stderr


def test_version_flag():
    code, stdout, _stderr = _run(["--version"])
    assert code == 0
    assert stdout.startswith("regressguard ")
