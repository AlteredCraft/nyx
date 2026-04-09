"""Reporter (Component 3h).

Generates session output by consuming the Event Bus log:
1. Shift Log (Markdown): per-task summary of work done
2. Exec Summary (Markdown): 5-10 line morning scan
3. Machine-readable state (JSON): full session data
4. PR links: draft PRs created, ready for review
"""
