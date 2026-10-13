# RegressGuard blog

Short, hands-on posts about shipping prompt-regression testing. Each post is self-contained and runnable against the open-source `regressguard` CLI.

## Posts

- [01 - Why prompt regression testing matters](01-why-prompt-regression-testing.md) - the failure mode LLM apps hit the first time a prompt tweak silently breaks a workflow, and why vibes-based review is not enough once a prompt is in production.
- [02 - RegressGuard in GitHub Actions](02-regressguard-in-github-actions.md) - a copy-pastable workflow that runs the eval suite on every pull request, fails the check on any case regression, and uploads the JSON report as a build artifact.
- [03 - Five prompt eval patterns, cheapest to most expensive](03-five-prompt-eval-patterns.md) - a runnable walkthrough of exact-match, regex-contains, JSON-shape-validation, semantic-similarity, and rubric-driven LLM-judge assertions, with one YAML case per pattern.

## How to use the series

Read 01 if you are deciding whether to adopt prompt regression testing at all. Read 02 once you have a case file and want to wire it into CI. Read 03 when you are deciding which assertion type each new case should use.

Full case schema and runner flags live in the [root README](../../README.md) and in [`.agent/eval-schema.md`](../../.agent/eval-schema.md).
