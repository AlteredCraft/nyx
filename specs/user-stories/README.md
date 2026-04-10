# User Stories

Stories that describe how Nyx's workflows behave from the outside. They exist to validate and stress-test `system-architecture.md` — not to replace it.

**If you find a `SPEC GAP` marker, resolve it in `system-architecture.md` and delete the marker.**

## Personas

See [`personas.md`](personas.md) for full descriptions. Short form:

| ID | Name | One-liner |
|----|------|-----------|
| P1 | **Operator** | Developer who queues tasks, runs overnight shifts, reads morning reports |
| P2 | **Integrator** | Engineer who scripts around Nyx — consumes machine-readable output, wires up notifications |

## Format Conventions

### Gherkin

Stories use Gherkin (Given/When/Then) so that acceptance criteria are unambiguous and testable. Format:

```
**Given** [precondition]
**And** [additional precondition]
**When** [action]
**Then** [expected outcome]
**And** [additional outcome]
**But** [outcome that does NOT happen]
```

Each `Scenario` block maps to one test case. Scenarios are grouped under a user story header.

### SPEC GAP

When writing a scenario exposes an ambiguity or missing decision in `system-architecture.md`, it is marked inline:

```
> [!question] SPEC GAP
> Description of what is unspecified or ambiguous, and why it matters for the scenario above.
```

Gaps are intentional — the stories exist to surface them. Grep for `SPEC GAP` to find all open questions at once.

### Coverage

Each story file covers:
- **Happy path** — the expected successful flow
- **Alternate paths** — valid variations (e.g., optional flags, edge input)
- **Error/edge cases** — invalid input, missing state, failure modes

## Files

| File | Workflow |
|------|----------|
| [`personas.md`](personas.md) | Persona definitions |
| [`us-01-task-management.md`](us-01-task-management.md) | Queuing and inspecting tasks |
| [`us-02-shift-execution.md`](us-02-shift-execution.md) | Starting and running a full shift |
| [`us-03-episode-and-verification.md`](us-03-episode-and-verification.md) | Executing a task episode and verifying output |
| [`us-04-model-routing.md`](us-04-model-routing.md) | Routing tasks to model backends |
| [`us-05-termination.md`](us-05-termination.md) | Detecting termination conditions and shutting down |
| [`us-06-reporting.md`](us-06-reporting.md) | Reading shift reports |
| [`us-07-monitoring.md`](us-07-monitoring.md) | Watching a shift in progress |
