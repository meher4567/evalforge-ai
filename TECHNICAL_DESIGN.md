# EvalForge AI — Technical Design

## Purpose of this doc

This is the engineering design document — the layer between `PROJECT_BLUEPRINT.md` (what the system *is*) and `BUILD_PLAN.md` (what we ship and when). This doc answers **how** the system works and **why** the design is shaped this way.

Read this before writing code. When implementation hits an ambiguous case, this doc is the tiebreaker. When this doc has an open question, resolve it before building the affected component.

---

## 1. Design goals (in priority order)

1. **Defensible numbers.** Every reported metric must come with measurable methodology. Pass-rate deltas are accompanied by bootstrap CIs. Calibration findings come with held-out validation.
2. **Reproducible runs.** Same case + same version + same evaluator should yield the same result (within documented nondeterminism). A reviewer cloning the repo and running `make demo` should see the exact numbers in the README.
3. **Pluggable evaluators.** Adding a new evaluator should require touching one file. Adding a new app type should require implementing one adapter contract. The platform must not bake assumptions about LLM/RAG specifics into the runner.
4. **Honest failure surfaces.** When something breaks (worker crash, evaluator timeout, malformed case), the failure must be visible at the right altitude — case-level errors don't tank the run, run-level errors don't tank the system.
5. **Free-tier feasible.** No paid-API dependency in the default path. Local embeddings, Ollama-optional, cost simulator instead of real billing.

Goals 1 and 2 are the hardest. They drive most of the design decisions below.

## 2. Non-goals (explicit)

These are deliberately out of scope. Resist scope creep into them.

- **Multi-tenancy / auth.** Single user, local-first. No login, no API keys, no RBAC.
- **Real-time eval.** Runs are async, batch-oriented. No streaming evals, no per-token eval.
- **Production deployment story.** No Kubernetes manifests, no Terraform, no cloud cost model. Docker Compose is the deployment.
- **Eval case authoring UX.** Cases come from JSONL imports. No in-UI case editor.
- **Cross-run analytics.** Comparison is between two runs. No "show me how this version trended over the last 10 runs."
- **Eval-of-eval (meta-eval).** Beyond the single calibration study, the platform does not evaluate its own evaluators in production.
- **General-purpose LLM gateway.** This is not a wrapper around model APIs. Versions adapt to model APIs; the platform doesn't abstract them.

## 3. System architecture

### Process topology

Five long-running processes plus on-demand workers:

1. **`api`** — FastAPI uvicorn, serves REST + serves the React build in production. One process.
2. **`worker_eval`** — Celery prefork worker pool for evaluation tasks. Concurrency = CPU count by default.
3. **`worker_compute`** — Celery worker dedicated to embedding/NLI inference. Single process, isolated from `worker_eval` so a stuck NLI inference doesn't block all eval cases.
4. **`db`** — PostgreSQL 16 with pgvector. Single instance, persistent volume.
5. **`broker`** — Redis 7. Single instance. Doubles as Celery broker and result backend.

Two worker pools is deliberate. The eval task itself is mostly I/O (DB writes, adapter calls). Embeddings and NLI are CPU-bound and benefit from being in a separate process where you can cap concurrency to 1 or 2 to avoid OOM.

### Why not asyncio everywhere

Tempting on paper. In practice:
- `sentence-transformers` is sync and CPU-heavy. Async wraps don't help.
- Celery has years of operational maturity for retry/visibility/dead-letter.
- The dashboard's API endpoints are I/O-bound enough that FastAPI's async handlers + SQLAlchemy async session is sufficient on the API side.

So: async API surface, sync worker pool, Celery as the bridge. This is conventional and correct.

### Boundaries

