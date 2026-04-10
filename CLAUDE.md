# CLAUDE.md — Nyx

## Project Overview

Nyx is a time-bounded AI task orchestrator for overnight autonomous execution. It queues tasks, runs them via multiple model backends (API and local), sandboxed and isolated per-task via git worktrees, then gracefully shuts down so the host machine can sleep.

## Architecture

`specs/system-architecture.md` is the source of truth for Nyx's design. When a design decision changes, update the spec in the same change — don't let code drift ahead of the spec. `specs/MILESTONE_1.md` is the dependency-ordered implementation checklist for the current milestone. Research findings and curated links are in `specs/research/`.

Key components:

| Component | Location | Role |
|-----------|----------|------|
| Orchestrator Core | `src/nyx/core/orchestrator.py` | Main loop, termination conditions |
| Event Bus | `src/nyx/core/events.py` | NDJSON structured event logging |
| Config | `src/nyx/core/config.py` | TOML config loading |
| Task Queue | `src/nyx/tasks/queue.py` | SQLite task store + state machine |
| Model Router | `src/nyx/routing/router.py` | Task-to-backend dispatch |
| Episode Runner | `src/nyx/execution/runner.py` | Spawn agent, capture output |
| Backend Adapters | `src/nyx/execution/adapters/` | Claude CLI, Agent SDK, OpenCode |
| Verification | `src/nyx/verification/engine.py` | Git truth check, build/test, policy |
| Worktree Manager | `src/nyx/git/worktrees.py` | Create/track/cleanup worktrees |
| Power Manager | `src/nyx/power/manager.py` | Caffeinate wrapper |
| Reporter | `src/nyx/reporting/reporter.py` | Shift log, exec summary |

## Implementation State

All `src/nyx/**/*.py` files are currently scaffolded with docstrings only — no functions, no classes, no logic. Milestone 1 is mid-implementation against `specs/MILESTONE_1.md`. Do not assume a component works because its file exists.

## Development Conventions

- **Python 3.11+** (for stdlib `tomllib`)
- **uv** for dependency management (`uv add`, not manual pyproject.toml edits)
- **pytest** for testing (`uv run pytest`)
- **TOML** for configuration (`nyx.toml`)
- **NDJSON** for event logs and streaming output
- Minimize external dependencies — use stdlib where possible
- Every component emits structured events to the Event Bus
- Tests assert on event sequences, not internal state
- Backend adapters implement a common interface (`BackendAdapter`)
- SQLite `:memory:` for unit tests, temp files for integration tests

## Testing

Follow a strict Red-Green-Refactor TDD cycle. Write tests first, watch them fail, then implement the minimum code to make them pass. Tests live in `tests/` organized by type (`unit/`, `integration/`).

```bash
uv run pytest                                       # all tests
uv run pytest tests/unit/                           # unit tests only
uv run pytest tests/integration/                    # integration tests only
uv run pytest tests/unit/test_queue.py::test_m1 -v  # single test
uv run pytest -k "handoff" -v                       # by keyword
```

Shared fixtures live in `tests/conftest.py`. Handoff sample files for the verification engine tests live in `tests/fixtures/handoffs/` (see `specs/MILESTONE_1.md` Step 7).

## Current Milestone

**Milestone 1: Core Loop (MVP)** — See `specs/MILESTONE_1.md` for the implementation checklist with dependency order. Start there.

## M1 Operating Notes

M1 differs from the eventual system in ways that matter for implementation:

- Runs in the current working directory. No git worktrees until M3.
- Does **not** revert failed episodes. Run Nyx in a clean tree; leftover state after a failed run is a triage signal, not a bug.
- Only the Claude CLI backend adapter exists. Router logic is essentially a passthrough until M2.
- State machine permits only `todo → in_progress → done|failed`. The `qa` and `blocked` enum values exist but are unreachable in M1.
- Only 4 of 8 termination conditions have active predicates (`duration_expired`, `budget_exhausted`, `queue_empty`, `signal_received`). The other four are stubs.

See "Known M1 limitations" in `specs/system-architecture.md` Section 5 for the full list.

## Key Design Principles

1. Episodic, not continuous (Ralph Loop pattern)
2. Model-agnostic — backends are pluggable
3. Git as truth oracle — never trust agent self-reports alone
4. Observable by default — every component emits events
5. Fail safe, not fail silent
6. Immutable task definitions
