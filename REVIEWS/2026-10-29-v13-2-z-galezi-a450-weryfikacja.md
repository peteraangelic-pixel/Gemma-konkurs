# v13.2 z `arena/a450b00f-pokemon` (`6b10853`) — audyt

**Recenzja z 2026-10-29** (sesja Gemma, `arena/c4eeb067`). Zakres: dwie zmiany v13.2
względem v13.1 (`cbefdd4` → `6b10853`), sprawdzone na prawdziwym silniku i na danych
z zapisanych runów. Plus poprawki wcześniejszego audytu, które nie były jeszcze zacommitowane.

---

## 0. Wniosek

| zmiana | status weryfikacji | efekt |
|---|---|---|
| **guard GAME_OVER w replayu** (mój drobiazg z audytu v13.1) | **zaimplementowany poprawnie, potwierdzony testem** | neutralny dla wyniku, usuwa cichą utratę replayu po śmierci |
| **`ESCALATE_ACTIONS` 60 → 10** | kod działa, env czytany, ale **próg mierzony na naszych danych jest 19× za czuły** | ryzyko: 15,3% puli tokenów na dyrektywy i „przestań próbować" na 31/32 poziomów, na których agent i tak był na tempie |
| playbook | bajt w bajt ten sam (md5 `e2d86b1e07fe`, 14 poziomów) | nadal 14/14, 184/184 hashy, **2,90** średniej na 25 grach publicznych |
| liczba testów „12+8" | **teraz prawdziwa** (`test_plan_commit` 12, `test_winpath` 8) | korekta wcześniejszego zawyżenia przyjęta |

