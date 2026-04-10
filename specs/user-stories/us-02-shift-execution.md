# US-02: Shift Execution

**As an Operator (P1),** I want to start Nyx and have it work through my task queue autonomously so that I wake up to completed tasks without having to intervene during the shift.

---

## Story 2-A: Basic shift run

### Scenario: Shift starts and processes tasks to completion

**Given** `nyx.toml` is present and valid
**And** the task queue contains at least one `todo` task
**And** the current directory is a git repository
**When** the operator runs `nyx run`
**Then** Nyx wraps itself in `caffeinate` to prevent machine sleep
**And** a `shift_started` event is emitted to the event log with the config snapshot and start timestamp
**And** Nyx processes tasks in priority-then-FIFO order until the queue is empty or a termination condition fires
**And** on exit, a `shift_ended` event is emitted with the termination reason and final statistics
**And** `caffeinate` is released before the process exits
**And** the exit code is 0

> [!question] SPEC GAP
> Where is the event log written? The architecture does not specify a default path or a config key for it. Define the default (e.g., `./nyx-YYYY-MM-DD.ndjson`) and whether it is configurable in `nyx.toml`.

> [!question] SPEC GAP
> Does `nyx run` require the current directory to be a git repository? In M1 there are no worktrees, but verification runs `git diff`. Define what happens if the working directory is not a git repo: hard error at startup, or deferred error at verification time?

---

### Scenario: Shift starts with a custom config path

**Given** a valid config file exists at `~/configs/my-nyx.toml`
**When** the operator runs `nyx run --config ~/configs/my-nyx.toml`
**Then** Nyx loads config from the specified path
**And** the shift proceeds normally

---

### Scenario: Config file not found

**Given** no `nyx.toml` exists in the current directory
**When** the operator runs `nyx run`
**Then** Nyx exits with a non-zero exit code
**And** an error message names the missing config file and its expected path
**But** no event log file is created
**But** `caffeinate` is not started

---

### Scenario: Config file is invalid

**Given** `nyx.toml` exists but contains a syntax error
**When** the operator runs `nyx run`
**Then** Nyx exits with a non-zero exit code
**And** the error message identifies the config key or line that is invalid
**But** no event log file is created

> [!question] SPEC GAP
> The architecture specifies that config loading validates fields and applies defaults, but does not list which fields are required vs. optional, or what the defaults are. Enumerate required config keys and their defaults.

---

### Scenario: No tasks in queue

**Given** `nyx.toml` is valid
**And** the task queue is empty (no `todo` tasks)
**When** the operator runs `nyx run`
**Then** Nyx emits `shift_started` then immediately evaluates the `queue_empty` termination condition
**And** Nyx emits `shift_ended` with reason `queue_empty`
**And** the shift report is written
**And** the exit code is 0

> [!question] SPEC GAP
> Should `nyx run` on an empty queue be a warning or a normal exit? An operator who accidentally runs `nyx run` before adding tasks might not notice a silent clean exit. Consider whether a distinct exit code or stderr warning is appropriate.

---

## Story 2-B: Shift with a duration limit

### Scenario: Shift respects `max_duration` and stops cleanly

**Given** `nyx.toml` sets `max_duration = "6h"`
**And** the queue has more tasks than can complete in 6 hours
**When** 6 hours of wall-clock time elapse
**And** the current episode finishes
**Then** Nyx evaluates the `duration_expired` termination condition and finds it true
**And** Nyx does not start another episode
**And** remaining `todo` tasks are left in `todo` state
**And** a `shift_ended` event is emitted with reason `duration_expired`, the configured limit, and actual elapsed time

> [!question] SPEC GAP
> The architecture says termination is checked "before starting each new episode" but does not specify the granularity for the duration check. Is it only checked at episode boundaries, or also at a polling interval during long-running episodes? Define the check point precisely.

---

### Scenario: Duration limit overridden via CLI flag

**Given** `nyx.toml` sets `max_duration = "6h"`
**When** the operator runs `nyx run --max-duration 2h`
**Then** the CLI value of 2 hours takes precedence over the config value

> [!question] SPEC GAP
> The architecture does not specify CLI-vs-config precedence rules. Define the override hierarchy (CLI flags > config file > defaults) explicitly.

---

### Scenario: Episode runs past the duration limit

**Given** `max_duration` is set to 30 minutes
**And** an episode is running and has been running for 31 minutes
**Then** Nyx does not kill the running agent subprocess
**And** Nyx waits for the episode to complete before evaluating the termination condition
**And** the total elapsed time in the shift log exceeds `max_duration`

> [!question] SPEC GAP
> The architecture is silent on whether there is an absolute hard kill (e.g., if an episode runs 10× over budget). Define whether Nyx ever force-kills a running agent, and if so, under what condition and with what grace period.

---

## Story 2-C: Shift with a cost budget

### Scenario: Shift respects `max_cost` and stops cleanly

**Given** `nyx.toml` sets `max_cost = 5.00`
**And** episodes have cumulatively spent $5.00 or more
**When** the current episode finishes
**Then** Nyx evaluates `budget_exhausted` and finds it true
**And** Nyx does not start another episode
**And** remaining `todo` tasks are left in `todo` state
**And** the `shift_ended` event includes configured budget, total spent, and remaining

> [!question] SPEC GAP
> The architecture says "cost tracking assumes Claude CLI (always populates cost)" but does not specify the exact mechanism: is cost parsed from the CLI's JSON output, a dedicated field, or inferred from token counts? Define the cost extraction interface for the Claude CLI adapter, and what happens if cost is missing from the output (e.g., network error, truncated output).

> [!question] SPEC GAP
> Is cumulative cost stored in the database (so a crash and restart can resume tracking) or held in memory only? Define the persistence model for cost state.

---

### Scenario: Single episode cost is not pre-checked against the budget

**Given** remaining budget is $0.10
**And** a task is next in the queue
**When** the orchestrator checks `budget_exhausted`
**Then** the predicate is false (remaining budget > 0)
**And** the episode is started even though it will likely exceed the remaining budget
**And** after the episode finishes and cost is tallied, `budget_exhausted` becomes true
**And** no further episodes are started

> [!question] SPEC GAP
> Should there be a pre-flight cost estimate check before dispatching an episode? The architecture mentions `estimate_cost` on the BackendAdapter interface but does not specify whether it is called in the main loop or only used for reporting. Clarify its role.
