from __future__ import annotations

import os

from locust import HttpUser, LoadTestShape, between, events, task


def _integer(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


class EvalForgeUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self) -> None:
        token = os.getenv("EVALFORGE_LOAD_API_KEY")
        if token:
            self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(10)
    def liveness(self) -> None:
        self.client.get("/livez", name="GET /livez")

    @task(5)
    def list_apps(self) -> None:
        self.client.get("/api/apps?limit=50", name="GET /api/apps")

    @task(4)
    def latest_dashboard(self) -> None:
        with self.client.get(
            "/api/dashboard/latest?failure_limit=25",
            name="GET /api/dashboard/latest",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                response.success()

    @task(2)
    def list_runs(self) -> None:
        self.client.get("/api/runs?limit=50", name="GET /api/runs")

    @task(1)
    def list_comparisons(self) -> None:
        self.client.get("/api/comparisons?limit=50", name="GET /api/comparisons")


class StagedLoadShape(LoadTestShape):
    """Ramp, sustain, and spike profile controlled entirely by environment variables."""

    stages = (
        {
            "duration": _integer("EVALFORGE_LOAD_RAMP_SECONDS", 60),
            "users": _integer("EVALFORGE_LOAD_RAMP_USERS", 25),
            "spawn_rate": _integer("EVALFORGE_LOAD_RAMP_SPAWN_RATE", 5),
        },
        {
            "duration": _integer("EVALFORGE_LOAD_SUSTAIN_SECONDS", 300),
            "users": _integer("EVALFORGE_LOAD_SUSTAIN_USERS", 50),
            "spawn_rate": _integer("EVALFORGE_LOAD_SUSTAIN_SPAWN_RATE", 10),
        },
        {
            "duration": _integer("EVALFORGE_LOAD_SPIKE_SECONDS", 360),
            "users": _integer("EVALFORGE_LOAD_SPIKE_USERS", 100),
            "spawn_rate": _integer("EVALFORGE_LOAD_SPIKE_SPAWN_RATE", 25),
        },
    )

    def tick(self) -> tuple[int, float] | None:
        elapsed = self.get_run_time()
        boundary = 0
        for stage in self.stages:
            boundary += stage["duration"]
            if elapsed < boundary:
                return stage["users"], stage["spawn_rate"]
        return None


@events.quitting.add_listener
def enforce_load_test_thresholds(environment, **_kwargs) -> None:
    stats = environment.runner.stats.total
    max_failure_ratio = float(os.getenv("EVALFORGE_LOAD_MAX_FAILURE_RATIO", "0.01"))
    max_p95_ms = _integer("EVALFORGE_LOAD_MAX_P95_MS", 750)
    p95_ms = stats.get_response_time_percentile(0.95) or 0
    if stats.fail_ratio > max_failure_ratio or p95_ms > max_p95_ms:
        environment.process_exit_code = 1
