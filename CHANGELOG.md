# Changelog

All notable changes are documented here. The project has not published a stable release yet.

## Unreleased

### Added

- Persisted custom gate-rule API and evaluator capability discovery
- Database migration gating, liveness/readiness endpoints, and non-root backend image
- Worker delivery leases, idempotent progress recounts, and dispatch-failure persistence
- Live dashboard source/context metadata, honest empty states, and packaged nginx API proxy
- Adapter and provider allowlists, inline-secret rejection, request correlation, and security headers
- Dependency audits, CodeQL, Dependabot, coverage gating, contribution, and security policy files

### Changed

- Comparison confidence intervals now pair samples by case identity
- Dashboard values and verdicts are derived from persisted runs and active gate rules
- Dashboard aggregation uses bounded bulk queries instead of per-case query loops
- Calibration assets are explicitly described as an author-scored synthetic fixture
