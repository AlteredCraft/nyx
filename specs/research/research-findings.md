---
title: "Night Shift AI Harness — Research Findings"
created: 2026-04-08
created_by: ~/.claude/skills/deep-research
topic: Building/customizing an AI harness for overnight autonomous task execution
status: research-complete
tags:
  - ai-harness
  - night-shift
  - autonomous-agents
  - docker-sbx
  - multi-model
  - orchestration
---

# Night Shift AI Harness — Research Findings

## Motivation

As a solo consultant and educator, my productive hours are the bottleneck. I spend daytime on high-value work — writing specs, teaching, creating content, reviewing output. But my MacBook sits idle overnight, and my task backlog grows faster than I can manually execute it. Coding tasks, research runs, vault maintenance, test generation — all of these can be specified during the day and executed autonomously while I sleep.

The goal is not "leave the computer on all night." It's the opposite: **run a bounded set of tasks for a set number of hours, then let the machine sleep.** No unnecessary power consumption, no runaway costs, no waking up to a mess. Wake up to PRs ready for review, research synthesized, and an exec summary of what happened.

This also serves as a forcing function for multi-model cost optimization. Frontier API models (Claude Opus, GPT-5) are powerful but expensive. Local models (Ollama Qwen, Devstral) are free but slower. An episodic orchestrator that can route between them — using local for cheap tasks, escalating to API for complex ones — turns overnight hours into high-leverage, low-cost productivity.

## Research Question

How to build a "night-shift" harness that queues AI tasks (coding, research, vault maintenance), runs them autonomously on a MacBook for a bounded number of hours using multiple models (Claude Code, Ollama, API models), sandboxed via Docker SBX, with git worktree isolation per task, then gracefully shuts down so the machine can sleep. Output: PRs, written files, summary logs, and an exec summary from the orchestrator.

---

## 1. What is "Night Shift" and why does it matter?

