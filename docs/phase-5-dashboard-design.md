# Phase 5 Dashboard Design

## Goal

Phase 5 turns EvalForge from a backend evaluation engine into a product someone can understand in two minutes. The dashboard is intentionally not a landing page. It is the actual operating surface for comparing a baseline RAG version against a candidate, seeing why the gate failed, and drilling into a trace.

## Design Source

The accepted concept image is committed at:

- `docs/design/phase-5-dashboard-concept.png`

The verified implementation screenshots are committed at:

- `docs/design/phase-5-dashboard-render.png`
- `docs/design/phase-5-dashboard-mobile-render.png`

The design direction is a quiet engineering dashboard:

- true white background
- cool gray borders
- blue navigation and baseline bars
- red failure states
- green pass states
- 8px maximum panel radius
- dense tables and trace details instead of marketing cards

## Screens Implemented

### Overview

The overview shows the whole story in the first viewport:

- benchmark identity
- candidate gate status
- pass rate, semantic similarity, p95 latency, and mean cost
- bootstrap CI ranges for every metric
- gate verdict
- comparison bars
- recent run table
- trace inspector on desktop

The trace inspector is visible on desktop because the first impression should communicate that EvalForge stores evidence, not only aggregate scores.

### Run Detail

The run detail view shows:

- selected run id
- app version
- run status
- cases and completed count
- progress bar
- run table for switching between runs
- trace inspector

This is the bridge between the run API and the trace debugger.

### Comparison

The comparison view shows:

- gate verdict
- comparison metric bars
- failure table
- evaluator filters

The failure table filter is local UI state. It proves the dashboard is not just a static screenshot.

### Traces

The trace view shows:

- failed case table
- current failed case
- question
- candidate answer
- ground truth
- semantic and keyword scores
- retrieval hit status
- retrieved context chunks with scores
- execution metadata

### Calibration

The calibration view is intentionally labeled as a preview. The project currently has a calibration methodology and synthetic preview values, but the final hand-labeled gold set is not complete. The UI says `methodology pending` so the project does not overclaim research results.

### Settings

The settings view exposes the active gate rules:

- metric
- direction
- tolerance
- verdict

This keeps the gate explainable during interviews.

## Component Architecture

The frontend lives under `frontend/src`.

- `App.tsx` composes the app shell, navigation, active view state, selected run state, selected trace state, and failure filter state.
- `data/demo.ts` contains measured demo benchmark data and realistic trace rows.
- `components/MetricCard.tsx` renders score cards with point estimates and CIs.
- `components/ComparisonBars.tsx` renders baseline vs candidate bars.
- `components/RunsTable.tsx` renders run history and run selection.
- `components/TraceInspector.tsx` renders the debugging evidence for one failed case.
- `components/CalibrationPanel.tsx` renders the synthetic calibration preview.
- `components/StatusPill.tsx` standardizes status visual language.
- `lib/format.ts` centralizes metric formatting.
- `api/client.ts` defines the future dashboard snapshot API boundary while falling back to local demo data.

The app is deliberately componentized so it is explainable file by file. `App.tsx` owns orchestration; components own presentation; data is isolated.

## Data Honesty

The headline numbers come from:

- `benchmarks/results/2026-05-31/demo_results.json`

Current measured benchmark:

- 500 eval cases
- 1000 total case executions
- 12.162 seconds elapsed
- 4933.21 cases per minute
- baseline pass rate: 100%
- candidate pass rate: 0%
- candidate semantic similarity: 0.284951
- p95 latency regression: 120ms to 260ms
- gate verdict: fail

The candidate is intentionally bad. It injects forbidden synthetic claims so the platform visibly catches a regression.

## Responsive Rules

Desktop:

- left sidebar remains fixed-width
- overview uses a main dashboard column plus right trace inspector
- metric cards use a two-by-two grid inside the main column
- tables scroll horizontally when necessary

Mobile:

- sidebar becomes compact top navigation
- secondary sidebar links are hidden
- metric cards stack one per row
- trace inspector moves below the table
- text remains inside its parent panels

## Verification

Commands run:

```powershell
npm run lint
npm test
npm run build
npm audit
```

Browser verification used Playwright because the Browser plugin was not exposed as a callable tool in this session.

Checked:

- desktop viewport: `1440x960`
- mobile viewport: `390x844`
- Overview renders metrics and trace inspector
- Comparison navigation works
- Failure filter works
- Traces navigation works
- Calibration view is marked as methodology pending
- browser console has no app errors
- favicon loads

## Known Gaps

The dashboard currently uses local benchmark-backed demo data. The `api/client.ts` boundary exists so the next phase can replace the local snapshot with a real `/api/dashboard/demo` endpoint without rewriting components.

The final calibration study is not complete. That is documented honestly in the UI and in `docs/calibration_findings.md`.
