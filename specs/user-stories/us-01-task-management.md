# US-01: Task Management

**As an Operator (P1),** I want to add tasks to Nyx's queue and inspect their state so that I can control what gets worked on and verify tasks are correctly defined before a shift starts.

---

## Story 1-A: Add a task

### Scenario: Task added successfully

**Given** a valid `nyx.toml` is present in the current directory
**And** the routing config defines task type `coding`
**When** the operator runs `nyx tasks add --title "Refactor auth module" --type coding --priority high --description "Extract JWT validation into standalone middleware"`
**Then** the task is written to the SQLite database with status `todo`
**And** Nyx prints the new task's ID to stdout
**And** the task's `title`, `type`, `priority`, and `description` are stored exactly as provided
**And** a creation timestamp is recorded on the task record

> [!question] SPEC GAP
> Is a `task_added` event emitted to the event log? The architecture says every component emits events, but no `task_added` event type is listed in the schema. Clarify whether the task queue emits events on write operations, and if so what the schema looks like.

---

### Scenario: Task added with minimum required fields

**Given** a valid `nyx.toml` is present
**When** the operator runs `nyx tasks add --title "Quick fix" --type coding`
**Then** the task is created with status `todo`
**And** priority defaults to a configured or hardcoded default
**And** description defaults to empty string or null

> [!question] SPEC GAP
> Which fields are required at task creation? The architecture lists `title`, `type`, `priority`, and `description` as task fields but does not specify which are optional or what defaults apply. Define required vs. optional fields and their defaults.

---

### Scenario: Required field missing

**Given** a valid `nyx.toml` is present
**When** the operator runs `nyx tasks add --type coding` (no `--title`)
**Then** Nyx exits with a non-zero exit code
**And** an error message is printed to stderr naming the missing field
**But** no record is written to the database

---

### Scenario: Unknown task type

**Given** routing config defines types `coding` and `research`
**When** the operator runs `nyx tasks add --title "Deploy docs" --type deploy`
**Then** Nyx exits with a non-zero exit code
**And** an error message lists the valid task types
**But** no record is written to the database

> [!question] SPEC GAP
> Are task types validated at `add` time against the routing config, or are they free-form strings that are only validated at dispatch time? If validated at add time, Nyx needs to read the routing config during `tasks add`, coupling the CLI command to the config. Clarify the validation point and what "valid types" means when no routing config exists.

---

### Scenario: No config file present

**Given** no `nyx.toml` exists in the current directory
**When** the operator runs `nyx tasks add --title "Refactor" --type coding`
**Then** Nyx either proceeds (task types are free-form and config is not needed) or exits with a clear error

> [!question] SPEC GAP
> Does `nyx tasks add` require `nyx.toml` to be present? The task queue is a SQLite file that could exist independently of the config. Define whether task management commands require a valid config and where the database file is located when no config is present.

---

## Story 1-B: List tasks

### Scenario: List pending tasks

**Given** the task queue contains three tasks with status `todo` and one with status `done`
**When** the operator runs `nyx tasks list`
**Then** the three `todo` tasks are shown
**But** the `done` task is not shown
**And** each row includes: task ID, title, type, priority, and status
**And** tasks are ordered by priority (descending), then by creation time (ascending) within the same priority

> [!question] SPEC GAP
> The architecture does not define the execution ordering rule beyond "priority". Specify whether tasks of equal priority are FIFO by creation time, and whether there is a numeric or named priority scale (e.g., `low/normal/high` or `1–5`).

---

### Scenario: List all tasks including completed

**Given** the queue contains tasks in various states
**When** the operator runs `nyx tasks list --all`
**Then** tasks in all states (`todo`, `in_progress`, `done`, `failed`) are shown
**And** the status column makes each task's state visible

---

### Scenario: Empty queue

**Given** no tasks exist in the database
**When** the operator runs `nyx tasks list`
**Then** Nyx prints a human-readable empty-state message (e.g., "No pending tasks.")
**And** the exit code is 0
**But** no table or blank rows are printed

---

### Scenario: Integrator requests machine-readable output

**Given** the queue contains tasks
**When** the integrator runs `nyx tasks list --json`
**Then** Nyx prints a JSON array to stdout, one object per task
**And** each object includes all task fields
**And** the output is valid JSON

> [!question] SPEC GAP
> The architecture does not specify which CLI commands support `--json`. Define whether all read commands (`list`, `inspect`, `status`) support `--json`, or only specific ones.

---

## Story 1-C: Inspect a task

### Scenario: Inspect a task with no episodes

**Given** a task exists with ID `abc123` and status `todo`
**When** the operator runs `nyx tasks inspect abc123`
**Then** output shows all task fields: ID, title, description, type, priority, status, creation timestamp
**And** output indicates no episodes have run yet

---

### Scenario: Inspect a task with episode history

**Given** a task with ID `abc123` has been attempted twice (two episodes recorded)
**When** the operator runs `nyx tasks inspect abc123`
**Then** output shows the task fields
**And** each episode is shown with: episode number, start time, end time, backend, model, token cost, and outcome
**And** episodes are listed in chronological order

> [!question] SPEC GAP
> The architecture describes the `Episode` model but does not specify what "outcome" means at the episode level vs. at the task level. An episode can end while the task remains `in_progress`. Define what per-episode outcome values exist (e.g., `verified_in_progress`, `verified_done`, `failed_ghost_edits`, etc.).

---

### Scenario: Task ID not found

**Given** no task with ID `xyz999` exists in the database
**When** the operator runs `nyx tasks inspect xyz999`
**Then** Nyx exits with a non-zero exit code
**And** an error message is printed to stderr
