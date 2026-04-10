# US-03: Episode Execution and Verification

**As an Operator (P1),** I want each task to be run by an agent and its output independently verified against git so that I can trust the completed task list — not just what the agent claims.

---

## Story 3-A: Successful single-episode task

### Scenario: Agent completes task, HANDOFF verified, task marked done

**Given** a task with status `todo` is selected by the orchestrator
**And** the routing config assigns it to the Claude CLI backend
**When** the episode runner builds a prompt and dispatches it to the Claude CLI adapter
**And** the agent runs, modifies `src/auth.py`, and writes `HANDOFF.md` with `Status: done` and `src/auth.py` in the files list
**And** `git diff --name-only` returns `src/auth.py`
**Then** the verification engine emits a `handoff_verified` event with `status: done`
**And** the task transitions from `in_progress` to `done`
**And** the episode is recorded with start time, end time, backend, model, and cost
**And** the orchestrator selects the next task

> [!question] SPEC GAP
> What is the exact prompt format sent to the agent? The architecture says the episode runner "builds a prompt from the task definition" but does not specify the template: which fields are included (`title`, `description`, both?), what surrounding instructions are given, and whether there is a system prompt vs. a user turn. Define the prompt structure.

> [!question] SPEC GAP
> Is `HANDOFF.md` always expected at the repository root? The architecture does not specify the path. Define the canonical location.

> [!question] SPEC GAP
> Does `HANDOFF.md` from a prior episode get deleted before a new episode starts? If not, the agent might read stale handoff context. Define who owns `HANDOFF.md` cleanup and when it happens.

---

### Scenario: Verification runs git diff against the working tree, not staged changes

**Given** the agent has written files to disk but not staged them
**When** the verification engine checks for changes
**Then** `git diff --name-only` (unstaged) is used, not `git diff --cached`

> [!question] SPEC GAP
> The architecture says "git diff" but does not specify whether the comparison is against the index (staged), the working tree (unstaged), or both. Agents using the Claude CLI will likely write files without staging. Clarify the exact git command used in verification.

---

## Story 3-B: Multi-episode task

### Scenario: Agent signals in-progress — task continues to a second episode

**Given** an agent writes `HANDOFF.md` with `Status: in_progress`, files listed, and a non-empty `Next Steps` section
**And** `git diff --name-only` returns files that exactly match the claimed files
**When** the verification engine processes the handoff
**Then** it emits `handoff_verified` with `status: in_progress`
**And** the task remains in `in_progress` state
**And** the episode is recorded
**When** the orchestrator starts the next episode for the same task
**Then** the prompt incorporates the `Next Steps` from the previous `HANDOFF.md`

> [!question] SPEC GAP
> The architecture does not define how context from the previous `HANDOFF.md` is threaded into the next episode's prompt. Options include: appending the full prior HANDOFF.md, injecting only `Next Steps`, or relying on the agent to re-read the file from disk. Specify the mechanism.

> [!question] SPEC GAP
> Is there a maximum episode count per task? Without a cap, a misbehaving agent could keep reporting `in_progress` indefinitely, consuming budget. Define whether a per-task episode limit exists and what happens when it is reached.

---

### Scenario: Agent completes the task on the second episode

**Given** a task has one recorded episode with outcome `in_progress`
**When** the second episode runs and the agent writes `HANDOFF.md` with `Status: done`
**And** `git diff --name-only` matches the claimed files
**Then** the verification engine emits `handoff_verified` with `status: done`
**And** the task transitions from `in_progress` to `done`
**And** both episodes are recorded under the same task ID

---

## Story 3-C: Verification failure — HANDOFF.md missing

### Scenario: Agent produces no HANDOFF.md

**Given** the agent finishes running
**And** no `HANDOFF.md` exists at the expected path
**When** the verification engine checks for the handoff file
**Then** it emits a `handoff_missing` event with the task ID and episode ID
**And** the task transitions to `failed`
**But** Nyx does not modify the working directory

---

## Story 3-D: Verification failure — HANDOFF.md malformed

### Scenario: HANDOFF.md exists but cannot be parsed

**Given** `HANDOFF.md` exists but is missing the `## Files Modified` section
**When** the verification engine attempts to parse it
**Then** it emits a `handoff_malformed` event with the task ID, episode ID, and the specific parse error
**And** the task transitions to `failed`
**But** Nyx does not modify the working directory

> [!question] SPEC GAP
> The architecture lists the four required sections (`## Status`, `## Files Modified`, `## Summary`, `## Next Steps`) but does not define what "malformed" means precisely. Is a missing section always malformed? What if `## Status` has an unrecognised value? What if `## Files Modified` is present but empty? Define the parser's tolerance and what triggers `handoff_malformed` vs. proceeding with an empty files list.

---

## Story 3-E: Verification failure — ghost edits

### Scenario: Agent claims files it did not change

**Given** `HANDOFF.md` lists `src/auth.py` as modified with `Status: done`
**And** `git diff --name-only` returns an empty result
**When** the verification engine compares claims to diff
**Then** it emits a `handoff_discrepancy_ghost_edits` event with the task ID, episode ID, and the claimed file list
**And** the task transitions to `failed`
**But** Nyx does not modify the working directory

---

### Scenario: Agent claims some files but diff shows more

**Given** `HANDOFF.md` lists `src/auth.py` with `Status: done`
**And** `git diff --name-only` returns `src/auth.py` and `src/middleware.py`
**When** the verification engine compares claims to diff
**Then** it emits a `handoff_discrepancy_unclaimed_edits` event
**And** the event payload includes the claimed files and the full diff file list
**And** the task transitions to `failed`

> [!question] SPEC GAP
> The architecture treats unclaimed edits as a failure, but this is arguably a conservative policy — the agent did real work, it just failed to document it fully. Consider whether this should be `failed` or a new `needs_review` state (which requires the `qa` state from the enum). Document the rationale in the architecture.

---

## Story 3-F: Empty episode

### Scenario: Agent writes HANDOFF.md with Status done but makes no changes

**Given** `HANDOFF.md` has `Status: done` and an empty `## Files Modified` section
**And** `git diff --name-only` returns an empty result
**When** the verification engine processes this case
**Then** it emits an `empty_episode` event
**And** the task transitions to `failed`

> [!question] SPEC GAP
> An empty episode where `Status: in_progress` and diff is also empty is a distinct case — is it `empty_episode` or something else? The 6-case sub-failure matrix in the architecture specifies `empty_episode` for `Status=done` + empty diff. Clarify what happens when `Status=in_progress` + empty diff.