**Werdykt:** v13.2 to krok w dobrym kierunku (eskalacja celuje dokładnie w dźwignię
„akcje na decyzję", która jest jedyną drogą do 50+), ale **wartość 10 jest zgadnięta, nie
zmierzona** — a nasze własne dane mówią, że lepszy jest próg **względny wobec ludzkiego
baseline'u**, który odpala 8 razy zamiast 154 i ani razu „przed czasem". Konkretna łatka: §4.

---

## 1. Co dokładnie się zmieniło

Diff `cbefdd4..6b10853`: 14 plików, ale realnie **dwie** zmiany behawioralne:

1. `src/arc3_winpath.py` +3 linie w `_replay_once`:

```python
raw_state = getattr(getattr(game_state, "raw", None), "state", None)
if str(getattr(raw_state, "name", raw_state)).upper().endswith("GAME_OVER"):
    return False  # dead frame: do not burn the level's replay on it
```

2. notebook, komórka 2: `ESCALATE_ACTIONS = 60` → `10` (i string `v13.1` → `v13.2`).
3. komórka 11: nowa treść patcha (to ta sama zmiana co 1).

Nic więcej: `playbook.json` identyczny, `PLAN_COMMIT="1"` bez zmian, `ARC3_LEVEL_TOKEN_CAP="0"`
bez zmian, `ONLY_RESET_LEVELS="true"` bez zmian.

## 2. Guard GAME_OVER — potwierdzony, robi dokładnie to, o co prosiłem

Test (prawdziwy silnik, ich moduł, dwa wpisy rosteru): wpis 1 rozwiązuje poziom 1, wpis 2
ginie losowo, a pętla woła `maybe_replay` **na martwej klatce**, potem wpis 3 to świeża kopia.

```
v13.1: maybe_replay na martwej klatce -> False; broken=[0]   <-- poziom spalony do końca wpisu
v13.2: maybe_replay na martwej klatce -> False; broken=[]    <-- nic nie spalone
       wpis 3: replay=True -> levels=1  (ścieżka nietknięta)
```

I test regresyjny, że replay między wpisami nadal działa po zmianie:

```
tu93: wpis 1 = 1 poziom / 18 akcji LLM / 10 800 tok  ->  wpis 2 = 1 poziom / 0 tok
vc33: wpis 1 = 1 poziom /  3 akcje                   ->  wpis 2 = 1 poziom / 0 tok
```

Uwaga metodyczna: guard czyta `game_state.raw.state`, a mój pierwszy symulator nie miał
atrybutu `raw` — guard **milczałby** i test certyfikowałby ścieżkę, której nie ma. Poprawiłem
symulator (`FakeState(raw=Raw(state=...))`), dopiero wtedy test ma sens. To dokładnie ten
rodzaj błędu, który daje fałszywe „ALL CHECKS PASSED".

## 3. `ESCALATE_ACTIONS` 60 → 10 — zmierzone na naszych danych

Co ta zmiana robi (kod w `base-v11.ipynb`, patch 0005): gdy `on_level` przekroczy kolejną
wielokrotność progu, do promptu dopisuje się jedna dyrektywa (540 znaków ≈ **146 tokenów**):

> „ESCALATION: N actions on level L without completing it. Stop probing by hand. In this
> turn: (1) state what the recorded transitions leave unexplained; (2) write the rule…
> (3) run `check_model()`… (4) only then `plan()` and `commit()`…"

To jest **nacisk promptowy, nie wymuszenie** — nic nie sprawdza, czy model wykonał punkty
1–4. (Commit message mówi „eskalacja to jedyne wymuszenie" — precyzyjniej: jedyne
*przypomnienie*; `commit()` pozostaje opcją, a jego wykonanie zależy od modelu.)

Wzięte z `r085` (8B, 32 ukończone poziomy, realne liczby akcji na poziom) i przeliczone
`escalation_audit.py`:

| próg | wstrzyknięć | tokenów dyrektyw | % puli gry | odpala **przed** ludzkim baseline'em |
|---|---|---|---|---|
| **@10 (v13.2)** | **154** | 22 330 | **15,3%** | **31/32 poziomów** |
| @60 (v13.1) | 12 | 1 740 | 1,2% | 7/32 |
| baseline×1,2 (propozycja) | **8** | 1 160 | 0,8% | **0/32** |

Przykłady, gdzie @10 mówi „przestań próbować" w trakcie dobrej passy:
`cn04/4` 41 akcji przy baseline 300, `cn04/5` 52 przy 208, `m0r0/3` 94 przy 203,
`dc22/2` 131 przy 102 (tu jedyny przypadek, gdzie nudge jest uzasadniony).

Dlaczego to nie jest tylko kwestia 15% puli: **kosztowna jest posłuszność, nie dyrektywa.**
Każda z 154 zachęt prosi o turę modelarską (`model_state`/`model_step`/`check_model`), a taka
tura to tysiące tokenów. Jeśli model posłucha choćby co czwartej, robi się z tego
~12 tys. tokenów (8% puli) *plus* akcje poświęcone na weryfikację modelu. Przy 12
wstrzyknięciach (v13.1) ten problem nie istnieje.

Druga strona: **kierunek jest słuszny.** `commit(plan, max_actions=40)` wykonuje plan
krok po kroku *wewnątrz jednej tury modelu* (`pc_play`), więc akcje z planu kosztują tylko
czas silnika (~0,3 s) zamiast ~12,9 s. Jeśli połowa akcji szłaby przez `commit`, sekundy na
akcję spadają z 12,9 do ~6,6, a okno 2 945 s pomieści **~450 akcji zamiast 226** — i to jest
dokładnie ten mechanizm, który z 26,8 robi 70+ w moim modelu budżetu (`PLAN-50.md` §2.3).
Czyli: v13.2 celuje w jedyną dźwignię, która ma sufit powyżej 50 — ale czułość progu jest
ustawiona tak, że płacimy za nią na poziomach, które i tak wygrywamy.

## 4. Konkretna poprawka (do wzięcia albo odrzucenia, ale mierzalna)

Próg względny wobec baseline'u. `base_actions_per_level` **już jest** w harnessie
(`GameRun.base_actions_per_level`, to samo, z czego liczy się RHAE), więc nie trzeba nowej
hydrauliki:

```python
def _escalate_threshold(self) -> int:
    """Nudge when the level costs more than the human baseline, not every N actions."""
    floor = _escalate_actions()                     # ARC3_ESCALATE_ACTIONS, np. 20
    try:
        base = self.game.game_run.base_actions_per_level or []
        level = int(self.game.current_state.levels_completed)
        b = int(base[level]) if level < len(base) else 0
    except Exception:
        b = 0
    return max(floor, int(b * 1.2))

# w pętli: zamiast escalate_every * (n+1) użyj self._escalate_threshold() * (n+1)
```

Na r085 to 8 wstrzyknięć zamiast 154, wszystkie na poziomach, na których realnie tracimy
punkty (`ls20/2` 175 vs 123, `ls20/3` 222 vs 73, `ka59/4` 69 vs 51, `m0r0/4` 31 vs 26,
`cn04/1` 35 vs 29, `dc22/2` 131 vs 102, `sc25/1` 47 vs 36 — 8 z 1,2× progiem).
Dodatkowo cap 2 eskalacji na poziom (`cap=2` w audycie) nic tu nie zmienia, ale chroni
przed pętlą na poziomie, na którym model nigdy nie zbuduje modelu.

Jeśli chcesz zostać przy progu absolutnym — **20, nie 10**: przy 20 na r085 jest 60
wstrzyknięć (6% puli), a pierwszy nudge wypada po 20 akcjach, czyli w okolicy mediany
ludzkiego baseline'u (26). Nadal 3× drożej niż v13.1, ale bez „przestań próbować" na
poziomach 1–2.

## 5. Co to znaczy dla slotu 30.10

- v13.2 jest **bezpieczniejszy niż v13.1** (guard) i **ryzykowniejszy** (eskalacja @10).
- Playbook nadal daje podłogę 2,90 na grach publicznych; pamięć między wpisami nadal zależy
  od tego, czy roster powtarza gry (sonda rosteru — wciąż nie ma danych).
- Prognoza bez zmian: **26–31**. @10 może ją obniżyć (15% puli dyrektyw + droga
  posłuszność), a nie podnieść, **jeśli** model zacznie zamiast działać — i tego nie da się
  rozstrzygnąć bez smoke'a.
- Jeśli slot ma iść mimo to: **v13.2 z `ARC3_ESCALATE_ACTIONS=20`** (albo z progiem
  baseline'owym z §4) i z sondą rosteru. Samo 10 bez pomiaru to zakład.

## 6. Ograniczenia

- Liczby „% puli" liczę z r085 (8B, uncapped) — runu 1:1 z v13.2 nie ma.
- „Model posłucha co czwartej eskalacji" to założenie, nie pomiar; pomiar wymaga smoke'a
  z logiem, ile razy padło `commit()`.
- Nie sprawdzałem, czy `check_model()`/`plan()` są w ogóle dostępne przy
  `ARC3_WORLD_MODEL=0`. Z patcha 0005 wynika, że tak (`_wm_enabled = _wm_auto or plan_commit`),
  ale to czytałem, nie uruchamiałem — sandbox potrzebowałby GPU.
