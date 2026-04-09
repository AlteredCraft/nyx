"""BackendAdapter interface.

All adapters implement this interface:
    run(prompt, worktree, sandbox_config, timeout) -> EpisodeResult
    health_check() -> bool
    estimate_cost(prompt_tokens) -> float
"""
