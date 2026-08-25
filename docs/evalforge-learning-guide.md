# EvalForge learning guide for ChatGPT tutoring

This guide is for the project owner who wants to understand EvalForge deeply enough to explain,
debug, extend, and present it confidently. It assumes basic familiarity with programming, but it
does not assume prior knowledge of LLM evaluation, distributed workers, statistics, authentication,
or production operations.

The goal is not to memorize every library. The goal is to understand why the system exists, how a
request moves through it, what can fail, and why the important engineering choices were made.

## How to use this file

1. Upload this file to ChatGPT, or paste the master prompt below into a new chat.
2. Study one module at a time. Do not ask for the whole project in one answer.
3. Ask ChatGPT to use examples from EvalForge instead of unrelated toy examples.
4. Answer the quiz yourself before asking for the solution.
5. Open the linked repository files while learning. Reading real code is part of the lesson.
6. Keep a small notes file containing your own explanations, not copied definitions.

One module should take roughly 45–90 minutes. The full core track is about 12–18 focused hours.

## Master tutor prompt

Copy this prompt into ChatGPT together with this document:

```text
Act as my patient senior software-engineering tutor. I am the owner of EvalForge AI, but I am still
learning several concepts used in it. Teach me from the attached EvalForge learning guide one module
at a time.

For each module:
1. First ask me 2 or 3 short questions to check what I already know.
2. Start with a plain-English analogy, then give the technically correct explanation.
3. Explain why the concept exists, what problem it solves, and what would go wrong without it.
4. Tie every important idea to the EvalForge architecture and referenced files.
5. Walk through one concrete example or request/data flow step by step.
6. Define unfamiliar terms immediately. Do not hide behind jargon.
7. Use small code excerpts or pseudocode only when they make the idea clearer.
8. End with a short recap, common mistakes, 5 quiz questions, and one small practical exercise.
9. Wait for my answers before moving to the next module.

Do not overwhelm me with advanced theory that is not needed to understand this project. Correct me
directly when my explanation is wrong. When I can explain a topic back accurately, help me turn my
explanation into a concise interview or project-demo answer.

Start with Module 1 unless I request another module.
```

## EvalForge in plain English

EvalForge tests whether a new version of an LLM or RAG application is better or worse than an old
version.

A user supplies:

- a **baseline** application version;
- a **candidate** application version;
- a suite of test cases;
- evaluators that score each output;
- gate rules that decide how much regression is acceptable.

EvalForge runs the same cases against both versions, stores outputs and traces, calculates quality,
latency, and cost metrics, estimates uncertainty, and returns a `pass`, `warn`, or `fail` decision.
The dashboard lets a user inspect aggregate results and open individual failed traces.

The main flow is:

```text
Test cases
   -> baseline and candidate runs
   -> adapter calls the application/model
   -> evaluators score each result
   -> PostgreSQL stores results and traces
   -> comparison computes paired metrics and confidence intervals
   -> gate rules produce pass/warn/fail
   -> API and React dashboard present the evidence
```

In production, FastAPI accepts requests, PostgreSQL stores durable data, Redis carries Celery work,
workers execute cases, and the React frontend calls the API.

## Learning map

| Module | Topic | Why it matters |
|---|---|---|
| 1 | LLM evaluation foundations | Understand the actual product problem |
| 2 | RAG, adapters, traces, and evaluators | Understand what EvalForge executes and records |
| 3 | Metrics, statistics, gates, and calibration | Understand whether the conclusions are trustworthy |
| 4 | FastAPI, schemas, services, and API flow | Understand the backend request lifecycle |
| 5 | PostgreSQL, relationships, and migrations | Understand how data remains consistent and durable |
| 6 | Redis, Celery, leases, retries, and idempotency | Understand asynchronous execution and failure recovery |
| 7 | React, TypeScript, API state, and the dashboard | Understand how results reach the user |
| 8 | Authentication, RBAC, and tenant isolation | Understand who can access which data |
| 9 | Testing, CI, security scanning, and containers | Understand how changes are verified safely |
| 10 | Deployment, observability, SLOs, and recovery | Understand how the system operates in production |

## Module 1: LLM evaluation foundations

### Concepts to learn

- What an LLM evaluation is and why normal unit tests are insufficient for probabilistic output.
- The difference between a test case, evaluation suite, run, run item, evaluator result, and trace.
- Baseline versus candidate testing.
- Offline evaluation versus online production monitoring.
- Deterministic metrics versus model-based or human evaluation.
- Regression testing: detecting whether a change made something materially worse.
- Why good-looking averages can hide important failed cases.

