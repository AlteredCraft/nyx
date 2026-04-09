---
title: "Nyx — System Architecture Spec"
version: 0.2.0
status: draft
created: 2026-04-09
language: Python 3.11+
config_format: TOML
research:
  findings: "./research/research-findings.md"
  links: "./research/research-links.md"
decisions_resolved:
  - "Language: Python (primary), flexibility for subcomponents in other languages"
  - "Name: Nyx"
  - "Config: TOML (stdlib tomllib)"
---

# Nyx — System Architecture Spec

## 1. System Purpose

A time-bounded orchestrator that queues AI tasks, executes them autonomously via multiple model backends (API and local), sandboxed and isolated per-task via git worktrees, then gracefully shuts down so the host machine can sleep. Observable and testable at every layer.

## 2. Design Principles

1. **Episodic, not continuous**: Fresh context per episode. Handoffs bridge episodes. (Ralph Loop pattern.)
2. **Model-agnostic**: The orchestrator dispatches to backends, not models. Adding a new model is configuration, not code.
3. **Git as truth**: Agent self-reports are claims. Git diff is truth. Cross-verify always.
4. **Observable by default**: Every component emits structured events. The system is debuggable from logs alone, without attaching a debugger or reading source.
5. **Testable in isolation**: Each component has a defined interface and can be tested with mock inputs/outputs. Integration tests run the full loop against a test repo.
6. **Fail safe, not fail silent**: Errors are loud. Unrecoverable states halt and report, never silently continue.
7. **Immutable task definitions**: Agents execute tasks; they cannot redefine them.

## 3. Major Components

### 3a. Orchestrator Core (the "daemon")

**Responsibility**: The main loop. Reads task queue, selects next task, dispatches to the appropriate backend via the Episode Runner, checks termination conditions, writes shift logs.

**Interfaces**:
- IN: Task Queue (reads next task), Config (routing rules, budgets, timeouts), Timer (duration remaining)
- OUT: Shift Log, Exec Summary, State checkpoints

**Key behaviors**:
- Sequential episode execution (parallel worktrees is a later milestone)
- 8 termination conditions evaluated before each episode
- Graceful shutdown: finish current episode, write handoff, write shift log, exit cleanly
- Checkpoint state to disk after every episode (crash recovery)

**Observability**: Emits structured events for: episode_start, episode_complete, episode_error, task_selected, task_completed, task_failed, termination_triggered, budget_update, state_checkpoint.

---

### 3b. Task Queue

**Responsibility**: Persistent, queryable store of task definitions with state tracking.

**Storage**: SQLite database with an abstraction interface. CLI for human interaction (add, list, prioritize, inspect, remove tasks).

**Schema (conceptual)**:
```
tasks
  id              TEXT PRIMARY KEY   -- e.g., "ns-001"
  title           TEXT NOT NULL
  spec            TEXT NOT NULL      -- full task specification (markdown)
  type            TEXT NOT NULL      -- "coding" | "research" | "maintenance"
  priority        INTEGER DEFAULT 0  -- higher = run first
  status          TEXT DEFAULT "todo" -- "todo" | "in_progress" | "qa" | "done" | "failed" | "blocked"
  model_affinity  TEXT               -- preferred model/backend (nullable, orchestrator decides if null)
  budget_cap      REAL               -- per-task budget limit in USD (nullable)
  worktree_path   TEXT               -- assigned worktree (set at execution time)
  episode_count   INTEGER DEFAULT 0
  created_at      TIMESTAMP
  updated_at      TIMESTAMP

episodes
  id              INTEGER PRIMARY KEY
  task_id         TEXT REFERENCES tasks(id)
  episode_num     INTEGER
  model_used      TEXT
  cost_usd        REAL
  duration_sec    INTEGER
  tasks_completed INTEGER            -- sub-task count completed in this episode
  exit_code       INTEGER
  handoff_path    TEXT
  created_at      TIMESTAMP

shift_log
  id              INTEGER PRIMARY KEY
  session_id      TEXT               -- unique per nyx run
  started_at      TIMESTAMP
  ended_at        TIMESTAMP
  reason          TEXT               -- termination reason
  total_cost_usd  REAL
  tasks_attempted INTEGER
  tasks_completed INTEGER
  tasks_failed    INTEGER
  summary         TEXT               -- markdown exec summary
```

**Immutability enforcement**: Once a task enters `in_progress`, its `spec` field is frozen. The abstraction layer rejects mutations to spec/title on non-`todo` tasks.

