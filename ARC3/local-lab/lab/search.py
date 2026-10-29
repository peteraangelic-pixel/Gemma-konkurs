"""Deterministic level search on the real engine - zero LLM tokens.

Two mechanisms carry this, both measured rather than assumed:

**Branching factor.** `available_actions` is a hard filter (never probe an action the engine
did not offer). For click games, pixels are not actions: a coarse grid of clicks is grouped
by the frame hash it produces and only one representative per *distinct effect* is searched.
Added here on top of the grid: the centroid of each non-background colour blob, because
games most often want the object, not the point.

**Snapshot cost.** A BFS node needs a game state it can fork. Measured on this engine,
`copy.deepcopy(game)` is 19 ms on ls20 - but 17 ms of that is camera interfaces and 8 ms
level templates, so `lab.fastclone` shares those after proving the share is bit-identical
to a full deepcopy. Per-game snapshot cost after calibration: 0.5-8.6 ms, step 0.07-2.9 ms.

A node is therefore 1-10 ms, i.e. 100-1000 nodes/s/core and 1.5-15k/s on 14 workers of a
5950X. Committed-reserve memory is the frontier: each pending node holds a live game, so
the frontier is capped and the cap is reported (`frontier_dropped`), because a silent drop
looks exactly like "search found nothing".
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

MOUSE = 6
KEY_ACTIONS = (1, 2, 3, 4, 5, 7)
GRID = 64


@dataclass(frozen=True)
class Candidate:
    action: int
    x: int = -1
    y: int = -1

    @property
    def data(self):
        return {"x": self.x, "y": self.y} if self.action == MOUSE else None

    def label(self) -> str:
        return f"A{self.action}({self.x},{self.y})" if self.action == MOUSE else f"A{self.action}"


def apply(driver, cand: Candidate):
    return driver.step(cand.action, cand.data)


# --------------------------------------------------------------------------- clicks
def _blob_centroids(frame, limit: int = 12) -> list:
    """Centroid of each colour's largest connected blob - the objects a game points at.

    Pure Python flood fill on purpose: scipy is not guaranteed in either environment
    (it is absent in this sandbox and in the Kaggle image), and a 64x64 board is 4096 cells,
    so a hand-rolled label pass costs well under a millisecond and is cached by frame hash.
    """
    import numpy as np  # noqa: PLC0415

    a = np.asarray(frame, dtype=np.int8)
    while a.ndim > 2:
        a = a[-1]
    h, w = a.shape
    flat = a.tolist()
    best: dict[int, tuple[int, tuple[int, int]]] = {}
    seen = [[False] * w for _ in range(h)]
    for y0 in range(h):
        row = flat[y0]
        for x0 in range(w):
            colour = row[x0]
            if colour == 0 or seen[y0][x0]:
                continue
            stack = [(y0, x0)]
            seen[y0][x0] = True
            size = 0
            sx = sy = 0
            while stack:
                y, x = stack.pop()
                size += 1
                sx += x
                sy += y
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny][nx] and flat[ny][nx] == colour:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            prev = best.get(colour)
            if prev is None or size > prev[0]:
                best[colour] = (size, (sx // size, sy // size))
    ranked = sorted(best.values(), key=lambda t: -t[0])
    return [c for _, c in ranked[:limit]]


def click_candidates(driver, cache: dict | None, stride: int = 8, max_distinct: int = 10) -> list:
    """One click per distinct *effect*: grid sweep + colour-blob centroids."""
    key = driver.hash()
    if cache is not None and key in cache:
        return cache[key]
    start = key
    seen: dict[str, Candidate] = {}
    probes = [(x, y) for y in range(stride // 2, GRID, stride) for x in range(stride // 2, GRID, stride)]
    probes += _blob_centroids(driver.last.frame)
    for x, y in probes:
        probe = driver.clone()
        try:
            probe.step(MOUSE, {"x": x, "y": y})
        except Exception:
            continue
        h = probe.hash()
        if h == start or h in seen:
            continue
        seen[h] = Candidate(MOUSE, x, y)
        if len(seen) >= max_distinct:
            break
    out = list(seen.values())
    if cache is not None:
        cache[key] = out
    return out


def expand(driver, click_cache: dict | None = None, max_clicks: int = 10, stride: int = 8) -> list:
    avail = driver.available
    out = [Candidate(a) for a in KEY_ACTIONS if a in avail]
    if MOUSE in avail:
        out.extend(click_candidates(driver, click_cache, stride=stride, max_distinct=max_clicks))
    return out


# --------------------------------------------------------------------------- stats
def node_cost_ms(driver, samples: int = 12) -> float:
    """Measured clone+step cost for this game - decides whether BFS is affordable."""
    cands = expand(driver)
    if not cands:
        return 0.0
    t = time.time()
    for i in range(samples):
        c = cands[i % len(cands)]
        child = driver.clone()
        try:
            apply(child, c)
        except Exception:
            pass
    return 1000.0 * (time.time() - t) / samples


# --------------------------------------------------------------------------- search
def find_next_level(
    session,
    node_budget: int = 20000,
    time_budget_s: float = 120.0,
    frontier_cap: int = 6000,
    max_depth: int = 80,
    max_clicks: int = 10,
    stride: int = 8,
    log=None,
):
    """Breadth-first search for the shortest action chain that raises `levels_completed`.

    Returns (path, stats). `path` was found on a clone of this exact state, so executing it
    lands on the next level. `stats['frontier_dropped']` > 0 means the node budget, not the
    game, was the limit - the single most useful number when tuning.
    """
    t0 = time.time()
    start_level = session.levels_completed
    start_hash = session.hash()
    q = deque([(session.clone(), ())])
    seen = {start_hash}
    nodes = 0
    clicks: dict = {}
    dropped = 0
    while q:
        if nodes >= node_budget or (time.time() - t0) >= time_budget_s:
            break
        state, path = q.popleft()
        if len(path) >= max_depth:
            continue
        for cand in expand(state, clicks, max_clicks, stride):
            if nodes >= node_budget or (time.time() - t0) >= time_budget_s:
                break
            nodes += 1
            child = state.clone()
            try:
                apply(child, cand)
            except Exception:
                continue
            if child.levels_completed > start_level:
                return path + (cand,), {
                    "nodes": nodes, "secs": round(time.time() - t0, 2), "found": True,
                    "depth": len(path) + 1, "frontier_dropped": dropped,
                }
            if child.is_over or child.is_won:
                continue  # death = dead end for this level; retrying is the caller's call
            h = child.hash()
            if h in seen:
                continue
            seen.add(h)
            if len(q) < frontier_cap:
                q.append((child, path + (cand,)))
            else:
                dropped += 1
    return None, {"nodes": nodes, "secs": round(time.time() - t0, 2), "found": False,
                  "frontier_dropped": dropped, "frontier_left": len(q)}


def replay_verify(session, path) -> bool:
    """Execute `path` on the live session and check the level count really moved."""
    before = session.levels_completed
    for cand in path:
        session.step(cand.action, cand.data)
    return session.levels_completed > before


def play_with_search(session, levels_wanted: int = 3, node_budget: int = 20000,
                     time_budget_s: float = 120.0, frontier_cap: int = 6000,
                     max_clicks: int = 10, log=print):
    """Chain `find_next_level` until `levels_wanted` levels are cleared or search stalls."""
    results = []
    while session.levels_completed < levels_wanted and not session.is_won:
        path, stats = find_next_level(
            session, node_budget=node_budget, time_budget_s=time_budget_s,
            frontier_cap=frontier_cap, max_clicks=max_clicks,
        )
        results.append(stats)
        if not path:
            break
        ok = replay_verify(session, path)
        if log:
            log(f"    level {session.levels_completed} in {len(path)} actions "
                f"({stats['nodes']} nodes, {stats['secs']}s, verify={ok}) "
                f"-> score {session.score():.2f}")
        if not ok:  # cannot happen with a deterministic engine; if it does, stop loudly
            results.append({"verify_failed": True})
            break
    return results
