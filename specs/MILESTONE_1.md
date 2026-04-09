---
title: "Milestone 1: Core Loop (MVP)"
status: not-started
spec: "./system-architecture.md#milestone-1-core-loop-mvp"
---

# Milestone 1: Core Loop (MVP)

See `system-architecture.md` Section 5 for full milestone description and Section 6 for observability/testing strategy.

## Goal

Read tasks from SQLite, run them sequentially via `claude -p --bare` in the current directory (no worktrees, no sandbox), verify via git diff, write a shift log. Wrapped in `caffeinate -s -t`.

## Implementation Order

Dependencies flow top-down. Each step should include unit tests.

### Step 1: Data Models (`src/nyx/tasks/models.py`)
- [ ] `Task` dataclass matching spec schema (Section 3b)
- [ ] `Episode` dataclass matching spec schema
- [ ] `ShiftLog` dataclass matching spec schema
- [ ] `EpisodeResult` dataclass (exit_code, cost_usd, duration_sec, handoff_path, files_modified)
- [ ] `ModelAssignment` dataclass (backend, endpoint, fallback, tool_constraints)
- [ ] `TaskStatus` enum: todo, in_progress, qa, done, failed, blocked
- [ ] Unit tests: construction, status transitions, immutability constraints

### Step 2: Event Bus (`src/nyx/core/events.py`)
- [ ] `EventBus` class with `.emit(component, event, task_id, episode, data)`
- [ ] NDJSON append-only file writer
- [ ] `.read_log() -> Iterator[dict]` for Reporter and tests
- [ ] In-memory mode for unit tests (no file I/O)
- [ ] Unit tests: emit events, read back, verify schema

### Step 3: Config Loader (`src/nyx/core/config.py`)
- [ ] Load `nyx.toml` via stdlib `tomllib`
- [ ] Parse into typed config objects: SessionConfig, SandboxConfig, RouteConfig, DefaultsConfig
- [ ] Validate required fields, apply defaults
- [ ] Unit tests: load example config, missing fields, bad values

### Step 4: Task Queue (`src/nyx/tasks/queue.py`)
- [ ] SQLite schema creation (tasks, episodes tables)
- [ ] Abstraction interface: `add_task()`, `next_task()`, `update_status()`, `get_task()`, `list_tasks()`
- [ ] State machine enforcement (valid transitions only)
- [ ] Immutability: reject spec/title mutations on non-todo tasks
- [ ] Episode recording: `record_episode()`
- [ ] `:memory:` support for tests
- [ ] Unit tests: CRUD, state transitions, immutability rejection, episode recording

### Step 5: Model Router (`src/nyx/routing/router.py`)
- [ ] Load `[[routes]]` from config
- [ ] Match task against routes (type, priority conditions)
- [ ] Return `ModelAssignment` with backend + endpoint + fallback
- [ ] First-match-wins evaluation order
- [ ] Fall through to `[defaults]` if no route matches
- [ ] Unit tests: matching logic, fallback, default, no-match

### Step 6: Backend Adapter Interface + Claude CLI Adapter
- [ ] `BackendAdapter` ABC in `src/nyx/execution/adapters/base.py`
  - `run(prompt, worktree, sandbox_config, timeout) -> EpisodeResult`
  - `health_check() -> bool`
  - `estimate_cost(prompt_tokens) -> float`
- [ ] `ClaudeCliAdapter` in `src/nyx/execution/adapters/claude_cli.py`
  - Spawn `claude -p --bare --output-format stream-json` via subprocess (shell=false)
  - Capture NDJSON stdout via pipe
  - Parse cost/duration from JSON result
  - Timeout handling via subprocess timeout
  - Health check: verify `claude` binary exists on PATH
- [ ] Unit tests: mock subprocess for adapter contract tests

### Step 7: Verification Engine (`src/nyx/verification/engine.py`)
- [ ] Stage 1 only for M1: handoff verification via `git diff`
  - Parse HANDOFF.md for claimed files_modified
  - Run `git diff --name-only` in worktree
  - Compare claims vs. reality, flag discrepancies
- [ ] Return `VerificationResult` (pass/fail, details, recommended action)
- [ ] Unit tests: mock git output, verify discrepancy detection

### Step 8: Episode Runner (`src/nyx/execution/runner.py`)
- [ ] Build episode prompt from: task spec, handoff (if exists), git context
- [ ] Dispatch to backend adapter
- [ ] Read HANDOFF.md from working directory after episode
- [ ] Return structured `EpisodeResult`
- [ ] Unit tests: mock adapter, verify prompt construction, result parsing

### Step 9: Reporter (`src/nyx/reporting/reporter.py`)
- [ ] Read event log (NDJSON)
- [ ] Generate Markdown shift log: per-task summary, episode counts, costs
- [ ] Generate brief exec summary (5-10 lines)
- [ ] Write to configured output directory
- [ ] Unit tests: feed canned events, verify shift log content

### Step 10: Power Manager (`src/nyx/power/manager.py`)
- [ ] Wrap orchestrator in `caffeinate -s -t <seconds>` via subprocess
- [ ] Graceful shutdown signal handling (finish current episode, then exit)
- [ ] Unit tests: verify caffeinate command construction, signal handling

### Step 11: Orchestrator Core (`src/nyx/core/orchestrator.py`)
- [ ] Main loop: select task -> route -> run episode -> verify -> checkpoint
- [ ] 8 termination conditions (spec Section 3a / Appendix A)
- [ ] State checkpointing to disk after each episode
- [ ] Crash recovery: load last checkpoint on startup
- [ ] Integration with all above components
- [ ] Integration tests: run full loop against test repo with mock adapter

### Step 12: CLI (`src/nyx/cli.py`)
- [ ] `nyx run --duration <duration> --budget <usd>` — start session
- [ ] `nyx tasks add <spec-file>` — add task from markdown file
- [ ] `nyx tasks list` — list queue with status
- [ ] `nyx tasks inspect <task-id>` — show task + episode history
- [ ] `nyx watch` — tail event log (NDJSON pretty-print)
- [ ] `nyx status` — show current/last session summary

### Step 13: Integration Test
- [ ] Create test repo fixture with real git
- [ ] Add 3 tasks to SQLite
- [ ] Run full loop with mock Claude CLI adapter (returns canned handoff + makes real git commits)
- [ ] Assert event sequence in NDJSON log
- [ ] Assert shift log content
- [ ] Assert task statuses in DB

## Test Fixtures Needed (`tests/conftest.py`)
- `tmp_git_repo` — disposable git repo with initial commit
- `tmp_db` — SQLite `:memory:` or temp file
- `event_bus` — in-memory EventBus instance
- `mock_claude_adapter` — returns canned EpisodeResult, optionally makes git commits
- `sample_config` — parsed from `nyx.toml.example`
- `sample_tasks` — 3 tasks of different types (coding, research, maintenance)
