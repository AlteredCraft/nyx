"""Power Manager (Component 3g).

Wraps the orchestrator process in caffeinate -s -t <seconds>.
Handles graceful shutdown: finish current episode, write handoff,
write shift log, exit cleanly, let the Mac sleep.
"""
