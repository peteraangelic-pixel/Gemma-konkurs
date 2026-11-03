"""Pure-Python implementation of the published ARC-AGI-3 D′ slot priority.

This module computes a game's *priority*; it does not implement the runner,
open games, call an LLM, or terminate/abandon a game. The runner should use
this value only when a model slot becomes available.

Formula and constants are restated from the public D′ notebook/research at:
https://github.com/mayankraj4728/ARC-AGI-3-2026

The public reference uses a priority scale of 1000 and evaluates fresh games
with the same formula as games already in progress (no unconditional
"fresh-first" priority band).
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable


@dataclass(frozen=True, slots=True)
class PrioritySnapshot:
    """Publicly observable state used to rank a game for the next model slot.

    Attributes:
        level: Current 1-based level index.
        actions: Actions spent on the current level.
        tokens: Generated tokens spent on the current level.
        total_levels: Total levels in the game, if known; defaults to 10.
        mean_tokens_per_cleared_level: Historical generated-token mean per
            completed level. Zero means no level has been completed yet.
    """

    level: int
    actions: float = 0.0
    tokens: float = 0.0
    total_levels: int | None = None
    mean_tokens_per_cleared_level: float = 0.0


@dataclass(frozen=True, slots=True)
class PriorityBreakdown:
    """Inspectable terms of D′; useful for local tests and debugging."""

    value: float
    depth_efficiency: float
    patience: float
    growth_bonus: float
    tail_fraction: float
    token_scale: float


def _finite_nonnegative(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(number):
        return default
    return max(0.0, number)


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _total_levels(value: object) -> int:
    try:
        count = int(value) if value is not None else 10
    except (TypeError, ValueError, OverflowError):
        count = 10
    return count if count > 0 else 10


def priority_breakdown(
    state: PrioritySnapshot,
    *,
    tail_fraction: float = 1.0,
) -> PriorityBreakdown:
    """Return D′'s unscaled score and its factors.

    D′ = A · M · C + B · φ
      A = (1 + 0.5(ℓ−1)) · norm(N) · (300/(300+a))**2.5
      M = clip((30,000/p)**0.4, 0.25, 4), or 1 before the first clear
      C = 0.1·max(0.1, 1−a/115) + 0.9·max(0.1, 1−t/T)
      T = 225,000 · clip(p/30,000, 0.5, 2)**0.5
      B = 16, 14, 10, 0 for >=3, 2, 1, 0 remaining levels
      φ = a caller-provided value in [0, 1], fading the growth bonus near
          the run's end. The reference run fades it over its final 40%.

    For norm(N), N is clamped to 6..10. The growth term uses the true N.
    ``tail_fraction`` should be computed by the host scheduler from remaining
    run time; this function does not access clocks or hidden game metadata.
    """
    try:
        level = max(1, int(state.level))
    except (TypeError, ValueError, OverflowError):
        level = 1

    actual_levels = _total_levels(state.total_levels)
    norm_levels = min(10, max(6, actual_levels))
    norm = 55.0 / (norm_levels * (norm_levels + 1) / 2.0)

    actions = _finite_nonnegative(state.actions)
    tokens = _finite_nonnegative(state.tokens)
    pace = _finite_nonnegative(state.mean_tokens_per_cleared_level)

    depth_efficiency = (1.0 + 0.5 * (level - 1)) * norm
    depth_efficiency *= (300.0 / (300.0 + actions)) ** 2.5
    if pace > 0.0:
        pace_multiplier = _clip((30_000.0 / max(1.0, pace)) ** 0.4, 0.25, 4.0)
        depth_efficiency *= pace_multiplier

    reference_pace = pace if pace > 0.0 else 30_000.0
    token_scale = 225_000.0 * _clip(reference_pace / 30_000.0, 0.5, 2.0) ** 0.5
    patience = (
        0.1 * max(0.1, 1.0 - actions / 115.0)
        + 0.9 * max(0.1, 1.0 - tokens / token_scale)
    )

    remaining_levels = max(0, actual_levels - level)
    growth_bonus = (0.0, 10.0, 14.0, 16.0)[min(remaining_levels, 3)]
    phi = _clip(_finite_nonnegative(tail_fraction, default=1.0), 0.0, 1.0)

    return PriorityBreakdown(
        value=depth_efficiency * patience + growth_bonus * phi,
        depth_efficiency=depth_efficiency,
        patience=patience,
        growth_bonus=growth_bonus,
        tail_fraction=phi,
        token_scale=token_scale,
    )


def dprime_value(state: PrioritySnapshot, *, tail_fraction: float = 1.0) -> float:
    """Unscaled D′ value (larger means the game is more attractive to serve)."""
    return priority_breakdown(state, tail_fraction=tail_fraction).value


def dprime_priority(state: PrioritySnapshot, *, tail_fraction: float = 1.0) -> int:
    """Integer priority compatible with the reference scheduler (×1000)."""
    value = int(dprime_value(state, tail_fraction=tail_fraction) * 1000.0)
    return max(1, value)


def rank_snapshots(
    states: Iterable[PrioritySnapshot],
    *,
    tail_fraction: float = 1.0,
) -> list[PrioritySnapshot]:
    """Stable descending priority order; original order breaks ties."""
    indexed = list(enumerate(states))
    indexed.sort(
        key=lambda item: (-dprime_priority(item[1], tail_fraction=tail_fraction), item[0])
    )
    return [state for _, state in indexed]


class ProgressPace:
    """Tiny adapter matching the public runner's pace-object contract.

    The runner may call ``record_completion(tokens_used, reference_tokens)``
    after a cleared level and read ``cost_multiplier()`` when ranking a game.
    This returns the mean generated tokens per cleared level; before the first
    clear it returns zero, which D′ interprets as its 30k-token reference pace.
    """

    def __init__(self) -> None:
        self._completed = 0
        self._tokens = 0.0

    def record_completion(self, tokens_used: float, reference_tokens: float = 0.0) -> None:
        del reference_tokens  # Kept for call-signature compatibility.
        self._tokens += _finite_nonnegative(tokens_used)
        self._completed += 1

    def cost_multiplier(self) -> float:
        return self._tokens / self._completed if self._completed else 0.0


def dprime_priority_adapter(
    state: object,
    *,
    tail_fraction: float | None = None,
    **_ignored: object,
) -> int:
    """Adapt a runner-style priority snapshot to ``dprime_priority``.

    The public runner interface uses ``cost_multiplier`` for the historical
    token pace and may provide extra keyword arguments. This adapter ignores
    unknown kwargs, defaults the tail fade to fully open, and never reads
    hidden game state. Confirm the target runner's snapshot attributes before
    wiring it into a competition notebook.
    """
    snapshot = PrioritySnapshot(
        level=getattr(state, "level", 1),
        actions=getattr(state, "actions", 0.0),
        tokens=getattr(state, "tokens", 0.0),
        total_levels=getattr(state, "total_levels", None),
        mean_tokens_per_cleared_level=getattr(state, "cost_multiplier", 0.0),
    )
    phi = 1.0 if tail_fraction is None else tail_fraction
    return dprime_priority(snapshot, tail_fraction=phi)
