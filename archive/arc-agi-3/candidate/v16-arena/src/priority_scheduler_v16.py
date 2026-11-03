"""Pure scheduler inputs and scoring; never reads hidden game metadata."""
from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    """Same truthiness contract as tool_agent._get_env_bool, without a cycle."""
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _finite_nonnegative(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return max(0.0, number)


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


# Expected future level-weight sum, conditional on completing the current level.
# 80k tokens are shared by ALL future levels; efficiency is NOT baked in.
# Source: arc3-levelup-chances, pooled_late_provisional, N6..10_H80000 / 0.8.
# KM duration distributions: separate levels 1-4, pooled observed levels 5-8
# for levels 5 onward. Levels 9-10 are extrapolated. Costs rounded up to 250
# tokens. 336 historical passes / 1,417 reached levels; not a contest fit.
# Tuples are indexed by current_level - 1. The final level has no future tail.
TAIL_LOOKUP_80K: dict[int, tuple[float, ...]] = {
    6: (3.9082328014, 5.0756939323, 5.3532912917, 5.6080111343,
        4.0898867400, 0.0),
    7: (3.9262240771, 5.1669653335, 5.6943514417, 6.6500041602,
        6.6562876217, 4.7715345300, 0.0),
    8: (3.9291260268, 5.1855629875, 5.7851444897, 7.0053702980,
        7.8471367942, 7.7045641090, 5.4531823200, 0.0),
    9: (3.9295002558, 5.1885168225, 5.8035897108, 7.0958580947,
        8.2469236991, 9.0442694281, 8.7528405964, 6.1348301100, 0.0),
    10: (3.9295397677, 5.1888936715, 5.8065473797, 7.1136691211,
         8.3474656955, 9.4884771003, 10.2414020621, 9.8011170838,
         6.8164779000, 0.0),
}


# Heuristic continuation value by levels remaining AFTER the current level:
# 3 or more -> 8; 2 -> 7; 1 -> 5; 0 -> 0. These are final B values,
# so neither score normalization nor the empirical efficiency discount applies.
TAIL_LOOKUP_REMAINING: dict[int, tuple[float, ...]] = {
    n: (8.0,) * (n - 3) + (7.0, 5.0, 0.0) for n in range(6, 11)
}


def parse_total_levels(value: object) -> int | None:
    """Validate public level-count metadata, then clip to the table domain."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number <= 0 or not number.is_integer():
        return None
    return min(10, max(6, int(number)))


@dataclass
class ProgressPace:
    completed: int = 0
    log_cost_ratio: float = 0.0
    # Raw generated tokens spent on cleared levels (D', ARC3_PRIORITY_DPRIME).
    # cost_multiplier() is a dimensionless 0.5-2.0 factor and cannot stand in
    # for this. getattr() keeps agents unpickled from older builds working.
    total_tokens: float = 0.0

    def record_completion(self, tokens_used: float, reference_tokens: float) -> None:
        used = _finite_nonnegative(tokens_used)
        reference = max(1.0, _finite_nonnegative(reference_tokens, default=1.0))
        observation = math.log(max(1.0, used) / reference)
        self.log_cost_ratio = (
            observation if self.completed == 0
            else 0.6 * self.log_cost_ratio + 0.4 * observation
        )
        self.total_tokens = (
            _finite_nonnegative(getattr(self, "total_tokens", 0.0)) + used
        )
        self.completed += 1

    def cost_multiplier(self) -> float:
        confidence = self.completed / (self.completed + 3.0)
        return math.exp(min(math.log(2.0), max(math.log(0.5),
                                             confidence * self.log_cost_ratio)))

    def mean_tokens_per_cleared_level(self) -> float:
        """D' pace: generated tokens per completed level, 0 before the first."""
        completed = max(0, int(getattr(self, "completed", 0)))
        total = _finite_nonnegative(getattr(self, "total_tokens", 0.0))
        return total / completed if completed else 0.0


@dataclass(frozen=True)
class PrioritySnapshot:
    level: int
    actions: int
    tokens: float
    cost_multiplier: float = 1.0
    # Appended to preserve four-argument callers and older pickled snapshots.
    total_levels: int | None = None
    # Appended for D'; read only when ARC3_PRIORITY_DPRIME is on.
    mean_tokens_per_cleared_level: float = 0.0


def priority_value(
    state: PrioritySnapshot, *, endgame: bool = False,
    tail_fraction: float | None = None, human_actions: float = 25.0,
    action_scale: float = 115.0, token_scale: float = 62000.0,
    action_weight: float = 0.25, tail_base: float = 6.0, tail_cap: float = 6.0,
    normalize_score: bool = False, tail_lookup: bool | str = False,
    tail_efficiency: float = 0.8,
) -> int:
    """No phase offset: all candidates must be evaluated at the same time.

    tail_fraction=None retains the endgame rule. Supplying a fraction
    keeps the likelihood proxy active and fades the tail instead of switching.
    The likelihood proxy is heuristic, not a calibrated completion probability.

    tail_lookup=True uses the empirical 80k table; "remaining" uses the
    fixed 8/7/5/0 table without an efficiency discount. False keeps the capped
    tail. normalize_score scales only A, never B or the endgame's 0.25 floor.
    """
    level = max(1, state.level)
    total_levels = parse_total_levels(getattr(state, "total_levels", None)) or 10
    actions, tokens = max(0, state.actions), max(0.0, state.tokens)
    pace = min(2.0, max(0.5, state.cost_multiplier))
    efficiency = (human_actions / (human_actions + actions)) ** 2
    current_value = level * efficiency
    if normalize_score:
        # Normalize immediate reward A to a ten-level reference (sum 1..10).
        # B is a separately chosen continuation value, not normalized reward.
        current_value *= 55.0 / (total_levels * (total_levels + 1) / 2)
    if endgame and tail_fraction is None:
        # Preserve the original arithmetic when normalization is disabled.
        value = (
            level * 0.25 + current_value if normalize_score
            else level * (0.25 + efficiency)
        ) / pace * 100
    else:
        if tail_lookup == "remaining":
            index = min(total_levels, level) - 1
            tail = TAIL_LOOKUP_REMAINING[total_levels][index]
        elif tail_lookup:
            future_efficiency = (
                min(1.0, max(0.0, tail_efficiency))
                if math.isfinite(tail_efficiency) else 0.8
            )
            index = min(total_levels, level) - 1
            tail = TAIL_LOOKUP_80K[total_levels][index] * future_efficiency
        else:
            tail = min(tail_cap, tail_base + level - 1)
        if tail_fraction is not None:
            tail *= min(1.0, max(0.0, tail_fraction))
        chance = (
            action_weight * 0.5 ** ((actions / action_scale) ** 2)
            + (1.0 - action_weight) * 0.5 ** ((tokens / (token_scale * pace)) ** 2)
        )
        value = (current_value + tail) * chance / pace * 100
    return max(1, int(value))


# --- D' slot priority (opt-in: ARC3_PRIORITY_DPRIME=1) ----------------------
# Restated from the published D' slot priority (scale 1000, no unconditional
# fresh-first band). Measured public draws on a comparable line: 31.54, 30.74,
# 29.05, 24.77 (mean ~29.0, n=4) against a comparable-baseline mean of ~25.77
# (SD ~3.93). That is a modest, noisy signal, not a proven gain, which is why
# the whole formula is one env switch and every legacy path stays byte-intact.
#
# The only new input it needs is the measured generated-token pace per cleared
# level. The host supplies it; nothing here reads hidden game metadata.
_DPRIME_LOGGED = False


def dprime_enabled() -> bool:
    return _env_bool("ARC3_PRIORITY_DPRIME", False)


def _dprime_total_levels(value: object) -> int:
    """True level count for the growth term; 10 when unknown or invalid."""
    if value is None or isinstance(value, bool):
        return 10
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return 10
    if not math.isfinite(number) or number <= 0 or not number.is_integer():
        return 10
    return int(number)


def dprime_value(
    state: PrioritySnapshot, *, tail_fraction: float | None = 1.0,
) -> float:
    """Unscaled D' priority: A * M * C + B * phi.

      A = (1 + 0.5 (level - 1)) * norm(N) * (300 / (300 + actions)) ** 2.5
      M = clip((30000 / pace) ** 0.4, 0.25, 4), or 1 before the first clear
      C = 0.1 * max(0.1, 1 - actions / 115) + 0.9 * max(0.1, 1 - tokens / T)
      T = 225000 * clip(pace / 30000, 0.5, 2) ** 0.5
      B = 16 / 14 / 10 / 0 for >=3 / 2 / 1 / 0 levels remaining
      phi in [0, 1] fades B near the end of the run
    """
    try:
        level = max(1, int(state.level))
    except (TypeError, ValueError, OverflowError):
        level = 1

    actual_levels = _dprime_total_levels(getattr(state, "total_levels", None))
    norm_levels = min(10, max(6, actual_levels))
    norm = 55.0 / (norm_levels * (norm_levels + 1) / 2.0)

    actions = _finite_nonnegative(getattr(state, "actions", 0.0))
    tokens = _finite_nonnegative(getattr(state, "tokens", 0.0))
    pace = _finite_nonnegative(getattr(state, "mean_tokens_per_cleared_level", 0.0))

    depth = (1.0 + 0.5 * (level - 1)) * norm
    depth *= (300.0 / (300.0 + actions)) ** 2.5
    if pace > 0.0:
        depth *= _clip((30_000.0 / max(1.0, pace)) ** 0.4, 0.25, 4.0)

    reference_pace = pace if pace > 0.0 else 30_000.0
    token_scale = 225_000.0 * _clip(reference_pace / 30_000.0, 0.5, 2.0) ** 0.5
    patience = (
        0.1 * max(0.1, 1.0 - actions / 115.0)
        + 0.9 * max(0.1, 1.0 - tokens / token_scale)
    )

    remaining = max(0, actual_levels - level)
    growth = (0.0, 10.0, 14.0, 16.0)[min(remaining, 3)]
    phi = 1.0 if tail_fraction is None else _clip(
        _finite_nonnegative(tail_fraction, default=1.0), 0.0, 1.0
    )
    return depth * patience + growth * phi


def dprime_priority(
    state: PrioritySnapshot, *, tail_fraction: float | None = 1.0,
) -> int:
    """Integer priority on the reference 1000 scale, never below 1."""
    return max(1, int(dprime_value(state, tail_fraction=tail_fraction) * 1000.0))


def select_priority(
    state: PrioritySnapshot, *,
    tail_fraction: float | None = None,
    endgame: bool = False,
    **legacy: object,
) -> int:
    """Single switch between the shipped priority and D'.

    With ARC3_PRIORITY_DPRIME unset this calls priority_value() with exactly
    the arguments it would have received, so v13.4 behaviour is unchanged.
    """
    if not dprime_enabled():
        return priority_value(
            state, tail_fraction=tail_fraction, endgame=endgame, **legacy
        )
    global _DPRIME_LOGGED
    if not _DPRIME_LOGGED:
        _DPRIME_LOGGED = True
        log.warning(
            "priority: D' slot priority active (ARC3_PRIORITY_DPRIME=1); "
            "legacy priority_value bypassed"
        )
    phi = tail_fraction
    if phi is None:
        # No shared clock: the legacy path would fall back to its endgame
        # switch here, so D' drops the growth bonus in that phase instead.
        phi = 0.0 if endgame else 1.0
    return dprime_priority(state, tail_fraction=phi)
