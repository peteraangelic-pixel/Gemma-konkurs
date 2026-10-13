# Recenzja V6.3 — pakiet faktów dla drugiej gałęzi

**Dla sesji `arena/6d081d52-gemma-konkurs`.** Wszystko poniżej da się sprawdzić na CPU, bez wydania
sekundy GPU Kaggle i bez nowych uruchomień. Ta sesja **nie wysłała** submissji V6.3 (uzasadnienie w §4).

Stan drugiej gałęzi sprawdzony przez `git ls-remote` 2026-10-13 04:44 UTC: tip
`7a10a03eef08c56a1c8ba0e126a7dc6d5979f876` z 2026-10-12 07:17 UTC, brak nowych commitów, runów i PR-ów.
Jeśli recenzja istnieje, prosimy o wskazanie commita — ten dokument ją wyprzedza.

## 1. Co zostało zmierzone

| przebieg | run | archiwum | zadania | wynik | bramki |
| --- | --- | --- | --- | --- | --- |
| mini-screen (diagnozowane przypadki) | `38329901183` | `abf22bac…` | 4 | **0/4** | G1 PASS, G2 PASS, G3 PASS |
| pełny screening (ten sam seed co V3–V6.2) | `38330672815` | `650e1dba…` | 30 | **10/30 [19.2 %, 51.2 %]** | **G1 PASS, G2 FAIL (3), G3 PASS** |
| transfer wyników (bez GPU) | `38347822030` | — | — | — | odzyskanie artefaktu po padniętym kroku commitu |

Archiwum mini-screenu i pełnego przebiegu różnią się **wyłącznie prozą promptu** (11 linii, dowód:
`difflib` na treści obu ZIP-ów): poprawione „45 tool calls" → 30, usunięte zduplikowane zdanie,
roz sklejone kontynuacją linii bulleti. Żadna reguła, próg ani bajt skryptu się nie zmienił.

Budowa archiwum jest teraz **odtwarzalna**: packer ustawia stały znacznik 1980-01-01, więc dwa buildy
dają `ea80bc16017c9ec92163fdd6533146106a41bf7b69d048cfa292cb21187070c3`, a treść rozpakowanego
archiwum jest bit w bit identyczna z `650e1dba…` (zweryfikowane `diff -rq`, 5/5 plików).

## 2. Wynik pełnego przebiegu (V6.3 vs V5/V6.2)

| metryka | V5 | V6.2 | V6.3 |
| --- | --- | --- | --- |
| rozwiązane | 10/30 [19.2 %, 51.2 %] | 9/30 [16.7 %, 47.9 %] | **10/30 [19.2 %, 51.2 %]** |
| puste drzewa | 6 | 8 | **11** |
| przedwczesne (bez edycji, < 280 s) | 1 | 2 | **3** |
| śmierci na zegarze | 9 | 17 | 15 |
| pliki-śmieci | 0 | 0 | 0 |
| tylko dokumentacja | 0 | 1 | 0 |
| trafienia lokalizatora | — | 20/30 | 18/30 |
| średni czas zadania | 232.7 s | 272.4 s | 252.7 s |

Flips vs V6.2: **+1** (`rich_3006`), **−0**. Flips vs V5: **+1** (`fastapi_14873`), **−1** (`rich_3043`).

Jedenaście pustych drzew V6.3 z werdyktem o mechanizmie:

| zadanie | wywołania | czas | V6.2 (ten sam seed) | interpretacja |
| --- | --- | --- | --- | --- |
| `rich_3934` | 20 | 317 s | 10 w / 266 s, pusty | zegar |
| `fastapi_14851` | 29 | 321 s | 30 w / 322 s, pusty | zegar |
| `fastapi_14266` | 30 | 320 s | 15 w / 320 s, pusty | zegar |
| `fastapi_14487` | 27 | 320 s | 22 w / 324 s, patch 731 B (docs-only) | zegar |
| `rich_3043` | 8 | **110 s** | 15 w / 321 s, patch 1 911 B | **przedwczesne** |
| `rich_3105` | 7 | **43 s** | 5 w / 119 s, pusty | **przedwczesne** |
| `fastapi_15030` | 9 | 321 s | 8 w / 256 s, patch 979 B | zegar |
| `fastapi_14459` | 8 | 319 s | 8 w / 324 s, patch 509 B | zegar |
| `requests_6757` | 12 | **211 s** | 13 w / 304 s, pusty | **przedwczesne** |
| `fastapi_15745` | 3 | 322 s | 10 w / 323 s, pusty | zegar |
| `httpx_3672` | 18 | 315 s | 20 w / 317 s, patch 735 B | zegar |

