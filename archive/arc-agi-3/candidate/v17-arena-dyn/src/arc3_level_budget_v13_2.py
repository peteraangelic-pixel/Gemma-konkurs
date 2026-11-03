"""ARC3 Duck v13.2, patch 0007: adaptive per-level token budget.

Upgrades patch 0004's `arc3_level_budget.py` from a static token cap to a
per-game adaptive policy, using the SAME two signals the engine hook already
provides (`generated_tokens`, `levels_completed`) - so the solver call site,
the class interface and the env switches stay drop-in compatible.

Why (both halves measured in this campaign):
  * Static cap harmed expensive, nearly-finished levels (su15: 56.4 -> 13.3
    under the 45k cap while no-cap runs scored higher overall), which is why
    v13.1 shipped with the cap OFF.
  * Cap-less runs burn 35..91% of a game's tokens on the one level the game
    never completes (0004 baseline: tn36 86%, ls20 91%; scoring is convex in
    depth, so those are the most expensive tokens in the run).

Design (pure logic, unit-testable with no harness, no GPU, no engine - same
discipline as 0004; see tests/test_arc3_dyn_budget.py):

  * Every time a level completes, the tokens it consumed are recorded into a
    short per-game history. The current level's cap is
        clamp(median(history) * ARC3_DYN_CAP_MULT,
              ARC3_DYN_CAP_MIN, ARC3_DYN_CAP_MAX)
    falling back to ARC3_LEVEL_TOKEN_CAP (the arming value) until two levels
    of the same game have been completed. An expensive game therefore earns a
    bigger budget before any RESET fires, and a cheap game is cut much sooner
    than a flat 45k ever would - the same knob adapts in both directions.
  * RESET ladder: after each free RESET the cap for the next attempt grows by
    ARC3_DYN_CAP_LADDER (default 1.5x) - "one clean re-plan, then one more
    generous try". Resets replenish on every completed level, exactly like
    0004.
  * ABANDON only when resets are exhausted AND the current level consumed
    ARC3_DYN_ABANDON_MULT (default 1.5x) of its current cap AND
    levels_completed >= ARC3_LEVEL_MIN_DONE. The adaptive cap is therefore
    never harsher than the static one it replaces.
  * ARC3_DYN_CAP=0 falls back to the EXACT 0004 static semantics (with
    ARC3_LEVEL_TOKEN_CAP as the static cap), so a single env flips this patch
    into a faithful control for A/B.

`peek` stays pure (the harness hands it to should_stop(), which may run it
many times per turn); `step` is the only mutating entry point and must be
called once per turn where the RESET actually happens.
"""
from __future__ import annotations

import os
from statistics import median

KEEP_GOING = "keep_going"
RESET_LEVEL = "reset_level"
ABANDON = "abandon"

DEFAULT_RESETS_MAX = 1
DEFAULT_CAP_MULT = 4.0
DEFAULT_CAP_MIN = 45_000
DEFAULT_CAP_MAX = 150_000
DEFAULT_LADDER = 1.5
DEFAULT_ABANDON_MULT = 1.5
DEFAULT_HISTORY = 8


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


