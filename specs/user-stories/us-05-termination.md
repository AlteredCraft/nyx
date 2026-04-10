# US-05: Termination and Graceful Shutdown

**As an Operator (P1),** I want Nyx to stop reliably when the right conditions are met — queue empty, budget gone, time up, or interrupted — so the machine can sleep and I never wake up to a runaway process or corrupted state.

In M1, four conditions have active predicates: `queue_empty`, `budget_exhausted`, `duration_expired`, `signal_received`. The remaining four (`human_stop_flag`, `consecutive_errors_exceeded`, `backend_health_failed`, `catastrophic_error`) are always-false stubs.

---

## Story 5-A: Queue empty

### Scenario: All tasks complete, shift exits cleanly

**Given** the task queue has three tasks, all of which complete successfully during the shift
**When** the orchestrator checks for the next task and finds no `todo` tasks remaining
**Then** `queue_empty` evaluates to true
**And** the orchestrator does not start another episode
**And** a `shift_ending` event is emitted with `reason = "queue_empty"`
**And** the shift report is written to disk
**And** the process exits with code 0
**And** `caffeinate` is released before exit

---

### Scenario: All remaining tasks are failed, none are todo

**Given** three tasks exist: two `done` and one `failed`
**And** no tasks are in `todo` state
**When** the orchestrator evaluates `queue_empty`
**Then** the predicate returns true (no `todo` tasks available regardless of failed tasks)
**And** the shift ends with reason `queue_empty`

> [!question] SPEC GAP
> The architecture does not define "queue empty" precisely: does it mean zero tasks total, zero `todo` tasks, or zero `todo`-or-`in_progress` tasks? The predicate name suggests zero `todo`, but there should be a formal definition. Also define how tasks in `in_progress` state at shift start (from a previous crashed shift) are handled.

---

## Story 5-B: Budget exhausted

### Scenario: Budget exhausted after an episode completes

**Given** `max_cost = 5.00` is configured
**And** episodes have accumulated $4.80 in cost before the current episode
**And** the current episode costs $0.30, bringing the total to $5.10
**When** the current episode finishes and cost is tallied
**Then** `budget_exhausted` evaluates to true
**And** a `shift_ending` event is emitted with `reason = "budget_exhausted"`, configured limit, and total spent
**And** remaining `todo` tasks are left unchanged
**And** the shift report records the overage

---

### Scenario: Budget is exactly met (boundary condition)

**Given** `max_cost = 5.00`
**And** cumulative cost reaches exactly $5.00 after an episode
**When** `budget_exhausted` is evaluated
**Then** the predicate returns true
**And** no additional episodes are started

> [!question] SPEC GAP
> Define the budget comparison: is it `>=` (exhausted at or above limit) or `>` (only above limit)? Floating-point equality is unreliable; specify whether the comparison uses integer cents or a tolerance.

---

## Story 5-C: Duration expired

### Scenario: Max duration elapses between episodes

**Given** `max_duration = "4h"` is configured
**And** the shift has been running for 4 hours and 3 minutes
**And** the current episode just finished
**When** the orchestrator checks `duration_expired`
**Then** the predicate returns true
**And** a `shift_ending` event is emitted with `reason = "duration_expired"`, the configured limit, and actual elapsed time
**And** remaining `todo` tasks are left unchanged

---

### Scenario: Episode extends beyond the configured duration

**Given** `max_duration = "2h"` is configured
**And** the shift has been running for 1h 55min when the last episode starts
**And** the episode takes 20 minutes to complete
**When** the orchestrator receives the episode result (at 2h 15min elapsed)
**Then** Nyx allows the episode to finish before evaluating `duration_expired`
**And** the shift ends after the episode completes, not mid-episode
**And** the `shift_ending` event records actual elapsed time as 2h 15min

> [!question] SPEC GAP
> The architecture is silent on a hard-kill timeout: if an episode goes massively over (e.g., the agent hangs for 3 hours when max_duration is 2h), does Nyx ever force-kill the subprocess? Define an optional `max_episode_duration` or a hard kill threshold and what state the task is left in if force-killed.

---

### Scenario: Duration expressed as hours and minutes

**Given** `max_duration = "1h30m"` or `max_duration = 5400` (seconds)
**When** Nyx loads the config
**Then** the duration is parsed correctly

> [!question] SPEC GAP
> The config format for `max_duration` is not specified. Define the accepted format(s): ISO 8601 duration (`PT6H`), human-readable shorthand (`6h`, `1h30m`), or integer seconds. Consistency with other duration fields matters.

---

## Story 5-D: Signal received

### Scenario: SIGINT (Ctrl-C) triggers graceful shutdown

**Given** a task episode is running
**When** the operator presses Ctrl-C
**Then** Nyx catches SIGINT and sets the `signal_received` flag
**And** the running episode is allowed to complete
**When** the episode finishes
**Then** `signal_received` evaluates to true
**And** a `shift_ending` event is emitted with `reason = "signal_received"`
**And** the shift report is written
**And** the process exits with a non-zero exit code indicating interruption

> [!question] SPEC GAP
> The architecture does not specify the exit code for SIGINT termination. Define exit codes for each termination reason: 0 for natural exits (`queue_empty`, `budget_exhausted`, `duration_expired`), non-zero for interruption or error (`signal_received`, future catastrophic conditions)?

---

### Scenario: SIGTERM triggers graceful shutdown

**Given** a shift is running
**When** the OS or a script sends SIGTERM to the Nyx process
**Then** Nyx handles SIGTERM the same way as SIGINT

> [!question] SPEC GAP
> The architecture mentions SIGINT but does not mention SIGTERM. Define which signals Nyx handles and whether they all follow the same graceful shutdown path.

---

### Scenario: Double SIGINT force-exits immediately

**Given** the operator has pressed Ctrl-C once and the shift is in graceful shutdown
**When** the operator presses Ctrl-C a second time
**Then** Nyx force-kills the running agent subprocess immediately
**And** the process exits without waiting for the episode to complete
**And** the in-progress task is left in `in_progress` state (or transitioned to `failed`)

> [!question] SPEC GAP
> The architecture does not describe the double-interrupt behavior or what task state is left behind on a force exit. Define: (a) whether double-interrupt is supported, (b) the state of the interrupted task, and (c) how the next `nyx run` should handle stale `in_progress` tasks from a previous forced exit.

---

## Story 5-E: Crash recovery (stale in_progress tasks)

### Scenario: Shift starts and finds a task stuck in in_progress from a previous crash

**Given** a previous shift crashed mid-episode leaving a task in `in_progress` state
**When** the operator runs `nyx run` again
**Then** Nyx detects the stale `in_progress` task at startup
**And** emits a `stale_task_detected` event (or equivalent)
**And** transitions the task to `failed` or re-queues it as `todo`
**And** the shift proceeds normally

> [!question] SPEC GAP
> The architecture mentions "state checkpointing and crash recovery" in the Orchestrator Core description (MILESTONE_1.md Step 11) but does not define the recovery policy. Define: (a) how stale `in_progress` tasks are detected, (b) whether they are retried or failed, and (c) whether this check happens at startup or lazily.
