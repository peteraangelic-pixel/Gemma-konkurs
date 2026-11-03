def _escalate_threshold(agent, floor: int) -> int:
    """ARC3_ESCALATE_RELATIVE=1: escalate relative to the human baseline.

    Threshold = max(floor, ARC3_ESCALATE_RATE * base_actions_per_level[
    current_level]); falls back to the absolute floor whenever the baseline
    is hidden (GameRun.base_actions_per_level is None) or the game reference
    is missing (analyzer_factory path). Measured on r085's 32 completed
    levels (ARC3/local-lab/escalation_audit.py, Gemma b38b82e; recomputed
    independently by Arena): absolute 10 -> 154 injections, 15.3% of the
    game's token pool, premature on 31/32 levels; relative(1.2, floor 20)
    -> 8 injections, 0.8%, premature on 0/32.
    """
    if not _get_env_bool("ARC3_ESCALATE_RELATIVE", False):
        return floor
    try:
        game = getattr(agent, "game", None)
        base = list(getattr(getattr(game, "game_run", None),
                            "base_actions_per_level", None) or [])
        level = int(getattr(game, "current_state").levels_completed)
        b = int(base[level]) if 0 <= level < len(base) else 0
    except Exception:
        b = 0
    if b <= 0:
        return floor
    try:
        rate = float((os.environ.get("ARC3_ESCALATE_RATE") or "1.2").strip())
    except ValueError:
        rate = 1.2
    return max(floor, int(b * rate))


