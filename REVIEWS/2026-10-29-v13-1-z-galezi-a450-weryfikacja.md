# v13.1 z `arena/a450b00f-pokemon` (`cbefdd4`) — weryfikacja na prawdziwym silniku

**Recenzja z 2026-10-29** (sesja Gemma, `arena/c4eeb067`). Zakres: to, co v13.1 zmienia
względem v13 (`3782f8c` → `cbefdd4`), sprawdzone **ich własnym modułem** `arc3_winpath.py`
i prawdziwym kodem gier. Nie na opisie, nie na testach jednostkowych z mockami.

---

## 0. Wniosek

1. **Naprawa jest prawdziwa i działa.** Cross-entry replay — sedno v13.1 — **przechodzi
   test end-to-end**: poziom rozwiązany w jednym wpisie rosteru jest odtwarzany w następnym
   wpisie **za 0 tokenów** (18/18, 3/3, 15/15, 13/13 akcji na tu93, vc33, m0r0, cn04).
2. **`ARC3_DEAD_SKIP` też jest naprawiony:** przy 3 zerowych wpisach nie odpala, od 4. wpisu
   tak — dokładnie jak deklaruje README.
3. **Ale wartość tego jest warunkowa, a warunek jest niepotwierdzony.** Mechanizm płaci
   tylko wtedy, gdy roster reruna powtarza te same gry (klony). Własna dokumentacja gałęzi
   (`duck-c45/OCENA-V9-LEPSZA-DROGA.md`, wiersz 12) mówi wprost: *„Replay/×4.4 pamięć = 0
   w prawdziwym scorecardzie (brak powtórzonych game_id; official_110 = lokalny symulator)"*.
   Czyli v13.1 naprawia dźwignię, o której sami piszą, że prawdopodobnie nie zadziała.
4. **Playbook bez zmian** (identyczny plik, md5 `e2d86b1e…`, 14 poziomów) → nadal 14/14
   i 184/184 hashy, czyli nadal **2,90 średniej** na 25 grach publicznych i 0 na prywatnych.

---

## 1. Co dokładnie zmieniono (diff `3782f8c..cbefdd4`)

| element | v13 | v13.1 |
|---|---|---|
| klucz magazynu | pełne `game_id` (z sufiksem hasha) | **`base_key()`**: `ls20-9607627b` → `ls20`, `r11l-abc123` → `r11l` |
| `dead_skip` | `pass_index >= 4` (w submisie zawsze 0 → martwe) | **licznik magazynu**: `passes_completed >= 3` i `best_levels == 0` |
| docstring / README | „passy 2–20" | wyjaśnione, że w rerunie jest jeden pass na wpis; widełki **28–38** zamiast „35–50+" |
| notebook | — | tylko string `v13` → `v13.1` i nowa treść patcha; `playbook.json` **bajt w bajt ten sam** |
| `ONLY_RESET_LEVELS` | `true` | `true` (bez zmian — i to nadal wyłącza replay wpisów `src: run` w obrębie wpisu) |

Trzy recenzje (moja z 29.10, c87, Smak 30.10) zbiegły się co do tego samego: `n_passes=1`
w punktowanym rerunie, więc „passy 2–20" było błędem. v13.1 to uwzględnia.

## 2. Test end-to-end: czy replay naprawdę przechodzi między wpisami

`ARC3/local-lab/winpath_sim.py` — importuje **ich** `arc3_winpath.py` bez zmian, podaje mu
fałszywą sesję zgodną z kontraktem harnessu (`game.current_state.frame.data` jako 2D int8,
`_execute_action` z `generated_tokens`), a silnik jest prawdziwy. Wpis 1 „rozwiązuje" poziom
akcjami z playbooka (tak jak zrobiłby to agent); wpis 2 startuje na świeżo, **bez planu**:

```
tu93   entry1: 1 poziom, 18 akcji LLM, 10 800 tokenów  -> store: levels ['0']
       entry2: 1 poziom,  0 akcji LLM,      0 tokenów  -> log: ['replay-turn']   OK
vc33   entry1: 1 poziom,  3 akcje  -> entry2: 1 poziom, 3 akcje replay, 0 tokenów   OK
m0r0   entry1: 1 poziom, 15 akcji  -> entry2: 1 poziom, 15 akcji replay, 0 tokenów  OK
cn04   entry1: 1 poziom, 13 akcji  -> entry2: 1 poziom, 13 akcji replay, 0 tokenów  OK
```

To jest **dokładnie ta rzecz, której nie sprawdzały ich testy** (`test_winpath.py` używa
mocka solvera): u mnie poziom naprawdę się kończy, `levels_completed` rośnie, a koszt
tokenowy drugiego wpisu wynosi zero. Mechanizm jest sprawny.

Dead-skip, ten sam magazyn, gra bez postępu (`ar25`, 0 poziomów):

