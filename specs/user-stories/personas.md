# Personas

Two personas cover the known use cases for Nyx. Both are inferred from the repo; update this file if real users emerge with different profiles.

---

## P1 — Operator

> "I queue up work before I go to sleep and read the results over coffee."

**Who they are:** A solo developer or small-team engineer who uses Nyx to run AI-powered tasks autonomously overnight on their own machine. They are comfortable with the command line and basic config files, but they do not want to babysit the process.

**What they care about:**
- Tasks get run and completed correctly while they sleep
- Clear, readable morning reports that don't require log parsing
- Budget and time limits that prevent surprises
- A clean, safe shutdown — no corrupted state, no runaway processes

**What they do not want:**
- To debug cryptic failures with no context
- Tasks silently skipped or dropped without explanation
- An agent "completing" a task that made no real changes

**Primary interactions:** `nyx tasks add`, `nyx run`, `nyx tasks list`, `nyx tasks inspect`, morning shift log

---

## P2 — Integrator

> "I want Nyx's output wired into my existing tooling."

**Who they are:** An engineer who embeds Nyx into a larger workflow — CI pipelines, notification scripts, dashboards, or team tooling. They interact with Nyx programmatically rather than interactively.

**What they care about:**
- Machine-readable output (JSON exec summaries, structured exit codes)
- Stable interfaces that don't break between patch versions
- Reliable, deterministic behavior they can build assertions around
- The ability to query current shift state from a script

**What they do not want:**
- Output that changes format without notice
- A process that hangs or needs interactive input
- Exit codes that don't reflect actual success/failure

**Primary interactions:** `nyx run` (in scripts), `nyx status --json`, JSON exec summary files, exit codes, `nyx watch` piped to a formatter
