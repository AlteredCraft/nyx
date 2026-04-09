# CLAUDE.md — Nyx

## Project Overview

Nyx is a time-bounded AI task orchestrator for overnight autonomous execution. It queues tasks, runs them via multiple model backends (API and local), sandboxed and isolated per-task via git worktrees, then gracefully shuts down so the host machine can sleep.

## Architecture

See `specs/system-architecture.md` for the full spec. Key components:

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

```bash
uv run pytest                    # Run all tests
uv run pytest tests/unit/        # Unit tests only
uv run pytest tests/integration/ # Integration tests only
```

## Key Design Principles

1. Episodic, not continuous (Ralph Loop pattern)
2. Model-agnostic — backends are pluggable
3. Git as truth oracle — never trust agent self-reports alone
4. Observable by default — every component emits events
5. Fail safe, not fail silent
6. Immutable task definitions