**Observability**: Emits events for: task_created, task_status_changed, task_budget_exceeded.

---

### 3c. Model Router

**Responsibility**: Given a task (type, complexity, model_affinity, budget constraints), select the model backend and endpoint to use.

**Inputs**: Task metadata, remaining session budget, routing configuration, backend health status.

**Outputs**: A `ModelAssignment` — which backend to use, which model endpoint, which permission/tool constraints to apply.

**Routing logic (configurable via TOML/YAML)**:
```
[[routes]]
match = { type = "maintenance" }
backend = "agent-sdk"
endpoint = "ollama/qwen2.5-coder:32b"
fallback = "openrouter/anthropic/claude-sonnet-4-6"

[[routes]]
match = { type = "coding", priority = ">5" }
backend = "claude-cli"
endpoint = "anthropic/claude-opus-4-6"

[[routes]]
match = { type = "research" }
backend = "agent-sdk"
endpoint = "openrouter/anthropic/claude-sonnet-4-6"

[defaults]
backend = "agent-sdk"
endpoint = "ollama/qwen2.5-coder:32b"
fallback = "openrouter/anthropic/claude-sonnet-4-6"
```

**Escalation**: When the Orchestrator Core detects diminishing returns (< 0.5 tasks/episode for 3 consecutive) on a local model, it re-queries the Router with `escalate=true`, which moves to the fallback chain.

**Observability**: Emits events for: model_selected, model_escalated, model_fallback_triggered, endpoint_health_check.

---

### 3d. Episode Runner

**Responsibility**: Execute a single bounded episode against a specific task in a specific worktree using a specific model backend. This is the "inner loop."

**Inputs**: Task spec, handoff (if exists), git context, model assignment, worktree path, sandbox config, episode timeout.

**Outputs**: Episode result (exit code, cost, duration, handoff path, files modified).

**Execution sequence**:
1. Build episode prompt (mission + handoff + git context + task tracker)
2. Spawn agent subprocess in sandbox (`shell=false`, restricted env vars)
3. Capture stdout via pipe (NDJSON stream for real-time cost/progress)
4. Wait for subprocess exit or timeout
5. Read HANDOFF.md from worktree
6. Return structured result

**Backend adapters** (pluggable):
- `ClaudeCliAdapter`: Invokes `claude -p --bare --output-format stream-json`
- `AgentSdkAdapter`: Invokes Anthropic Agent SDK headless, targeting configurable base URL (Ollama, OpenRouter, Anthropic direct)
- `OpenCodeAdapter`: (future) Invokes OpenCode with agent team config

Each adapter implements a common interface:
```
interface BackendAdapter:
    run(prompt, worktree, sandbox_config, timeout) -> EpisodeResult
    health_check() -> bool
    estimate_cost(prompt_tokens) -> float
```

**Observability**: Emits events for: episode_spawned, episode_stdout_line (streaming), episode_exited, episode_timeout, subprocess_error.

---

### 3e. Verification Engine

**Responsibility**: After each episode, verify that work was actually done correctly.

**Three verification stages**:

1. **Handoff verification**: Cross-check HANDOFF.md claims against `git diff`. Flag truth discrepancies.
2. **Build verification**: Run the project's verification command (build, test, lint) in the worktree. Configurable per-repo via `verify_command` in config. Auto-detect from `package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod` if not specified.
3. **Policy verification**: Check blocked files weren't modified, lockfiles weren't touched, credential files weren't created.

**Outputs**: VerificationResult (pass/fail per stage, details, recommended action: commit | revert | log_for_review).

**On failure**: Revert the episode's changes in the worktree (`git checkout -- .` or `git stash`), increment error counter, log details.

**Observability**: Emits events for: verification_started, handoff_verified, handoff_discrepancy, build_passed, build_failed, policy_violation, verification_complete.

---

### 3f. Worktree Manager

**Responsibility**: Create, track, and clean up git worktrees for tasks.

**Behaviors**:
- Create worktree when task enters `in_progress`: `git worktree add <path> -b nyx/<task-id>`
- Track worktree-to-task mapping in Task Queue DB
- On task completion: create draft PR from worktree branch, then prune worktree
- On task failure: preserve worktree for human inspection, log location
- On session end: report orphaned worktrees in shift log

**Observability**: Emits events for: worktree_created, worktree_pruned, worktree_orphaned, pr_created.

---

### 3g. Power Manager

**Responsibility**: Keep the Mac awake for the configured duration, then allow sleep.

