# US-07: Live Monitoring

**As an Operator (P1),** I want to check on a running shift without stopping it so that I can satisfy my curiosity or triage a concern without risking data loss.

**As an Integrator (P2),** I want to query current shift state programmatically so that my scripts can react to what Nyx is doing right now.

---

## Story 7-A: Tailing the event stream

### Scenario: Operator watches a running shift

**Given** `nyx run` is active in one terminal
**When** the operator runs `nyx watch` in a second terminal
**Then** `nyx watch` locates the active shift's event log
**And** displays events already written (full shift history from the start)
**And** continues to display new events as they are written by the running shift
**And** each event is formatted as a human-readable line, not raw JSON

> [!question] SPEC GAP
> The architecture does not specify how `nyx watch` locates the active shift's event log. Options include: a well-known path convention (`./nyx-current.ndjson`), a PID/lock file written by `nyx run`, or a config key. Define the discovery mechanism.

> [!question] SPEC GAP
> The architecture does not specify the human-readable format for `nyx watch` output. Define whether events are formatted as timestamped one-liners (e.g., `[12:34:56] task_routed task=abc123 backend=claude_cli`), whether colour is used, and whether a `--verbose` flag exists for raw JSON output.

---

### Scenario: Stopping nyx watch does not affect the running shift

**Given** `nyx watch` is running and displaying events
**When** the operator presses Ctrl-C in the `nyx watch` terminal
**Then** `nyx watch` exits
**But** `nyx run` continues unaffected

---

### Scenario: nyx watch when no shift is running

**Given** no `nyx run` process is active
**When** the operator runs `nyx watch`
**Then** `nyx watch` exits with a non-zero code and a clear human-readable message (e.g., "No active shift found.")
**But** does not block indefinitely waiting for a shift to start

> [!question] SPEC GAP
> Should `nyx watch` optionally wait for a shift to start (`--wait` flag or default behavior)? Define whether it is a one-shot reader or can block until a shift appears.

---

### Scenario: nyx watch on a completed shift's log

**Given** a shift has completed and its event log exists on disk
**When** the operator runs `nyx watch --file nyx-shift-2026-04-09.ndjson`
**Then** `nyx watch` displays all events from the file
**And** exits after the last event (does not block waiting for new events)

> [!question] SPEC GAP
> The architecture does not specify whether `nyx watch` accepts a `--file` argument for replaying historical logs. Define whether this is in scope for M1 or deferred.

---

## Story 7-B: Shift status snapshot

### Scenario: Operator checks shift status while it is running

**Given** `nyx run` is active and processing tasks
**When** the operator runs `nyx status`
**Then** Nyx prints a concise summary including:
  - Shift start time and elapsed duration
  - Currently executing task: title and how long the current episode has been running
  - Task counts: completed, failed, remaining
  - Cumulative cost so far
**And** the command exits immediately (does not poll or block)

> [!question] SPEC GAP
> How does `nyx status` determine the currently executing task? Options include: reading the `in_progress` task from the database, reading the most recent `task_started` event from the event log, or reading a dedicated state file. Define the data source and what happens if the database and event log disagree.

---

### Scenario: Operator checks status between episodes

**Given** a task just completed and the orchestrator is selecting the next task (gap between episodes)
**When** the operator runs `nyx status`
**Then** the output shows no currently executing task (or "selecting next task…")
**And** the completed/remaining counts are up to date

> [!question] SPEC GAP
> The between-episode state is not represented in the task state machine (tasks are either `todo`, `in_progress`, or terminal). Define what `nyx status` shows when the orchestrator is between episodes — specifically whether "idle but running" is distinguishable from "no shift running".

---

### Scenario: Integrator queries status as JSON

**Given** `nyx run` is active
**When** the integrator runs `nyx status --json`
**Then** Nyx prints a JSON object to stdout containing all the same fields as the human-readable output
**And** the JSON is valid
**And** the exit code is 0

---

### Scenario: Status when no shift is running and no history exists

**Given** Nyx has never been run
**When** the operator runs `nyx status`
**Then** Nyx prints a message indicating no shift history exists
**And** exits with code 0

---

### Scenario: Status when no shift is running but history exists

**Given** a shift completed yesterday
**And** no shift is currently active
**When** the operator runs `nyx status`
**Then** Nyx shows a summary of the most recently completed shift
**And** clearly indicates the shift is not currently running (e.g., "Last shift: completed 2026-04-08 at 06:42")

> [!question] SPEC GAP
> The architecture does not define how Nyx determines whether a shift is currently running vs. completed. Define the mechanism: PID file presence, a `shift_active` flag in the database, or detecting a running process by name. Also define what happens if a PID file exists but the process is dead (stale lock).
