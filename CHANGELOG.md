# Changelog

All notable changes to PromptForge / RegressGuard are documented in this file.

The project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0-dev] - 2026-09-10

Phase 2 scope decision. Path (d) `consolidate marketable surface` chosen after 50+ consecutive standups showed zero operator movement on Gates 1-4 (`.env`, `.secrets/`, GitHub App registration, hosted URL). Non-operator-gated content + SEO iteration takes priority over queue-then-stall paths.

### Planned

- Extract `regressguard` (eval-runner + Dockerfile + tests + examples) to standalone repo `fainir/regressguard`. See plan.md task `phase-2-scoping.extract-repo`.
- SEO copy iteration on `fainir/promptforge-landing` for terms `LLM eval CI` and `prompt regression testing`. See plan.md task `phase-2-scoping.seo-copy-iteration`.
- Preserve paths (a) `standalone-UI hosted URL`, (b) `github-app-skeleton reactivation`, (c) `stripe-checkout` as opportunistic pivots auto-activating on operator Gate-1 clearance.

Evidence: `.agent/phase-2-scope-2026-09-09.md` (scope decision, ~110 lines).

## [0.1.0] - 2026-09-09

Phase 1 close at reduced scope. Three shippable items verified against live state at the `phase-1-close-checkpoint` fire.

### Added

- Landing page (Day 23, 2026-07-04). Self-hosted / CLI framing. Live at `fainir.github.io/promptforge-landing`. Lighthouse mobile SEO score 100 (Day 26 baseline). See plan.md task `landing-page` and commit `630799b3` on `fainir/promptforge-landing` for the self-hosted framing edit (Day 85, 2026-09-09).
- Eval-runner MVP (Day 24, 2026-07-05). CLI harness that runs prompt regression evals over a fixture set and emits JSON output. Source: `eval_runner/` in this tree. See plan.md task `eval-runner-mvp`.
- Docker image (Day 36, 2026-07-17). Reproducible container for the eval-runner. Source: `Dockerfile` in this tree. See plan.md task `docker-image`.
- README Quickstart (Day 85, 2026-09-09). `README.md` `## Quickstart` section covering the self-hosted CLI + Docker path. See plan.md task `phase-1-close-checkpoint.readme-quickstart` and `.agent/runs/readme-quickstart-2026-09-09.md`.

### Changed

- Portfolio status flipped to `closed-reduced-scope` at Day 85. Evidence: `.agent/portfolio-link.json` line 11 `"phase_1_status": "closed-reduced-scope"`.

### Deferred

- Standalone-UI hosted URL (blocked on operator `flyctl auth login` or equivalent host token).
- GitHub App skeleton (blocked on operator registration + `.env` + `.secrets/`).
- Stripe checkout (transitive on standalone-UI).

Evidence pointers: `.agent/plan.md` (progress line 39/42 92% at Day 87 close), `.agent/retros/retro-2026-09-11.md`, `.agent/phase-2-scope-2026-09-09.md`.