**Implementation**: Wrap the entire orchestrator process in `caffeinate -s -t <seconds>`. This is the outermost layer — if the orchestrator crashes, caffeinate also exits and the Mac sleeps.

**Graceful shutdown sequence**:
1. Timer fires (duration limit reached) OR all tasks complete OR human stop flag detected
2. Orchestrator finishes current episode (does not interrupt mid-episode)
3. Writes final handoff for in-progress task
4. Writes shift log + exec summary
5. Exits cleanly
6. Caffeinate releases, Mac sleeps

**Optional upgrade**: launchd plist for crash recovery with auto-restart (30-second throttle).

**Observability**: Emits events for: session_started (with duration), session_timer_warning (e.g., 30min remaining), session_ending, session_complete.

---

### 3h. Reporter

**Responsibility**: Generate human-readable and machine-readable output at session end.

**Outputs**:
1. **Shift Log** (Markdown): Per-task summary — what was attempted, completed, failed, blocked. Episode counts, models used, costs. Written to a configurable output directory.
2. **Exec Summary** (Markdown): 5-10 line high-level summary suitable for quick morning scan. Tasks completed, total cost, any items needing attention.
3. **Machine-readable state** (JSON): Full session state for programmatic consumption — task statuses, episode history, budget tracking, error log.
4. **PR links**: List of draft PRs created, ready for review.

**Observability**: The Reporter consumes the event log from all other components to build its output. It is the primary consumer of the observability system.

---

### 3i. Event Bus (Observability Backbone)

**Responsibility**: Structured event logging that all components emit to and the Reporter consumes from.

**Design**: Simple in-process event emitter + append-only log file (NDJSON). Not a distributed message bus — this is a single-process system.

**Event schema**:
```json
{
  "ts": "2026-04-09T03:15:22Z",
  "component": "episode_runner",
  "event": "episode_complete",
  "task_id": "ns-001",
  "episode": 3,
  "data": { "exit_code": 0, "cost_usd": 1.23, "duration_sec": 312 }
}
```

**Consumers**:
- Reporter (reads at session end to build shift log)
- Orchestrator Core (reads for budget tracking, termination decisions)
- CLI (can tail the event log for real-time monitoring: `nyx watch`)

**Testability**: The event log is the primary integration test artifact. Assert on event sequences to verify correct orchestration behavior without inspecting internal state.

---

## 4. Component Relationships

```
                        [CLI]
                         |
                    [Task Queue DB]
                         |
  caffeinate ──> [Orchestrator Core] <── [Config]
                    |    |    |
              [Model   [Event  [Power
              Router]   Bus]   Manager]
                 |       |
           [Episode Runner]
            |      |      |
     [Backend  [Sandbox  [Worktree
     Adapters]  Config]   Manager]
            |
     [Verification Engine]
            |
        [Reporter]
```

**Data flow**:
1. Human adds tasks via CLI -> Task Queue DB
2. Human starts session: `nyx run --duration 6h --budget 50`
3. Power Manager wraps process in caffeinate
4. Orchestrator Core reads next task from Queue
5. Model Router selects backend + model
6. Worktree Manager creates/locates worktree
7. Episode Runner spawns agent in sandbox within worktree
8. All components emit to Event Bus
9. Verification Engine validates episode output
10. Orchestrator checks termination conditions, loops or exits
11. Reporter reads Event Bus, writes Shift Log + Exec Summary

## 5. Development Order

Designed for incremental value — each milestone produces a usable system.

### Milestone 1: Core Loop (MVP)
**Implementation checklist**: See [`MILESTONE_1.md`](./MILESTONE_1.md) for dependency-ordered task list and test fixtures.

**Components**: Orchestrator Core, Task Queue (SQLite + CLI), Episode Runner (Claude CLI adapter only), Verification Engine (git verification only), Event Bus, Reporter (basic shift log)

**What it does**: Read tasks from SQLite, run them sequentially via `claude -p --bare` in the current directory (no worktrees, no sandbox), verify via git diff, write a shift log. Wrapped in `caffeinate -s -t`.

**Testable**: Unit tests for each component with mock interfaces. Integration test: add 3 tasks, run the loop against a test repo, assert event sequence and shift log content.

### Milestone 2: Multi-Model Routing
**Components**: Model Router, Agent SDK adapter, Ollama integration

**What it does**: Route tasks to different backends based on type/priority. Local models for cheap tasks, API for complex ones. Escalation on diminishing returns.

**Testable**: Router unit tests with mock backends. Integration test: queue tasks with different model affinities, verify correct routing in event log.

