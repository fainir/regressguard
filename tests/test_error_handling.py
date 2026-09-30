"""Provider-error handling: a raising provider marks the case with error, aggregation stays correct."""

from eval_runner.cli import run_case, run_suite


class _RaisingProvider:
    def __init__(self, exc: BaseException):
        self._exc = exc

    def complete(self, prompt: str) -> str:
        raise self._exc


class _SequenceProvider:
    """Returns canned responses in order; raises the configured exception on the Nth call (1-indexed)."""

    def __init__(self, responses: list[str], raise_on: int, exc: BaseException):
        self._responses = list(responses)
        self._raise_on = raise_on
        self._exc = exc
        self._n = 0

    def complete(self, prompt: str) -> str:
        self._n += 1
        if self._n == self._raise_on:
            raise self._exc
        return self._responses[self._n - 1]


def test_run_case_marks_provider_error():
    case = {"input": "x", "assertions": [{"type": "exact", "value": "y"}]}
    report = run_case(case, "{{input}}", _RaisingProvider(ConnectionError("boom")))
    assert report["passed"] is False
    assert report["error"] == "ConnectionError: boom"
    assert report["response"] is None
    assert report["assertions"] == []
    assert report["input"] == "x"


def test_run_suite_mixed_ok_and_error():
    cases = [
        {"input": "a", "assertions": [{"type": "exact", "value": "hi"}]},
        {"input": "b", "assertions": [{"type": "exact", "value": "hi"}]},
        {"input": "c", "assertions": [{"type": "exact", "value": "hi"}]},
    ]
    provider = _SequenceProvider(
        responses=["hi", "unused", "hi"],
        raise_on=2,
        exc=TimeoutError("upstream"),
    )
    report = run_suite("{{input}}", cases, provider)
    assert report["pass"] == 2
    assert report["fail"] == 1
    assert report["cases"][0]["passed"] is True
    assert "error" not in report["cases"][0]
    assert report["cases"][1]["passed"] is False
    assert report["cases"][1]["error"] == "TimeoutError: upstream"
    assert report["cases"][2]["passed"] is True
