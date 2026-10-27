# RegressGuard

[![CI](https://github.com/fainir/regressguard/actions/workflows/ci.yml/badge.svg)](https://github.com/fainir/regressguard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A small, self-hosted CLI for developers shipping LLM features: run a prompt template against a file of test cases and fail the CI build when any case stops passing.

Prompt edits and model upgrades break things quietly. A one-line tweak that fixes one bug report can change the output shape for inputs nobody re-checked. RegressGuard turns "I read a few outputs and it looked fine" into a case file that runs on every pull request: each case is an input plus checks (`exact`, `contains`, `regex`, `llm-judge`), and the exit code tells CI whether they all still pass.

## Quick start

Needs Python 3.11+ and git. No API key: the bundled `stub` provider returns canned responses.

```bash
git clone https://github.com/fainir/regressguard.git
cd regressguard
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
regressguard --prompt "{{input}}" \
  --cases examples/quickstart-cases.json \
  --provider stub \
  --stub-responses examples/quickstart-stub-responses.json
```

The JSON report goes to stdout, a one-line summary to stderr, and the exit code is `0`:

```text
{
  "pass": 3,
  "fail": 0,
  "cases": [ ... ]
}
regressguard: 3 passed, 0 failed
```

Now replay the same cases against responses from a "worse" prompt to see what a regression looks like:

```bash
regressguard --prompt "{{input}}" \
  --cases examples/quickstart-cases.json \
  --provider stub \
  --stub-responses examples/regressed-stub-responses.json \
  --out report.json
echo "exit code: $?"
```

```text
FAIL case 1 ("Return only the string 'ok' with no punctuation or whites..."): expected 'ok', got 'OK.'
FAIL case 3 ('Give me a US phone number in the format 555-123-4567.'): regex /\b\d{3}-\d{3}-\d{4}\b/ did not match
regressguard: 1 passed, 2 failed
exit code: 1
```

## Install

RegressGuard is not published on PyPI. Install it from GitHub:

```bash
pip install "git+https://github.com/fainir/regressguard"
```

The core is stdlib-only. Add the SDK for the provider you use, either directly or as an extra:

```bash
pip install anthropic   # for --provider anthropic
pip install openai      # for --provider openai
# or in one step:
pip install "regressguard[anthropic] @ git+https://github.com/fainir/regressguard"
```

Since there are no tagged releases yet, pin a commit in CI (`...regressguard@<commit-sha>`).

**Docker.** The image has both SDKs installed. By default it starts the [web UI](#web-ui-and-http-api); pass a command to run the CLI instead:

```bash
docker build -t regressguard .
docker run --rm -v "$(pwd)/examples:/examples:ro" regressguard \
  regressguard --prompt "{{input}}" \
    --cases /examples/quickstart-cases.json \
    --provider stub \
    --stub-responses /examples/quickstart-stub-responses.json
```

## Usage

### Against a real model

```bash
export ANTHROPIC_API_KEY=...
regressguard \
  --prompt "$(cat prompts/support-reply.md)" \
  --cases evals/support-reply.json \
  --provider anthropic \
  --out report.json
```

`{{input}}` in the prompt is replaced by each case's `input`. Each rendered prompt is sent as a single user message. `llm-judge` checks reuse the same provider and model as the judge.

### In GitHub Actions

```yaml
name: Prompt evals
on: pull_request

jobs:
  evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "regressguard[anthropic] @ git+https://github.com/fainir/regressguard"
      - name: Run evals
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          regressguard \
            --prompt "$(cat prompts/support-reply.md)" \
            --cases evals/support-reply.json \
            --provider anthropic \
            --out eval-report.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: eval-report
          path: eval-report.json
```

Any failing case fails the step, so making this job a required status check blocks the merge. The [blog post on CI](docs/blog/02-regressguard-in-github-actions.md) walks through it.

### Flags

| Flag | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--prompt` | yes | - | Prompt template. `{{input}}` is replaced with each case's `input`. |
| `--cases` | yes | - | Path to the [case file](#case-file-format). |
| `--provider` | yes | - | `anthropic`, `openai`, or `stub`. |
| `--model` | no | `claude-haiku-5-5` for anthropic | Model id. Required for `openai`. Ignored for `stub`. |
| `--stub-responses` | with `stub` | - | JSON file mapping each rendered prompt to a canned response. |
| `--out` | no | stdout | Write the JSON report to this file instead of stdout. |
| `--timeout` | no | `60` | Per-request timeout in seconds for `anthropic` / `openai`. The SDKs retry rate limits and 5xx errors twice. |
| `--version` | no | - | Print the version and exit. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every case passed. |
| `1` | At least one case failed, or its provider call raised (timeout, auth error, ...). |
| `2` | Usage or configuration error: bad flags, missing or malformed case file, provider could not be set up. Nothing was run. |

## Case file format

A JSON object with a top-level `cases` array. Unknown fields are ignored. The whole file is validated before anything runs, so a typo is an error (exit `2`), not a silently passing case.

```json
{
  "cases": [
    {
      "input": "Give me a US phone number in the format 555-123-4567.",
      "expected": "Optional reference answer, for humans reading the report.",
      "assertions": [
        { "type": "regex", "value": "\\b\\d{3}-\\d{3}-\\d{4}\\b" }
      ]
    }
  ]
}
```

| Field | Required | Meaning |
| --- | --- | --- |
| `input` | yes | String substituted into the prompt at `{{input}}`. |
| `expected` | no | Informational only. Never compared. |
| `assertions` | yes, at least one | Checks applied to the response. The case passes only if all of them pass. |

| `type` | `value` | Passes when |
| --- | --- | --- |
| `exact` | expected response | `response.strip() == value.strip()` |
| `contains` | substring | `value` appears in the response (case-sensitive). |
| `regex` | Python regex | `re.search(value, response)` finds a match. Use `(?i)` for case-insensitive. |
| `llm-judge` | a label for the report | The judge's answer to `judge_prompt` (with `{{response}}` filled in) starts with `PASS`. Leading blank lines, markdown and punctuation are ignored; anything else fails. |

[`examples/eval-cases.json`](examples/eval-cases.json) uses all four types, including an `llm-judge` prompt.

## Report format

```json
{
  "pass": 1,
  "fail": 1,
  "cases": [
    {
      "input": "...",
      "response": "the model's output",
      "assertions": [
        { "type": "exact", "value": "ok", "passed": false, "detail": "expected 'ok', got 'OK.'" }
      ],
      "passed": false
    },
    {
      "input": "...",
      "response": null,
      "assertions": [],
      "passed": false,
      "error": "TimeoutError: ..."
    }
  ]
}
```

If a provider call raises for a case (including an `llm-judge` call), that case gets an `error` field and counts as a failure, and the remaining cases still run.

## Web UI and HTTP API

The same runner is available over HTTP, with a single-page form for pasting a prompt and cases:

```bash
regressguard-server        # or: python -m eval_runner.server
# regressguard: serving on http://127.0.0.1:8787
```

| Endpoint | Purpose |
| --- | --- |
| `GET /` | The web UI. |
| `POST /run` | JSON body `{"prompt", "cases", "provider", "model"?, "stub_responses_inline"?}`. Returns the report. Bad input is a `400`; bodies over 1 MB are a `413`. |
| `GET /health` | `{"status": "ok"}` |

Each successful run appends a row (timestamp, prompt hash, case count, pass, fail, provider, `X-Session-Id` header) to a SQLite file. Over HTTP the stub provider only takes inline responses; it never reads files named in the request.

The server has no authentication and calls the model with the server's API keys. Keep it on localhost (the default) or behind your own auth.

## Configuration

| Environment variable | Used by | Default | Meaning |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | `--provider anthropic` | - | Read by the Anthropic SDK. |
| `OPENAI_API_KEY` | `--provider openai` | - | Read by the OpenAI SDK. |
| `REGRESSGUARD_HOST` | server | `127.0.0.1` (`0.0.0.0` in Docker) | Bind address. |
| `REGRESSGUARD_PORT` | server | `8787` | Port. |
| `REGRESSGUARD_DB` | server | `./regressguard.db` (`/data/regressguard.db` in Docker) | SQLite file for run history. Write errors are logged and do not fail the request. |

## How it works

1. Load and validate the case file.
2. For each case, render the prompt and call the provider once (`max_tokens` 1024 for Anthropic).
3. Apply each assertion to the response; `llm-judge` makes one more provider call.
4. Write the JSON report, print a summary to stderr, exit `0`, `1` or `2`.

The code is a few hundred lines of stdlib Python in [`eval_runner/`](eval_runner/): `cli.py` (runner and CLI), `assertions.py`, `providers.py`, `server.py` and `store.py`.

## Limitations

- **No baseline comparison.** Every case must pass on every run; a case that is broken on `main` too still fails the build. Keep the case file green, and fix or remove known-broken cases.
- **Nondeterminism is up to you.** There is no retry-and-vote for flaky cases. Prefer `exact` / `contains` / `regex` where they work, and keep `llm-judge` rubrics strict.
- Cases run one at a time, with a single user message per call. No system prompt, temperature or `max_tokens` flags yet.
- Built-in providers are Anthropic, OpenAI and the offline stub.
- `webhook/` holds GitHub webhook signature verification and a pull request event handler, groundwork for a GitHub App. It is not wired to an endpoint yet and is not part of the installed package.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

The tests are hermetic: no network and no API keys. See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).

## Blog

Posts on prompt regression testing live in [`docs/blog/`](docs/blog/README.md): why it matters, running RegressGuard as a pull request check, and five assertion patterns from cheapest to most expensive.

## License

[MIT](LICENSE)
