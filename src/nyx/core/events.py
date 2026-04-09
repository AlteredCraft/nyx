"""Event Bus (Component 3i) — Observability backbone.

Simple in-process event emitter + append-only NDJSON log file.
All components emit structured events; the Reporter and tests consume them.

Event schema:
    {
        "ts": "2026-04-09T03:15:22Z",
        "component": "episode_runner",
        "event": "episode_complete",
        "task_id": "ns-001",
        "episode": 3,
        "data": {"exit_code": 0, "cost_usd": 1.23, "duration_sec": 312}
    }

The event log is the primary integration test artifact. Assert on event
sequences to verify correct orchestration without inspecting internal state.
"""
