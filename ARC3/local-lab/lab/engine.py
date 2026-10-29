"""Local ARC-AGI-3 engine: bootstrap, a session that counts actions per level, and the
official RHAE score.

Why this exists: the Kaggle rerun is the only place the real score is produced, and a
rerun costs ~9 h of GPU and one slot. Everything that can be decided offline should be,
and the games the gateway serves are the same engine, so the offline engine is a faithful
place to measure *mechanisms* (not to precompute solutions for hidden games, which cannot
work: the scored games are not in the notebook's inputs).

Engine packages: `arcengine` (pure Python, from PyPI, requires >=3.12 only as metadata) and
`arc_agi` (the Arcade/wrapper). On Python 3.11 both import fine when the wheels are
extracted and put on sys.path - ARC3_ENGINE_PATHS=/path/to/arc_agi:/path/to/arcengine
does that, and plain `pip install` works too.

Measured on the 25 public games (this sandbox, 2 cores): 0.26-0.48 ms per step,
0.38 ms per reset, 3.8 ms per deepcopy of a live session. That matters: a search does
~2 000 steps/s per core, so 16 cores buy ~30 000 steps/s and a level is usually a few
thousand nodes. The bottleneck in the Duck harness is the model, not the engine.
"""
from __future__ import annotations

import copy
import glob
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from lab.fastclone import Driver, frame_hash_of  # noqa: E402
from lab.fastclone import action_enum as _action_enum  # noqa: E402


def action_enum(value):
    """Re-export: ints from `available_actions` -> GameAction."""
    return _action_enum(value)


# --------------------------------------------------------------------------- bootstrap
def bootstrap(engine_paths: str | None = None) -> tuple:
    """Import arc_agi + arcengine, adding extracted-wheel dirs to sys.path if needed."""
    paths = engine_paths if engine_paths is not None else os.environ.get("ARC3_ENGINE_PATHS", "")
    for p in [p for p in paths.split(":") if p]:
        if p not in sys.path:
            sys.path.insert(0, p)
    logging.disable(logging.WARNING)  # the engine is chatty per step
    try:
        from arc_agi import Arcade, OperationMode, LocalEnvironmentWrapper  # noqa: PLC0415
        from arcengine import GameAction, GameState  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment problem, not logic
        raise SystemExit(
            "arcengine/arc_agi not importable. Either `pip install arcengine arc-agi` "
            "(needs --break-system-packages on a managed Python) or extract both wheels and "
            "set ARC3_ENGINE_PATHS=<dir with arc_agi/>:<dir with arcengine/>.\n"
            f"original error: {exc}"
        ) from exc
    return Arcade, OperationMode, LocalEnvironmentWrapper, GameAction, GameState


def find_games_dir(explicit: str | None = None) -> Path:
    """Locate environment_files/ (25 public games). Never hardcode a Kaggle path."""
    for cand in (
        explicit,
        os.environ.get("ARC3_GAMES"),
        "ARC3/games/environment_files",
        "../games/environment_files",
        "arc-agi-3/games/environment_files",
        "games/environment_files",
    ):
        if not cand:
            continue
        p = Path(cand)
        if p.is_dir() and any(p.glob("*/[a-z0-9]*/metadata.json")):
            return p.resolve()
    # last resort: walk a couple of levels down from the repo root
    for pattern in ("**/environment_files/*/*/metadata.json",):
        hits = [Path(h).parents[1] for h in glob.glob(pattern, recursive=True)]
        if hits:
            return hits[0].resolve()
    raise SystemExit("games dir not found; pass --games-dir or set ARC3_GAMES")


# --------------------------------------------------------------------------- metadata
@dataclass
class GameMeta:
    game_id: str
    slug: str
    baseline_actions: list
    tags: list = field(default_factory=list)
    path: str = ""

    @property
    def n_levels(self) -> int:
        return len(self.baseline_actions)


