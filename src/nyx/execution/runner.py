"""Episode Runner (Component 3d).

Executes a single bounded episode: builds the prompt, spawns the agent
subprocess in a sandbox, captures stdout via pipe (NDJSON), waits for
exit or timeout, reads the handoff, returns a structured result.

Uses BackendAdapter interface — pluggable across Claude CLI,
Anthropic Agent SDK, and future backends.
"""
