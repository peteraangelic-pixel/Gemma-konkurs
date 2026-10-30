# Indeks recenzji (od najnowszej)

| data | plik | czego dotyczy | werdykt w jednym zdaniu |
|---|---|---|---|
| 2026-10-30 | `2026-10-30-v13-7-final-audyt.md` | duck-v13-7-final (gałąź 5ed750ef, commit `de57e4d`) | to **v16 + patch 0010** (0006–0009/playbook/winpath md5 identyczne); 0010 jest poprawny i podłączony, ale na traktach r085 daje **6 RESET / 0 ABANDON na 10 gier**, a premisa „35–91% tokenów" to dziś **25%** — nośnik, nie dźwignia; ich bramka **a/call ≥ 6,0 = 50 pkt** odtworzona niezależnie (4,441 → 5,9) |
| 2026-10-30 | `2026-10-30-v17-action-efficiency-audyt.md` | duck-v17-action-efficiency (gałąź 5ed750ef, commit `283a36b`) | liczby się odtwarzają (7/7, 40,06), ale 40,06 to planista, nie warstwa — `agent.py`/`run_eval.py` nie importują `action_efficiency_layer`; na r085 cięcie akcji −30% = **+2,05 pkt**, a +1 poziom = +16,4 → **nie nakładać, nie robić v18** |
| 2026-10-30 | `2026-10-30-v13-4-v15-porownanie-i-v16.md` | v13.4-unified (Smak) + duck-v15 (Pokemon) + moje v16 | oba pakiety w porządku, ale ich eskalacja relatywna jest w rerunie martwa (baseline `None`); 0009 self-pace to jedyny próg, który tam działa |
| 2026-10-30 | `2026-10-30-v13-3-arena-weryfikacja.md` | v13.3-arena (`5548d35`) | mechanizm opener-hinta istnieje i jest właściwą dźwignią `tok/akcję`; patch 0007 (log) wchodzi czysto i odtwarza plik 1:1; zostawia 10 na eskalacji |
| 2026-10-29 | `2026-10-29-v13-2-z-galezi-a450-weryfikacja.md` | v13.2 (`6b10853`) | guard GAME_OVER działa; `ESCALATE_ACTIONS=10` mierzone na r085: 154 nudge'ów = 15,3% puli i 31/32 „przestań próbować" na poziomach wygrywanych |
| 2026-10-29 | `2026-10-29-v13-1-z-galezi-a450-weryfikacja.md` | v13.1 (`cbefdd4`) | replay między wpisami rosteru działa (0 tokenów), ale płaci tylko przy cyklicznym rosterze — 0 albo +5…15 |
| 2026-10-29 | `2026-10-29-v13-mega-z-galezi-a450-weryfikacja.md` | v13 (`3782f8c`) | playbook 14/14 i 184/184 hashy odtworzone; dwie z trzech dźwigni są w submisji martwe |
| 2026-10-25 | `2026-10-25-arc3-dwie-galezie-pokemon-i-co-z-tego-wynika.md` | dwie gałęzie Pokemon | — |
| 2026-10-24 | `2026-10-24-arc-agi-3-dlaczego-nie-ma-45.md` | diagnoza „dlaczego nie 45+" | — |
| 2026-10-16 | `2026-10-16-weryfikacja-raportu-drugiej-galezi.md` | raport drugiej gałęzi | — |