### EvalForge files to inspect

- [Project overview](../README.md)
- [Architecture and end-to-end flow](architecture.md)
- [Evaluation metric definitions](eval-metrics.md)
- [API objects and endpoints](api.md)

### Questions ChatGPT should help you answer

1. Why should the baseline and candidate run the same cases?
2. Why is one impressive demo output not evidence of quality?
3. When is exact match useful, and when is it misleading?
4. What is the difference between evaluating an answer and evaluating retrieval?

### Practical exercise

Invent five test cases for a simple question-answering bot. For each case, write the input, expected
facts, one forbidden claim, and a tag such as `easy`, `unanswerable`, or `hallucination_risk`.

You understand this module when you can explain EvalForge in two minutes without mentioning library
names such as FastAPI, React, or Celery.

## Module 2: RAG, adapters, traces, and evaluators

### Concepts to learn

- RAG: retrieve relevant documents, then generate an answer using that context.
- Why retrieval quality and answer quality are different dimensions.
- The adapter pattern: a stable interface around different applications and model providers.
- Why provider secrets and hosts must be controlled.
- A trace as evidence of what happened during one case.
- Why each evaluator returns a separate result rather than one combined score.
- Evaluator failure versus application failure.

### EvalForge files to inspect

- [Adapter contract](../backend/app/adapters/base.py)
- [Deterministic demo adapter](../backend/app/adapters/demo_rag.py)
- [Provider-backed RAG adapter](../backend/app/adapters/llm_rag.py)
- [Evaluator engine](../backend/app/evaluators/engine.py)
- [Basic evaluators](../backend/app/evaluators/basic.py)
- [Faithfulness evaluator](../backend/app/evaluators/faithfulness.py)
- [Adapter security controls](../backend/app/adapters/security.py)

### Questions ChatGPT should help you answer

1. How can a retrieval result be correct while the final answer is unfaithful?
2. Why does the run executor depend on an adapter interface instead of provider-specific code?
3. What information should a useful trace contain?
4. Why should one failed evaluator not erase all other results for that case?

### Practical exercise

Trace one deterministic demo case by hand: question, retrieved document, answer, trace steps, and the
result each evaluator should produce.

You understand this module when you can describe how a new LLM application could plug into
EvalForge without changing the comparison or dashboard code.

## Module 3: metrics, statistics, gates, and calibration

This is the most conceptually important module. Learn the intuition before formulas.

### Concepts to learn

- Accuracy-like metrics: exact match, keyword coverage, token F1, retrieval hit rate.
- Risk metrics: forbidden claims and faithfulness.
- Operational metrics: latency and cost.
- Mean versus median versus percentile; especially why p95 latency matters.
- Paired comparisons: comparing baseline and candidate on the same case.
- Sampling uncertainty and confidence intervals.
- Bootstrap confidence intervals in plain English.
- Gate rules, tolerance, and `pass`/`warn`/`fail` decisions.
- False positives and false negatives.
- Calibration: whether automated scores agree with independent human judgment.
- Inter-rater agreement and weighted Cohen kappa.
- Why synthetic author-labeled data is not independent validation.

### EvalForge files to inspect

- [Statistics helpers](../backend/app/services/statistics.py)
- [Comparison and gate logic](../backend/app/services/comparison.py)
- [Metric documentation](eval-metrics.md)
- [Benchmark interpretation](benchmark-interpretation.md)
- [Current synthetic calibration report](calibration_report.md)
- [Human labeling rubric](labeling_rubric.md)

### Important intuition

If the candidate passes 88% of cases and the baseline passes 90%, the observed difference is
`-2 percentage points`. That number alone does not tell us whether the candidate truly regressed or
whether the difference could reasonably come from sample variation. A paired confidence interval
uses the per-case differences to express that uncertainty. Gate rules then apply a product decision
to the measured evidence.

Statistics do not choose product risk tolerance. They describe evidence; the gate policy decides
what evidence is acceptable.

### Practical exercise

Create a table of ten cases with baseline and candidate pass/fail values. Calculate the pass rates,
identify improved/regressed/unchanged cases, and explain why the pairing contains more information
than comparing two unrelated averages.

You understand this module when you can explain why a gate can fail even when the candidate average
looks similar, and why calibration needs blinded independent labelers.

