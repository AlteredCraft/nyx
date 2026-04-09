"""Model Router (Component 3c).

Given a task (type, complexity, model_affinity, budget constraints),
select the model backend and endpoint to use.

Routing rules are loaded from nyx.toml [[routes]] sections.
Supports match conditions, fallback chains, and escalation on
diminishing returns.
"""
