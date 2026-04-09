"""Task Queue (Component 3b).

Persistent, queryable store of task definitions with state tracking.
SQLite backend with an abstraction interface.

State machine: todo -> in_progress -> qa -> done | failed | blocked

Immutability: once a task enters in_progress, its spec field is frozen.
The abstraction layer rejects mutations to spec/title on non-todo tasks.
"""