### Milestone 3: Worktree Isolation
**Components**: Worktree Manager, PR creation

**What it does**: Each task gets its own worktree and branch. Successful tasks auto-create draft PRs.

**Testable**: Worktree lifecycle tests against a test repo. Verify branch creation, isolation between tasks, PR creation, cleanup.

### Milestone 4: Sandboxing
**Components**: Docker SBX integration in Episode Runner

**What it does**: Agent subprocesses run inside Docker sandboxes with filesystem/network controls.

**Testable**: Verify sandbox creation/teardown, filesystem isolation (agent can't write outside worktree), network policy enforcement.

### Milestone 5: Parallel Execution
**Components**: Orchestrator Core upgrade for concurrent episodes across worktrees

**What it does**: Run multiple tasks simultaneously in separate worktrees/sandboxes.

**Testable**: Verify no cross-contamination between concurrent tasks, correct budget tracking across parallel episodes.

### Milestone 6: Advanced Reporting + Monitoring
**Components**: Reporter upgrade (exec summary, PR links, cost breakdown), CLI `watch` command for real-time tailing

**What it does**: Rich morning report, real-time monitoring option.

## 6. Observability & Testability Strategy

### Observability Layers

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| **Events** | NDJSON event log | Primary observability. Every component emits structured events. Reporter and tests consume these. |
| **Agent stdout** | Piped NDJSON stream | Real-time cost/progress from agent subprocesses. |
| **Git state** | `git log`, `git diff` | Truth oracle for verification. |
| **Task DB** | SQLite queries | Task state machine. CLI inspectable. |
| **Shift log** | Markdown file | Human-readable session summary. |
| **Process health** | Exit codes, PID files | Crash detection for launchd integration. |

### Testing Strategy

| Level | Scope | How |
|-------|-------|-----|
| **Unit** | Each component in isolation | Mock interfaces. Router gets mock backends, Episode Runner gets mock subprocess, Verification gets mock git output. |
| **Integration** | Full loop against test repo | Real SQLite, real git, mock agent (returns canned handoff + makes real git commits). Assert on event log and shift log. |
| **Contract** | Backend adapter compliance | Each adapter implements the `BackendAdapter` interface. Contract tests verify: spawn, capture output, timeout, health check. |
| **End-to-end** | Real agent, real repo | Run a minimal task (e.g., "add a comment to line 1 of README.md") through the full system. Verify PR created, shift log accurate. Expensive — run sparingly. |
| **Chaos** | Failure modes | Kill agent mid-episode (verify crash recovery). Exceed budget mid-session (verify termination). Create a task that always fails (verify error threshold). Corrupt handoff (verify discrepancy detection). |

### Key Testability Decisions

1. **Event Bus is the primary test interface**. Integration tests assert on event sequences, not internal state. This decouples tests from implementation details.
2. **Backend adapters are the primary mock boundary**. The Episode Runner doesn't know or care whether it's talking to a real Claude instance or a test harness that returns canned responses.
3. **SQLite is testable in-process**. Use `:memory:` databases for unit tests, temp files for integration tests. No external database process.
4. **Git operations are testable via temp repos**. Create disposable git repos in test fixtures, run real git commands against them.

## 7. Open Decision Points

### Resolved

1. ~~**Programming language**~~: **Python 3.11+** (primary). Subcomponents may use other languages where appropriate. Agent SDK is native Python, SQLite/subprocess/git are stdlib.
2. ~~**Project name**~~: **Nyx**. CLI: `nyx run`, `nyx tasks`, `nyx watch`.
3. ~~**Config file format**~~: **TOML** (`nyx.toml`). Uses stdlib `tomllib`. Zero external deps.
5. ~~**Agent SDK integration**~~: Native Python — no shell wrapper needed since orchestrator is Python.

### Blocking Milestone 2

4. **OpenRouter vs. direct API keys**: OpenRouter simplifies multi-provider access but adds a dependency and marginal latency. Direct API keys (Anthropic, OpenAI) give full control. Can support both — but which is the default path?

### Non-blocking (can decide during development)

6. **Handoff format**: Start with 6-section minimal (Nightcrawler-style). Evolve as needed.
7. **Verification command auto-detection**: Nice-to-have. Start with explicit config, add detection later.
8. **launchd integration**: Optional upgrade after caffeinate-only MVP works.
9. **Non-coding task paths**: Vault maintenance doesn't need worktrees or sandboxing. Design the lightweight path when we get to those task types.