class LevelBudget:
    """Tracks one game's spend on the level it is currently playing.

    Same constructor signature and public surface as patch 0004, so the
    existing solver hook is unchanged; the policy inside `peek` is what
    v13.2 replaces.
    """

    def __init__(
        self,
        level_token_cap: int = 0,
        resets_max: int = DEFAULT_RESETS_MAX,
        min_done_levels: int = 0,
    ) -> None:
        self.static_cap = max(0, int(level_token_cap))
        self.max_resets = max(0, int(resets_max))
        self.min_done = max(0, int(min_done_levels))
        # dynamic-policy configuration (env overridable, see from_env)
        self.dyn_enabled = _env_bool("ARC3_DYN_CAP", True) and self.static_cap > 0
        self.cap_mult = max(1.0, _env_float("ARC3_DYN_CAP_MULT", DEFAULT_CAP_MULT))
        self.cap_min = max(1, _env_int("ARC3_DYN_CAP_MIN", self.static_cap or DEFAULT_CAP_MIN))
        self.cap_max = max(self.cap_min, _env_int("ARC3_DYN_CAP_MAX", DEFAULT_CAP_MAX))
        self.ladder = max(1.0, _env_float("ARC3_DYN_CAP_LADDER", DEFAULT_LADDER))
        self.abandon_mult = max(1.0, _env_float("ARC3_DYN_ABANDON_MULT", DEFAULT_ABANDON_MULT))
        self.history_max = max(2, _env_int("ARC3_DYN_HISTORY", DEFAULT_HISTORY))
        # runtime state
        self.level_start_levels = 0
        self.level_start_tokens = 0
        self.resets_used = 0
        self._level_costs: list[int] = []

    @classmethod
    def from_env(cls) -> "LevelBudget":
        return cls(
            level_token_cap=_env_int("ARC3_LEVEL_TOKEN_CAP", 0),
            resets_max=_env_int("ARC3_LEVEL_RESETS_MAX", DEFAULT_RESETS_MAX),
            min_done_levels=_env_int("ARC3_LEVEL_MIN_DONE", 0),
        )

    @property
    def enabled(self) -> bool:
        return self.static_cap > 0

    # ---- dynamic cap -----------------------------------------------------

    def _current_cap(self) -> int:
        """Cap for the CURRENT attempt (includes the reset ladder)."""
        if not self.dyn_enabled:
            # static fallback: flat cap, byte-equivalent to patch 0004
            return self.static_cap
        base = float(self.static_cap)
        if len(self._level_costs) >= 2:
            base = max(base, median(self._level_costs) * self.cap_mult)
        base = min(max(base, self.cap_min), self.cap_max)
        return int(base * (self.ladder ** self.resets_used))

    # ---- core policy -----------------------------------------------------

    def _spent_on_level(self, generated_tokens: int, levels_completed: int) -> int:
        """Tokens spent on the CURRENT level since it started (or since its
        last free reset). A level that just completed starts a fresh budget
        even if `step` has not observed it yet, so `peek` can never act on
        the turn the game made progress."""
        if int(levels_completed) > self.level_start_levels:
            return 0
        return max(0, int(generated_tokens) - self.level_start_tokens)

    def peek(self, generated_tokens: int, levels_completed: int) -> str:
        """Pure decision - safe to call from should_stop() as often as needed."""
        if not self.enabled:
            return KEEP_GOING
        spent = self._spent_on_level(generated_tokens, levels_completed)
        if spent < self._current_cap():
            return KEEP_GOING
        if self.dyn_enabled:
            # adaptive branch
            if self.resets_used < self.max_resets:
                return RESET_LEVEL
            if spent < int(self._current_cap() * self.abandon_mult):
                return KEEP_GOING
            if int(levels_completed) < self.min_done:
                return KEEP_GOING
            return ABANDON
        # static fallback: byte-equivalent decisions to patch 0004
        if self.resets_used < self.max_resets:
            return RESET_LEVEL
        if int(levels_completed) < self.min_done:
            return KEEP_GOING
        return ABANDON

    def step(self, generated_tokens: int, levels_completed: int) -> str:
        """Decision + bookkeeping. Call once per turn, where the RESET happens."""
        generated_tokens = int(generated_tokens)
        levels_completed = int(levels_completed)
        if levels_completed > self.level_start_levels:
            # Progress: record what the level cost, fresh budget, resets back.
            cost = generated_tokens - self.level_start_tokens
            if cost > 0:
                self._level_costs.append(cost)
                if len(self._level_costs) > self.history_max:
                    self._level_costs.pop(0)
            self.level_start_levels = levels_completed
            self.level_start_tokens = generated_tokens
            self.resets_used = 0
            return KEEP_GOING
        decision = self.peek(generated_tokens, levels_completed)
        if decision == RESET_LEVEL:
            self.resets_used += 1
            self.level_start_tokens = generated_tokens
        return decision

    def describe(self) -> str:
        if self.dyn_enabled:
            return (
                f"DynLevelBudget(median={int(median(self._level_costs)) if len(self._level_costs) >= 2 else 'n/a'}, "
                f"cap={self._current_cap()}, resets={self.resets_used}/{self.max_resets}, "
                f"mult={self.cap_mult}, min={self.cap_min}, max={self.cap_max}, "
                f"ladder={self.ladder}, abandon_mult={self.abandon_mult}, "
                f"level={self.level_start_levels}, min_done={self.min_done})"
            )
        return (
            f"LevelBudget(cap={self.static_cap}, resets={self.resets_used}/{self.max_resets}, "
            f"level={self.level_start_levels}, min_done={self.min_done})"
        )
