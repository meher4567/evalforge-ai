# Load testing

EvalForge ships a read-heavy staged Locust profile in `benchmarks/locustfile.py`. It ramps to
25 users, sustains 50 users for five minutes, then spikes to 100 users by default. The test exits
non-zero when the aggregate failure ratio exceeds 1% or p95 response time exceeds 750 ms.

Install and run it against a non-production environment:

```bash
cd backend
uv sync --group load
EVALFORGE_LOAD_API_KEY='<personal-api-key>' \
  uv run --group load locust \
  -f ../benchmarks/locustfile.py \
  --host https://your-api.example.com \
  --headless --csv ../benchmarks/results/load
```

The workload is read-only. It exercises liveness, app/run/comparison lists, and the latest
dashboard aggregation. Override any stage with the `EVALFORGE_LOAD_*` variables defined in the
locustfile. Run provider-heavy evaluation traffic as a separate, budget-capped exercise because
external model latency, quotas, and cost otherwise hide API capacity.

Release acceptance criteria:

- error ratio below 1%;
- aggregate p95 below 750 ms for the default profile;
- no database pool exhaustion, worker lease buildup, or Redis eviction;
- recovery to the pre-spike p95 within five minutes;
- all API and worker SLO alerts remain below paging thresholds.