The "Night Shift" pattern has emerged as a recognized workflow in the AI-assisted development community in early 2026. The core premise: **human time is the bottleneck, not compute**. As [Jamon Holmgren articulates](https://jamon.dev/night-shift), "My time, energy, and 'human token usage' are highly constrained and expensive resources," while agent tokens are abundant and cheap.

The workflow separates human and AI work into distinct time periods. During the day, humans handle strategic work: gathering requirements, writing specs, reviewing output. At night (or whenever the human is away), agents autonomously execute queued tasks. You wake up to PRs, test results, and summary logs.

[OpenAI's "Harness Engineering" article](https://openai.com/index/harness-engineering/) formalized the conceptual framework: **humans design environments, specify intent, and build feedback loops; agents execute**. Their team built a million-line product with zero manually-written code, achieving 3.5 PRs per engineer per day, with single Codex runs routinely working for 6+ hours unattended. The key insight: "give Codex a map, not a 1,000-page instruction manual" — use AGENTS.md as a table of contents, not an encyclopedia.

The underlying execution model draws from [Geoffrey Huntley's Ralph Wiggum Loop](https://ghuntley.com/loop/) — autonomous agents performing one task per loop iteration, with fresh context each time. Huntley's insight: software becomes "clay on the pottery wheel" where problems trigger a loop restart rather than debugging a degraded session. OpenAI's harness engineering article [directly references this pattern](https://openai.com/index/harness-engineering/). (See Appendix A for full treatment of the Ralph Loop and episodic execution.)

Multiple teams have independently converged on this pattern:
- [Hamy's orchestrator](https://hamy.xyz/blog/2026-02_ai-orchestrator-overnight) completed 15 tasks across 10 hours overnight using an 8-phase engineering pipeline
- [ZELTREX's Night Shift](https://zeltrex.com/blog/night-shift-ai-writes-code-while-you-sleep) runs task dispatch every 2 hours, completing 8-12 tasks nightly
- [Koan](https://alexissukrieh.com/blog/asynchronous-agentic-coding-the-ai-workflow-no-one-is-talking-about/) operates via GitHub issues, delivering ready-to-review branches by morning

---

## 2. The Six Death Spirals of Overnight Agents

Before designing a harness, it's critical to understand why naive approaches fail. The [Nightcrawler article on DEV.to](https://dev.to/thebasedcapital/why-your-overnight-ai-agent-fails-and-how-episodic-execution-fixes-it-2g50) documents six failure modes that are now well-understood:

1. **Context Cliff**: After 30-60 minutes, the model's effective context fills. It re-reads files, contradicts earlier decisions, and begins undoing its own work.
2. **Hallucinated Handoff**: The agent claims tasks are complete that were never actually committed. Self-assessment diverges from git reality.
3. **Budget Inferno**: Uncontrolled API costs as the agent loops on hard problems. A single multi-turn loop can burn $200 overnight.
4. **Infinite Retry Loop**: Agent cycles between two broken states — fix A breaks B, fix B breaks A — for hours with zero progress.
5. **Silent Crash**: Process dies at 2 AM (OOM, network timeout, sleep event) leaving half-finished work with no record.
6. **Drift Spiral**: Agent gradually abandons its mission, adding unrequested features and refactoring code it shouldn't touch.

Each of these has direct implications for harness architecture (see Section 5). The consensus solution — **episodic execution** with bounded episodes and structured handoffs — directly addresses all six. Rather than fighting context degradation in a continuous session, the orchestrator runs fresh-context episodes and uses the [Ralph Loop pattern](https://ghuntley.com/loop/) to iterate reliably. (See Appendix A for the full episodic execution deep-dive.)

---

## 3. Existing Implementations — Landscape Assessment

### Orbit Nightshift (open-source, Python)
- **URL**: [orbit.build/blog](https://www.orbit.build/blog/introducing-nightshift-autonomous-overnight-agent)
- **Published**: April 6, 2026 (2 days ago)
- **Architecture**: Two-loop daemon — a Hardening Loop (discovers issues via 7 strategies: security, test coverage, performance, etc.) and a Feature Builder Loop (decomposes features into buildable waves). Five rotating daemon roles (Builder, Reviewer, Overseer, Strategist, Achiever).
- **Guardrails**: 7 verification stages after each cycle, blocked file protection, anti-tunnel-vision enforcement, self-modification guards, watchdog with rate-limited restart.
- **Output**: Markdown shift log, machine-readable JSON state, runner log, isolated branch with atomic commits.
- **Model support**: Agent-pluggable via adapters (Claude Code, Codex).
- **Assessment**: Architecturally sophisticated but brand new (2 GitHub stars). **Best used as a requirements/design reference, not a dependency.** Its verification stages and role rotation patterns are worth studying.

### Nightcrawler (~500 LOC TypeScript)
- **URL**: [DEV.to article](https://dev.to/thebasedcapital/why-your-overnight-ai-agent-fails-and-how-episodic-execution-fixes-it-2g50)
- **Architecture**: Episodic execution with structured handoffs. Bounded episodes where each reads the previous HANDOFF.md, verifies claims via `git log`/`git diff`, works on one task, writes a new handoff.
- **Termination**: 8 conditions — human stop flag, agent indicates done/blocked, episode limit (24), duration limit (12h), budget limit ($50), error threshold (10), fatal error, diminishing returns (< 0.5 tasks/episode for 3 consecutive).
- **Crash recovery**: macOS launchd supervision with auto-restart, 30-second throttle, sleep/wake handling.
- **Key insight**: Task immutability — `tasks.json` is extracted from mission checkboxes and agents can only flip tasks `false` to `true`. Cannot delete, rename, reorder, or add tasks. Prevents agents from redefining missions to match what they accomplished.
- **Assessment**: Lean, well-reasoned. The episodic model and 8 termination conditions are the most portable design patterns in this space.

### Happy Cog Nightshift (batch processing framework)
- **URL**: [happycog.com](https://www.happycog.com/insights/introducing-nightshift-a-batch-processing-framework-for-ai-agents)
- **Architecture**: 3-agent role separation — Manager (orchestrates, delegates), Dev (executes, self-validates), QA (independent verification, read-only).
- **Key innovation**: Self-improving instructions. The Dev agent refines task definitions during execution, creating a learning loop where the system gets progressively faster through the batch queue.
- **Task queue**: CSV-based persistent queue with state machine (`todo -> in_progress -> qa -> done`). Supports pause/resume.
- **Assessment**: Excellent for batch/repetitive tasks (migrations, test generation). The Manager/Dev/QA separation and self-improving instructions are worth adopting.

### Jamon Holmgren's Night Shift (workflow, not a tool)
- **URL**: [jamon.dev/night-shift](https://jamon.dev/night-shift)
- **Philosophy**: Day shift = human spec writing. Night shift = autonomous agent execution (12+ hours). Morning = human review (2-4 hours).
- **Configuration**: `AGENT_LOOP.md` (workflow process), `AGENTS.md` (150-line router), `REVIEW_PERSONAS.md` (6 personas: Designer, Architect, Domain Expert, Code Expert, Performance Expert, Human Advocate).
- **Results**: 5x faster development velocity after one month of iteration.
- **Key insight**: "Automated testing is incredibly important. This WILL NOT WORK if you don't have a super robust end-to-end testing harness."
- **Assessment**: The most mature workflow description. Not a tool you run, but the design philosophy your tool should implement.

### Hamy's AI Orchestrator
- **URL**: [hamy.xyz](https://hamy.xyz/blog/2026-02_ai-orchestrator-overnight)
- **Architecture**: State machine with 8-phase pipeline (Triage -> Research -> PRD -> Tech Research -> Design -> Spec -> Build -> Review). Fresh agents per phase to avoid context degradation.
- **Performance**: 15 tasks in 10 hours, ~$90 in tokens.
- **Key insight**: "It's okay to sacrifice speed for quality, considering we want this to be run fully autonomously." Each phase outputs to a file, making it model-agnostic.
- **Assessment**: The phase-based pipeline with file-based inter-phase communication is a strong pattern for model-agnostic design.

---

## 4. Key Infrastructure Components

### 4a. Docker SBX — Sandboxing

[Docker Sandboxes](https://www.docker.com/blog/docker-sandboxes-run-agents-in-yolo-mode-safely/) are purpose-built for this use case. Key facts from [multiple](https://www.ajeetraina.com/how-i-sandboxed-my-ai-coding-agent-using-docker-sandboxes/) [sources](https://blog.codeminer42.com/everything-you-need-to-know-about-docker-ai-sandboxes/):

- **MicroVM isolation** (not just containers) — each sandbox gets its own kernel via macOS `virtualization.framework`. Hypervisor-level, not namespace-level.
- **Private Docker daemon** per sandbox — agents can build images and run containers inside the sandbox without accessing host Docker.
- **YOLO mode safely**: "Agents need a true bounding box: constraints defined before execution. Inside that box, the agent should be able to move fast." ([Docker blog](https://www.docker.com/blog/docker-sandboxes-run-agents-in-yolo-mode-safely/))
- **Native agent support**: Claude Code, Codex, Gemini CLI, OpenCode, Kiro. Explicitly supports NanoClaw and OpenClaw.
- **Installation**: `brew install docker/tap/sbx` — standalone, doesn't require Docker Desktop.
- **Usage**: `docker sandbox run claude ~/projects/myrepo`
- **Network/filesystem controls** configurable per sandbox.

**Alternatives**: [Agent Safehouse](https://themenonlab.blog/blog/agent-safehouse-macos-kernel-sandbox-ai-agents) uses macOS `sandbox-exec` (Seatbelt) for kernel-level enforcement without Docker overhead. [jai](https://jai.scs.stanford.edu/) from Stanford's Secure Computer Systems group uses Linux namespaces with copy-on-write overlays — one command, no setup.

**Sandbox Comparison Matrix:**

| Dimension                 | Docker SBX                                               | Agent Safehouse                                        | Stanford jai                                              |
| ------------------------- | -------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------- |
| **Isolation level**       | Hypervisor (microVM, own kernel)                         | Kernel (macOS Seatbelt sandbox-exec)                   | Namespace (Linux mount/user namespaces)                   |
| **Platform**              | macOS, Windows, Linux                                    | macOS only                                             | Linux only                                                |
| **Setup**                 | `brew install docker/tap/sbx`                            | Single shell script, zero deps                         | Single command (`jai claude`)                             |
| **Agent support**         | Claude Code, Codex, Gemini CLI, OpenCode, Kiro, NanoClaw | Any agent (wraps command)                              | Claude, Codex, Cursor                                     |
| **Docker-in-Docker**      | Yes (private daemon per sandbox)                         | No                                                     | No                                                        |
| **Filesystem model**      | Mounted project workspace only                           | Deny-first allowlist (project dir r/w, toolchains r/o) | Copy-on-write overlay (CWD r/w, home overlaid, rest r/o)  |
| **Network controls**      | Configurable per sandbox                                 | No (pass-through)                                      | Not documented                                            |
| **Credential protection** | Isolated from host                                       | Denies ~/.ssh, ~/.aws by default                       | Home dir hidden in "bare" mode                            |
| **Overhead**              | Moderate (microVM startup)                               | Minimal (kernel enforcement)                           | Minimal (namespace creation)                              |
| **Security posture**      | Strong (hypervisor boundary)                             | Medium (OS sandbox, not VM)                            | Light ("casual sandbox, not a promise of perfect safety") |
| **Unattended/YOLO mode**  | Explicitly designed for it                               | Compatible                                             | Compatible                                                |
| **Requires Docker**       | Standalone (no Docker Desktop)                           | No                                                     | No                                                        |

**Assessment for Night Shift Harness**: Docker SBX is the strongest choice for overnight unattended execution — hypervisor-level isolation with native agent support and configurable network/filesystem controls. Agent Safehouse is a lighter alternative for macOS-only setups where Docker overhead isn't wanted. Stanford jai is Linux-only, ruling it out for MacBook use, but its copy-on-write overlay model is worth studying if the harness ever targets Linux servers.

### 4b. macOS Power Management


The simplest approach per the [caffeinate guide](https://www.theapplegeek.co.uk/blog/caffeinate) and [WebSearch findings](https://ss64.com/mac/caffeinate.html):

```bash
# Keep Mac awake for exactly 6 hours, then let it sleep
caffeinate -s -t 21600 ./night-shift-orchestrator
```

The `-s` flag is the key: it keeps the system awake **only while the child process is active**. If the orchestrator finishes early, caffeinate stops early. If it runs the full 6 hours, caffeinate enforces the cutoff and the Mac sleeps.

For more robust process supervision, [Nightcrawler's launchd approach](https://dev.to/thebasedcapital/why-your-overnight-ai-agent-fails-and-how-episodic-execution-fixes-it-2g50) adds:
- Automatic restart on crash (30-second throttle)
- Sleep/wake lifecycle integration
- Hard timeout enforcement
- Log persistence via stdout/stderr redirection
- PID-based lockfile for duplicate prevention

**Recommendation**: Use `caffeinate -s -t <seconds>` as the outer wrapper (simple, reliable, self-terminating), with launchd as an optional upgrade for crash recovery if the orchestrator proves fragile.

### 4c. Claude Code Headless Mode

Claude Code's programmatic interface is mature per [multiple](https://claudelab.net/en/articles/claude-code/claude-code-bare-flag-headless-automation-guide) [guides](https://docs.bswen.com/blog/2026-03-13-claude-code-headless-mode) and [official docs](https://code.claude.com/docs/en/best-practices):

```bash
# Basic headless execution
claude -p "Implement feature X" --output-format json

# Bare mode (skip hooks, LSP, plugins — ~14% faster for batch)
claude -p "Run tests" --bare --output-format json

# With tool restrictions
claude -p "Review code" --allowedTools "Read,Glob,Grep,Bash(git log:*)"

# With permission mode
claude --permission-mode acceptEdits -p "Add type annotations"

# Session resumption
claude --session-id abc123 -p "Continue previous work"

# Hard timeout
timeout 3600 claude -p "Build feature" --bare
```

Key capabilities for orchestration:
- JSON output with cost tracking, duration, token usage
- Session IDs for multi-turn work within episodes
- `--allowedTools` / `--disallowedTools` for per-task permissions
- `--bare` flag skips all initialization overhead (hooks, LSP, plugins, skills)

### 4d. Multi-Model Routing

**This is the most critical architectural decision for avoiding vendor coupling.**

There's an important distinction between two layers of multi-model support:

**Layer 1: Model API routing** (which LLM answers a prompt) — This is the "chat completion" layer. Options include:

- **[OpenRouter](https://openrouter.ai/)**: Single endpoint, 500+ models from 60+ providers, OpenAI-compatible API. Auto Exacto routing (March 2026) optimizes tool-calling requests automatically. Free-tier models available. Pay-per-token with transparent pricing. No self-hosting required.
- **[OpenCode Zen](https://opencode.ai/zen)**: Curated set of 40+ tested/benchmarked models for coding agents specifically. Includes free models (Big Pickle, Qwen3.6 Plus Free, Nemotron 3 Super Free). Bring-your-own-key support alongside Zen models. Pay-as-you-go.
- **[LiteLLM](https://github.com/BerriAI/litellm)** (~40k stars): Self-hosted Python proxy, 140+ providers, YAML routing config with fallback chains and load balancing. Adds a local process but gives full control over routing logic and cost tracking.
- **Ollama direct**: Local models (Qwen, Devstral, Llama) via OpenAI-compatible API at `localhost:11434`. Zero cost, zero latency to API, full privacy.

**Layer 2: Agentic execution** (which harness runs the task) — This is fundamentally different from chat completion. An agentic coding backend needs to read files, run commands, manage git, and iterate autonomously. Options:

- **[Anthropic Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)** (formerly Claude Code SDK): Can run headless, supports subagents with isolated context windows, reads/writes files, runs tests. Model-flexible via `ANTHROPIC_BASE_URL` — can point at Ollama or OpenRouter for non-Anthropic models. This is the most mature agentic SDK.
- **Claude Code CLI** (`claude -p --bare`): Headless mode with JSON output, tool restrictions, budget tracking. Tightly coupled to Anthropic models but battle-tested for autonomous execution.
- **[OpenCode](https://opencode.ai/docs/agents/)**: Built-in agent teams that can mix models from different providers in the same team. [Oh My OpenAgent (OMO)](https://a2a-mcp.org/blog/what-is-oh-my-openagent) adds a three-layer orchestration system (Planning/Orchestration/Execution) with 10+ specialized agent roles and provider-agnostic task routing.

[Model routing research](https://zylos.ai/research/2026-03-02-ai-agent-model-routing) shows **40-85% cost reduction** while maintaining 90-95% quality by routing appropriately.

**Recommended approach for the harness**: Separate the two layers cleanly.
- For **model API routing**: Use OpenRouter as the cloud gateway (broadest model access, no self-hosting) + Ollama for local models. This avoids running a LiteLLM proxy process while still getting multi-provider access.
- For **agentic execution**: Use the Anthropic Agent SDK as the primary backend (it can target any OpenAI-compatible endpoint via base URL override, including OpenRouter and Ollama). Consider OpenCode/OMO as a secondary backend for tasks that benefit from multi-agent teams.
- The orchestrator dispatches tasks to the appropriate agentic backend + model combination based on task type and cost constraints.

[NanoClaw's approach](https://github.com/qwibitai/nanoclaw) validates this pattern: agents run inside containers using the Claude Agent SDK, but support any Claude-compatible endpoint via `ANTHROPIC_BASE_URL`. This enables Ollama/OpenRouter/Fireworks as drop-in alternatives without changing the agentic execution layer.

### 4e. Git Worktree Management

Git worktrees have become the [dominant isolation primitive](https://zylos.ai/research/2026-02-22-git-worktree-parallel-ai-development) for parallel AI agents. Key findings from [multiple](https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution) [sources](https://www.gitworktree.org/cases/parallel-ai-agents):

- Each agent gets its own working directory and git index while sharing a single `.git` object store
- No disk waste from full clones, no file-level conflicts between agents
- Claude Code has native worktree support (the `Agent` tool's `isolation: "worktree"` parameter)
- [agent-worktree](https://github.com/nekocode/agent-worktree) (131 stars, Rust) provides CLI tooling for managing agent worktrees

**Workflow pattern** from [workmux](https://raine.dev/blog/git-worktrees-parallel-agents/):
1. Orchestrator creates worktrees per task: `git worktree add ../task-001 -b nightshift/task-001`
2. Agent executes within the worktree directory
3. On completion, orchestrator verifies build/tests in the worktree
4. Successful worktrees get PR'd or merged; failed ones get logged and cleaned up

---

## 5. Architectural Requirements for the Night Shift Harness

Synthesizing across all sources, here are the requirements a harness must satisfy:

### Core Loop
1. **Task Queue**: Persistent, immutable task definitions (prevent agents from redefining missions). Support coding tasks, research tasks, and maintenance tasks.
2. **Episodic Execution**: Bounded episodes (not infinite sessions) with structured handoffs between them. Each episode: read handoff -> verify previous claims via git -> work on task -> write new handoff.
3. **Model Router**: Assign tasks to appropriate backends based on complexity, cost, and capability. Route via OpenRouter (cloud) + Ollama (local) with orchestrator-level dispatch logic.
4. **Worktree Isolation**: One git worktree per task. Agent operates in its worktree, orchestrator manages lifecycle.
5. **Verification Loop**: After each episode/task, run build, test, lint. Failed verification = revert or log for human review.

### Guardrails (from Nightcrawler + Orbit Nightshift)
6. **8 Termination Conditions**: Human stop flag, agent done/blocked, episode limit, duration limit, budget limit, error threshold, fatal error, diminishing returns.
7. **Blocked Paths/Files**: Configurable deny-list (lockfiles, infrastructure, credentials).
8. **Budget Enforcement**: Per-task and per-session spending caps.
9. **Anti-Drift**: Task immutability + cross-category balance (anti-tunnel-vision from Orbit).

### Sandboxing
10. **Docker SBX** (primary): Each agent task runs inside a Docker sandbox with filesystem/network controls. Strongest isolation for overnight unattended execution. Agent Safehouse as lighter macOS-only alternative if Docker overhead proves problematic. (See comparison matrix in Section 4a.)
11. **Credential Isolation**: Agents never hold raw API keys; inject at request time (NanoClaw pattern). Restrict child process environment variables to required-only.

### Power Management
12. **Caffeinate Wrapper**: `caffeinate -s -t <seconds>` around the orchestrator process.
13. **Graceful Shutdown**: On time limit, finish current episode, write handoff, clean up worktrees.

### Output & Reporting
14. **Per-Task Artifacts**: Worktree branch, commit log, test results, agent logs.
15. **Shift Log**: Machine-readable (JSON) + human-readable (Markdown) summary of all work.
16. **Executive Summary**: High-level report: tasks attempted, completed, failed, blocked, costs, recommendations.
17. **PR Creation**: Successful tasks auto-create draft PRs for morning review.

### Multi-Model
18. **Backend Abstraction**: Common task interface that can dispatch to Anthropic Agent SDK (targeting OpenRouter, Ollama, or Anthropic direct), Claude Code CLI (`-p`), or OpenCode agent teams. Mistral Vibe's open-source harness architecture (skills system, programmatic mode, custom agents) is a design reference for how to build this abstraction — not a target backend.
19. **Task-Model Routing**: Configuration that maps task types/complexity to model+backend combinations. E.g., vault cleanup -> Ollama Qwen 32B via Agent SDK; complex coding -> Claude Opus via CC CLI; research -> Claude Sonnet via Agent SDK + OpenRouter.
20. **Fallback Chains**: If primary model fails or hits diminishing returns, escalate to a more capable model for that specific task.

---

## 6. Build vs. Buy vs. Fork Assessment

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Build from scratch** | Full control, tailored to your stack (Obsidian vault, CC skills, multi-model). No dependency on nascent projects. | Most effort upfront. Must solve episodic execution, handoffs, verification, reporting from scratch. | **Recommended approach**, using patterns from existing tools. |
| **Fork Nightcrawler** | Lean (~500 LOC TS), well-designed episodic model, launchd integration. | TypeScript (may not be your preferred stack), tightly coupled to Claude Code `-p`, no multi-model support. | Good design reference. Too Claude-coupled for your multi-model requirement. |
| **Fork Orbit Nightshift** | Most feature-complete architecture. Python. Model-agnostic design. | Brand new (2 stars), unknown code quality, complex (two loops, five roles). Risk of inheriting undiscovered bugs. | **Best requirements document**, not a production dependency. |
| **Adopt NanoClaw** | Container isolation, Claude SDK with Ollama support, scheduled tasks. | Messaging-oriented (channels/groups), not task-queue oriented. Would need significant reshaping. | Learn from its credential isolation and container patterns. |
| **Use Claude Code triggers/schedule** | Zero build effort. Native CC integration. | Couples entirely to CC. No multi-model. No worktree orchestration. No budget controls. | Insufficient for requirements. |

**Verdict**: Build a custom orchestrator, heavily informed by:
- **Nightcrawler's** episodic execution model + 8 termination conditions + task immutability
- **Orbit Nightshift's** verification stages + shift log format + role rotation
- **Happy Cog's** Manager/Dev/QA agent separation + self-improving instructions
- **OpenAI's** progressive disclosure + repo-as-knowledge-base philosophy
- **NanoClaw's** credential isolation + container adapter patterns

---

## 7. Proposed Architecture Sketch

### Inter-Process Communication

How do the orchestrator, agents, and verification processes talk to each other? Research from [Clord](https://clord.dev/blog/file-based-ai-coordination/) and [Zylos](https://zylos.ai/research/2026-02-26-safe-ipc-patterns-ai-agent-toolchains) converges on a clear answer for this use case:

**File-based coordination is sufficient — and preferred — for sequential episodic execution.**

The orchestrator runs episodes sequentially (or in parallel across worktrees, but each episode is a self-contained subprocess). There is no need to interrupt an agent mid-episode. The orchestrator:
1. Writes the episode prompt + handoff to disk
2. Spawns the agent as a subprocess (`spawn(..., { shell: false })`)
3. Waits for the subprocess to exit
4. Reads the agent's output (HANDOFF.md, STATE.json, git changes)
5. Decides what to do next

This is the [file-based coordination pattern](https://clord.dev/blog/file-based-ai-coordination/): "Every programming language, every AI model, every tool on earth knows how to read and write files." The key benefits for overnight execution:
- **Debuggable**: If something goes wrong, inspect the files. No log parsing or event replay.
- **Resumable**: Partial output persists on disk. Crash recovery reads the last checkpoint.
- **Auditable**: Complete workflow history is preserved in the filesystem.

**Where files aren't enough**:
- **Subprocess stdout/stderr**: For real-time cost tracking and progress monitoring, the orchestrator should capture agent stdout via pipes (not files). Use [NDJSON framing](https://zylos.ai/research/2026-02-26-safe-ipc-patterns-ai-agent-toolchains) — each line is a complete JSON object. Claude Code's `--output-format stream-json` already outputs this way.
- **Stop flag**: The human stop signal (`touch STOP`) is a sentinel file — the orchestrator checks for it between episodes. No need for signals or sockets.
- **Budget/timer**: Internal to the orchestrator process. No IPC needed.

**Security note**: When spawning agent subprocesses, always use direct `execve` (argument arrays, `shell=false`), never shell interpolation. Pass content via stdin, not argv. Restrict child environment variables to required-only — agents should not inherit API keys they don't need. See [Zylos IPC patterns](https://zylos.ai/research/2026-02-26-safe-ipc-patterns-ai-agent-toolchains) for the full threat model.

**Bottom line**: The night-shift harness is a sequential batch processor with file-based state, not a real-time distributed system. Files for state + handoffs, pipes for streaming output, sentinel files for control signals. No message queues, no WebSockets, no shared databases needed.

```
                    caffeinate -s -t <N>
                           |
                    [Orchestrator Daemon]
                     |        |       |
              Task Queue   Budget   Timer
              (immutable)  Tracker  (graceful
                                    shutdown)
                           |
                    [Episode Runner]
                     |            |
              Read HANDOFF.md    Verify via git
                     |
              [Model Router]
              /      |       \
         Claude    Ollama    Agent SDK
         Code -p   (local)   + OpenRouter
              \      |       /
          [Docker SBX Sandbox]
                     |
            [Git Worktree per Task]
                     |
              [Verification]
              build / test / lint
                     |
              Pass?  --yes--> Commit + PR
                     --no---> Revert + Log
                     |
              Write HANDOFF.md
                     |
              Check 8 Termination Conditions
                     |
              Continue? --yes--> Next Episode
                       --no---> Write Shift Log
                                + Exec Summary
                                + Sleep
```

---

## 8. Open Questions for Implementation Planning

1. **Language choice**: The orchestrator needs to manage subprocesses, parse JSON, handle git, and run HTTP calls to LiteLLM/Ollama. Python is the path of least resistance (LiteLLM is Python, Docker SDK is Python, rich ecosystem). Go or Rust would be better for a daemon that runs for hours but add friction. The existing implementations split: Orbit Nightshift = Python, Nightcrawler = TypeScript, agent-worktree = Rust.

2. **Model routing layer**: OpenRouter (cloud gateway, no self-hosting) + Ollama (local) appears simpler than running a LiteLLM proxy. The Anthropic Agent SDK's base URL override means the agentic layer can target either. OpenCode Zen is worth evaluating for curated coding-model access with cost optimization. Key decision: how much routing intelligence lives in the orchestrator vs. delegated to an external gateway?

3. **Task definition format**: Leaning toward **SQLite** with an abstraction interface and CLI for task management. SQLite gives concurrent access, state machine tracking (`todo -> in_progress -> qa -> done`), query-based task selection (priority, type, model affinity), and budget tracking — all without an external database process. The NanoClaw pattern validates this: single-file database, simple schema, CLI-friendly. The abstraction layer ensures the orchestrator core isn't coupled to SQLite directly, enabling future migration if needed.

2. **How to handle vault maintenance tasks**: Obsidian vault work doesn't need Docker sandboxing or git worktrees. It needs direct filesystem access. Consider a separate "lightweight" execution path for non-coding tasks.

3. **Cost model**: Claude Opus runs ~$15/M input, $75/M output. A 6-hour session could cost $50-150. Ollama Qwen 32B on a MacBook Pro runs at ~15-20 tok/s with zero marginal cost. The routing decisions have real financial implications overnight.

---

## 9. Recommended Next Steps

1. **Write a spec** for the orchestrator using the requirements in Section 5 as a starting point
2. **Prototype the episodic loop** — this is the core: read handoff, dispatch to model, verify, write handoff, check termination
3. **Start with `caffeinate -s -t` + Claude Code `-p --bare`** in a single worktree as the MVP
4. **Add multi-model routing** (OpenRouter + Ollama + Agent SDK) as the second milestone
5. **Add Docker SBX sandboxing** as the third milestone
6. **Add parallel worktrees** as the fourth milestone
7. **Build the shift log / exec summary** reporter throughout

---

## Appendix A: Episodic Execution & The Ralph Wiggum Loop

### Origin and Attribution

The Ralph Wiggum Loop was created by [Geoffrey Huntley](https://ghuntley.com/loop/), who introduced the concept of treating software development as iterative agent loops rather than linear construction. The name comes from The Simpsons — the agent, like Ralph, cheerfully keeps going regardless of obstacles. OpenAI's harness engineering article directly [references the Ralph Wiggum Loop](https://openai.com/index/harness-engineering/) as a pattern they use internally.

Huntley's core principle: **"Ralph works autonomously in a single repository as a single process that performs one task per loop."** Software becomes malleable — like clay on a pottery wheel — where problems trigger a loop restart that addresses failures systematically rather than trying to debug a degraded continuous session.

The [Dev Interrupted podcast](https://linearb.io/dev-interrupted/podcast/inventing-the-ralph-wiggum-loop) with Huntley goes deeper into the economics: at roughly $10.42/hour in compute, simple bash loops with deterministic context allocation are "fundamentally changing the unit economics of code." An [open-source scaffold](https://github.com/agenticloops-ai/ralph-loop) exists for Claude Code, though building your own is the point.

### What Is Episodic Execution?

Episodic execution is the architectural pattern that emerges when you apply the Ralph Loop philosophy to overnight/unattended operation. The core insight: **context windows are finite, but work is not. Build around that.**

Instead of one long session that degrades over hours, you run a series of **bounded episodes** with **structured handoffs** between them. Each episode gets a fresh context window — full cognitive resources — and reads the previous episode's handoff to pick up where it left off.

```
Episode 1 [fresh 200K context] → works → writes HANDOFF.md
    ↓ orchestrator verifies via git, checks termination conditions
Episode 2 [fresh 200K context] → reads HANDOFF.md → works → writes HANDOFF.md
    ↓ orchestrator verifies via git, checks termination conditions
Episode 3 [fresh 200K context] → reads HANDOFF.md → works → writes HANDOFF.md
    ↓ ...continues until termination condition met
```

### Why This Matters for Multi-Model / Local Models

This is where episodic execution becomes critical for the night-shift harness. A local model (Ollama Qwen 32B, Devstral, etc.) running on a MacBook has:
- **Smaller effective context** than frontier API models
- **Lower single-pass capability** — may need 5 episodes to accomplish what Claude Opus does in 1
- **Zero marginal cost** — those 5 episodes cost $0 in API fees

The episodic model makes this a **routing optimization problem, not an architectural problem**. The orchestrator doesn't care whether a task took 1 episode or 5 — it checks the same termination conditions and verifies the same handoff against git either way. The model router decides:

| Task Type | Frontier (API) | Local (Ollama) | Trade-off |
|-----------|---------------|----------------|-----------|
| Complex refactor | 1-2 episodes, ~$3-5 | 5-8 episodes, $0 | Time vs. cost |
| Test generation | 1 episode, ~$1 | 2-3 episodes, $0 | Local usually fine |
| Research/synthesis | 1 episode, ~$2-4 | Often insufficient | API preferred |
| Lint fixes, formatting | 1 episode, ~$0.50 | 1 episode, $0 | Always use local |
| Vault maintenance | 1 episode, ~$0.50 | 1-2 episodes, $0 | Local preferred |

The budget tracker across episodes enables a **cost-aware routing strategy**: start with local models, escalate to API when the diminishing returns detector fires (< 0.5 tasks/episode for 3 consecutive episodes on local), then fall back to a frontier model for that specific task.

### The Orchestration Loop (Pseudocode)

The core loop synthesized from [Nightcrawler](https://dev.to/thebasedcapital/why-your-overnight-ai-agent-fails-and-how-episodic-execution-fixes-it-2g50), [the Ralph Loop](https://ghuntley.com/loop/), and [Hamy's orchestrator](https://hamy.xyz/blog/2026-02_ai-orchestrator-overnight):

```python
def run_night_shift(config):
    state = load_or_init_state()
    
    while True:
        # 1. Check 8 termination conditions
        cont, reason = should_continue(state, config)
        if not cont:
            write_shift_log(state, reason)
            write_exec_summary(state)
            break
        
        # 2. Select next task from queue
        task = select_next_task(state.task_queue)
        if not task:
            write_shift_log(state, "queue_empty")
            break
        
        # 3. Route task to appropriate model
        model = route_task(task, state.budget_remaining, config.routing_rules)
        
        # 4. Ensure worktree exists for this task
        worktree = ensure_worktree(task)
        
        # 5. Build episode prompt
        prompt = build_episode_prompt(
            mission=task.spec,
            handoff=read_handoff(worktree) if handoff_exists(worktree) else None,
            git_context=get_git_context(worktree),
            task_tracker=state.task_queue  # immutable
        )
        
        # 6. Run one bounded episode in sandbox
        result = run_episode(
            model=model,
            prompt=prompt,
            worktree=worktree,
            sandbox=config.sandbox,  # Docker SBX config
            timeout=config.episode_timeout
        )
        
        # 7. Verify claims against git
        verify_handoff(worktree, result)
        
        # 8. Run verification (build/test/lint)
        if verify_build(worktree):
            commit_work(worktree, task)
            if task_complete(task, worktree):
                create_draft_pr(worktree, task)
                mark_task_done(state, task)
        else:
            revert_episode(worktree)
            state.errors.total += 1
        
        # 9. Update state, checkpoint
        state.budget_spent += result.cost
        state.current_episode += 1
        state.episode_history.append(result.summary)
        checkpoint_state(state)
```

### The 8 Termination Conditions

Before each episode, evaluated in order:

```python
def should_continue(state, config):
    # 1. Human stop flag — touch a file to kill it
    if Path(config.stop_flag_path).exists():
        return False, "human_stop"
    
    # 2. Agent says done or blocked
    if not state.termination_check.should_continue:
        return False, state.termination_check.reason
    
    # 3. Episode limit (default: 24)
    if state.current_episode >= config.max_episodes:
        return False, "episode_limit"
    
    # 4. Duration limit (default: matches caffeinate -t)
    elapsed_hours = (now() - state.started_at).total_seconds() / 3600
    if elapsed_hours >= config.max_duration_hours:
        return False, "duration_limit"
    
    # 5. Budget limit (default: $50)
    if state.budget_spent >= config.max_budget:
        return False, "budget_limit"
    
    # 6. Error threshold (default: 10)
    if state.errors.total >= config.error_threshold:
        return False, "error_threshold"
    
    # 7. Fatal error
    if state.errors.fatal > 0:
        return False, "fatal_error"
    
    # 8. Diminishing returns: < 0.5 tasks/episode for 3 consecutive
    recent = state.episode_history[-3:]
    if len(recent) == 3:
        avg_completed = sum(ep.tasks_completed for ep in recent) / 3
        if avg_completed < 0.5:
            return False, "diminishing_returns"
    
    return True, None
```

Condition 8 is the most subtle and the most important for multi-model setups. When a local model is struggling (< 0.5 tasks per episode for 3 episodes), the orchestrator has two options:
- **Terminate** and log the task as blocked for human review
- **Escalate** to a frontier model for this specific task (costs money but may unstick progress)

The escalation strategy is configurable per task type.

### The Handoff Document

The handoff is what makes episodes composable. It's the agent's **claim** about what happened; git is the **truth**. Three proven formats:

**Minimal (Nightcrawler-style, 6 sections):**
```markdown
# Episode N Handoff

## Summary
[1-2 sentences: what was accomplished this episode]

## Work Completed
- [specific file changes with descriptions]

## In-Progress Work
- [what's partially done, what remains]

## Key Context for Next Episode
- [decisions made, assumptions, environment notes]

## Files Modified
- path/to/file.py: [description of change]

## Errors Encountered
- [any issues and how they were resolved or deferred]
```

**Comprehensive (8-section template from [Don't Sleep On AI](https://dontsleeponai.com/handoff-prompt)):**
Adds Project Identity, Architecture Map, "What Could Go Wrong", "How To Think About This Project", a Do-Not-Touch List, and **Confidence Flags** (high/medium/low) so the next episode knows what to trust vs. verify.

**Split-file (from [Handoff CLI](https://semiherdogan.medium.com/handoff-a-better-way-to-run-autonomous-development-loops-00e97e62d470)):**
Separates state across 5 files: FEATURE.md, SPEC.md, DESIGN.md, STATE.md, SESSION.md. Prevents a single handoff from growing unbounded across many episodes.

**Recommendation for the night-shift harness**: Start with the minimal 6-section format. Add confidence flags from the 8-section template. If handoffs grow too large over many episodes, migrate to the split-file approach.

### Git as Truth Oracle

Between episodes, the orchestrator cross-checks the handoff against reality:

```python
def verify_handoff(worktree, result):
    claimed_files = parse_handoff(result.handoff).files_modified
    actual_changes = git_diff_names(worktree)
    
    for claimed in claimed_files:
        if claimed not in actual_changes:
            state.errors.truth_discrepancy += 1
            log(f"HANDOFF LIE: agent claimed {claimed} modified, git disagrees")
```

This prevents the **Hallucinated Handoff** death spiral. The agent cannot claim it changed files that `git diff` says were not modified.

### Task Immutability

Tasks are extracted from the mission spec into an immutable tracker. Agents can only flip tasks from `not done` to `done`. They cannot:
- Delete tasks
- Rename or reorder tasks
- Add new tasks
- Flip tasks back to `not done`

This prevents agents from **redefining the mission to match what they actually accomplished** — a subtle failure mode where the agent "succeeds" by lowering the bar.

### Spawn Budgets (from [Blake Crosley's Ralph implementation](https://blakecrosley.com/en/blog/ralph-agent-architecture))

When using agent frameworks that support subagent spawning (Claude Code's `Agent` tool, Codex subagents), unconstrained spawning causes exponential token burn. The fix: **budget inheritance**.

A root episode with spawn_budget=12 can create at most 12 total subagents across all recursion levels. This allows deep chains while preventing exponential growth. Without this, Crosley reported 10x normal token consumption from runaway subagent spawning.

### Crash Recovery

Two approaches, layer as needed:

**Simple: caffeinate -s wrapping**
```bash
#!/bin/bash
# night-shift.sh — run for 6 hours then let Mac sleep
caffeinate -s -t 21600 python3 orchestrator.py --config nightshift.toml
```
If the orchestrator crashes, caffeinate also exits and the Mac sleeps. You investigate in the morning. Simple, no magic.

**Robust: launchd supervision (from [Nightcrawler](https://dev.to/thebasedcapital/why-your-overnight-ai-agent-fails-and-how-episodic-execution-fixes-it-2g50))**
```xml
<!-- ~/Library/LaunchAgents/com.nightshift.orchestrator.plist -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nightshift.orchestrator</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/caffeinate</string>
        <string>-s</string>
        <string>-t</string>
        <string>21600</string>
        <string>/usr/local/bin/python3</string>
        <string>/path/to/orchestrator.py</string>
    </array>
    <key>KeepAlive</key>
    <dict>
        <key>Crashed</key>
        <true/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>Nice</key>
    <integer>5</integer>
    <key>StandardOutPath</key>
    <string>/tmp/nightshift/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/nightshift/stderr.log</string>
</dict>
</plist>
```

This auto-restarts the orchestrator on crash (30-second cooldown), wraps it in caffeinate for sleep prevention, runs at lower priority, and persists logs. The orchestrator resumes from its last checkpoint — the episodic model makes this safe because each episode is independent.

### Summary: Why Episodic Execution Is the Core Pattern

| Property | Continuous Session | Episodic Execution |
|----------|-------------------|-------------------|
| Context quality | Degrades over time | Fresh each episode |
| Crash recovery | Lost state | Resume from handoff |
| Multi-model | Locked to one model | Route per episode |
| Budget control | Inside the agent (unreliable) | Between episodes (orchestrator-enforced) |
| Verification | Agent self-reports | Git cross-checks |
| Local model viability | Limited by context | 5 episodes at $0 = 1 API episode at $3 |
| Graceful shutdown | Interrupt mid-work | Finish episode, write handoff, sleep |

The episodic model is what makes it possible to run local models cost-effectively overnight. A local Qwen 32B that needs 5 iterations to accomplish what Claude Opus does in one is **not a problem** — it's a feature. Each iteration is bounded, verified, and checkpointed. The overnight window gives you ample time, and the cost is zero. The orchestrator's job is to make those 5 iterations reliable, not to make them unnecessary.