def load_meta(games_dir: Path) -> dict:
    """slug -> GameMeta, from the per-game metadata.json shipped with the public set."""
    out = {}
    for meta_path in sorted(Path(games_dir).glob("*/[a-z0-9]*/metadata.json")):
        d = json.loads(meta_path.read_text())
        slug = meta_path.parent.name
        out[slug] = GameMeta(
            game_id=d.get("game_id", slug),
            slug=slug,
            baseline_actions=list(d.get("baseline_actions") or []),
            tags=list(d.get("tags") or []),
            path=str(meta_path.parent),
        )
    return out


# --------------------------------------------------------------------------- scoring
# Authoritative source: tufa-arc-agi-framework/src/taaf/game.py::_compute_final_score
#   per level: min(115, (baseline/actions)**2 * 100) if completed and actions>0 else 0
#   raw   = sum(level_score * weight) / sum(weights), weight = 1-indexed level number
#   cap   = 100 * sum(weights of levels that scored) / sum(all weights)
#   score = min(raw, cap)
# The cap is the whole reason efficiency is a secondary lever: efficiency can compensate a
# wasteful level elsewhere in the same game, but it can never lift the game above the
# 100-point scale that clearing exactly k of n levels allows.
LEVEL_CAP = 115.0        # = 1.15 * 100, applied to the level score in points
COMPLETION_SCALE = 100.0


def level_score(baseline: int, actions: int, level_cap: float = LEVEL_CAP) -> float:
    """Per-level term in points: min(115, (baseline/actions)^2 * 100)."""
    if actions is None or actions <= 0 or not baseline:
        return 0.0
    return min(level_cap, (baseline / actions) ** 2 * 100.0)


def game_score(actions_per_level, baselines, levels_completed=None,
               level_cap: float = LEVEL_CAP, completion_scale: float = COMPLETION_SCALE) -> float:
    """Exact re-implementation of taaf's `_compute_final_score` (which mirrors the
    arc_agi scorecard v0.9.8). Verified against 32 saved `final_score` values in
    `verify_scoring.py` - all of them, including the ones that fooled our first attempt.

    Two traps this encodes, both of which inflated earlier estimates:
      * a level only counts when `levels_completed` reached it - `actions_per_level` has an
        entry for the level currently being ground, and crediting it turned a real 0.35 on
        cn04 into 11.30 (32x);
      * `level_cap` is 115 points but the completion cap is on the 100 scale, so an
        efficiency better than baseline is swallowed whenever the game is incomplete.
    """
    n = len(baselines)
    if n == 0:
        return 0.0
    done = n if levels_completed is None else max(0, min(n, int(levels_completed)))
    total_score = 0.0
    total_w = 0
    scored_w = 0
    for idx in range(n):
        weight = idx + 1
        total_w += weight
        acts = actions_per_level[idx] if idx < len(actions_per_level) else 0
        ls = level_score(baselines[idx], acts, level_cap) if idx < done else 0.0
        if ls > 0:
            scored_w += weight
        total_score += ls * weight
    if total_w == 0:
        return 0.0
    return min(total_score / total_w, completion_scale * scored_w / total_w)


def level_value_table(baselines, level_cap: float = LEVEL_CAP, actions=None) -> list:
    """Points per level at baseline efficiency, and cumulatively - the token allocation map.

    Level k is worth k/sum(1..n) of the game, so on a 9-level game the last level alone is
    9/45 = 20 % of that game while the first is 2.2 %. Depth, not breadth.
    """
    n = len(baselines)
    total_w = sum(range(1, n + 1))
    rows, cum = [], 0.0
    for idx, base in enumerate(baselines):
        # `actions_per_level` carries trailing zeros for levels not reached yet: those must
        # be planned at baseline efficiency, not scored as zero.
        acts = actions[idx] if actions and idx < len(actions) and actions[idx] else base
        pts = level_score(base, acts, level_cap) * (idx + 1) / total_w
        cum += pts
        rows.append({"level": idx + 1, "baseline_actions": base, "actions": acts,
                     "points": round(pts, 3), "cumulative": round(min(cum, 100.0), 3),
                     "share_of_game": round((idx + 1) / total_w, 4)})
    return rows


