# Examples

This directory ships four small JSON files you can feed directly to `regressguard run` to see the tool work without any API keys or external services. Everything here runs against the bundled `stub` provider that returns canned responses, so a clean clone can execute the full flow in under 30 seconds.

The `quickstart-*` pair is the 3-case tour referenced from `docs/getting-started.md`. The non-quickstart pair is the broader 4-case eval set referenced from the top-level `README.md` and used in CI smoke tests.

## Files in this directory

- **`eval-cases.json`** - The 4-case eval set covering all assertion types (`exact`, `contains`, `regex`, plus one freeform case). Pair this with `stub-responses.json` for an offline run that exercises every validator in the matrix.
- **`quickstart-cases.json`** - The 3-case minimal set used by the Getting Started walkthrough. One case per primary assertion type (`exact`, `contains`, `regex`). Pair with `quickstart-stub-responses.json`.
- **`quickstart-stub-responses.json`** - Canned responses keyed by prompt for the quickstart cases, so `--provider stub` resolves every input without a live model call.
- **`stub-responses.json`** - Canned responses for the full 4-case `eval-cases.json` set; a superset of the quickstart response map.

## Running these

From the repo root:

```bash
# Minimal 3-case quickstart (offline, no API key)
regressguard run \
  --cases examples/quickstart-cases.json \
  --provider stub \
  --stub-responses examples/quickstart-stub-responses.json

# Full 4-case eval set (offline)
regressguard run \
  --cases examples/eval-cases.json \
  --provider stub \
  --stub-responses examples/stub-responses.json
```

Case and response schemas are documented in `.agent/eval-schema.md`.
