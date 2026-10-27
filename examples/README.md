# Examples

Small JSON files you can feed directly to `regressguard` to see it work without any API keys or external services. They run against the bundled `stub` provider, which returns canned responses keyed by the rendered prompt.

The `quickstart-*` pair is the 3-case tour from the [Quick start](../README.md#quick-start). The other pair is a broader 4-case set that also exercises `llm-judge`.

## Files in this directory

- **`quickstart-cases.json`** - 3 cases, one per deterministic assertion type (`exact`, `contains`, `regex`). Pair with `quickstart-stub-responses.json`.
- **`quickstart-stub-responses.json`** - Canned responses for the quickstart cases, so `--provider stub` resolves every input without a live model call.
- **`regressed-stub-responses.json`** - The same three prompts answered the way a worse prompt might answer them. Run it against `quickstart-cases.json` to see a failing run and exit code `1`.
- **`eval-cases.json`** - 4 cases covering all assertion types, including an `llm-judge` rubric. Pair with `stub-responses.json`.
- **`stub-responses.json`** - Canned responses for `eval-cases.json`, including the judge's `PASS` verdict (keyed by the rendered judge prompt).

## Running these

From the repo root, after `pip install -e .`:

```bash
# 3-case quickstart (offline, no API key): exit 0
regressguard --prompt "{{input}}" \
  --cases examples/quickstart-cases.json \
  --provider stub \
  --stub-responses examples/quickstart-stub-responses.json

# The same cases against regressed responses: exit 1
regressguard --prompt "{{input}}" \
  --cases examples/quickstart-cases.json \
  --provider stub \
  --stub-responses examples/regressed-stub-responses.json

# Full 4-case set including llm-judge (offline): exit 0
regressguard --prompt "{{input}}" \
  --cases examples/eval-cases.json \
  --provider stub \
  --stub-responses examples/stub-responses.json
```

The case file format is documented in the [README](../README.md#case-file-format).