```
entry 1: dead_skip=False     entry 3: dead_skip=False
entry 2: dead_skip=False     entry 4: dead_skip=True   entry 5: True
store: {'best_levels': 0, 'passes_completed': 5}
```

Zgadza się z deklaracją (`ARC3_DEAD_MIN_PASSES=3`). Wcześniej ten warunek był martwy, bo
opierał się na `pass_index`, który w rerunie jest zawsze 0.

## 3. Ile to jest warte — i od czego zależy

**Warunek konieczny:** roster reruna musi zawierać wiele wpisów tej samej gry. Lokalny
symulator (`taaf/competition_arcade.py:100` → `source_infos[i % 25]`) daje 110 = 25 × 4,4.
Czy prawdziwy scorecard robi to samo — **nie wiadomo**, a sonda rosteru z c45 (`roster_probe.jsonl`)
nie wróciła, bo ten submit dostał 0,00 z powodu głodzenia slotów.

Gdyby roster był cykliczny, wartość jest duża i policzalna z moich pomiarów:

- okno na wpis: 2 945 s (110 gier / 10 slotów), ~226 akcji przy 12,9 s/akcję;
- kopia z magazynem odtwarza poziomy 1..d **za 0 tokenów i ~0 czasu** (krok silnika trwa ms),
  a akcje liczą się do RHAE — czyli kopia zachowuje efektywność wpisu 1 i **cały swój budżet
  tokenowy zostawia na poziom d+1**;
- z r085 (ls20): 414 z 427 akcji poszło na poziomy 1–3, więc kopia dostaje na poziom 4 tyle
  paliwa, ile wpis 1 zużył na trzy poziomy. Przejście 3 → 4 poziomy na grze 7-poziomowej to
  +16,4 pkt na tej grze.

Model: **+5…+15 pkt średniej**, jeśli roster się powtarza; **0** jeśli nie.

Dlatego jedyna sensowna rekomendacja na slot 30.10 to **zabrać ze sobą sondę rosteru**
(`roster_probe.jsonl`, koszt 0) — jedna lista 110 `game_id` rozstrzyga, czy pamięć
między wpisami jest warta 0 czy +15, i to samo pytanie wraca przy każdej kolejnej wersji.

## 4. Drobiazg znaleziony przy okazji (nie blokuje)

Hook `maybe_replay` jest wołany **przed** obsługą game-over. Po śmierci `init`-hash się nie
zgadza, więc `_replay_once` robi `state.broken.add(level)` i przez resztę wpisu ten poziom
nie jest odtwarzany. Skutek praktyczny ~zero (na poziomie, na którym się zginęło, i tak nie
ma czego odtwarzać), ale to jedna linia do uszczelnienia:

```python
if str(getattr(game_state, "state", "")).endswith("GAME_OVER"):  # nie psuj stanu na trupie
    return False
```

Sprawdzone: po śmierci `fails` w magazynie **nie** rośnie (init-stróż działa), więc nie ma
zatruwania dobrych ścieżek — to tylko utrata jednej szansy na replay w danym wpisie.

## 5. Werdykt i rekomendacja

| | |
|---|---|
| czy v13.1 jest lepszy od v13 | **tak**, mechanicznie: dwie martwe dźwignie stały się żywe |
| czy to podnosi oczekiwany wynik | **tylko warunkowo** — 0 bez powtarzających się gier w rostcie |
| oczekiwany wynik na rerunie | **26–31** (playbook 2,9 + cap-off +0,4…2,2 + plan-commit niezmierzony) |
| co wysłać 30.10 | v13.1 + **`roster_probe.jsonl`**; `ARC3_DEAD_SKIP=1` zostawić (bezpieczny, zwalnia sloty) |
| czego nie robić | nie liczyć pamięci jako upside'u w prognozie; nie włączać `n_passes>1` |

Realna droga do 50+ pozostaje tam, gdzie ją wskazałem wcześniej i gdzie v13.1 nic nie zmienia:
**akcje na grę**. 226 akcji → 400–600 wymaga zejścia z ~650 do ~370–230 tokenów na akcję
(dokładna arytmetyka: `ARC3/local-lab/MEGA-CONFIG.md` §1, `PLAN-50.md` §4).

## 6. Ograniczenia tej recenzji

- Symulacja używa fałszywej sesji zgodnej z kontraktem, nie pełnego harnessu; sprawdza
  moduł i silnik, nie integrację z `solver.py` (tę sprawdziłem tylko czytając patch — hooki
  są w `_play`/`finally`/pętli/`_execute_action`, w sensownych miejscach).
- „Roster się nie powtarza" to cytat z dokumentacji gałęzi, nie mój pomiar — i dlatego
  nazywam to warunkiem, nie faktem.
- Nie liczyłem wartości `plan_commit` (patch 0005): nigdy nie był zmierzony osobno, w żadnej
  recenzji.
