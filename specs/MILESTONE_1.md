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
- [ ] `EpisodeResult` dataclass (exit_code, `cost_usd: float | None`, duration_sec, handoff_path, files_modified)
- [ ] `ModelAssignment` dataclass (backend, endpoint, fallback, tool_constraints)
- [ ] `TaskStatus` enum: todo, in_progress, qa, done, failed, blocked (full enum for forward compat; M1 only reaches todo/in_progress/done/failed)
- [ ] `TerminationReason` enum with all 8 values (4 active, 4 stub — see Section 3a)
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
- [ ] State machine validator — M1 permits only `todo → in_progress → done|failed`. All other transitions raise. Unused enum values (`qa`, `blocked`) remain in the schema but cannot be reached.
- [ ] Immutability: reject spec/title mutations on non-todo tasks
- [ ] Episode recording: `record_episode()` — `episode_count` increments without touching `status`; status only changes at terminal
- [ ] `:memory:` support for tests
- [ ] Unit tests: CRUD, parameterized valid/invalid transitions (M1 subset + explicit rejection of qa/blocked/backward moves), immutability rejection, episode recording

### Step 5: Model Router (`src/nyx/routing/router.py`)
- [ ] Load `[[routes]]` from config
- [ ] Match task against routes (type, priority conditions)
- [ ] Return `ModelAssignment` with backend + endpoint + fallback
- [ ] First-match-wins evaluation order
- [ ] Fall through to `[defaults]` if no route matches
- [ ] Unit tests: matching logic, fallback, default, no-match

### Step 6: Backend Adapter Interface + Claude CLI Adapter
- [ ] `BackendAdapter` `typing.Protocol` in `src/nyx/execution/adapters/base.py` (not an ABC — structural typing, zero-inheritance mocks)
  - `run(self, prompt: str, cwd: Path, timeout: int) -> EpisodeResult`
  - `health_check(self) -> bool`
  - `estimate_cost(self, prompt_tokens: int) -> float | None`
- [ ] `ClaudeCliAdapter` in `src/nyx/execution/adapters/claude_cli.py`
  - Spawn `claude -p --bare --output-format stream-json` via subprocess (shell=false)
  - Capture NDJSON stdout via pipe
  - Parse cost/duration from JSON result (always populates `cost_usd` — None reserved for future non-reporting backends)
  - Timeout handling via subprocess timeout
  - Health check: verify `claude` binary exists on PATH
- [ ] Unit tests: fake adapter that satisfies the Protocol without inheritance; mock subprocess for Claude CLI contract tests

### Step 7: Verification Engine (`src/nyx/verification/engine.py`)

M1 implements Stage 1 (handoff verification) only. Stages 2 (build) and 3 (policy) are deferred.

- [ ] **Handoff parser** (`src/nyx/verification/handoff.py`): parse the four-section markdown format (`Status`, `Files Modified`, `Summary`, `Next Steps`) per the contract in Section 3j
  - Case-insensitive heading match
  - Accept `-`, `*`, `+` bullet markers
  - Strip backticks, whitespace, leading `./` from paths
  - Fail loudly if any required section is missing — raise `HandoffMalformed`
- [ ] **Engine** checks the 6-case sub-failure matrix (Section 3e) and emits one event per case:
  - `handoff_missing` — no HANDOFF.md on disk → task `failed`
  - `handoff_malformed` — parser raises → task `failed`
  - `handoff_discrepancy_ghost_edits` — claims files, `git diff` empty → task `failed`
  - `handoff_discrepancy_unclaimed_edits` — `git diff` has files not in claims → task `failed`
  - `empty_episode` — claims + diff both empty, `Status: done` → task `failed`
  - `handoff_verified` — claims match diff exactly → `done` or stays `in_progress` per `## Status` section
