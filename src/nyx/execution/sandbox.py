"""Docker SBX sandbox integration.

Manages sandbox lifecycle for agent subprocesses:
create sandbox, mount worktree, configure network/filesystem policies,
run agent inside sandbox, tear down on completion.
"""
