"""CLI entry point for Nyx.

Commands:
    nyx run --duration 6h --budget 50    Start a nightshift session
    nyx tasks add <spec-file>            Add a task to the queue
    nyx tasks list                       List queued tasks
    nyx tasks inspect <task-id>          Show task details + episode history
    nyx watch                            Tail the event log in real time
    nyx status                           Show current/last session status
"""


def main():
    """CLI entry point."""
    raise NotImplementedError("CLI not yet implemented")
