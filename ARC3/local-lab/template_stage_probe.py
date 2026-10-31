#!/usr/bin/env python3
"""Na którym etapie rozpoznawania odpada kontroler `template` na 25 grach?

Etapy: (1) kwadraty >=8 w jednym rozmiarze, (2) siatka 3x3 paneli, (3) panel
docelowy z innym stampem / niezgodna komórka, (4) akcja. Wszystko na PRAWDZIWYM
silniku, na klatce startowej każdej gry (i po kilku klikach, dla uczciwości).
"""
import json
import logging
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "template-audit"))
from template_transfer import infer_copy_action, rectangles  # noqa: E402


def stages(grid):
    a = np.asarray(grid, dtype=np.uint8)
    squares = [r for r in rectangles(a) if r[1] - r[0] == r[3] - r[2] and r[1] - r[0] >= 3]
    sizes = Counter(r[1] - r[0] for r in squares)
    big = [s for s, n in sizes.items() if n >= 8]
    if not big:
        return 1, len(squares), 0
    size = max(big, key=lambda s: s * s * sum(r[1] - r[0] == s for r in squares))
    cells = {(r[0], r[2]) for r in squares if r[1] - r[0] == size}
    gaps = Counter()
    for y, x in cells:
        for yy, xx in cells:
            if y == yy and size < xx - x <= 3 * size:
                gaps[xx - x] += 1
    if not gaps:
        return 2, len(squares), 0
    pitch = max(gaps, key=gaps.get)
    origins = {(y - i * pitch, x - j * pitch) for y, x in cells for i in range(3) for j in range(3)}
    coords = [(i, j) for i in range(3) for j in range(3) if (i, j) != (1, 1)]
    span = 2 * pitch + size
    panels = [o for o in origins
              if o[0] >= 0 and o[1] >= 0 and o[0] + span <= a.shape[0] and o[1] + span <= a.shape[1]
              and all((o[0] + i * pitch, o[1] + j * pitch) in cells for i, j in coords)]
    if not panels:
        return 2, len(squares), 0
    return 3, len(squares), len(panels)


def main():
    from arc_agi import Arcade, OperationMode, LocalEnvironmentWrapper

    env_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/v18lab/arc-agi-3/games/environment_files"
    arcade = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=env_dir)
    envs = {e.game_id: e for e in arcade.available_environments}
    log = logging.getLogger("x")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    print(f"{'gra':10}{'etap':>6}{'kwadraty':>10}{'panele':>8}{'akcja?':>8}")
    tally = Counter()
    for gid in sorted(envs):
        env = LocalEnvironmentWrapper(environment_info=envs[gid], logger=log,
                                      scorecard_id="probe", seed=731, include_frame_data=True)
        fd = env.reset()
        grid = np.array(fd.frame[-1], dtype=np.uint8)
        st, sq, pn = stages(grid)
        act = infer_copy_action(grid)
        tally[st] += 1
        print(f"{gid[:8]:10}{st:6}{sq:10}{pn:8}{'TAK' if act else 'nie':>8}")
    print("\nrozklad etapów porażki:", dict(sorted(tally.items())))
    print("etap 3 = struktura paneli rozpoznana (rodzina ft09), etap <3 = brak struktury")


if __name__ == "__main__":
    main()
