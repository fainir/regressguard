# Changelog

All notable changes to RegressGuard are documented in this file.

The project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `pyproject.toml`, so `pip install -e .` and `pip install "git+https://github.com/fainir/regressguard"` work. Installs the `regressguard` and `regressguard-server` commands; provider SDKs are optional extras (`anthropic`, `openai`, `all`).
- `--timeout` (default 60 seconds per provider request) and `--version`.
- A pass/fail summary listing the failing cases on stderr. Stdout is still only the JSON report.
- `examples/regressed-stub-responses.json`, a canned regression for trying a failing run.
- MIT license and a CI workflow (tests on Python 3.11 to 3.13, the quick start, and the Docker image).

### Changed

- The case file is validated before anything runs. Configuration errors (missing or malformed case file, unknown assertion type, invalid regex, provider setup) exit `2` with a one-line message instead of a traceback with exit `1`.
- The default Anthropic model is now `claude-haiku-5-5`. `--provider openai` requires `--model`.
- `llm-judge` accepts `PASS` after leading blank lines, markdown or punctuation.
- Failed `exact` and `regex` checks say what was expected and what came back.
- Server: handles requests concurrently, caps request bodies at 1 MB, and stores run history in `./regressguard.db` by default (was `.agent/regressguard.db`). Over HTTP the stub provider only accepts `stub_responses_inline`; the `stub_responses` file path is rejected.
- The Docker image installs the package with both provider SDKs, and its health check follows `REGRESSGUARD_PORT`.

### Fixed

- A case with no `assertions` (for example a typo like `assertion`) passed without checking anything.
- An `llm-judge` call that raised aborted the whole run instead of failing only that case.
- `--provider openai` without `--model` sent the Claude default model id to OpenAI.
- The web UI and webhook modules were missing from the repository: `GET /` returned 500 and `docker build` failed.
- The SQLite store never closed its connections.
- Webhook signature verification raised on non-ASCII signature headers and accepted an empty secret.

## [0.1.0] - 2026-09-09

### Added

- Eval runner CLI: renders a prompt template for each case in a JSON case file, calls the provider, applies `exact`, `contains`, `regex` and `llm-judge` assertions, writes a JSON report, and exits non-zero when any case fails.
- Providers: Anthropic, OpenAI, and an offline `stub` provider with canned responses.
- HTTP server with a web UI, `POST /run`, `GET /health`, and SQLite run history.
- Docker image.
