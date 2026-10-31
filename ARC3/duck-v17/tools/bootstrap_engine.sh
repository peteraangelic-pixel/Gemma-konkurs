#!/usr/bin/env bash
# Odtworzenie lokalnego przyrządu pomiarowego ARC-AGI-3 od zera, z publicznych źródeł.
#
# Po co: żeby "skąd wziąć pomiar" miało odpowiedź jedną komendą, a nie zależenie od tego,
# co zostało w /tmp z poprzedniej sesji (a nie zostaje nic — /tmp nie persystuje).
#
# Co robi:
#   1. ściąga arcengine 0.9.3 i arc-agi 0.9.9 z PyPI (wheele, bez pipa: wymagają py>=3.12,
#      a sandbox ma 3.11 — dlatego rozpakowujemy i wrzucamy na PYTHONPATH),
#   2. klonuje pliki 25 gier publicznych z gałęzi Smaka (arc-agi-3/games/environment_files),
#   3. odpala smoke: kontroler `template` wyjęty z notebooka na ft09 — oczekiwane 25 akcji / 3 poziomy.
#
# Użycie:
#   bash tools/bootstrap_engine.sh            # do /tmp/arc3-rig
#   ARC3_RIG=/opt/rig bash tools/bootstrap_engine.sh
#
# Po zakończeniu:
#   export PYTHONPATH=$ARC3_RIG/ae:$ARC3_RIG/agx
#   export ARC3_GAMES=$ARC3_RIG/games/environment_files
set -euo pipefail

RIG="${ARC3_RIG:-/tmp/arc3-rig}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(dirname "$HERE")"
NB="${ARC3_NOTEBOOK:-$PKG/arc3-duck-v17.ipynb}"

ENGINE_WHL="https://files.pythonhosted.org/packages/49/ce/efc5dcb66cacfe4c6ada2ba07ed7a6d9971110c9fd6d540793ed6748a12c/arcengine-0.9.3-py3-none-any.whl"
AGI_WHL="https://files.pythonhosted.org/packages/90/53/ddc9450fdbcfaa1af63e2985027f5f3d85c8fccc71b5611cea16f17a0aef/arc_agi-0.9.9-py3-none-any.whl"
GAMES_REPO="https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs.git"
GAMES_BRANCH="codex/arc-local-lab-v18-20261030"

mkdir -p "$RIG"
echo "== rig: $RIG"

if [ ! -d "$RIG/ae/arcengine" ]; then
  curl -sL --max-time 180 -o "$RIG/e.whl" "$ENGINE_WHL"
  curl -sL --max-time 180 -o "$RIG/a.whl" "$AGI_WHL"
  mkdir -p "$RIG/ae" "$RIG/agx"
  unzip -q -o "$RIG/e.whl" -d "$RIG/ae"
  unzip -q -o "$RIG/a.whl" -d "$RIG/agx"
  echo "== wheele rozpakowane"
fi

if [ ! -d "$RIG/games/environment_files" ]; then
  rm -rf "$RIG/smak"
  git clone -q --depth 1 -b "$GAMES_BRANCH" "$GAMES_REPO" "$RIG/smak"
  mkdir -p "$RIG/games"
  cp -a "$RIG/smak/arc-agi-3/games/environment_files" "$RIG/games/"
  echo "== gry skopiowane ($(ls "$RIG/games/environment_files" | wc -l) szt.)"
fi

# zależności runtime'u silnika (na 3.11 trzeba je doinstalować w systemie)
python3 - <<'PY' || pip install --quiet --break-system-packages flask pydantic python-dotenv numpy requests
import flask, pydantic, dotenv, numpy, requests
PY

echo "== smoke: kontroler z notebooka na ft09"
PYTHONPATH="$RIG/ae:$RIG/agx" ARC3_GAMES="$RIG/games/environment_files" ARC3_NB="$NB" python3 - <<'PY'
import importlib.util, logging, os, numpy as np
from arc_agi import Arcade, OperationMode, LocalEnvironmentWrapper
from arcengine import GameAction

nb = os.environ["ARC3_NB"]
spec = importlib.util.spec_from_file_location("ext", os.path.join(os.path.dirname(nb), "tools", "extract_module.py"))
ext = importlib.util.module_from_spec(spec); spec.loader.exec_module(ext)
out = os.path.join(os.environ.get("TMPDIR", "/tmp"), "arc3-rig-modules")
os.makedirs(out, exist_ok=True)
for name, body in ext.files(ext.patch_text(nb)).items():
    with open(os.path.join(out, os.path.basename(name)), "w") as fh:
        fh.write(body)
t = importlib.util.spec_from_file_location("t", os.path.join(out, "codex_template_transfer.py"))
m = importlib.util.module_from_spec(t); t.loader.exec_module(m)

envs = {e.game_id: e for e in Arcade(operation_mode=OperationMode.OFFLINE,
        environments_dir=os.environ["ARC3_GAMES"]).available_environments}
log = logging.getLogger("x"); log.addHandler(logging.NullHandler()); log.setLevel(logging.CRITICAL)
gid = [g for g in envs if g.startswith("ft09")][0]
env = LocalEnvironmentWrapper(environment_info=envs[gid], logger=log, scorecard_id="smoke",
                              seed=731, include_frame_data=True)
fd = env.reset(); ctl = m.TemplateTransfer(); n = 0
while n < 256:
    a = ctl.act(np.array(fd.frame[-1], dtype=np.uint8),
                [6] if 6 in (fd.available_actions or []) else [], int(fd.levels_completed) + 1)
    if a is None:
        break
    fd = env.step(GameAction.ACTION6, {"x": int(a[1]), "y": int(a[2])}); n += 1
print(f"SMOKE: {len(envs)} gier; ft09 = {n} akcji, {fd.levels_completed} poziomów "
      f"(oczekiwane 25 / 3)")
assert (n, fd.levels_completed) == (25, 3), "smoke nie zgadza się z pomiarem referencyjnym"
PY

echo "== gotowe. eksportuj:"
echo "   export PYTHONPATH=$RIG/ae:$RIG/agx"
echo "   export ARC3_GAMES=$RIG/games/environment_files"
