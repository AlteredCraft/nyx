# US-06: Shift Reporting

**As an Operator (P1),** I want a clear, readable report waiting for me when I wake up so that I can understand what happened overnight without parsing logs.

**As an Integrator (P2),** I want machine-readable output I can consume in scripts so that I can pipe shift results into notifications, dashboards, or CI checks.

---

## Story 6-A: Shift log (human-readable)

### Scenario: Shift log is written after a clean shift

**Given** a shift completes with reason `queue_empty`
**And** three tasks were attempted: two `done`, one `failed`
**When** the reporter reads the event log and generates the shift log
**Then** a Markdown file is written to a predictable path
**And** the file includes: shift start timestamp, end timestamp, actual duration, termination reason, total cost, and a task count summary (2 done, 1 failed)
**And** each task has its own section showing: title, final status, episodes run, cost, and the summary text from its final `HANDOFF.md`
**And** the failed task's section includes the failure reason (e.g., `ghost_edits`)

> [!question] SPEC GAP
> The architecture does not specify where the shift log is written. Define the default path (e.g., `./nyx-shift-YYYY-MM-DD.md` relative to the working directory) and whether it is configurable in `nyx.toml`. Also define whether one file is created per shift or whether a single file is appended to across multiple shifts.

> [!question] SPEC GAP
> The `## Summary` field in `HANDOFF.md` is described as "1-3 sentence narrative" but the reporter's use of it is not specified. Define whether the reporter includes the raw summary text verbatim, truncates it, or reformats it.

---

### Scenario: Shift log is written after an interrupted shift (SIGINT)

**Given** the operator interrupted the shift with Ctrl-C while one task was in-progress
**When** the reporter runs as part of graceful shutdown
**Then** a shift log is written reflecting the partial shift
**And** the in-progress task is shown with status `failed` or `interrupted` and no cost (if the episode was force-killed) or the partial episode data (if the episode completed before shutdown)
**And** the termination reason is `signal_received`

> [!question] SPEC GAP
> If the episode did complete before SIGINT took effect, is its verification result included in the shift log? Define whether the reporter uses the event log (authoritative) or the database state (may lag) as its source, and how partial episodes are represented.

---

### Scenario: Shift log written atomically

**Given** the reporter is writing a shift log
**When** the reporter crashes mid-write
**Then** a partial shift log file is not left on disk (write to temp file, rename on completion)

> [!question] SPEC GAP
> The architecture does not specify atomic write requirements for the reporter. Define whether the reporter writes atomically (tmp + rename) or directly. A partial log file with a valid filename would be misleading to the operator.

---

## Story 6-B: JSON exec summary (machine-readable)

### Scenario: JSON exec summary is written alongside the shift log

**Given** a shift completes
**When** the reporter runs
**Then** a JSON file is written to a path adjacent to the shift log (e.g., same directory, same date stem, `.json` extension)
**And** the JSON contains all fields from the shift log in structured form
**And** the JSON is valid and parseable

---

### Scenario: Integrator reads JSON to trigger a notification

**Given** a shift has completed and the JSON exec summary exists
**When** the integrator's post-shift script reads the file
**Then** the JSON includes: `shift_id`, `started_at`, `ended_at`, `duration_seconds`, `termination_reason`, `total_cost_usd`, and a `tasks` array
**And** each task object includes: `id`, `title`, `type`, `status`, `episodes`, `cost_usd`, `failure_reason` (null if not failed)

> [!question] SPEC GAP
> The architecture does not define the JSON exec summary schema. Define a versioned schema (include a `schema_version` field) so integrators can detect breaking changes. Also define whether the JSON schema is documented in `system-architecture.md` or a separate schema file.

---

### Scenario: JSON exec summary is written even on abnormal exits

**Given** a shift ends due to `signal_received` or an unrecoverable error
**When** the reporter runs as part of shutdown
**Then** a JSON exec summary is written for the partial shift
**And** it accurately reflects the tasks that completed and those that did not

---

## Story 6-C: Raw event log

### Scenario: Every state transition has a corresponding event

**Given** a full shift runs with three tasks through various states
**When** the operator opens the NDJSON event log
**Then** every task state transition (`todo→in_progress`, `in_progress→done`, `in_progress→failed`) has a corresponding event line
**And** every verification outcome (all six sub-failure cases) has a distinct `event_type`
**And** each event line is a valid JSON object with at minimum: `timestamp`, `event_type`, and `task_id` (where applicable)
**And** events are ordered chronologically in the file

---

### Scenario: Event log survives a crash

**Given** a shift is running and the process crashes mid-shift
**When** the operator opens the event log
**Then** all events up to the crash are present and valid
**But** there is no partial JSON line at the end (events are written atomically per line)

> [!question] SPEC GAP
> The architecture says the event bus is append-only NDJSON but does not specify write atomicity at the line level. If a process crashes mid-write of a JSON line, the file will contain an unparseable partial line. Define whether line writes are atomic (write full line + newline in a single write call) and how the reader handles a trailing partial line.

---

### Scenario: Integrator filters events by task ID

**Given** the NDJSON event log contains events for multiple tasks
**When** the integrator runs `grep '"task_id":"abc123"' nyx-shift.ndjson`
**Then** all and only the events for task `abc123` are returned
**And** the chronological order is preserved

> [!question] SPEC GAP
> The architecture does not define the `task_id` field name or guarantee its presence across all event types. Define which events carry `task_id`, which carry `episode_id`, and whether both are always co-present when an episode context exists. A consistent schema here is essential for programmatic log processing.
