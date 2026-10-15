# Contributing to RegressGuard

Thanks for your interest in RegressGuard. This project is a small, focused CLI for catching prompt regressions in CI, and we welcome contributions that keep it that way: fast, Dockerable, and friendly to deterministic eval runs.

## Clone and run tests locally

RegressGuard is a Python 3.11+ CLI with a thin test suite you can run without a GPU or an API key (fixtures stub the model calls).

```bash
git clone https://github.com/fainir/regressguard.git
cd regressguard
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install pytest
pytest -q
```

If you prefer Docker, `docker build -t regressguard .` produces an image that mirrors the CI environment. The `tests/` directory expects to be run from the repo root.

## Add a new eval case

Eval cases live in a YAML or JSON file under `examples/` (or wherever your project keeps them). Each case has an input, an expected shape, and a check type. The five supported check types are `exact`, `regex`, `json_schema`, `semantic`, and `llm_judge` (see `docs/blog/03-five-prompt-eval-patterns.md`).

```yaml
cases:
  - id: greeting-friendly
    input: "Say hello to Avery."
    check:
      type: regex
      pattern: "(?i)hello.*avery"
```

To contribute a new case or check pattern, add the YAML snippet, run `regressguard run --cases <your-file>` locally, and include the output in your PR description. If you are adding a new check type, land it with at least one fixture under `tests/` and a short note in `CHANGELOG.md`.

## Report a bug

Open a GitHub issue at https://github.com/fainir/regressguard/issues with:

- RegressGuard version (`regressguard --version`) and Python version.
- A minimal reproduction: the smallest cases file and command that triggers the bug.
- Expected vs. actual output.

If the bug is a false regression (a case flips pass/fail across runs with no prompt change), please attach two `--json-out` artifacts so we can diff them.

## Open a pull request

1. Fork the repo and create a topic branch (`git checkout -b fix/case-id-collision`).
2. Make the change. Keep diffs small and focused on one concern.
3. Run `pytest -q` and `regressguard run --cases examples/eval-cases.json` locally.
4. Push and open a PR against `main`. In the description, link any related issue and paste the local test output.
5. A maintainer will review within a few business days. We squash-merge, so write a commit message you are happy to see on `main`.

For larger changes, open a draft PR or an issue first so we can agree on scope before you invest time.