## Module 4: FastAPI, schemas, services, and API flow

### Concepts to learn

- HTTP requests, methods, paths, headers, status codes, and JSON responses.
- FastAPI route handlers and dependency injection.
- Pydantic request validation and response schemas.
- Separation between API routes, domain services, and database models.
- Async I/O: waiting for the database without blocking the server thread.
- Why validation errors, authentication errors, conflicts, and missing resources use different
  status codes.
- Health, readiness, and liveness endpoints.

### EvalForge files to inspect

- [Application setup and middleware](../backend/app/main.py)
- [Run API](../backend/app/api/runs.py)
- [Comparison API](../backend/app/api/comparisons.py)
- [Execution schemas](../backend/app/schemas/execution.py)
- [Run dispatcher](../backend/app/services/run_dispatcher.py)
- [Health API](../backend/app/api/health.py)

### Request walkthrough to ask ChatGPT for

Ask ChatGPT to trace `POST /api/runs` from incoming JSON through validation, authentication,
tenant checks, database writes, dispatch, worker execution, and the final run status.

### Practical exercise

Choose one endpoint from [api.md](api.md). Write its expected request, successful response, and
three failure responses before reading its implementation.

You understand this module when you can identify which layer should change when adding a field,
business rule, or new endpoint.

## Module 5: PostgreSQL, relationships, and migrations

### Concepts to learn

- Tables, rows, primary keys, foreign keys, indexes, unique constraints, and transactions.
- One-to-many and many-to-many relationships in the EvalForge domain.
- SQLAlchemy models versus Pydantic API schemas.
- Why transactions keep related changes consistent.
- N+1 queries and why bulk loading matters.
- Schema migrations and why production databases cannot simply be recreated.
- PostgreSQL as the system of record; Redis as disposable coordination state.
- Tenant IDs as part of the data-access boundary.

### EvalForge files to inspect

- [Database entities](../backend/app/models/entities.py)
- [Database base helpers](../backend/app/db/base.py)
- [Database session](../backend/app/db/session.py)
- [Alembic migrations](../backend/migrations/versions/)
- [Dashboard aggregation](../backend/app/services/dashboard_aggregation.py)

### Practical exercise

Draw the relationships between organization, app, version, suite, case, run, run item, evaluator
result, trace, and comparison. Mark which records must carry or inherit organization ownership.

You understand this module when you can explain why deleting Redis must not delete evaluation
history, and why a migration needs a backup and rollback plan.

## Module 6: Redis, Celery, leases, retries, and idempotency

### Concepts to learn

- Why long evaluation work should not keep an HTTP request open.
- Queue, broker, producer, consumer, worker, task, acknowledgement, and retry.
- Redis as Celery's broker in this architecture.
- At-least-once delivery: a task can be delivered more than once.
- Idempotency: repeating work does not create an incorrect additional effect.
- Leases: temporary ownership that another worker can recover after expiry.
- Late acknowledgement, bounded retries, and terminal states.
- Race conditions and authoritative progress recounting.
- Why database uniqueness constraints are a final safety layer.

### EvalForge files to inspect

- [Celery application](../backend/app/workers/celery_app.py)
- [Worker tasks](../backend/app/workers/tasks.py)
- [Run executor](../backend/app/services/run_executor.py)
- [Worker lease tests](../backend/tests/test_worker_leases.py)
- [Worker tests](../backend/tests/test_worker.py)

### Failure scenario to study

A worker finishes a model call and writes results, but crashes before acknowledging the queue task.
Ask ChatGPT to explain what can happen next and how idempotency, leases, and uniqueness constraints
prevent duplicated results or a permanently stuck run.

You understand this module when you can explain why “the task ran once in my test” is not a safe
distributed-systems assumption.

## Module 7: React, TypeScript, API state, and the dashboard

### Concepts to learn

- React components, props, state, effects, and event handlers.
- TypeScript interfaces as compile-time contracts.
- Vite as development/build tooling.
- Loading, success, empty, authentication, and error states.
- Fetching JSON from an API and validating HTTP/content-type failures.
- Why explicit demo mode must not silently replace missing production data.
- Why credentials are memory-only and disappear on refresh.
- Unit/component tests versus real-browser E2E tests.

### EvalForge files to inspect

