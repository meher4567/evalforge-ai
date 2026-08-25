# Production launch and 90+ completion plan

Last updated: 2026-08-20

This is the owner handoff for taking EvalForge from a verified repository to a defensible
production release. Complete the phases in order. A checked box means the work was performed and
the required evidence was saved; it must not mean that someone only reviewed the instructions.

Never paste passwords, API keys, bootstrap tokens, database URLs, or telemetry credentials into a
GitHub issue, pull request, screenshot, terminal transcript, or committed file.

## Current verified state

| Area | Current state |
|---|---|
| Hardening branch | `codex/evalforge-top-level-hardening` at `352bbbb` |
| Pull request | [PR #2](https://github.com/meher4567/evalforge-ai/pull/2), ready for review |
| Branch protection | Strict required checks, one independent approval, resolved conversations, no force pushes or branch deletion |
| Final PR checks | 8 of 8 passed, including backend, frontend, CodeQL, aggregate security, and Docker/Celery smoke |
| Backend verification | 277 passed, 2 intentional skips, 73.38% coverage, Ruff clean |
| Frontend verification | 19 tests, TypeScript, production build, and Chromium E2E passed |
| Security scan | Zero open CodeQL alerts on the PR |
| Demo preview | [Final Vercel preview](https://frontend-qi0l20zuq-meher4567s-projects.vercel.app) |
| Render | `render.yaml` validated; managed services are not yet deployed from `main` |
| License | Apache-2.0 |
| Honest score | Approximately 92/100 for repository engineering and 88/100 for externally demonstrated project maturity |

The gap between the two scores matters. The codebase is well engineered, but a strong public claim
also needs independently labeled real outputs, measured behavior against real model providers, and
evidence from an actual managed deployment.

## Definition of done

EvalForge may be described as a production-ready 90+ project only when all of these are true:

- [ ] PR #2 received an independent approval and was merged without bypassing branch protection.
- [ ] API, worker, PostgreSQL, Redis, and frontend are running on managed infrastructure with TLS.
- [ ] The first owner was bootstrapped, the bootstrap secret was rotated, and live RBAC/tenant
      isolation checks passed.
- [ ] Production demo fallback is disabled and a real provider-backed evaluation completes.
- [ ] Metrics, traces, errors, dashboards, and actionable alerts are receiving live data.
- [ ] The default load profile passes against staging, followed by a budget-capped provider test.
- [ ] A checksum-verified production backup was restored into a disposable database inside the RTO.
- [ ] An independently and blindly labeled calibration study passes its pre-registered criteria.
- [ ] Release `v0.1.0` was tagged from reviewed `main`, and its archives and checksums were verified.
- [ ] Known limitations and measured claims remain explicit in the README and release notes.

## Priority and effort summary

| Priority | Work | Typical focused effort | Blocks |
|---|---|---:|---|
| P0 | Independent review and merge | 1–3 hours plus reviewer availability | Every deployment step |
| P0 | Managed Render and Vercel production deployment | 1–2 days | Public production launch |
| P0 | Bootstrap, RBAC, tenant, provider, and security smoke tests | 0.5–1 day | Production acceptance |
| P1 | Telemetry dashboards, alerts, and soak | 1–3 days | Operational evidence |
| P1 | Staging and real-provider load tests | 2–4 days | Capacity claims |
| P1 | Independent blinded calibration | 5–10 days plus labeler availability | Credible evaluator-quality claims |
| P1 | Backup/restore and disaster-recovery drill | 0.5–1 day | Durability claims |
| P2 | Custom domains, release assets, case study, and `v0.1.0` | 1–2 days | Polished public release |

Expected total: roughly 2–4 focused engineering weeks. Labeler scheduling, provider quotas, DNS,
and managed-service provisioning can extend calendar time without increasing engineering effort.

## Phase 1: independent review and protected merge

### Owner actions

- [ ] Add or invite a collaborator who can review the repository.
- [ ] Ask that reviewer to inspect the migration, tenant boundaries, authentication, secret
      handling, worker lease/idempotency behavior, and deployment configuration.
- [ ] Resolve every review conversation with code or a written rationale.
- [ ] Require a fresh approval after the final push. The branch rule intentionally requires this.
- [ ] Confirm all required checks still refer to the final head commit.

Read-only verification:

```bash
gh pr checks 2 --repo meher4567/evalforge-ai
gh pr view 2 --repo meher4567/evalforge-ai \
  --json isDraft,mergeStateStatus,reviewDecision,headRefOid,statusCheckRollup
```

Expected result:

- `isDraft` is `false`;
- `reviewDecision` is `APPROVED`;
- all required checks are successful;
- the reviewed head SHA matches the PR head SHA.

Merge only after those conditions are true:

```bash
gh pr merge 2 --repo meher4567/evalforge-ai --squash --delete-branch
git switch main
git pull --ff-only origin main
```

### Acceptance evidence

- Link to the approving review.
- Link to the merged PR.
- Merge commit SHA from `main`.
- Screenshot or JSON output showing the required checks passed on the merged revision.

Do not create `v0.1.0` from the feature branch and do not use administrator bypass to replace the
independent review.

## Phase 2: production decisions before provisioning

Record these decisions in a private launch issue or operations ticket:

| Decision | Required choice |
|---|---|
| Environment layout | At minimum `staging` and `production`; never load-test production first |
| Region | Keep API, worker, PostgreSQL, and Redis in one region unless a measured need says otherwise |
| Service plan | Non-sleeping API and worker for production; database plan with automated backups |
| Public origins | Final API URL, frontend URL, and optional custom domains |
| Model provider | Groq, OpenAI, or both, with explicit quota and test budget |
| Error reporting | Sentry project or an equivalent error backend |
| Tracing | OTLP-compatible collector and trace backend |
| Metrics | Prometheus-compatible scraper and dashboard/alert destination |
| Backup storage | Encrypted object storage, retention period, owner, and deletion policy |
| On-call owner | One named person for alerts and one backup contact |

The free plans in `render.yaml` are suitable for a demonstration or staging environment. Do not
claim the documented availability or backup SLOs from a sleeping or non-backed-up production plan.

## Phase 3: deploy the Render stack

After `render.yaml` exists on merged `main`, open the
[Render Blueprint deployment](https://dashboard.render.com/blueprint/new?repo=https%3A%2F%2Fgithub.com%2Fmeher4567%2Fevalforge-ai).

The Blueprint should create:

- `evalforge-api` from `backend/Dockerfile`;
- `evalforge-worker` from `backend/Dockerfile.worker`;
- PostgreSQL 16 as `evalforge-postgres`;
- Redis as `evalforge-redis`;
- the shared `evalforge-production` environment group.

### Required environment values

| Variable | Requirement |
|---|---|
| `EVALFORGE_ENVIRONMENT` | Must remain `production` |
| `EVALFORGE_RUN_MODE` | Must remain `celery` |
| `EVALFORGE_DATABASE_URL` | Supplied from the Render PostgreSQL resource |
| `EVALFORGE_REDIS_URL` | Supplied from the Render Redis resource |
| `EVALFORGE_AUTH_TOKEN_PEPPER` | Unique generated secret; never reuse between environments |
| `EVALFORGE_BOOTSTRAP_TOKEN` | Unique generated secret used only for the first-owner ceremony, then rotated |
| `EVALFORGE_METRICS_TOKEN` | Unique generated secret used only by the metrics scraper |
| `EVALFORGE_CORS_ORIGINS` | Exact comma-separated HTTPS frontend origins; no `*` in production |
| `EVALFORGE_ALLOWED_HOSTS` | Render API hostname plus any final custom API hostname |
| `GROQ_API_KEY` | Set only if Groq-backed adapters will be tested or used |
| `OPENAI_API_KEY` | Set only if OpenAI-backed adapters will be tested or used |
| `EVALFORGE_OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP/HTTP endpoint for production traces |
| `EVALFORGE_OTEL_EXPORTER_OTLP_HEADERS` | Collector authentication headers, if required |
| `EVALFORGE_SENTRY_DSN` | Error-reporting DSN; PII collection remains disabled in code |

Keep the generated values in a real secret manager. Restrict who can read or rotate them. A
rotation of `EVALFORGE_AUTH_TOKEN_PEPPER` invalidates every existing session and personal API key,
so record a maintenance and user-notification procedure before production use.

### Safe first deployment order

1. Provision PostgreSQL and Redis.
2. Deploy the API. Its container runs `alembic upgrade head` before starting Uvicorn.
3. Confirm the API reaches `/readyz` successfully.
4. Start or resume the Celery worker only after the migration is at head.
5. Inspect API and worker logs for secrets, tracebacks, migration errors, or connection retries.

This order avoids a first-deployment race in which a worker receives traffic before the schema is
ready.

### Health and metrics verification

Set the API origin without a trailing slash:

```bash
export EVALFORGE_API_ORIGIN='https://evalforge-api.example.com'
curl -fsS "${EVALFORGE_API_ORIGIN}/livez"
curl -fsS "${EVALFORGE_API_ORIGIN}/healthz"
curl -fsS "${EVALFORGE_API_ORIGIN}/readyz"
```

Required results:

- all three requests use valid TLS;
- `/livez` returns HTTP 200;
- `/readyz` returns HTTP 200 only when PostgreSQL, Redis, and the Alembic revision are healthy;
- no database URL, token, stack trace, or internal hostname appears in the body.

Verify that metrics reject anonymous access, then test the scraper token without placing it in
shell history:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "${EVALFORGE_API_ORIGIN}/metrics"
read -rsp 'Metrics token: ' EVALFORGE_METRICS_TOKEN_INPUT; echo
curl -fsS \
  -H "Authorization: Bearer ${EVALFORGE_METRICS_TOKEN_INPUT}" \
  "${EVALFORGE_API_ORIGIN}/metrics" | head
unset EVALFORGE_METRICS_TOKEN_INPUT
```

The anonymous request must return `401`; the authenticated request must include
`evalforge_http_requests_total` and request-duration histogram metrics.

### Render acceptance evidence

- Service URLs, region, and plan names, without credentials.
- Successful API migration log line and current Alembic revision.
- `/readyz` response and timestamp.
- Worker startup and successful task-processing log lines.
- Confirmation that PostgreSQL is not publicly reachable except through an explicitly approved
  access path.

## Phase 4: bootstrap the first owner

Perform this once, from a trusted machine and network. Use a unique password from a password
manager. The password must be at least 12 characters; use substantially more than the minimum.

```bash
read -rsp 'Bootstrap token: ' EVALFORGE_BOOTSTRAP_INPUT; echo
read -rsp 'New owner password: ' EVALFORGE_OWNER_PASSWORD_INPUT; echo

curl -fsS -X POST "${EVALFORGE_API_ORIGIN}/api/auth/bootstrap" \
  -H 'Content-Type: application/json' \
  -H "X-EvalForge-Bootstrap-Token: ${EVALFORGE_BOOTSTRAP_INPUT}" \
  --data "$(jq -n \
    --arg email 'owner@example.com' \
    --arg password "${EVALFORGE_OWNER_PASSWORD_INPUT}" \
    --arg display_name 'Project Owner' \
    --arg organization_name 'EvalForge' \
    --arg organization_slug 'evalforge' \
    '{email: $email, password: $password, display_name: $display_name,
      organization_name: $organization_name, organization_slug: $organization_slug}')"

unset EVALFORGE_BOOTSTRAP_INPUT EVALFORGE_OWNER_PASSWORD_INPUT
```

Replace the example email and organization values before running the command. Treat the response
token as a secret. Do not save the response in an issue or terminal recording.

Immediately after success:

- [ ] Log in through `/api/auth/login` and verify `/api/auth/me` returns the correct owner and
      organization.
- [ ] Verify the original bootstrap call cannot create a second user.
- [ ] Rotate `EVALFORGE_BOOTSTRAP_TOKEN` to a new inaccessible random value. Keep a non-empty value
      because production configuration validates its presence at startup.
- [ ] Create a named personal API key for automation with the shortest practical expiry.
- [ ] Store that API key in the CI or load-test secret store and verify the plaintext appears only
      once at creation.
- [ ] Log out and confirm that the session token is revoked.

## Phase 5: deploy the production frontend

The existing Vercel URL is an explicit demo preview. Production must use the live Render API and
must not silently fall back to local demo data.

Set these Vercel Production environment variables in the project settings:

| Variable | Production value |
|---|---|
| `VITE_API_BASE_URL` | Exact HTTPS Render API origin, without a trailing slash |
| `VITE_DEMO_MODE` | `false` |

These are Vite build-time values. Redeploy after every change.

```bash
vercel deploy --prod --yes --cwd frontend
```

After Vercel provides the production origin:

1. Set `EVALFORGE_CORS_ORIGINS` on Render to that exact origin.
2. Add the custom frontend origin too if a custom domain will be used.
3. Redeploy/restart the API so the new CORS configuration is active.
4. Confirm both the Vercel hostname and custom hostname use valid TLS.

### Frontend acceptance tests

- [ ] A signed-out visit does not expose tenant data.
- [ ] Owner login succeeds and the dashboard loads persisted API data.
- [ ] Refreshing the page clears the browser credential and requires a new login. This is the
      intended memory-only security behavior.
- [ ] DevTools Application storage contains no EvalForge session token or API key.
- [ ] `VITE_DEMO_MODE=false` prevents local demo data from hiding an API failure.
- [ ] Running the dashboard evaluation creates baseline and candidate runs, the worker completes
      them, and the comparison view shows a gate verdict.
- [ ] Browser requests use HTTPS only and show no CORS, mixed-content, or CSP errors.
- [ ] Mobile and desktop layouts remain usable on the production build.

## Phase 6: live RBAC and tenant-isolation acceptance

Automated tests already cover these boundaries. Production acceptance must prove that deployment
configuration did not bypass them.

Create two disposable organizations and test users for each role. Use synthetic data only.

| Test | Expected result |
|---|---|
| Owner reads and writes within its organization | Allowed |
| Admin manages non-owner members | Allowed |
| Admin grants or removes the owner role | `403` |
| Evaluator creates runs/comparisons | Allowed |
| Evaluator manages members | `403` |
| Viewer reads dashboards and traces | Allowed |
| Viewer creates or mutates resources | `403` |
| Organization B requests an Organization A resource ID | `404`, not `403` |
| Disabled or removed member reuses an old credential | Authentication fails |
| Five incorrect passwords are entered | Account locks for 15 minutes |
| Password is changed | Other active login sessions are revoked |

Additional checks:

- [ ] The final owner cannot be removed or demoted.
- [ ] API keys show only their prefix after creation.
- [ ] Expired and revoked API keys fail authentication.
- [ ] CORS rejects an unapproved origin.
- [ ] Host validation rejects an unapproved `Host` header.
- [ ] Provider adapter configuration rejects inline secrets and unapproved hosts/modules.

Delete the disposable users, organizations, keys, and synthetic records when testing is complete.
Save a redacted result matrix as release evidence.

## Phase 7: observability, dashboards, and SLOs

Follow [operations.md](operations.md) for the metric names, SLOs, and suggested PromQL. Complete all
of the following:

- [ ] Connect the API to an OTLP collector and confirm traces include API spans and request IDs.
- [ ] Connect Sentry and trigger a controlled non-sensitive test exception in staging.
- [ ] Scrape `/metrics` using the dedicated metrics token.
- [ ] Build dashboards for request rate, 5xx ratio, p50/p95/p99 latency, in-flight requests, run
      creation, queue depth, worker task failures, stale leases, PostgreSQL pressure, Redis memory,
      and backup age.
- [ ] Add fast-burn and slow-burn availability/latency alerts from the documented SLOs.
- [ ] Alert on `/readyz` failure, growing Celery queue, repeated task retries, stale run-item leases,
      Redis eviction, database connection exhaustion, and backup age.
- [ ] Route a test alert to the real owner and record acknowledgement time.
- [ ] Confirm logs and error events do not contain prompts, outputs, passwords, tokens, or provider
      credentials unless a documented data policy explicitly permits the content.
- [ ] Run a 24–72 hour staging soak and review error rate, p95 latency, queue behavior, and memory.

Operational acceptance requires dashboards with real data, at least one successfully delivered test
alert, and links/screenshots that reveal no secrets or user data.

## Phase 8: staging and real-provider load testing

Never begin with production. Populate staging with synthetic records that approximate the expected
number of apps, runs, cases, results, and traces.

### Read-heavy API profile

```bash
cd backend
uv sync --group load
read -rsp 'Staging personal API key: ' EVALFORGE_LOAD_API_KEY; echo
export EVALFORGE_LOAD_API_KEY

uv run --group load locust \
  -f ../benchmarks/locustfile.py \
  --host https://staging-api.example.com \
  --headless \
  --csv ../benchmarks/results/staging-load

unset EVALFORGE_LOAD_API_KEY
```

The default profile ramps to 25 users, sustains 50, and spikes to 100. It fails automatically if
the aggregate error ratio exceeds 1% or p95 exceeds 750 ms.

Acceptance criteria:

- [ ] Failure ratio below 1%.
- [ ] Aggregate p95 below 750 ms.
- [ ] No database pool exhaustion or Redis eviction.
- [ ] No growing stale-lease count or unrecovered queue backlog.
- [ ] p95 returns to its pre-spike range within five minutes.
- [ ] No paging SLO fires unexpectedly.
- [ ] CSV, HTML/report output, service sizes, dataset size, commit SHA, and timestamps are retained.

### Budget-capped real-provider profile

The shipped Locust workload is intentionally read-only. Test evaluation throughput separately:

1. Set a hard provider budget and request/token quota before running anything.
2. Use a real provider adapter with secrets supplied only through approved environment variables.
3. Run a 20-case baseline/candidate pair as a correctness and cost smoke test.
4. Increase to 100 cases only if the smoke test has no unexpected retries, costs, or errors.
5. Run at worker concurrency 1, 2, and 4; do not increase concurrency beyond provider quotas.
6. Record queue delay, provider latency, end-to-end run latency, retry rate, token usage, cost per
   case, cost per comparison, and terminal failure rate.
7. Test provider 429, timeout, and transient 5xx behavior with a controlled fault or low quota.
8. Confirm failed or retried tasks do not create duplicate evaluator results.

Do not publish the deterministic Docker throughput figure as provider throughput. Publish the model,
provider, region, case count, worker size, concurrency, and measurement date with every result.

## Phase 9: independently labeled blinded calibration

This is the largest remaining credibility item. The current fixture is author-scored and synthetic;
it is useful for regression testing but cannot validate production evaluator quality.

Use [labeling_rubric.md](labeling_rubric.md) and the limitations in
[calibration_report.md](calibration_report.md).

### Study design

- [ ] Collect at least 200 real model outputs; target 300–500 if the domains and failure modes are
      diverse.
- [ ] Sample across difficulty, domain, input length, retrieval success/failure, model/provider,
      answerable/unanswerable questions, hallucination bait, and safety-sensitive cases.
- [ ] Remove secrets and personal data according to an explicit retention policy.
- [ ] Freeze a study manifest containing dataset hash, code commit, models, prompt versions,
      evaluator versions, thresholds, sampling rules, and exclusions.
- [ ] Pre-register primary metrics and pass/fail criteria before examining human labels.
- [ ] Split cases into tuning/validation and untouched test sets. Never tune on the test split.

Recommended pre-registered primary outputs:

- weighted Cohen kappa between human labelers;
- Pearson and Spearman association between evaluator scores and adjudicated human scores;
- false-positive and false-negative rates at the deployment threshold;
- precision, recall, F1, and confidence intervals for unacceptable answers;
- per-slice results for the major domains and failure types;
- coverage/abstention rate for evaluators that can decline to score.

### Blinded labeling protocol

1. Use at least two labelers who did not implement the evaluator being assessed.
2. Randomize case order and replace model/provider/evaluator identifiers with opaque IDs.
3. Hide automatic metric scores, gate verdicts, candidate/baseline identity, and other labelers'
   decisions.
4. Have both labelers score every case independently using the frozen 1–5 rubric.
5. Capture a reason code and optional short rationale, not just a numeric label.
6. Adjudicate disagreements without revealing automatic scores. Use a third adjudicator when
   possible.
7. Relabel a random subset at least 24 hours later to estimate intra-rater consistency.

If weighted kappa is below 0.6, stop, clarify the rubric, and relabel. A target of 0.7 or higher is
preferable before using the set for public evaluator claims.

### Analysis and anti-leakage rules

- Tune thresholds only on the tuning/validation split.
- Open the test split once, after thresholds and code are frozen.
- Report confidence intervals and sample counts; do not report only point estimates.
- Mark slices with too few cases as insufficient evidence rather than presenting unstable rates.
- Preserve negative findings and evaluator failure examples.
- Version the study; never silently replace labels or cases after publishing results.
- Publish anonymized inputs/outputs only when policy permits. Otherwise publish hashes, schema,
  sampling method, and aggregate results.

Reproduce the repository analysis format with:

```bash
uv run --directory backend python -m app.calibration.analyze
```

Store the final non-sensitive study manifest, methodology, aggregate results, confidence intervals,
limitations, and reviewer sign-off in a versioned `docs/calibration/` directory. Raw sensitive data
belongs in approved private storage, not Git.

### Calibration acceptance criteria

- [ ] Minimum case count and frozen split documented.
- [ ] Two independent blinded label sets plus adjudication completed.
- [ ] Weighted kappa at least 0.6, preferably at least 0.7.
- [ ] Threshold selected without test-set leakage.
- [ ] FPR/FNR and confidence intervals acceptable for the stated use case.
- [ ] No critical slice has an unexplained material performance collapse.
- [ ] A reviewer who did not build the metric signs off on the methodology and claims.

## Phase 10: backup, restore, and disaster recovery

Use a production database plan with automated backups, then independently exercise the repository
scripts from [disaster-recovery.md](disaster-recovery.md).

Create and verify a backup:

```bash
DATABASE_URL='<source-postgres-url>' \
EVALFORGE_BACKUP_DIR='./backups' \
./scripts/backup_postgres.sh
```

Restore into a new disposable database, never over production:

```bash
EVALFORGE_RESTORE_DATABASE_URL='<disposable-target-url>' \
EVALFORGE_CONFIRM_RESTORE=RESTORE \
./scripts/restore_postgres.sh ./backups/evalforge-YYYYMMDDTHHMMSSZ.dump
```

After restore:

- [ ] Verify the SHA-256 checksum and `pg_restore --list` result.
- [ ] Confirm `alembic current` is at the expected revision.
- [ ] Point a disposable API and Redis instance at the restored database.
- [ ] Verify `/readyz`, owner login, organizations, memberships, apps, suites, cases, runs, results,
      comparisons, gate rules, and trace counts.
- [ ] Run one deterministic evaluation and comparison.
- [ ] Record backup start/end, restore start/end, archive size, RPO, observed RTO, and operator.
- [ ] Delete the disposable environment and test credentials after evidence is captured.
- [ ] Schedule the next quarterly restore drill.

Acceptance requires a checksum-valid restore inside the four-hour RTO and within the configured RPO.
A backup that has never been restored is not sufficient evidence.

## Phase 11: custom domains, release, and rollout

### Domain and TLS

- [ ] Configure production frontend and API custom domains.
- [ ] Verify automated TLS issuance and renewal.
- [ ] Update `EVALFORGE_CORS_ORIGINS` and `EVALFORGE_ALLOWED_HOSTS` to the final hostnames.
- [ ] Verify HTTP redirects to HTTPS and that no asset or API request uses mixed content.
- [ ] Keep old platform hostnames only if they are intentionally supported and tested.

### Release preparation

- [ ] Complete [release-checklist.md](release-checklist.md).
- [ ] Update `CHANGELOG.md` with migration, authentication, deployment, known limitations, and
      upgrade/rollback notes.
- [ ] Replace screenshots only if the production UI materially differs from the committed images.
- [ ] Link load, calibration, backup/restore, and observability evidence from the release issue.
- [ ] Confirm CI and CodeQL pass on merged `main`.
- [ ] Confirm no unresolved high/critical dependency or code-scanning alert exists.

Create the first release only from reviewed `main`:

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m 'EvalForge AI v0.1.0'
git push origin v0.1.0
gh run watch --repo meher4567/evalforge-ai
gh release view v0.1.0 --repo meher4567/evalforge-ai
```

The release workflow reruns backend/frontend verification, generates `.tar.gz` and `.zip` source
archives, writes `SHA256SUMS`, and publishes the GitHub release.

### Rollout and rollback

1. Back up PostgreSQL and record the current application image/revision.
2. Deploy the API and wait for migrations/readiness.
3. Deploy/resume workers and verify task execution.
4. Deploy the frontend with demo mode disabled.
5. Run the authentication, tenant, evaluation, comparison, metrics, and UI smoke tests.
6. Watch error rate, p95, database pressure, Redis, queue depth, and stale leases for at least one
   hour of active use and the full agreed soak period.
7. If rollback is required, preserve post-migration data first. Roll back application and schema
   only with a reviewed data-migration plan.
8. Write a brief launch report with observed behavior, incidents, follow-ups, and claim changes.

## Final scorecard

Use this scorecard instead of a vague statement that the project is complete:

| Dimension | Weight | Passing evidence |
|---|---:|---|
| Evaluation correctness and statistical rigor | 25 | Independent blinded calibration, confidence intervals, honest limitations |
| Security and multi-tenancy | 20 | Live RBAC/isolation matrix, zero unresolved serious alerts, secret rotation evidence |
| Reliability and data integrity | 15 | Worker idempotency evidence, readiness, restore drill, no duplicate results |
| Testing and CI/CD | 15 | Protected reviewed merge, full tests, CodeQL, audits, immutable action pins |
| Observability and operations | 10 | Live metrics/traces/errors, dashboards, alert delivery, SLO soak |
| Performance and cost | 10 | Staging load plus real-provider latency/cost/retry evidence |
| Documentation and release quality | 5 | Runbooks, limitations, changelog, tagged reproducible release |

Interpretation:

- **90–92:** production-capable with credible evidence and explicitly bounded limitations;
- **93–95:** strong external calibration, restore history, provider capacity data, and stable live
  operations;
- **96+:** requires sustained real adoption, multiple production incidents/drills, independent
  security review, and repeated calibration across domains—not additional README polish.

## Master completion checklist

- [ ] Independent PR approval
- [ ] Protected merge to `main`
- [ ] Managed staging deployment
- [ ] Managed production deployment
- [ ] Non-sleeping production services and automated database backups
- [ ] First owner bootstrap and bootstrap-token rotation
- [ ] Production Vercel build with `VITE_DEMO_MODE=false`
- [ ] Live RBAC and cross-tenant checks
- [ ] Real provider evaluation and comparison
- [ ] Metrics, traces, errors, dashboards, and delivered test alert
- [ ] Staging load profile passed
- [ ] Budget-capped provider throughput/cost test passed
- [ ] Independent blinded calibration passed
- [ ] Checksum backup/restore drill passed inside RTO
- [ ] Custom domains and TLS verified
- [ ] `CHANGELOG.md` and evidence links updated
- [ ] `v0.1.0` tagged from reviewed `main`
- [ ] Release archives and `SHA256SUMS` verified
- [ ] Post-launch soak and launch report completed

When every P0 and P1 item has evidence, a 90+ claim is achievable and defensible. Until then,
describe EvalForge as a production-oriented, comprehensively tested evaluation platform with
remaining external validation and managed-production evidence work.
