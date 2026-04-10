# US-04: Model Routing

**As an Operator (P1),** I want tasks automatically dispatched to the right model backend based on my routing config so that different kinds of work use appropriately capable (and priced) models without manual intervention.

---

## Story 4-A: Rule-based routing

### Scenario: Task matches a routing rule

**Given** `nyx.toml` contains:
```toml
[[routing.rules]]
task_type = "coding"
backend = "claude_cli"
model = "claude-opus-4-5"

[[routing.rules]]
task_type = "research"
backend = "claude_cli"
model = "claude-sonnet-4-5"
```
**And** a task with type `coding` is selected from the queue
**When** the model router evaluates the rules
**Then** it returns a `ModelAssignment` with `backend = "claude_cli"` and `model = "claude-opus-4-5"`
**And** a `task_routed` event is emitted with the task ID, matched rule index, and the resulting `ModelAssignment`
**And** the episode runner dispatches to the Claude CLI adapter using the assigned model

---

### Scenario: First matching rule wins when multiple rules could match

**Given** two rules both match task type `coding`, the first specifying `opus` and the second specifying `sonnet`
**When** the router evaluates the rules
**Then** it returns the `ModelAssignment` from the first matching rule
**And** the second matching rule is not evaluated

> [!question] SPEC GAP
> The architecture says "first-match-wins" but does not define whether rules are evaluated in the order they appear in `nyx.toml` or sorted by some other criterion. Specify that evaluation order equals the order of appearance in the config file.

---

### Scenario: Task type is case-sensitive in routing rules

**Given** a routing rule specifies `task_type = "Coding"` (capital C)
**And** a task has type `coding` (lowercase)
**When** the router evaluates the rules
**Then** the rule does not match
**And** the fallback or default is used instead

> [!question] SPEC GAP
> The architecture does not specify whether task type matching is case-sensitive. Define it explicitly. Case-insensitive matching is more forgiving but can mask inconsistencies in task definitions.

---

## Story 4-B: Default fallback routing

### Scenario: No rule matches — default backend is used

**Given** routing rules cover `coding` and `research`
**And** `nyx.toml` defines `[routing] default_backend = "claude_cli"` and `default_model = "claude-haiku-4-5"`
**And** the queue contains a task with type `maintenance`
**When** the router evaluates all rules and finds no match
**Then** it returns a `ModelAssignment` using the default backend and model
**And** a `task_routed` event is emitted with `matched_rule = null` indicating the fallback was used
**And** the episode runs normally using the default assignment

---

### Scenario: No rule matches and no default is configured

**Given** routing rules cover `coding` only
**And** no `default_backend` is set in `nyx.toml`
**And** the queue contains a task with type `research`
**When** the router finds no match and no default
**Then** a `routing_failed` event is emitted with the task ID and type
**And** the task transitions to `failed`
**But** the shift continues with the next task

> [!question] SPEC GAP
> The architecture does not specify whether a missing default backend is a startup error (validated at config load) or a per-task runtime error. If it is a startup error, the shift never begins. If it is runtime, individual tasks fail. Define the validation point.

---

## Story 4-C: Config validation at startup

### Scenario: Routing config references an unknown backend

**Given** a routing rule specifies `backend = "opencode"` but the OpenCode backend adapter is not available in M1
**When** Nyx loads the config
**Then** Nyx exits with a non-zero exit code
**And** the error message names the unsupported backend
**But** no shift starts

> [!question] SPEC GAP
> The architecture lists three backends (Claude CLI, Agent SDK, OpenCode) but M1 only implements Claude CLI. Define whether unknown backends cause a startup error or a per-task routing failure, and whether there is a registry of available backends that config validation can check against.

---

### Scenario: Routing config is empty

**Given** `nyx.toml` contains no routing rules and no default backend
**When** Nyx loads the config
**Then** Nyx either rejects the config at startup (if default is required) or succeeds with a warning

> [!question] SPEC GAP
> Is a routing section required in `nyx.toml`? Define whether Nyx can start with no routing config at all, and if so, what happens when the first task is dispatched.