- [Main dashboard application](../frontend/src/App.tsx)
- [API client and dashboard flow](../frontend/src/api/client.ts)
- [Demo-only data](../frontend/src/data/demo.ts)
- [Component tests](../frontend/src/App.test.tsx)
- [Browser E2E test](../frontend/e2e/dashboard-run.spec.ts)
- [Vercel configuration](../frontend/vercel.json)

### Practical exercise

Follow the “Run evaluation” button from its click handler through API calls and back to the refreshed
dashboard. Write the sequence as numbered steps without copying code.

You understand this module when you can explain the difference between data rendered from the live
API and explicitly labeled local demo data.

## Module 8: authentication, RBAC, and tenant isolation

### Concepts to learn

- Authentication answers “who are you?”; authorization answers “what may you do?”
- Session tokens versus personal API keys.
- Password hashing versus token fingerprinting.
- Secret pepper, expiry, revocation, lockout, and credential rotation.
- RBAC roles: owner, admin, evaluator, and viewer.
- Multi-tenancy: one service stores data for multiple organizations.
- Tenant isolation and why cross-tenant IDs return `404` instead of revealing existence.
- CORS and trusted hosts; what they protect and what they do not protect.
- Why OIDC-ready schema is not the same as a completed OIDC login flow.

### EvalForge files to inspect

- [Authentication guide](authentication.md)
- [Authentication routes](../backend/app/api/auth.py)
- [Credential handling](../backend/app/services/authentication.py)
- [Request authentication](../backend/app/core/auth.py)
- [Tenant and role helpers](../backend/app/core/tenancy.py)
- [Organization/member routes](../backend/app/api/organizations.py)
- [Tenant authentication tests](../backend/tests/test_tenant_auth.py)

### Practical exercise

Create a permission table for every role. Then explain these results: viewer mutation returns `403`,
cross-tenant resource access returns `404`, invalid credentials return `401`, and duplicate
bootstrap returns `409`.

You understand this module when you can explain the complete path from a browser credential to an
organization-scoped database query.

## Module 9: testing, CI, security scanning, and containers

### Concepts to learn

- Unit, integration, contract, migration, component, E2E, load, and smoke tests.
- What code coverage measures and what it cannot prove.
- Linting, formatting, type checking, and dependency auditing.
- CI as repeatable verification on a clean machine.
- Required checks and protected branches.
- CodeQL static analysis and false-positive review.
- Docker image versus container; Docker Compose as a local multi-service environment.
- Why a passing unit suite is not enough to prove API, worker, database, Redis, and frontend work
  together.

### EvalForge files to inspect

- [Backend test suite](../backend/tests/)
- [Frontend tests](../frontend/src/api/client.test.ts)
- [Main CI workflow](../.github/workflows/ci.yml)
- [CodeQL workflow](../.github/workflows/codeql.yml)
- [Docker/Celery smoke workflow](../.github/workflows/docker-smoke.yml)
- [Docker Compose stack](../docker-compose.yml)
- [Backend container](../backend/Dockerfile)

### Practical exercise

Pick one feature and identify the smallest unit test, integration test, E2E test, and production
signal that together would give confidence in it.

You understand this module when you can explain why EvalForge runs both fast tests and a full
Docker/Celery smoke test in GitHub Actions.

## Module 10: deployment, observability, SLOs, and recovery

### Concepts to learn

- Build-time versus runtime configuration.
- Environment variables and secret management.
- TLS, domains, CORS origins, allowed hosts, and health checks.
- Logs, metrics, traces, and error reporting: four different types of evidence.
- p95 latency, availability, error budget, SLI, SLO, and alert.
- Readiness versus liveness.
- Backup, restore, RPO, and RTO.
- Rollout, rollback, migration risk, and disaster recovery.
- Why a backup is not trustworthy until it has been restored successfully.

### EvalForge files to inspect

- [Render Blueprint](../render.yaml)
- [Production completion plan](production-launch-and-90-plus-plan.md)
- [Operations and SLOs](operations.md)
- [Load testing](load-testing.md)
- [Disaster recovery](disaster-recovery.md)
- [Release checklist](release-checklist.md)
- [Backup script](../scripts/backup_postgres.sh)
- [Restore script](../scripts/restore_postgres.sh)

### Practical exercise

Pretend `/readyz` is failing while `/livez` works. List the evidence you would inspect, in order,
before changing code or restarting everything.

You understand this module when you can explain how to deploy EvalForge safely and how to prove it
is healthy after deployment.

## Two-week study schedule

