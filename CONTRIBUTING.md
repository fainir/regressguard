# Contributing to RegressGuard

Thanks for your interest in RegressGuard. This project is a small, focused CLI for catching prompt regressions in CI, and we welcome contributions that keep it that way: fast, Dockerable, stdlib-only at its core, and friendly to deterministic eval runs.

## Clone and run tests locally

RegressGuard needs Python 3.11+. The test suite runs without a GPU, an API key or network access (the `stub` provider and fake SDK modules stand in for model calls).

```bash
git clone https://github.com/fainir/regressguard.git
cd regressguard
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

If you prefer Docker, `docker build -t regressguard .` produces the same image CI builds. Run the tests from the repo root.

## Add a new eval case

Cases live in a JSON file with a top-level `cases` array (see [Case file format](README.md#case-file-format)). Each case has an `input` and one or more `assertions`. The supported assertion types are `exact`, `contains`, `regex` and `llm-judge`.

```json
{
  "cases": [
    {
      "input": "Say hello to Avery.",
      "assertions": [{ "type": "regex", "value": "(?i)hello.*avery" }]
    }
  ]
}
```

To contribute an example case, add it under `examples/` with matching stub responses, run it locally, and include the output in your PR description:

```bash
regressguard --prompt "{{input}}" \
  --cases examples/eval-cases.json \
  --provider stub \
  --stub-responses examples/stub-responses.json
```

If you are adding a new assertion type, add it to `ASSERTION_TYPES` and `validate_assertion` in `eval_runner/assertions.py`, cover its pass and fail paths in `tests/test_assertions.py`, document it in the README, and add a line to `CHANGELOG.md`.

## Report a bug

Open a GitHub issue at https://github.com/fainir/regressguard/issues with:

- RegressGuard version (`regressguard --version`) and Python version.
- A minimal reproduction: the smallest case file and command that triggers the bug.
- Expected vs. actual output.

If the bug is a flaky result (a case flips between pass and fail across runs with no prompt change), attach the two `--out` reports so we can diff them.

## Open a pull request

1. Fork the repo and create a topic branch (`git checkout -b fix/case-id-collision`).
2. Make the change. Keep diffs small and focused on one concern.
3. Run `python -m pytest` and the example command above.
4. Push and open a PR against `main`. In the description, link any related issue and paste the local test output.
5. A maintainer will review within a few business days. We squash-merge, so write a commit message you are happy to see on `main`.

For larger changes, open a draft PR or an issue first so we can agree on scope before you invest time.