# --------------------------------------------------------------------------- session
def frame_hash(fd) -> str:
    """Hash the last frame + level count (see fastclone.frame_hash_of)."""
    return frame_hash_of(fd.frame, getattr(fd, "levels_completed", 0))


_ACTION_BY_ID: dict = {}


def action_for(action_id: int, GameAction=None):
    """int from `available_actions` -> GameAction member.

    `GameAction(1)` raises ValueError even though `GameAction.ACTION1.value` prints as 1
    (the enum carries a custom value object), so the mapping is built by name.
    """
    global _ACTION_BY_ID
    if not _ACTION_BY_ID:
        if GameAction is None:
            from arcengine import GameAction as GA  # noqa: PLC0415

            GameAction = GA
        _ACTION_BY_ID = {0: GameAction.RESET}
        for i in range(1, 8):
            _ACTION_BY_ID[i] = getattr(GameAction, f"ACTION{i}")
    return _ACTION_BY_ID[int(action_id)]


class Session:
    """One game, driven directly through `game.perform_action`.

    Why not the wrapper: `wrapper.step()` appends every frame to an internal history
    (`_set_last_response`), which costs a copy per step and grows without bound in a
    search. Direct driving is 3-5x faster and flat in memory. `verify_against_wrapper`
    below proves the two paths agree action for action, which is what lets a level cleared
    here count as cleared in a Kaggle rerun.

    Action accounting is conservative: the RESET that starts a level is counted, and so is
    a reset after a death. If anything this over-counts relative to the scorecard, so
    local scores are a floor.
    """

    def __init__(self, game, meta=None, clone_policy: str = "full_deepcopy"):
        self.d = Driver(game, meta, clone_policy)
        self.meta = meta
        self.d.reset()

    # -- identity
    @property
    def levels_completed(self) -> int:
        return self.d.levels_completed

    @property
    def actions_per_level(self) -> list:
        return self.d.actions_per_level

    @property
    def total_actions(self) -> int:
        return self.d.total_actions

    @property
    def clone_policy(self) -> str:
        return self.d.policy

    # -- play
    def reset(self):
        return self.d.reset()

    def step(self, action: int, data: dict | None = None):
        return self.d.step(action, data)

    @property
    def available(self) -> list:
        return self.d.available

    @property
    def is_over(self) -> bool:
        return self.d.is_over

    @property
    def is_won(self) -> bool:
        return self.d.is_won

    def hash(self) -> str:
        return self.d.hash()

    @property
    def last(self):
        """Last FrameDataRaw (frame list, levels_completed, state, available_actions)."""
        return self.d.last

    def clone(self) -> "Session":
        s = Session.__new__(Session)
        s.d = self.d.clone()
        s.meta = self.meta
        return s

    # -- report
    def score(self) -> float:
        if not self.meta:
            return 0.0
        return game_score(self.actions_per_level, self.meta.baseline_actions,
                          levels_completed=self.levels_completed)

    def report(self) -> dict:
        return {
            "game": self.meta.slug if self.meta else "?",
            "levels": self.levels_completed,
            "levels_total": self.meta.n_levels if self.meta else None,
            "actions": self.total_actions,
            "actions_per_level": self.actions_per_level,
            "score": round(self.score(), 2),
            "clone_policy": self.clone_policy,
        }


def verify_against_wrapper(lab, slug: str, actions: int = 40, seed: int = 3) -> dict:
    """Prove Session (direct) and the official wrapper agree bit for bit.

    Runs the same pseudo-random action sequence through `LocalEnvironmentWrapper.step`
    and through Session, comparing last-frame hashes, level counts, states and available
    actions at every step. This is the test that licenses using the fast path for search.
    """
    import random  # noqa: PLC0415

    from lab.fastclone import sample_action  # noqa: PLC0415

    rng = random.Random(seed)
    w_session = lab.session(slug, use_wrapper=True)
    d_session = lab.session(slug)
    mismatches = 0
    for i in range(actions):
        a, data = sample_action(w_session, rng)
        f1 = w_session.step(a, data)
        f2 = d_session.step(a, data)
        if (frame_hash_of(f1.frame, f1.levels_completed)
                != frame_hash_of(f2.frame, f2.levels_completed)
                or f1.levels_completed != f2.levels_completed
                or f1.state != f2.state
                or list(f1.available_actions or []) != list(f2.available_actions or [])):
            mismatches += 1
    return {"game": slug, "actions": actions, "mismatches": mismatches}