Use 60–90 minutes per session. Add rest days if needed; understanding is more important than speed.

| Session | Focus | Output you should create |
|---|---|---|
| 1 | Project overview and Module 1 | Two-minute product explanation |
| 2 | Module 2 | One case traced from input to evaluator results |
| 3 | Module 3, metrics | Metric comparison table |
| 4 | Module 3, statistics | Plain-English paired CI and gate explanation |
| 5 | Module 4 | `POST /api/runs` request-flow diagram |
| 6 | Module 5 | Domain/entity relationship diagram |
| 7 | Module 6 | Worker crash and retry explanation |
| 8 | Module 7 | Frontend evaluation sequence |
| 9 | Module 8 | RBAC and tenant-isolation matrix |
| 10 | Module 9 | Test pyramid for one feature |
| 11 | Module 10 | Deployment and incident checklist |
| 12 | Full review | Ten-minute project presentation plus questions |

## Questions you should eventually answer confidently

Use these as a final mock interview or project-demo session with ChatGPT:

1. What problem does EvalForge solve, and who would use it?
2. Why compare baseline and candidate on identical cases?
3. What is the difference between an adapter, evaluator, run item, result, and trace?
4. Why are confidence intervals and paired statistics included?
5. What is a false positive in a regression gate?
6. Why is the current synthetic calibration fixture not production evidence?
7. How does the system recover if a Celery worker crashes midway through a task?
8. How do leases and idempotency differ?
9. Why is PostgreSQL the system of record while Redis is disposable?
10. How does organization isolation reach from authentication to database queries?
11. Why does cross-tenant access return `404`?
12. Why are browser credentials stored only in memory?
13. What does `/readyz` prove that `/livez` does not?
14. Why are unit tests, E2E tests, and Docker smoke tests all necessary?
15. What evidence is still required before making a strong production-quality claim?

## Topics not worth learning deeply yet

Know that these exist, but do not let them delay understanding the current system:

- Kubernetes, service meshes, and multi-region orchestration;
- distributed consensus algorithms such as Raft or Paxos;
- writing custom cryptographic primitives;
- training foundation models from scratch;
- advanced frontend state-management frameworks;
- vector-database internals beyond basic embedding search;
- formal statistical proofs beyond the intuition used by the project;
- event sourcing, CQRS, or microservice decomposition;
- complex OIDC federation before one provider flow is actually required.

Learn these only when a concrete product or scale requirement makes them necessary.

## Compact glossary

| Term | Meaning in EvalForge |
|---|---|
| Adapter | Standard wrapper used to run an application/model version |
| Baseline | Existing version used as the reference |
| Candidate | New version being evaluated for regression |
| Case | One structured evaluation input and expected evidence |
| Suite | Versioned collection of evaluation cases |
| Evaluator | Component that scores one aspect of an output |
| Trace | Detailed evidence from one case execution |
| Gate | Policy that converts comparison evidence into pass/warn/fail |
| Confidence interval | Range expressing uncertainty around an estimated metric difference |
| Calibration | Testing automated scores against independent human labels |
| API | HTTP interface used by the frontend, CLI, or automation |
| Transaction | Group of database changes that succeeds or fails together |
| Migration | Versioned change to the database schema |
| Queue | Buffer of work waiting for workers |
| Lease | Temporary right for one worker to process an item |
| Idempotency | Safety property that repeated execution does not duplicate the effect |
| Tenant | One isolated organization using the shared system |
| RBAC | Permissions assigned through roles |
| CORS | Browser rule controlling which frontend origins may call the API |
| Metric | Numeric measurement such as pass rate, latency, or cost |
| Trace span | Timed operation sent to an observability backend |
| SLO | Target reliability level measured over time |
| RPO | Maximum acceptable amount of data loss measured in time |
| RTO | Maximum acceptable recovery duration |

## Final learning outcome

You do not need to remember every class or endpoint. You are ready when you can:

- explain the product and end-to-end flow without notes;
- justify the main architecture decisions and their tradeoffs;
- follow one case through API, database, queue, worker, evaluator, comparison, and UI;
- distinguish measured evidence from an unsupported quality claim;
- identify the correct layer when a bug or feature request appears;
- explain the security and reliability boundaries honestly;
- demonstrate the project, answer follow-up questions, and say what remains to be proven.

After completing the guide, ask ChatGPT to conduct a mock 20-minute EvalForge technical review. It
should challenge your reasoning, not merely ask for definitions.
