# RegressGuard in GitHub Actions: a copy-pasteable CI setup for prompt tests

The first post in this series argued that prompts need regression tests. This one makes that argument executable. In about ten minutes you can wire a GitHub Actions workflow that runs your prompt evals on every pull request, prints a human-readable pass or fail, and refuses to merge when a prompt regresses.

Nothing in here is specific to RegressGuard. The same shape works with any eval runner you prefer. We use RegressGuard because it emits a non-zero exit code on failure and writes a JSON report you can keep as a build artifact - two features that make CI integration cheap.

## The workflow

Create `.github/workflows/regressguard.yml` in your repository with the following contents.

```yaml
name: RegressGuard
on:
  pull_request:
    paths:
      - "prompts/**"
      - "evals/**"
      - ".github/workflows/regressguard.yml"
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  evals:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install RegressGuard
        run: pip install "regressguard[anthropic] @ git+https://github.com/fainir/regressguard"

      - name: Run evals
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          regressguard \
            --prompt "$(cat prompts/summarize.md)" \
            --cases evals/summarize.json \
            --provider anthropic \
            --out eval-report.json

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: eval-report.json
```

Three things worth noticing. First, the `paths` filter means the workflow only runs when prompts, evals, or the workflow itself change - no wasted minutes when a developer edits unrelated code. Second, the API key lives in `secrets.ANTHROPIC_API_KEY` so you can rotate it without touching the repo. Third, the report upload runs with `if: always()`, so the full JSON report (every response and every check) is attached to failed runs, which are the ones you want to read.

RegressGuard is not on PyPI, so the install step pulls it from GitHub. Pin a commit (`...regressguard@<sha>`) once you have a setup you trust. One `regressguard` call runs one prompt template against one case file; if you have several prompts, add one step per prompt.

## Reading the output

When the job finishes, open the Actions tab and expand the "Run evals" step. A run where a prompt change broke two of three cases looks like this:

```
FAIL case 1 ("Return only the string 'ok' with no punctuation or whites..."): expected 'ok', got 'OK.'
FAIL case 3 ('Give me a US phone number in the format 555-123-4567.'): regex /\b\d{3}-\d{3}-\d{4}\b/ did not match
regressguard: 1 passed, 2 failed
Error: Process completed with exit code 1.
```

Each failing case gets one line: its position in the case file, the start of its input, and the check that failed. The full responses are in the uploaded `eval-report.json`. That is the signal you care about: a specific case, a specific check, and what the model said instead.

The exit code is 0 only when every case passes and 1 when any case fails or its model call errors. A broken setup - a missing case file, a typo in an assertion, an unknown provider - exits 2 before any model call, so a misconfigured job fails loudly instead of passing with nothing checked.

## Gating merges

To make the check binding, add a required status check in your branch protection rules.

1. In the repository, go to Settings, Branches, and open the rule for `main`.
2. Enable "Require status checks to pass before merging".
3. In the "Status checks that are required" list, search for `RegressGuard / evals` and add it.
4. Save.

From that point forward, a pull request that regresses any eval is simply not mergeable. The author gets a specific reason, pinned to specific cases, instead of a vague review comment two days later. If you want to allow override, use GitHub's "Bypass who can push to matching branches" setting rather than disabling the check - that way the override is auditable.

For teams that are not ready to hard-gate, keep the workflow as "advisory" by not adding it to required checks. The check still runs and shows its result on the PR; it just does not block.

## Known-broken cases and flakes

RegressGuard does not compare against a baseline run: every case in the file must pass. That keeps the rule simple - the case file on `main` is the baseline, and it should be green. If a case is known broken, fix the prompt or move the case out of the file until you do. A check that is always red teaches people to ignore it.

A common early frustration is prompt flakes: a case that passes nineteen times and fails on the twentieth. RegressGuard does not rerun cases or take a majority vote, so the defense is in how you write cases. Check the parts of the output that must be stable with `exact`, `contains`, and `regex`, keep `llm-judge` rubrics strict and specific, and when a case still flaps, ask whether it checks something the prompt does not actually pin down.

## What to do this week

Pick one prompt your team ships, write three evals for it (one happy path, one adversarial, one past-bug reproduction), and drop the workflow above into the repository. By Friday you will have a PR check that actually knows whether your prompt still works. The third post in this series goes deeper on how to design those three evals so they catch real regressions and not noise.