# --------------------------------------------------------------------------- facade
class Lab:
    """Holds the Arcade and hands out sessions. One per process (not thread-safe)."""

    def __init__(self, games_dir: str | Path | None = None, engine_paths: str | None = None):
        Arcade, OperationMode, LocalEnvironmentWrapper, _, _ = bootstrap(engine_paths)
        self._cls = (LocalEnvironmentWrapper,)
        self.dir = find_games_dir(str(games_dir) if games_dir else None)
        self.meta = load_meta(self.dir)
        self.arcade = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(self.dir))
        self._envs = {e.game_id: e for e in self.arcade.available_environments}
        self._policies: dict = {}
        self._policy_evidence: dict = {}

    def slugs(self) -> list[str]:
        """Game slugs in sorted order, matched to the metadata by game_id prefix."""
        by_prefix = {}
        for slug, m in self.meta.items():
            by_prefix[m.game_id.split("-")[0]] = slug
        out = []
        for gid in self._envs:
            out.append(by_prefix.get(gid.split("-")[0], gid))
        return sorted(out)

    def env_for(self, slug: str, seed: int = 0):
        for gid, env in self._envs.items():
            if gid.split("-")[0] == slug or gid == slug:
                return env
        raise KeyError(f"no environment for {slug!r}; known: {self.slugs()}")

    def _wrapper(self, slug: str, seed: int = 0):
        wrapper, = self._cls
        LOG = logging.getLogger("arc3lab")
        LOG.addHandler(logging.NullHandler())
        return wrapper(
            environment_info=self.env_for(slug),
            logger=LOG,
            scorecard_id="lab",
            seed=seed,
            include_frame_data=False,
        )

    def session(self, slug: str, seed: int = 0, use_wrapper: bool = False) -> Session:
        """A ready-to-play Session. `use_wrapper=True` returns the official, slow path."""
        w = self._wrapper(slug, seed)
        meta = self.meta.get(slug)
        if use_wrapper:
            return _WrapperSession(w, meta)
        policy = self.policy_for(slug, seed)
        return Session(w._game, meta, clone_policy=policy)

    def policy_for(self, slug: str, seed: int = 0) -> str:
        """Calibrated clone policy for a game, cached per process."""
        if slug in self._policies:
            return self._policies[slug]
        from lab.fastclone import calibrate_policy  # noqa: PLC0415

        def make():
            return Driver(self._wrapper(slug, seed)._game, self.meta.get(slug), "full_deepcopy")

        policy, evidence = calibrate_policy(make)
        self._policies[slug] = policy
        self._policy_evidence[slug] = evidence
        return policy


class _WrapperSession:
    """The official path, used only as an oracle for `verify_against_wrapper`."""

    def __init__(self, wrapper, meta):
        self.w = wrapper
        self.meta = meta
        self.last = wrapper.reset()
        self.total_actions = 1
        self.actions_per_level: list[int] = []
        self._level_start = 1

    @property
    def levels_completed(self) -> int:
        return int(getattr(self.last, "levels_completed", 0) or 0)

    @property
    def available(self) -> list:
        return list(getattr(self.last, "available_actions", []) or [])

    def reset(self):
        self.last = self.w.reset()
        self.total_actions += 1
        return self.last

    def step(self, action: int, data: dict | None = None):
        a = action_enum(action)
        self.last = self.w.step(a, data) if data is not None else self.w.step(a)
        self.total_actions += 1
        lvl = int(getattr(self.last, "levels_completed", 0) or 0)
        while len(self.actions_per_level) < lvl:
            self.actions_per_level.append(self.total_actions - self._level_start)
            self._level_start = self.total_actions
        return self.last

    def score(self) -> float:
        if not self.meta:
            return 0.0
        return game_score(self.actions_per_level, self.meta.baseline_actions,
                          levels_completed=self.levels_completed)
