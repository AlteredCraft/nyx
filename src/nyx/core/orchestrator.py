"""Orchestrator Core (Component 3a).

The main loop. Reads tasks from the queue, selects the next task,
dispatches to the appropriate backend via the Episode Runner, checks
termination conditions after each episode, and writes shift logs on exit.

Key behaviors:
- Sequential episode execution (parallel worktrees is a later milestone)
- 8 termination conditions evaluated before each episode
- Graceful shutdown: finish current episode, write handoff, write shift log
- Checkpoint state to disk after every episode (crash recovery)
"""
