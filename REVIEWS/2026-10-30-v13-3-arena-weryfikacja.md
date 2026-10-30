# v13.3-arena z gałęzi `arena/5ed750ef-smak-domu-konkurs` (`5548d35`) — audyt

**Recenzja z 2026-10-30.** To pakiet zbudowany przez inną sesję Areny (autor zmian: „Arena"),
lineage: v13.2 (Pokemon `6b10853`) → v13.3-arena. Sprawdzone na prawdziwym silniku, na
pliku patcha i na tekście scaffoldu.

---

## 0. Wniosek

**Mechanizm jest prawdziwy i lepszy kierunkowo od wszystkiego, co było w v13.2.** Nie „kolejna
korekta opisu": `ARC3_OPENER_COMMIT_HINT=1` włącza istniejącą w harnessie linię promptu, która
każe modelowi wybierać `action(actions)` (batch) zamiast pojedynczej akcji. To jest **ta sama
dźwignia co `commit(plan)`, ale tańsza** — bez sandboxa, bez planu, bez weryfikacji oczekiwań.
Akcje z batcha nie kosztują tokenów, więc `tok/akcję` spada, a przy stałym wallclocku na grę
rosną akcje na grę — a to jest jedyna zmienna, która realnie skaluje wynik.

Co sprawdziłem i co znalazłem:

| element | status | uwaga |
|---|---|---|
| `_opener_commit_hint()` w scaffoldzie | **istnieje**, czytane przy budowie każdego openera | `_get_env_bool("ARC3_OPENER_COMMIT_HINT", False)`, tekst doklejany w `_build_user_prompt` |
| patch 0007 (log win-path) | **stosuje się czysto** na moduł z v13.2 i daje **bajt w bajt** ich `src/arc3_winpath.py` | `git apply --check` + `cmp` — bez zastrzeżeń |
| 11/11 testów winpath | **przechodzi** lokalnie (arcengine 0.9.3 na ścieżce) | w v13.2 było 8; 3 nowe dotyczą logu |
| replay między wpisami po 0007 | **nadal działa, 0 tokenów** | `tu93`: `replay start` → `record` → `replay ok`, wpis 2 = 0 akcji LLM |
| playbook | bajt w bajt v13.2 (md5 `e2d86b1e07fe`), 14 poziomów | podłoga 2,90 bez zmian |
| `base-v11.ipynb`, patch 0006 | md5 identyczne z v13.2 | łańcuch 6 patchy nietknięty, 7. to log |
| notebook | 36 komórek; różnice tylko w kom. 1, 2 i writerze 0007 | zgodne z ich deklaracją |

**Trzy zastrzeżenia**, żadne nie dyskwalifikuje pakietu (szczegóły w §2–§4).

## 1. Dlaczego to jest lepsze niż v13.2 (mechanizm, nie opinia)

Wszystkie poprzednie wersje zakładały, że model sam zechce wykonać wiele akcji na turę. Dane
z r019/r085 mówią, że nie chce: **~1,0–4,4 akcji na wywołanie**, przy ~12,9 s na akcję i puli
2945 s na grę. Czas na akcję to w ~85% generowane tokeny (regresja z r085: 17,2 ms na token
generowany), więc:

```
akcje_na_grę = czas_na_grę / (tok_na_akcję × 17,2 ms)
```

Batch nie zmienia liczby potrzebnych akcji — zmienia `tok_na_akcję`. Przy `a/call` 4,36 → 6,5
(i tej samej liczbie tokenów na wywołanie) `tok/akcję` spada o ~33%, czyli **akcji na grę rośnie
o ~50%**. To jest dokładnie ten sam efekt, który w moim modelu budżetu przenosi 26,8 na 45–70,
ale osiągnięty jednym `os.environ`, a nie patchem pętli decyzyjnej.

Upstream liczba w docstringu (sekwencje po resumption batchują 6,73/6,91, po świeżym openerze
5,43/3,91) to **korelacja z typem tury, nie wynik włączenia hinta**. Kierunek jest dobrze
uzasadniony, ale efekt samego przełącznika nie był jeszcze zmierzony — i to jest jedyne, co
można mu zarzucić.

## 2. Co v13.3 zostawia na stole

**(a) `ESCALATE_ACTIONS` nadal 10.** Zmierzone na r085 (32 ukończone poziomy, `escalation_audit.py`):
10 odpala 154× (15,3% puli gry w samym tekście dyrektyw) i na **31/32** poziomach każe
przestać próbować, gdy agent jest na tempie albo lepszy od ludzkiego baseline'u. Przy 20: 60×
(6,0%). v13.3 nie rusza tej liczby — świadomie, dla porównywalności z v13.2. Ale w połączeniu
z hintem oba naciski („batchuj" i „przestań probować, zbuduj model") idą w różne strony.

**(b) Zero pomiaru powtarzalności rosteru.** Log 0007 mówi, czy replay *strzelił*, ale nie
odpowiada na pytanie „czy roster w ogóle powtarza gry" — a bez tego nie wiadomo, czy
`ARC3_WINPATH` jest wart 0 czy +5…15.

**(c) Komentarz w OCENA o historii jest odwrócony.** „Trim historii
(`ARC3_HISTORY_ASSISTANT_TURNS` 150→np. 48): −30% tok/akcję" — w tym scaffoldzie domyślna
wartość to **30** (`_persistent_history_assistant_turns()` → `_get_env_int("ARC3_HISTORY_ASSISTANT_TURNS", 30)`),
nie 150. Ustawienie 48 **podniosłoby** limit, czyli zwiększyło historię, a nie przycięło.
Jako „przygotowana opcja na 1.11" jest więc opisana w drugą stronę; sensowny eksperyment to
raczej 30 → 18, i to z jawnym ryzykiem utraty pamięci poziomu.

## 3. Uczciwa ocena ryzyka

- Hint zmienia rozkład tur: mniej wywołań, więcej akcji w każdym. Jeśli model zacznie
  „batchować" ślepo po 8 akcji w nieznanym poziomie, straci precyzję i poziom będzie droższy
  w akcjach, mimo tańszych tokenów. To realne ryzyko i widać je **tylko** w meteringu
  (`actions_per_call` ↑ przy `score` ↓).
- Log 0007: zero ryzyka semantycznego (42 linie, wszystkie `_log(...)`, poza gorącymi
  ścieżkami), ale **nie wyciska** się go w submiscie — zostawia kilkanaście linii na grę.
- `ARC3_WINPATH_LOG` domyślnie 1: przy 110 grach to ~1,5 tys. linii w logu Kaggle. Nie problem.

## 4. Werdykt

v13.3-arena **przechodzi weryfikację**: mechanizm istnieje, patch wchodzi czysto, testy
przechodzą, replay działa, playbook nietknięty. To najlepszy pakiet z tej gałęzi i pierwszy,
który atakuje `tok/akcję` bez dotykania pętli decyzyjnej.

Dołożenie do niego dwóch rzeczy, które mam zmierzone (eskalacja 20) i zaimplementowane
(sondy), daje **v15** — patrz `ARC3/duck-v15/README.md`.