- **API → DB:** SQLAlchemy 2.x with async sessions. Use the ORM for CRUD, drop to Core for the comparison aggregations (they're heavy reads with computed columns).
- **API → Broker:** producer-only. API never consumes tasks.
- **Worker → DB:** sync SQLAlchemy session per task. Open at task start, commit + close at end. No long-lived sessions.
- **Worker → Adapter:** in-process call into the adapter module. Adapters do not run in subprocesses — too much overhead. Worker timeout is the safety net.

## 4. Conceptual domain model

The domain has six core entities. Misunderstanding their relationships is the most common source of architecture confusion.

```
App                      (logical product being evaluated, e.g. "customer-support-rag")
 ├── AppVersion          (a specific config snapshot — prompt + model + retriever)
 └── EvalSuite           (a named collection of cases)
      └── EvalCase       (an input + expected outputs + tags)

EvalRun                  (one execution of one EvalSuite against one AppVersion)
 └── EvalRunItem         (per-case execution within a run)
      ├── Trace          (the structured execution record)
      └── EvalResult[]   (one per evaluator)

Comparison               (relates two EvalRuns: baseline + candidate)
 └── RegressionReport    (computed metrics + CIs + gate verdict)
```

### Key invariants

- **An EvalRun is bound to exactly one AppVersion.** Comparing models means running each as its own run.
- **An EvalCase is immutable after first run.** Edits create a new case id. This is the only way to keep historical run results meaningful.
- **An EvalResult belongs to (EvalRunItem, Evaluator).** Re-running the same case + version + evaluator produces a new EvalResult row, not an update. Old results stay queryable; "latest" is determined by `created_at`.
- **A Comparison is between two runs of the same app on the same suite.** Cross-suite comparisons are out of scope.

### Why case immutability matters

If cases mutate, every comparison becomes ambiguous. "v1 had a 92% pass rate" — on which case set? The version at run time? The current case state? Immutable cases mean the run is fully reproducible from `(case_id_list, version_id)`.

The cost: editing a case requires creating a new case row and updating the suite-membership table. Worth it.

## 5. Data schema (full, with rationale)

### Core tables

**`apps`**
- `id` (uuid, pk)
- `name` (text, unique)
- `description` (text)
- `created_at` (timestamptz)

Trivial. The `name` unique constraint matters for the UI's "create-or-find" workflow.

**`app_versions`**
- `id` (uuid, pk)
- `app_id` (uuid, fk → apps)
- `name` (text)   — e.g. `v1_baseline_bge_top3`
- `config` (jsonb)   — full version config: prompt, model, retriever params, temperature, etc.
- `adapter_module` (text)   — Python import path of the adapter for this version
- `created_at` (timestamptz)
- unique on `(app_id, name)`

Why `config` as JSONB: versions vary radically by app type. A RAG version has different fields from a SQL agent version. JSONB beats a sparse columnar schema.

Why `adapter_module` as a string: lets you ship different adapters in the same codebase and bind a version to one. Adapters are imported dynamically by name at run time.

**`eval_suites`**
- `id` (uuid, pk)
- `app_id` (uuid, fk → apps)
- `name` (text)
- `created_at` (timestamptz)
- unique on `(app_id, name)`

**`eval_cases`**
- `id` (uuid, pk)
- `suite_id` (uuid, fk → eval_suites)
- `external_id` (text, nullable)   — from the import file, for traceability
- `payload` (jsonb)   — input, expected_output, expected_facts, forbidden_claims, reference_context, tags, difficulty
- `created_at` (timestamptz)

Cases are immutable. `payload` is JSONB for the same reason as `app_versions.config`.

**`eval_runs`**
- `id` (uuid, pk)
- `app_version_id` (uuid, fk)
- `suite_id` (uuid, fk)
- `evaluator_config_id` (uuid, fk → evaluator_configs)
- `status` (enum: `pending | running | completed | partial | failed`)
- `started_at` (timestamptz)
- `completed_at` (timestamptz, nullable)
- `case_count` (int)
- `case_completed` (int)
- `case_errored` (int)

Why explicit counters and not a computed query: the dashboard polls run progress, and `SELECT COUNT(*) WHERE status=...` over thousands of run items is expensive. Counters are updated atomically by the worker as items complete.

`partial` status: the run finished but some cases errored. Distinct from `failed` (the run itself crashed).

**`eval_run_items`**
- `id` (uuid, pk)
- `run_id` (uuid, fk)
- `case_id` (uuid, fk)
- `status` (enum: `queued | running | completed | errored | timed_out`)
- `attempt_count` (int, default 1)
- `recorded_latency_ms` (int, nullable)
- `recorded_cost_usd` (numeric(10,6), nullable)
- `error_message` (text, nullable)
- `started_at` (timestamptz, nullable)
- `completed_at` (timestamptz, nullable)
- unique on `(run_id, case_id)`

The unique constraint enforces one-shot execution per (run, case). Re-runs go into a new run.

**`traces`**
- `id` (uuid, pk)
- `run_item_id` (uuid, fk, unique)
- `payload` (jsonb)   — full trace: input, prompt_used, retrieved_chunks, model_used, output, model_metadata
- `created_at` (timestamptz)
- index on `run_item_id` only

Separated from `eval_run_items` because the trace can be ~5-50KB; keeping it in a side table means listing run items is fast.

**`eval_results`**
- `id` (uuid, pk)
- `run_item_id` (uuid, fk)
- `evaluator_name` (text)
- `score` (numeric(10,6))   — primary numeric score
- `passed` (boolean)   — derived from score + threshold
- `details` (jsonb)   — per-evaluator richer output (e.g., per-fact hit breakdown)
- `created_at` (timestamptz)
- index on `(run_item_id, evaluator_name)`

One row per (run_item, evaluator). Re-running an evaluator post-hoc creates a new row.

**`evaluator_configs`**
- `id` (uuid, pk)
- `name` (text)
- `config` (jsonb)   — list of evaluators with their thresholds
- `created_at` (timestamptz)

A named bundle of evaluators applied to a run. Lets you A/B different evaluator suites against the same cases.

### Comparison tables

**`comparisons`**
- `id` (uuid, pk)
- `baseline_run_id` (uuid, fk)
- `candidate_run_id` (uuid, fk)
- `gate_rules_id` (uuid, fk → gate_rules)
- `status` (enum: `pending | computed | failed`)
- `created_at` (timestamptz)
- check: `baseline_run_id != candidate_run_id`

**`regression_reports`**
- `id` (uuid, pk)
- `comparison_id` (uuid, fk, unique)
- `metrics` (jsonb)   — full struct of metric_name → {baseline_point, baseline_ci_lower, baseline_ci_upper, candidate_point, candidate_ci_lower, candidate_ci_upper, delta_point, delta_ci_lower, delta_ci_upper, significance}
- `gate_verdict` (enum: `pass | warn | fail`)
- `gate_reasons` (jsonb)   — array of {metric, verdict, threshold_violated}
- `created_at` (timestamptz)

Metrics in JSONB so adding a new metric doesn't require a migration.

**`gate_rules`**
- `id` (uuid, pk)
- `name` (text)
- `rules` (jsonb)   — array of {metric, direction (higher_better/lower_better), tolerance, severity}
- `created_at` (timestamptz)

### Calibration tables

**`gold_labels`**
- `id` (uuid, pk)
- `case_id` (uuid, fk)
- `version_id` (uuid, fk)
- `label_score` (int)   — 1-5 hand label
- `labeler_id` (text)
- `rubric_version` (text)
- `labeled_at` (timestamptz)
- `notes` (text, nullable)

The "gold set" lives in the same DB. Labels are tied to (case, version) because the same case has different outputs from different versions.

**`embedding_cache`**
- `text_hash` (text, pk part 1)
- `model_id` (text, pk part 2)
- `embedding` (vector)
- `created_at` (timestamptz)

pgvector column. Used by semantic-sim, forbidden-claim semantic fallback, and any future evaluator that needs embeddings.

### Indexes (the non-obvious ones)

- `eval_run_items(run_id, status)` — for progress queries
- `eval_results(run_item_id, evaluator_name)` — for the comparison aggregation
- `traces(run_item_id)` — fast trace lookup
- `embedding_cache(text_hash, model_id)` — pk-driven, no extra index needed

Do not index `eval_results.passed` or `eval_results.score` — low cardinality + always queried with run filter means the run_item_id index is enough.

## 6. API contract (full)

All endpoints return JSON. Errors follow RFC 7807 problem details.

### App endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/apps` | `{name, description}` | `App` |
| GET | `/api/apps` | — | `App[]` |
| GET | `/api/apps/{app_id}` | — | `App` |

### Version endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/apps/{app_id}/versions` | `{name, config, adapter_module}` | `AppVersion` |
| GET | `/api/apps/{app_id}/versions` | — | `AppVersion[]` |

### Suite + case endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/apps/{app_id}/suites` | `{name}` | `EvalSuite` |
| POST | `/api/suites/{suite_id}/cases/import` | JSONL (multipart) | `{imported, errors[]}` |
| GET | `/api/suites/{suite_id}/cases` | query: limit, offset, tag | `EvalCase[]` |
| GET | `/api/suites/{suite_id}/summary` | — | `{case_count, tag_distribution}` |

### Run endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/runs` | `{app_version_id, suite_id, evaluator_config_id, case_ids?}` | `EvalRun` |
| GET | `/api/runs` | query: app_id, status, limit | `EvalRun[]` |
| GET | `/api/runs/{run_id}` | — | `EvalRun & progress` |
| GET | `/api/runs/{run_id}/items` | query: status, evaluator, tag | `EvalRunItem[]` |
| GET | `/api/runs/{run_id}/traces/{case_id}` | — | `Trace` |
| POST | `/api/runs/{run_id}/cancel` | — | `EvalRun` |

`case_ids` optional: if omitted, run the full suite. If provided, run only that subset. Used by re-run-flaky and re-run-failed flows.

### Comparison endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/comparisons` | `{baseline_run_id, candidate_run_id, gate_rules_id}` | `Comparison` |
| GET | `/api/comparisons/{comparison_id}` | — | `Comparison & RegressionReport` |
| GET | `/api/comparisons/{comparison_id}/failures` | query: evaluator, tag | `{case_id, baseline_pass, candidate_pass, baseline_score, candidate_score}[]` |
| GET | `/api/comparisons/{comparison_id}/gate-decision` | — | `{verdict, reasons[]}` |

### Calibration endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/calibration/labels` | `{case_id, version_id, label_score, notes}` | `GoldLabel` |
| GET | `/api/calibration/dataset` | — | full gold set with joined scores |
| GET | `/api/calibration/analysis` | — | `{per_evaluator: {pearson, spearman, confusion_matrix}}` |

### Conventions
- Timestamps: ISO 8601 with timezone
- Pagination: `limit` + `offset` everywhere
- Bulk endpoints have an explicit batch limit (50 for imports, 500 for cases)
- `204 No Content` for cancels and deletes
- `409 Conflict` for state-violations (e.g., comparing a still-running run)

## 7. Async execution model

### Task topology

```
on POST /runs:
    1. API creates eval_run row (status=pending)
    2. API enqueues N tasks: run_eval_case(run_id, case_id) for each case
    3. API updates run.status = running, returns 202

per task:
    1. Worker pulls task from queue
    2. Worker sets run_item.status = running
    3. Worker loads case + version config
    4. Worker calls adapter.run(case.payload.input, version.config)
       — bounded by adapter_timeout (default 30s)
    5. Worker stores trace
    6. Worker invokes each evaluator in evaluator_config
       — each evaluator has its own timeout (default 10s, faithfulness 60s)
    7. Worker stores eval_results
    8. Worker sets run_item.status = completed, increments run.case_completed
    9. If run.case_completed + run.case_errored == run.case_count:
        — worker sets run.status = completed (or partial if any errors)
```

### Retry semantics

- Adapter errors (timeout, exception): retry up to 2 times with exponential backoff (1s, 4s). Then mark run_item as `errored`.
- Evaluator errors: do not retry the whole task. Mark that evaluator's result as `errored=true` with the exception in `details`. Other evaluators on the same case still run.
- DB errors during result storage: Celery retries the task (idempotent because of the unique constraint on `(run_id, case_id)`).

### Idempotency

The unique constraint on `eval_run_items(run_id, case_id)` is what makes retries safe. If a task crashes mid-write, Celery retries; on retry, the worker first checks if the run_item is already `completed` — if so, no-op.

For evaluators specifically: re-running an evaluator on the same run_item is allowed (creates a new `eval_results` row). The "latest" row is the one used. This lets you add an evaluator after the run and back-fill.

### Concurrency tuning

- `worker_eval` concurrency: `min(cpu_count, 4)`. Eval tasks are I/O-light but adapter calls can be CPU-heavy (RAG retrieval, sentence embeddings inline in adapter).
- `worker_compute` concurrency: 1 or 2. NLI inference can OOM if you parallelize without care; keep it serial unless GPU is available.

### Why this matters for the resume bullet

Resume claims "throughput of N cases/min on M workers." That number must be measurable. Benchmark `throughput.py` varies M and reports the curve. The flat region of the curve tells you where you're DB-bound vs adapter-bound.

## 8. Evaluator architecture

### The contract

Every evaluator implements:

```python
class Evaluator(Protocol):
    name: str
    requires_fields: list[str]  # case payload fields it needs
    typical_latency_ms: int

    def score(self, case: EvalCase, output: AdapterOutput, config: dict) -> EvalResult:
        ...
```

`EvalResult` has: `score (float in [0,1])`, `passed (bool)`, `details (dict)`, `errored (bool)`, `error_message (str | None)`.

Evaluators are registered in a module-level dict. Adding one is: write the class, add to the registry. No other code changes.

### Composition vs orchestration

Evaluators are pure functions of (case, output). They do not call each other. The runner invokes them in sequence. This means:
- Reordering evaluators doesn't change results
- Adding an evaluator post-hoc is a back-fill, not a re-run
- A slow evaluator (faithfulness NLI) doesn't block fast ones — they run in deterministic order so caching is straightforward

### Per-evaluator deep-dive

#### Exact match
- Score: 1.0 if `output.answer == case.payload.expected_output`, else 0.0
- Passed: score == 1.0
- Use: only on cases tagged with exact-answer requirements

#### Contains-keywords (expected facts)
- Score: fraction of `case.payload.expected_facts` whose canonical form appears as substring (case-insensitive, whitespace-normalized) in `output.answer`
- Details: `{facts_hit: [...], facts_missed: [...]}`
- Passed: configurable threshold, default 0.8

#### Semantic similarity
- Score: cosine similarity between embedding(output.answer) and embedding(case.payload.expected_output)
- Embedding model: `all-MiniLM-L6-v2` (384-dim, fast, decent quality)
- Cached in `embedding_cache` keyed by `(sha256(text), model_id)`
- Cache hit rate target: >90% on second run of the same suite (only candidate outputs are new)
- Passed: score > 0.7 default

#### Retrieval hit rate
- Score: 1.0 if any retrieved chunk's `doc_id` matches `case.payload.expected_chunk_id` (or `expected_doc_id`), else 0.0
- Only applicable if case has expected retrieval target
- Details: `{retrieved_ids: [...], expected_id, matched: bool}`

#### Retrieval faithfulness (the hard one)
- For each sentence in `output.answer`:
  - Get NLI judgment (entail/contradict/neutral) against the concatenated retrieved context
  - Score sentence as 1.0 if entail, 0.5 if neutral, 0.0 if contradict
- Output score: average across sentences
- Model: `cross-encoder/nli-deberta-v3-base` (~440MB, ~500ms per inference on CPU)
- Latency mitigation:
  - Batch sentences per call
  - Cap at 5 sentences per answer (truncate longer answers, document this)
  - Subsample: only run faithfulness on every 5th case unless `--full-faithfulness` flag is set
- Details: per-sentence verdicts

This is the slowest evaluator and most likely to drive worker design decisions.

#### Forbidden claim
- Stage 1 (regex): if any string in `case.payload.forbidden_claims` matches as regex in `output.answer`, score = 0.0
- Stage 2 (semantic, only if stage 1 misses): cosine similarity between embedding(answer sentences) and embedding(forbidden_claims). If max sim > 0.85, score = 0.0
- Otherwise score = 1.0
- Details: which stage triggered, which claim

Two-stage design: cheap first pass catches the obvious cases, expensive second pass catches paraphrases. Most cases stop at stage 1.

#### Latency threshold
- Score: 1.0 if `output.latency_ms <= config.threshold_ms`, else `max(0, 1 - (latency - threshold) / threshold)`
- Continuous scoring (not pass/fail) so the comparison can show "candidate is slower but still under budget."

#### Cost threshold
- Same shape as latency, using `output.estimated_cost_usd`

#### LLM-judge (calibration only)
- Prompt template committed to `evaluators/llm_judge_prompt.md`
- Calls Ollama by default (no paid API needed), or OpenAI/Anthropic if configured
- Output is parsed to score 1-5, normalized to [0, 1] via `(score - 1) / 4`
- Not in any default evaluator_config — only enabled when running the calibration suite

### Failure mode handling

If an evaluator errors:
1. Its `eval_results` row gets `errored=true`, score=null, details contains exception
2. The case overall is **not marked failed** — other evaluators still count
3. The dashboard shows errored evaluators with a warning icon
4. Pass-rate computation excludes errored evaluators from the denominator (don't blame the eval for the evaluator crashing)

This is the same pattern as flaky-test handling in real CI: the test counts as "inconclusive," not "fail."

## 9. Statistical methodology

### Why bootstrap CIs (in depth)

Three reasons, in order of importance:

1. **Distribution-free.** Pass rate is bounded [0, 1] and often skewed. Normal-approximation CIs (Wilson, Wald) are well-defined for proportions, but for derived metrics like "average semantic similarity weighted by tag" the distribution is opaque. Bootstrap works for any statistic computable from the sample.
2. **BCa correction.** Bias-corrected and accelerated bootstrap handles skewness and bias in the sampling distribution. For pass rate near the boundaries (95%+ or <5%), BCa intervals are noticeably tighter and more accurate than percentile bootstrap.
3. **Communicable.** "Resample 1000 times and look at the spread" is interview-friendly. "Inverse-of-the-MLE Fisher-information adjusted" is not.

### Bootstrap protocol

For each metric on each run:
1. Sample with replacement N times from the run's `eval_run_items`, where N = original size, repeated B = 1000 times
2. Recompute the metric on each resample
3. Compute the BCa-adjusted 2.5% and 97.5% percentiles

Use `scipy.stats.bootstrap(data, statistic, n_resamples=1000, method='BCa')`.

For pair-wise comparison (baseline vs candidate), compute the bootstrap CI on the delta directly: resample each run separately, compute candidate_metric - baseline_metric per resample, take the 2.5/97.5 percentiles of the deltas. This is the right way to get a CI on a difference.

### Multiple-comparison issue

We compute CIs on ~6 metrics simultaneously. Strictly, the family-wise error rate is inflated. Two options:
- **Apply Holm-Bonferroni** correction: tighten the alpha per metric so the family-wise alpha stays at 5%
- **Report per-metric and disclose** the family count

Decision: report per-metric, disclose that 6 metrics are tested, do not apply correction by default. Rationale: the gate verdict aggregates across metrics with explicit rules, not via combined p-values. The interviewer will ask about this — be ready to defend.

### Gate logic (precise)

```
For metric M with direction D (higher_better or lower_better), tolerance T:
    
    delta_point = candidate.point - baseline.point   if D == higher_better
                  baseline.point - candidate.point   if D == lower_better
    
    delta_ci_lower, delta_ci_upper = bootstrap_ci_on_delta(baseline, candidate)
    
    if delta_ci_upper < -T:
        verdict = FAIL  (significantly worse beyond tolerance)
    elif delta_ci_lower < -T:
        verdict = WARN  (point estimate is worse beyond tolerance, but CI overlaps zero)
    elif delta_point > 0:
        verdict = PASS  (better, regardless of significance)
    else:
        verdict = PASS  (worse but within tolerance)
```

Run-level verdict: worst per-metric verdict. FAIL > WARN > PASS.

### Sample-size considerations

500 cases is enough for pass-rate CIs of ±~3pp when true rate is around 80%. Below that, CIs get wider; the dashboard should show CI widths so the user knows when to trust the delta.

For per-tag analysis: with 6 tags × 500 cases, each tag has ~80 cases. CI on a per-tag pass rate is wider — ±~9pp. Useful for spotting trends, not for triggering gates.

## 10. Calibration study methodology

### Why N=50 and not N=500

Each case takes ~10 minutes to label well. N=500 = 80+ hours of pure labeling work. N=50 = ~8 hours.

Statistical power at N=50:
- Pearson correlation detectable: r ≥ 0.39 at α=0.05, power=0.8
- This is enough to distinguish "evaluator is correlated with truth" from "evaluator is noise"
- Not enough to distinguish r=0.7 from r=0.8

For the purpose of the project (showing methodology + finding directional results), N=50 is right. The doc must explicitly state this limit and discuss what N=500 would buy.

### Stratification

10 cases per tag (6 tags) = 60 cases nominally. Trim to 50 by dropping some `easy` cases (over-represented). The stratification ensures every case type is represented; uniform random sampling on 500 cases would underweight `adversarial` since it's only 20% of the suite.

### Hand-labeling rubric

`docs/labeling_rubric.md` must specify:
- The 5-point scale anchors:
  - 5: fully correct, well-grounded, no extra claims
  - 4: correct but slight verbosity or minor unsupported addition
  - 3: partially correct (1+ facts right, 1+ facts wrong or missing)
  - 2: mostly wrong but on-topic
  - 1: irrelevant, refused, or off-topic
- How to handle borderline cases (always round down)
- How to handle "answer not in corpus" cases (5 if model correctly says it doesn't know; 1 if it hallucinates)
- A list of 5 worked examples spanning the scale

### Self-agreement check

Label 10 cases twice with at least 24 hours between. Compute weighted Cohen's κ.

- κ ≥ 0.8: excellent agreement, labels are reliable
- 0.6 ≤ κ < 0.8: acceptable, report it
- κ < 0.6: labels are too noisy; refine the rubric and re-label

Report whatever you measure. A measured κ=0.65 is more honest than a claimed κ=0.9.

### Inter-evaluator analysis

For each evaluator E, against gold labels G:

- **Pearson r**(E_scores, G_scores) — captures monotonic + linear relationship
- **Spearman ρ**(E_scores, G_scores) — captures monotonic only; more robust
- **Confusion matrix**: bin E into {fail (<0.5), borderline (0.5-0.7), pass (>0.7)} and G into {fail (1-2), borderline (3), pass (4-5)}; cross-tabulate

Per-tag breakdown of the same.

### Disagreement analysis

For each pair of evaluators (E1, E2), find cases where |E1 - E2| is largest (top 10). Inspect manually. Look for:
- Systematic bias by case type
- Specific failure modes (e.g., judge favors verbose answers)
- Correlation with output length, latency, model used

The named finding usually emerges from this step.

### Held-out validation of weighting

If the calibration study suggests an evaluator-weighting scheme ("trust semantic-sim 0.7, judge 0.3 for retrieval cases"), validate it:
- Split the 50 cases into 30 fit + 20 held-out
- Fit weights on the 30
- Report agreement on the held-out 20

This is the part that prevents the finding from being circular. The held-out number is the headline.

## 11. Trace storage strategy

### Schema decision: JSONB column, not normalized

Pros of JSONB:
- Schema-flexible — RAG traces have different shape from SQL-agent traces
- One write per trace, one read per trace
- pg's JSONB indexing is good enough for our query patterns

Cons:
- Can't aggregate across traces in SQL without unnesting
- Storage is less compact than dedicated columns

Decision: JSONB. The cons don't hurt us — aggregation happens at the `eval_results` level (which is normalized), traces are read individually.

### Size budget

Estimated trace size: 5-50KB depending on retrieved-context length.
- 500 cases × 4 versions × 20KB avg = ~40MB per full demo run
- Postgres handles this trivially
- Total project DB after 10 demo runs: well under 1GB

### Query patterns

- "Show trace for run_item X" — by `run_item_id` index, O(1)
- "Show all errored traces in run Y" — join on run_items.status='errored', filter
- "Show traces where model_used = 'llama3.2:3b'" — need a GIN index on `payload->>'model_used'` if this becomes common

Add the GIN index only if the dashboard adds a "filter traces by model" feature. Don't pre-optimize.

### Trace payload shape (recommended)

```
{
  "input": { "question": "..." },
  "version_config": { "model": "...", "prompt": "...", "top_k": 3 },
  "steps": [
    { "step": "retrieve", "duration_ms": 45, "result": { "chunks": [...] } },
    { "step": "format_prompt", "duration_ms": 1, "result": { "prompt": "..." } },
    { "step": "generate", "duration_ms": 1200, "result": { "answer": "...", "model": "...", "usage": {...} } }
  ],
  "output": { "answer": "...", "retrieved_chunks": [...] },
  "metadata": { "started_at": "...", "completed_at": "...", "total_latency_ms": 1246 }
}
```

The `steps` array is what makes the trace viewer useful — debugging means tracing through the steps.

## 12. Cost simulation methodology

### Why simulated cost

Real cost requires hitting paid APIs in every eval. That's expensive (running 500 cases × 4 versions on GPT-4 = $$$) and unreliable (rate limits, API outages). Simulated cost is reproducible and shows the same product behavior.

### Algorithm

For each adapter call:
1. Count input tokens using `tiktoken` (cl100k for OpenAI-family) or the HF tokenizer for the model in use
2. Count output tokens the same way
3. Look up `{input_per_1k, output_per_1k}` for the model in `config/model_costs.yaml`
4. Compute `cost = (in_tokens * in_rate + out_tokens * out_rate) / 1000`

Stored in `eval_run_items.recorded_cost_usd`.

### Model cost config

`config/model_costs.yaml` committed with current rates as of build time. Each entry has a `as_of` date.

```yaml
models:
  gpt-4o:
    input_per_1k: 0.005
    output_per_1k: 0.015
    as_of: "2026-05-01"
  llama-3.2-3b-ollama:
    input_per_1k: 0.0   # local
    output_per_1k: 0.0
    note: "Local Ollama, zero marginal cost; energy not modeled"
```

This is honest: local models are simulated as zero. If you wanted to model GPU-amortized cost, you'd add an `infrastructure_per_token` field. Out of scope for A-.

### Cost evaluator semantics

The cost threshold evaluator compares `recorded_cost_usd` to a configured threshold. Cost delta in regression reports is `candidate_avg_cost - baseline_avg_cost`. Cost is always reported per-case-average, never per-run-total (run totals are misleading when case counts differ).

## 13. Result caching strategy

Re-running the same case + version + evaluator is wasteful. Cache strategy:

### Adapter output cache

Key: `sha256(case_input + version_config_json)`
Stored: `(cache_key, adapter_output_json, created_at)` in a `adapter_output_cache` table
TTL: 24 hours

When the worker starts a case:
1. Compute cache key
2. If hit: skip adapter call, use cached output
3. If miss: call adapter, store output

Cache invalidation: bumping a version config changes the hash. Editing a case creates a new case_id. So the cache is invalidated naturally by the data model.

**Skip the cache** in two cases:
- `--no-cache` flag on the run (for re-running a known-flaky case)
- The case is tagged `nondeterministic` (so flakiness benchmarks aren't masked)

### Evaluator result cache

Key: `(run_item_id, evaluator_name, evaluator_config_hash)`
This is the `eval_results` table — already a cache by design. If a row exists for this key, reuse it.

### Embedding cache

Already covered in §5. pgvector table keyed by text hash + model.

### Cache hit rate as a benchmark

`benchmarks/cache_efficiency.py` reports:
- Hit rate on a re-run of the same suite (should be ~100%)
- Hit rate on a re-run after editing one case (should be ~99.8%)
- Hit rate on a re-run with a new version (should be 0% for adapter, ~50%+ for embeddings if cases overlap)

## 14. Failure modes

### Adapter timeout
**Symptom:** adapter call exceeds `adapter_timeout`.
**Handling:** worker raises TimeoutError, retries up to 2x. If still failing, run_item.status = `timed_out`, run_item.error_message set, evaluator results all marked errored.
**Surface:** dashboard shows timeout count per run; comparison excludes timed-out items from both runs' pass rate denominators if either side timed out.

### Adapter crashes
**Symptom:** uncaught exception in adapter.run().
**Handling:** worker catches, retries 2x. After exhaustion: run_item.status = `errored`, error_message set.
**Surface:** same as timeout. Distinguishable in UI by error message.

### Evaluator crashes
**Symptom:** uncaught exception in evaluator.score().
**Handling:** that evaluator's result has errored=true. Other evaluators on the same item still run.
**Surface:** dashboard shows error icon next to that evaluator's score. Comparison treats errored evaluators as missing data, not as failures.

### NLI model OOM
**Symptom:** torch raises OOM during faithfulness scoring.
**Handling:** worker_compute is configured with concurrency=1 and `max_tasks_per_child=10` to release memory periodically. If OOM still occurs, faithfulness on that case errors out; remaining evaluators continue.
**Surface:** dashboard shows; benchmark report flags this as a known operational risk.

### Worker crashes mid-task
**Symptom:** OS-killed, segfault, machine reboot.
**Handling:** Celery's visibility_timeout returns the task to the queue after a configurable delay. The retry hits the unique constraint and either resumes or no-ops.
**Surface:** dashboard might briefly show a task stuck in `running` state before re-pickup. Acceptable for a portfolio project.

### DB connection pool exhaustion
**Symptom:** workers get "QueuePool limit exceeded" exceptions.
**Handling:** keep pool size > worker concurrency × 2. Don't share sessions across tasks.
**Prevention:** load test as part of benchmark protocol; pool size in config.

### Race on counter updates
**Symptom:** two workers complete simultaneously and both try to increment `eval_runs.case_completed`.
**Handling:** use `UPDATE ... SET case_completed = case_completed + 1` (atomic) not read-then-write.
**Verify:** include this in the run-status integration test.

### Comparison computed before runs finish
**Symptom:** user POSTs comparison while one run is still running.
**Handling:** API returns 409 Conflict with message. UI disables the "compare" button until both runs are completed/partial.

### Calibration with too few labels
**Symptom:** user runs analysis with <30 labels.
**Handling:** API returns 422 with explanatory message ("calibration requires at least 30 labeled cases for stable correlation estimates"). Threshold is configurable but documented.

## 15. Performance reasoning

### Where time is spent on a 500-case run

Estimated (will vary by hardware):

| Component | Time per case | Total | Notes |
|---|---|---|---|
| Adapter (RAG, top-3 retrieval + LLM gen) | 500-2000ms | 250s-1000s | dominated by LLM gen |
| Semantic similarity (cached) | 5ms | 2.5s | cache hit rate ~50% on first run |
| Semantic similarity (uncached) | 50ms | — | first compute |
| Faithfulness NLI | 500ms | 250s | the bottleneck |
| Retrieval hit rate | 1ms | 0.5s | string compare |
| Other evaluators | 10ms | 5s | trivial |
| DB writes (trace + 8 results) | 20ms | 10s | batched |
| **Total wall time** (8 workers) | — | ~150-250s | with full parallelism |

The faithfulness NLI dominates on the compute side; the adapter dominates on the wall-clock side.

### Optimization order (when actually slow)

1. **Batch NLI calls.** One batch of 8 sentences is much faster than 8 individual calls. Worth implementing.
2. **Cache embeddings across runs.** Already covered.
3. **Increase worker count to CPU count.** Helps until adapter latency dominates.
4. **Move sentence-transformers to a long-lived process.** Loading the model takes 2-3s; doing it once per worker boot vs once per task matters.
5. **Quantize NLI model.** int8 quantization roughly halves latency, minor accuracy hit. Document the tradeoff.

### What we deliberately don't optimize

- GPU support. Adds installation complexity, hurts reviewer reproducibility.
- Async DB writes for traces. They're small enough.
- Caching faithfulness results. Output text changes per run; cache hit rate would be near zero.

### API latency target

p95 < 300ms on dashboard endpoints. Sources of latency:
- Comparison aggregation: heavy read with computed columns. Materialize the result in `regression_reports` at compute time so the GET is cheap.
- Trace fetch: single-row lookup, fast.
- Run list: paginated, indexed, fast.

If p95 > 300ms, the comparison aggregation is the suspect. Profile it; pre-materialize aggressively.

## 16. Reproducibility + nondeterminism

### The reproducibility goal

`make demo` on a fresh clone should produce numbers within ±2% of the README's headline numbers.

### Sources of nondeterminism

1. **LLM generation temperature > 0** — set to 0 for the demo by default. Document that temperature=0 doesn't guarantee determinism on all backends (vLLM yes, Ollama mostly, OpenAI no).
2. **Retrieval ordering ties** — if two chunks have equal cosine score, the order depends on insertion. Stabilize by secondary sort on `doc_id`.
3. **Sentence-transformer batch order** — when batching, ordering can affect floating-point summation. Pin batch size to 1 for benchmarks; use larger batches only in production.
4. **Bootstrap resampling** — seed the RNG. `scipy.stats.bootstrap` accepts `random_state`; pin it to 42 in the comparison code.

### Documented nondeterminism

Some evaluations are intentionally nondeterministic:
- LLM-judge with temperature > 0
- Adapters that use sampling

These cases are tagged `nondeterministic`. They are used for the flaky-eval benchmark, where the *variance* is the metric, not the score.

### Stochasticity benchmark

`benchmarks/flaky_eval.py`:
1. Pick 50 cases tagged `nondeterministic`
2. Run each N=5 times against the same version
3. Compute per-case standard deviation of the primary evaluator score
4. Report: histogram of σ, count of cases classified as stable/flaky/inconclusive

This produces a real number to put in the resume bullet.

## 17. Observability of the platform itself

This is meta — the evaluation platform needs to be observable too. Otherwise, when a benchmark fails, you have no way to debug.

### What to log

- Every API request: method, path, status, latency_ms
- Every worker task: start, end, retries, error class
- Every DB transaction taking > 100ms
- Cache hit/miss rates per cache layer

Output: structured JSON to stdout, captured by Docker logs. No log shipping infrastructure.

### Health endpoint

`GET /healthz` returns:
- DB connection ok
- Redis connection ok
- Worker count (queried via Celery inspect)
- Last 5min queue depth

This is what the Overview dashboard polls.

### Metrics endpoint (optional, nice-to-have)

`GET /metrics` in Prometheus format. Out of scope for A-; mention as future work in the README.

## 18. Open design questions

These are deliberately unresolved. Resolve before building the affected component.

### Q1: How are evaluator thresholds chosen?
**Options:**
- (a) Hardcoded sensible defaults per evaluator (e.g., semantic sim > 0.7)
- (b) Learned from a held-out training set
- (c) Configured per case via case payload

**Lean:** (a) for v1, with config override in `evaluator_configs`. (b) is over-engineering for portfolio scope. (c) might be useful for adversarial cases where the bar is different.

**Resolve before:** Phase 3a.

### Q2: Should the LLM-judge run by default in calibration mode?
**Options:**
- (a) Only when explicitly enabled in evaluator_config
- (b) Auto-enabled when running against the gold-set suite

**Lean:** (a). Calibration is a deliberate phase, not an implicit one.

**Resolve before:** Phase 6.

### Q3: Trace viewer drill-down depth?
**Options:**
- (a) Flat list of steps with expandable JSON payloads
- (b) Custom renderers per step type (retrieve = chunk list with scores, generate = prompt + output diff)
- (c) Both, with (b) preferred and (a) as fallback

**Lean:** (c). Build (a) first; add (b) for `retrieve` and `generate` steps only.

**Resolve before:** Phase 5.

### Q4: Comparison failure-table grouping?
**Options:**
- (a) One row per failing case
- (b) Grouped by failure reason (which evaluator failed)
- (c) Grouped by tag

**Lean:** (a) with a filter UI for evaluator and tag. Grouping adds UI complexity; filtering is simpler.

**Resolve before:** Phase 5.

### Q5: How to handle case-level differences in evaluator applicability?
Example: retrieval hit rate doesn't apply to cases without `expected_chunk_id`. Three options:
- (a) Evaluator returns null/skipped; aggregation excludes
- (b) Evaluator returns score=1.0 (don't penalize)
- (c) Cases declare applicable evaluators in their payload

**Lean:** (a). Evaluator returns `EvalResult(score=None, passed=None, skipped=True)`. Aggregation treats skipped as not-in-denominator.

**Resolve before:** Phase 3a.

## 19. Future work (deliberately out of scope)

Listed here so the README can reference them as "future work" without ambiguity:

- Multi-tenancy + auth
- Real-time evaluation
- Web-based case authoring
- Cross-run analytics + trend dashboards
- Eval-of-eval (meta-evaluation)
- GPU inference path
- Prometheus metrics + Grafana
- Kubernetes deployment
- Webhook notifications on gate failures
- CI/CD integration (eval as a PR check)
- Multi-language case support (currently English-only)
- Multi-modal evaluation (image, audio outputs)
- Active learning for case generation

Each of these is a real project on its own. They are not weaknesses — they are honest scope boundaries.

## 20. References + reading list

Useful to cite in the README and have read for interview prep:

- **Bootstrap methods:** Efron & Tibshirani, *An Introduction to the Bootstrap* (1993) — Chapter 14 on BCa
- **Pass-rate CIs for proportions:** Brown, Cai, DasGupta, *Interval Estimation for a Binomial Proportion* (2001)
- **LLM evaluation:** Liang et al., *Holistic Evaluation of Language Models (HELM)* (2022)
- **Faithfulness in RAG:** Es et al., *RAGAS: Automated Evaluation of Retrieval Augmented Generation* (2023)
- **NLI for entailment scoring:** He et al., *DeBERTaV3* (2021)
- **Sentence embeddings:** Reimers & Gurevych, *Sentence-BERT* (2019)
- **Inter-rater reliability:** Cohen, *A Coefficient of Agreement for Nominal Scales* (1960); weighted-κ extension by Cohen (1968)

The READMEs of `Ragas`, `Promptfoo`, `DeepEval`, and `LangSmith` are also worth reading to know what the field looks like — and to be able to articulate the difference.