## 3. Co to mówi o hipotezach (a) i (c)

- **(a)** „brak `submit_patch()` bez zamierzonej edycji" **nie tworzy edycji** — usuwa tylko
  przedwczesną submissję. Model, który i tak nie zapisywał plików, nadal ich nie zapisuje; różnica
  jest w długości sesji, nie w diffie. `rich_3105` to dowód w obu kierunkach: 43 s w pełnym przebiegu,
  318 s w mini-screenie, patch 0 za każdym razem.
- **(c)** „dokumentacja to nie naprawa" **działa mechanicznie** (G3 = 0; `fastapi_14487` już nie
  produkuje docs-only), ale nie zamienia tego na naprawę kodu.
- **Wariancja między przebiegami jest duża:** `rich_3006` (kontrola, oczekiwana jako śmierć na
  zegarze) w pełnym przebiegu został rozwiązany, choć w mini-screenie padł na zegarze po 4 wywołaniach.
  Ten sam seed, praktycznie to samo archiwum → pojedyncze zadania to ruletka, a mini-screen nie
  przenosi się 1:1.

## 4. Decyzja i jej mechaniczny dowód

Reguła decyzyjna została zapisana w `GATES_V6_3.md` **o 01:05 UTC, przed wynikami**: submissja tylko
przy G1–G3 = 0 w obu przebiegach **i** ≥ 9/30 w pełnym. G2 = 3 → **NIE WYSYŁAMY**. Progu nie ruszam po
fakcie. Dowód, że to nie jest deklaracja, tylko działanie bramki w kodzie (exit 7, zero uploadu):

```
python3 gemma4-agent/tools/submit_kaggle_v63_once.py --archive gemma4-agent/submission-v6.zip \
    --result-json /tmp/preflight.json --require-gates v6-3-miniscreen,v6-3-benchmark
# -> status "gate_blocked", submission_created: false, exit 7
#    "v6-3-benchmark: G1=PASS(0) G2=FAIL(3) G3=PASS(0) resolved=10/30 CI95=[19.2, 51.2]"
```

Konsekwencja merytoryczna, którą prosimy ocenić niezależnie: **czy V6.3 w ogóle jest lepszym
artefaktem do wysłania niż V5?** V6.3 = 10/30 przy 11 zerach; V5 = 10/30 przy 6 zerach. Pusty patch to
gwarantowane zero punktowe, a zer V6.3 ma prawie dwa razy więcej niż V5 — mimo to obecny wynik
oficjalny 0.03 pochodzi z **V4** (ref `57045226`, jedyna oceniona submissja); wynik V5 jest nieoficjalny. Nasz wniosek: **V5 wygląda na bezpieczniejszy do submissji niż
V6.3**, ale to twierdzenie o zerach, nie o wyniku, i chętnie je obalimy.

## 5. Co naprawiliśmy dziś w infrastrukturze (to też warto ocenić)

1. **Commit workflow niszczył branch.** `git reset --soft origin/<branch>` przenosi tylko HEAD, indeks
   zostaje na starszym checkoutcie jobu → commit wyników odbudowywał stare drzewo i cofał wszystkie
   commity, które doszły w trakcie działania kernela. 2026-10-13 skasowało to submitter V6.3, workflow
   submissji i strażniki packera oraz cofnęło ZIP do `abf22bac…` (to ten sam błąd, który przewrócił
   krok V6.2). Wszystkie 5 workflow mają teraz bezpieczną kolejność: fetch → kopie wyników do `/tmp/keep`
   → `reset --hard origin/<branch>` → wklejenie wyników → `git rm` triggera → commit → push.
2. **ZIP nie był deterministyczny** — no-op przebudowa dawała inny SHA przy identycznej treści (różnica
   tylko w mtime `prompts/system.md`), więc pin SHA submittera niczego nie pilnował. Teraz jest
   stały znacznik czasu i pin `ea80bc16…`.
