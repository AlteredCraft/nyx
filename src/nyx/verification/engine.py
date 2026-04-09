"""Verification Engine (Component 3e).

Three stages after each episode:
1. Handoff verification: cross-check HANDOFF.md claims against git diff
2. Build verification: run verify_command (build/test/lint) in worktree
3. Policy verification: blocked files, lockfiles, credential files

On failure: revert episode changes, increment error counter, log details.
"""
