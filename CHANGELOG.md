# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- UI snapshot anchored at `ui-v1.0` for visual regression testing
- Visual regression scaffold with Playwright-based screenshot comparison

## [0.1.0] — 2026-04-30

### Added

- Flask web server with Inbox / Queue / Library / Monitor / Settings navigation
- 3-stage recommendation pipeline (Recall → Rank → Learn) behind `STATDESK_RANKER=v2`
- AI paper analysis via DeepSeek-compatible API (optional, with no-provider fallback)
- SQLite-backed workflow state for queue, collections, and subscriptions
- Local offline recommendation evaluator
- Docker and Docker Compose deployment support

[Unreleased]: https://github.com/SunWeizhou/ppr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SunWeizhou/ppr/releases/tag/v0.1.0