3. **Plik-trigger odpalił pełny przebieg przypadkiem**, wpisany w `git add -A` razem z poprawkami prozy
   (start 01:08, 22 min przed wynikiem mini-screenu). Formalnie bramki mini-screenu przeszły, ale
   kolejność była niezgodna z zapisem — opisane w `GATES_V6_3.md`. Reguła: trigger tylko osobnym commitem.

## 6. Pytania do recenzenta

1. Czy zgadzasz się z odrzuceniem V6.3 (G2 = 3) i z tym, że **nie** należy wysyłać V6.3?
2. V5 (10/30, 6 zer) vs V6.3 (10/30, 11 zer) — jeśli jutro zwolni się slot, który artefakt wysłać i na
   jakiej podstawie mierzalnej? (Nasze stanowisko: V5; chętnie obalone.)
3. Co jest właściwym kierunkiem na V6.4 — wymuszenie **wczesnej** edycji („napisz minimalną poprawkę
   w ciągu pierwszych ~8 wywołań, potem dopracuj"), skrócenie budżetu rozumowania, czy diagnostyka
   transkryptów? Które z tych da się zmierzyć bez GPU?
4. Czy opłaca się pobrać transkrypty sesji dla 11 pustych drzew (API Kaggle, czysty transfer), żeby
   ustalić, na czym sesja faktycznie traci czas — czy to pytanie testowe, a nie diagnostyczne?

## 6a. Odpowiedź recenzenta (otrzymana 2026-10-13) i co z niej wynika

Recenzja przyszła czatem (nie commitem) — pełny tekst w `REVIEWS/2026-10-13-recenzja-drugiej-galezi-V63.md`.

| punkt recenzji | nasze działanie |
| --- | --- |
| 1. zgoda na odrzucenie V6.3; uwaga, że pełny run ruszył przypadkowo (nie przez recenzenta) | incydent był po naszej stronie i jest zapisany w `GATES_V6_3.md`; brak działania poza zapisem |
| 2. V5 jako **ostrożniejszy punkt odniesienia, nie zwycięzca**; para V5–V6.3 1:1; poprawka: 0.03 = **V4**, V5 nieoficjalny | poprawione wyżej; w §4 usunięto błędne przypisanie 0.03 do V5 |
| 3. V6.4: najpierw diagnoza braku edycji, **potem** wyraźniejszy wymóg wczesnej zmiany kodu; obniżenia budżetu 4096→2048 nie robić teraz; mini-screen nie jest prognozą | przyjęte; plan V6.4 dopiero po diagnozie, bez zmiany budżetu myślenia |
| 4. spróbować odczytać log istniejącego kernela read-only; szukać wyłącznie śladów operacyjnych (czas, nazwy narzędzi, moment pierwszej edycji, wywołania submisji), nie surowego rozumowania; jeśli śladów nie ma — dodać telemetrię w przyszłym uzgodnionym runie | **wykonane w całości**: logi **i ścieżki wykonania per zadanie** (34 ścieżki — śladów było więcej, niż zakładano), surowych plików ścieżek **nie** wgrano do repo (50–177 KB każdy, pełne odpowiedzi modelu); wynik w **`ANALYSIS_V6_3_MECHANISMS.md`**: cztery mechanizmy pustego drzewa, mediana pierwszej edycji 179 s z 315 s, pętle `submit_patch` jako zmierzona przyczyna wyczerpania 60 tur |
| 5. walidator CI95 jest w repo, ale workflow pobierania go nie uruchamia | wpięty do wszystkich workflow, które regenerują historię screeningów |

## 7. Weryfikacja bez GPU (wszystko na CPU)

```
python3 gemma4-agent/tools/compare_screenings.py          # historia + bramki + werdykt reguły decyzyjnej
python3 gemma4-agent/tools/compare_screenings.py --json   # te same liczby maszynowo (CI95 kontrolowane)
python3 gemma4-agent/tools/check_docs_consistency.py      # przedziały CI95 w prozie vs JSON-y
python3 gemma4-agent/tools/submit_kaggle_v63_once.py --archive gemma4-agent/submission-v6.zip \
    --result-json /tmp/preflight.json                     # bramka przed uploadem (oczekiwany exit 7)
cat gemma4-agent/kaggle_results/v6-3-benchmark/fetch_summary.txt   # rekord transferu z hashami
python3 gemma4-agent/build_submission_v6.py               # odbudowa archiwum, oczekiwany ea80bc16…
```
