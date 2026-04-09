"""Worktree Manager (Component 3f).

Create, track, and clean up git worktrees for tasks.
- Create worktree on task start: git worktree add <path> -b nyx/<task-id>
- Track worktree-to-task mapping in Task Queue DB
- On completion: create draft PR, prune worktree
- On failure: preserve for inspection, log location
"""
