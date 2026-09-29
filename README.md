# RegressGuard eval-runner

Self-hosted CI eval harness for LLM apps (Docker image + CLI). Point it at a prompt template and a case file, get pass/fail counts + per-case results in JSON. Ships as a small CLI you can drop into any pipeline; a GitHub App wrapper (`webhook/`) is being built on top of it.

## Quickstart

Zero API keys, one `docker run`, green pass/fail in under 5 minutes. Uses the bundled `stub` provider so no network or credentials are needed.

```
git clone <this-repo> promptforge && cd promptforge
docker build -t regressguard:latest .
docker run --rm -v "$(pwd)/examples:/examples:ro" regressguard:latest \
  python -m eval_runner.cli \
    --prompt "{{input}}" \
    --cases /examples/quickstart-cases.json \
    --provider stub \
    --stub-responses /examples/quickstart-stub-responses.json
```

Expected tail of the JSON output: `"pass": 3, "fail": 0, ...` across three cases (one `exact`, one `contains`, one `regex`). Exit code is `0` on all-pass, `1` on any fail. Swap `/examples/quickstart-cases.json` for your own case file (schema in [`.agent/eval-schema.md`](.agent/eval-schema.md)) to run the harness against your own prompts; drop `--provider stub --stub-responses ...` and pass `--provider anthropic` (with `ANTHROPIC_API_KEY` in the environment) to run against a real model.

## Install

Requires Python 3.11+. The core CLI is stdlib-only, so stub runs need no third-party deps:

```
git clone <this-repo> promptforge && cd promptforge
```

Provider adapters are imported lazily. Install only the SDK for the provider you actually use:

```
pip install anthropic   # for --provider anthropic
pip install openai      # for --provider openai
                        # nothing needed for --provider stub
```

No package install step - run the CLI as a module (`python -m eval_runner.cli`) from the repo root.

## Usage

```
python -m eval_runner.cli \
  --prompt <TEMPLATE> \
  --cases <PATH> \
  --provider {anthropic,openai,stub} \
  [--model <ID>] \
  [--stub-responses <PATH>] \
  [--out <PATH>]
```

| Flag | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--prompt` | yes | - | Prompt template. `{{input}}` is substituted with each case's `input` field. |
| `--cases` | yes | - | Path to the case file (see [Case schema](#case-schema)). |
| `--provider` | yes | - | One of `anthropic`, `openai`, `stub`. |
| `--model` | no | `claude-haiku-4-5-20251001` | Model id passed to `anthropic` / `openai`. Ignored for `stub`. |
| `--stub-responses` | conditional | - | Required when `--provider stub`. JSON file mapping rendered prompt -> canned response. |
| `--out` | no | stdout | If set, writes the JSON report to this path. |

Exit code is `0` when every case passes and `1` when any case fails or errors.

## Case schema

Case files are JSON documents with a top-level `cases` array. Each case has an `input`, an optional `expected` (informational), and one or more `assertions`. Four assertion types are supported: `exact`, `contains`, `regex`, `llm-judge`. Full schema and semantics live in [`.agent/eval-schema.md`](.agent/eval-schema.md). A worked example with all four types is at [`examples/eval-cases.json`](examples/eval-cases.json).

### Report schema

The runner prints (or writes) JSON of the shape:

```json
{
  "pass": 4,
  "fail": 0,
  "cases": [
    {
      "input": "...",
      "response": "model's output",
      "assertions": [
        { "type": "exact", "value": "ok", "passed": true, "detail": "exact match (True)" }
      ],
      "passed": true
    }
  ]
}
```

If a provider raises for a case (network error, timeout, auth failure), the case gets `{"passed": false, "error": "<ExcType>: <msg>", "response": null, "assertions": []}` and the suite continues. The `error` key is present only on errored cases. Errored cases count as `fail` in the suite total.

## Examples

### Stub run (no API key, deterministic)

Reproduces the 4/4-pass fixture report from `.agent/runs/eval-runner-cli-2026-07-09.json`:

```
python -m eval_runner.cli \
  --prompt "{{input}}" \
  --cases examples/eval-cases.json \
  --provider stub \
  --stub-responses examples/stub-responses.json
```

Output ends with `"pass": 4, "fail": 0, ...`. Useful for CI smoke tests and for developing new assertion types against known responses.

### Anthropic run (real model)

```
export ANTHROPIC_API_KEY=sk-ant-...
python -m eval_runner.cli \
  --prompt "{{input}}" \
  --cases examples/eval-cases.json \
  --provider anthropic \
  --model claude-haiku-4-5-20251001 \
  --out report.json
```

Runs each case through the model, applies assertions (including `llm-judge`, which re-uses the same provider as the judge), writes the report to `report.json`.

## Web UI

The same eval-runner is exposed as a tiny HTTP surface for browser-driven runs, so you can paste a prompt + cases and get a per-case pass/fail table without touching the CLI. Start the server locally with `python -m eval_runner.server` from the repo root; it binds `127.0.0.1:8787` and serves the single-page form at `GET /`, the JSON runner at `POST /run`, and a health probe at `GET /health`. The form takes a prompt template textarea (uses the same `{{input}}` substitution as the CLI), a cases JSON textarea (top-level `{"cases": [...]}` schema as in [`.agent/eval-schema.md`](.agent/eval-schema.md)), a provider dropdown (`anthropic` / `openai` / `stub`), an optional model id, and — for the stub path — an inline stub-responses JSON textarea; on submit the browser POSTs `{prompt, cases, provider, model?, stub_responses_inline?}` with an `X-Session-Id` header (UUID cached in `localStorage`) and renders `{pass, fail}` plus a per-case table (input / response / assertions / passed). Every successful run also appends one row to a SQLite persistence store with columns `id, ts, prompt_hash, cases_count, pass, fail, provider, session_id` — see [`eval_runner/store.py`](eval_runner/store.py) for the schema. The store path defaults to `.agent/regressguard.db` and can be overridden via the `REGRESSGUARD_DB` environment variable (`REGRESSGUARD_DB=/tmp/runs.db python -m eval_runner.server`); persistence is best-effort, so a store error is logged to stderr but does not fail the response. A worked end-to-end curl transcript against the stub suite (with the sqlite row query that confirms the write) lives at [`.agent/runs/standalone-ui-2026-07-21.md`](.agent/runs/standalone-ui-2026-07-21.md).

## Tests

The pytest suite covers assertions (12 cases across all 4 types + schema errors), the CLI (3 cases: all-pass stub, exit-1 on fail, missing-stub-responses errors), per-case error isolation (2 cases: single-raise + mixed-ok-and-error), the HTTP server (12 cases: POST /run happy + validation + GET / HTML + health + inline stub-responses + persistence), the SQLite runs store (5 cases: record + read back + auto-schema + list ordering + prompt-hash stability), and the webhook module (5 cases: HMAC verify + PR-event handler). Run:

```
python -m pytest tests/ -v
```

Expected: 39 passed.
