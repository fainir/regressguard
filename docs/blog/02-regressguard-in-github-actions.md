# RegressGuard in GitHub Actions: a copy-pasteable CI setup for prompt tests

The first post in this series argued that prompts need regression tests. This one makes that argument executable. In about ten minutes you can wire a GitHub Actions workflow that runs your prompt evals on every pull request, prints a human-readable pass or fail, and refuses to merge when a prompt regresses.

Nothing in here is specific to RegressGuard. The same shape works with any eval runner you prefer. We use RegressGuard because it emits a non-zero exit code on failure and writes a short Markdown summary - two features that make CI integration cheap.

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
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install RegressGuard
        run: pip install regressguard==0.3.*

      - name: Run evals
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          regressguard run evals/ \
            --baseline main \
            --report-md $GITHUB_STEP_SUMMARY \
            --json-out eval-report.json

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: eval-report.json

      - name: Comment on PR
        if: github.event_name == 'pull_request' && always()
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          header: regressguard
          path: $GITHUB_STEP_SUMMARY
```

Four things worth noticing. First, the `paths` filter means the workflow only runs when prompts, evals, or the workflow itself change - no wasted minutes when a developer edits unrelated code. Second, the API key lives in `secrets.ANTHROPIC_API_KEY` so you can rotate it without touching the repo. Third, the report goes to `$GITHUB_STEP_SUMMARY`, which shows up directly in the Actions UI. Fourth, the sticky PR comment overwrites itself on every run, so the PR conversation does not fill up with duplicate reports.

## Reading the output

When the job finishes, open the Actions tab and expand the "Run evals" step. You will see something like this.

```
RegressGuard 0.3.1
Loaded 12 evals from evals/
Baseline: main @ 7a1b2c3

PASS  evals/intent-classifier.yml       12/12
FAIL  evals/summarizer.yml               9/10  (regressed vs baseline)
PASS  evals/entity-extractor.yml         8/8

1 regression, 29/30 cases passed.
```

The counts are per case, not per file. The `(regressed vs baseline)` tag means that at least one case in that eval file passed on `main` but fails on the pull request's commit. That is the signal you care about. A case that fails in both branches is a known-broken case, not a regression - RegressGuard still reports it but does not block the merge.

The exit code is 0 only when there are zero regressions. New failures that are also baseline failures do not fail the job. New failures introduced by the change do.

## Gating merges

To make the check binding, add a required status check in your branch protection rules.

1. In the repository, go to Settings, Branches, and open the rule for `main`.
2. Enable "Require status checks to pass before merging".
3. In the "Status checks that are required" list, search for `RegressGuard / evals` and add it.
4. Save.

From that point forward, a pull request that regresses any eval is simply not mergeable. The author gets a specific reason, pinned to specific cases, instead of a vague review comment two days later. If you want to allow override, use GitHub's "Bypass who can push to matching branches" setting rather than disabling the check - that way the override is auditable.

For teams that are not ready to hard-gate, keep the workflow as "advisory" by not adding it to required checks. The PR comment still appears; it just does not block.

## Baselines and flakes

The baseline flag `--baseline main` tells RegressGuard to compare the current run against the most recent run on `main`. If `main` has never been evaluated, the first run creates the baseline and no regressions can be reported. This means your first CI run is always green, which is the correct behavior - you have nothing to regress against yet.

A common early frustration is prompt flakes: a case that passes nineteen times and fails on the twentieth. RegressGuard handles this with a `samples` field in the eval definition that reruns a case N times and takes the majority vote. Three samples is usually enough to cut flake noise by an order of magnitude without tripling your API bill. Set it per-case rather than globally so stable cases stay cheap.

## What to do this week

Pick one prompt your team ships, write three evals for it (one happy path, one adversarial, one past-bug reproduction), and drop the workflow above into the repository. By Friday you will have a PR check that actually knows whether your prompt still works. The third post in this series goes deeper on how to design those three evals so they catch real regressions and not noise.