- [ ] **M1 on failure: do not touch the working directory.** Capture `git status --porcelain` and `git diff --stat` into the episode record. Emit `verification_failed`. Artifacts persist for morning triage.
- [ ] Return `VerificationResult` (outcome, matched case, snapshots, recommended action)
- [ ] Parameterized unit tests over `tests/fixtures/handoffs/` — one fixture per sub-failure case plus a well-formed positive
- [ ] Unit tests: mock git output to drive each of the 6 matrix rows; assert correct event emitted and task status returned

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
- [ ] Termination check function evaluates all 8 conditions (spec Section 3a); M1 implements active predicates for 4, stubs return False for the other 4:
  - Active: `duration_expired`, `budget_exhausted`, `queue_empty`, `signal_received`
  - Stub: `human_stop_flag`, `consecutive_errors_exceeded`, `backend_health_failed`, `catastrophic_error`
- [ ] SIGINT/SIGTERM handler sets a flag; loop checks it before each episode (does not interrupt mid-episode)
- [ ] Budget tracker increments local counter from `EpisodeResult.cost_usd`; when `None`, emit `cost_unknown` and treat as zero
- [ ] State checkpointing to disk after each episode
- [ ] Crash recovery: load last checkpoint on startup
- [ ] Integration with all above components
- [ ] Integration tests: run full loop against test repo with mock adapter; parameterized tests for each of the 4 active termination conditions

### Step 12: CLI (`src/nyx/cli.py`)

Thin argparse layer over the tested Python API. No orchestration logic lives here; no integration tests run through the CLI.

- [ ] `nyx run --duration <duration> --budget <usd>` — start session
- [ ] `nyx tasks add <spec-file>` — add task from markdown file
- [ ] `nyx tasks list` — list queue with status
- [ ] `nyx tasks inspect <task-id>` — show task + episode history
- [ ] `nyx watch` — tail event log (NDJSON pretty-print)
- [ ] `nyx status` — show current/last session summary
- [ ] **Smoke tests only** (see Section 6):
  - `nyx --help` and `nyx <cmd> --help` exit zero
  - One mock-based test per subcommand: verify args parse and the expected API function is called with the expected payload
  - One end-to-end CLI smoke test: `nyx run --duration 30s --budget 0.01` with a mock adapter, starts and stops cleanly

### Step 13: Integration Test
- [ ] Create test repo fixture with real git
- [ ] Add 3 tasks to SQLite (one per path: verified success, verification failure, empty-episode failure)
- [ ] Run full loop with mock Claude CLI adapter (returns canned handoff + makes real git commits)
- [ ] Assert event sequence in NDJSON log, including the correct sub-failure events for the failing tasks
- [ ] Assert shift log content
- [ ] Assert task statuses in DB (one `done`, two `failed`)
- [ ] Assert the working directory was not modified by the verification engine (M1 no-revert guarantee)

## Test Fixtures Needed (`tests/conftest.py`)
- `tmp_git_repo` — disposable git repo with initial commit
- `tmp_db` — SQLite `:memory:` or temp file
- `event_bus` — in-memory EventBus instance
- `mock_claude_adapter` — satisfies the `BackendAdapter` Protocol without inheritance; returns canned `EpisodeResult`, optionally makes git commits
- `sample_config` — parsed from `nyx.toml.example`
- `sample_tasks` — 3 tasks of different types (coding, research, maintenance)

## Handoff Fixtures (`tests/fixtures/handoffs/`)

One file per verification sub-failure row plus the positive case. Loaded by parameterized tests for the handoff parser (Step 7) and the verification engine.

- `well_formed.md` — all four sections, Status=in_progress
- `well_formed_done.md` — all four sections, Status=done
- `missing_files_modified.md` — missing required section → `handoff_malformed`
- `bullet_variants.md` — mix of `-`, `*`, `+` markers + backticked paths + `./` prefix
- `empty_file_list.md` — `## Files Modified` present but empty
- `ghost_edits.md` — lists files, paired with a test that ensures `git diff` is empty → `handoff_discrepancy_ghost_edits`
- `unclaimed_edits.md` — empty file list, paired with a test where `git diff` shows edits → `handoff_discrepancy_unclaimed_edits`
- `empty_episode.md` — Status=done, empty Files Modified, paired with empty `git diff` → `empty_episode`
