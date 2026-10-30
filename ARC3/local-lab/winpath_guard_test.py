"""Does the v13.2 GAME_OVER guard behave: skip without poisoning the level's replay?

Reproduces the exact scenario the guard exists for: entry 1 records a level's winning path,
entry 2 dies, and the patched solver loop calls `maybe_replay` on the dead frame *before* its
auto-reset branch. On v13.1 that call marks the level broken for the rest of the entry; on
v13.2 it returns early. Entry 3 then proves the stored path is still usable.

    python3 winpath_guard_test.py <arc3_winpath.py> <playbook.json>
    (add ARC3_ENGINE_PATHS / --games-dir as in the other tools)
"""
import sys, os, tempfile, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
for _p in (os.environ.get("ARC3_ENGINE_PATHS") or "").split(":"):
    if _p:
        sys.path.insert(0, _p)
import winpath_sim as W
os.environ.update(ARC3_WINPATH="1", ARC3_WINPATH_DIR=tempfile.mkdtemp(), ARC3_DEAD_SKIP="0")
wp = W.load_winpath(sys.argv[1])
from lab.engine import Lab
from arcengine import ActionInput, GameAction, GameState
lab = Lab(games_dir=os.environ.get('ARC3_GAMES'))
book = json.load(open(sys.argv[2]))
plan = [(x['name'], x.get('data')) for x in book['games']['cn04']['levels']['0']['actions']]

web = lab.session('cn04'); s1 = W.FakeSession(web, wp, 'cn04-e1'); wp.begin_session(s1)
for name, data in plan:
    s1._execute_action(ActionInput(id=GameAction[name], data=dict(data or {})), generated_tokens=600)
wp.end_session(s1)
print('wpis 1 -> levels', web.levels_completed, '(magazyn ma ścieżkę poziomu 1)')

# wpis 2: gra ginie (losowo), potem pętla woła maybe_replay NA MARTWEJ KLATCE
web2 = lab.session('cn04'); s2 = W.FakeSession(web2, wp, 'cn04-dead'); wp.begin_session(s2)
import random; random.seed(3)
while not web2.is_over:
    a = random.choice([x for x in web2.available if x != 0] or [1])
    d = {"x": random.randrange(64), "y": random.randrange(64)} if a == 6 else {}
    s2._execute_action(ActionInput(id=GameAction.__members__[f'ACTION{a}'], data=d), generated_tokens=600)
print('wpis 2: game_over =', web2.is_over, '| raw.state =', getattr(web2.last, 'state', None))
st = wp._SESSIONS[id(s2)]
consumed = wp.maybe_replay(s2)
print(f'  maybe_replay na martwej klatce -> {consumed}; broken={sorted(st.broken)} '
      f'(puste = poziom NIE został spalony)')
wp.end_session(s2)

# wpis 3: świeża kopia, zdrowa klatka -> replay musi nadal działać
web3 = lab.session('cn04'); s3 = W.FakeSession(web3, wp, 'cn04-clean'); wp.begin_session(s3)
ok = wp.maybe_replay(s3)
print(f'wpis 3 (świeża kopia): replay={ok} -> levels={web3.levels_completed} '
      f'{"OK" if ok and web3.levels_completed==1 else "REGRESJA"}')
