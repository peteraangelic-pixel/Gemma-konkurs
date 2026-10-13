# Porównanie: moje V6.6 a praca drugiej gałęzi (2026-10-13 ~19:00 UTC)

## Ustalenie podstawowe: drugiej V6.6 **nie ma w repozytorium**

Sprawdzone przez `git ls-remote` i przegląd wszystkich gałęzi (nie z pamięci ani z założenia):

| gałąź | tip | ostatni commit | co zawiera |
| --- | --- | --- | --- |
| `arena/6d081d52-gemma-konkurs` (ich) | `8eb94cd` | **2026-10-13 08:53:56 UTC** | paczka **V6.4** (`submission-v6.4.zip`, `build_submission_v64.py`, `V6_4_PREPARATION.md`) |
| `arena/c4eeb067-gemma-konkurs` (moja) | `27c4f1d` | 2026-10-13 17:59:43 UTC | V6.4 (zmierzony), V6.5, **V6.6** |
| `main` | `c0256ba` | 2026-10-10 | bez zmian |

Na ich gałęzi **nie ma żadnego pliku V6.6** (sprawdzone `git ls-tree | grep -i "6\.6\|v66"` — zero
wyników), nie ma otwartych PR-ów, a ostatni ich commit jest sprzed **9 godzin**. Runy Actions z ich
gałęzi: brak nowych.

**Wniosek: nie da się porównać „mojego V6.6 z ich V6.6", bo ich V6.6 nie istnieje po stronie
repozytorium.** Jeżeli tamta sesja zbudowała coś lokalnie w swoim sandboksie, musi to wypchnąć —
praca niepchnięta jest dla mnie niewidoczna (ta sama pułapka, w którą wpadłem dziś rano, ogłaszając
„zero nowych osiągnięć", gdy ich paczka V6.4 istniała tylko w ich worktree).

Poniżej porównuję więc to, co realnie da się porównać: **moje V6.6 z ich najnowszą pracą, czyli V6.4.**

## Plik po pliku: ich V6.4 vs moje V6.6

| plik | stan | ich | moje |
| --- | --- | --- | --- |
| `agent.yaml` | różne (komentarze) | 1116 B | 1928 B |
| `eval_config.yaml` | **identyczne** | 1125 B | 1125 B |
| `configs/sampling.yaml` | **identyczne** | 609 B | 609 B |
| `tools/locate.py` | różne (komentarz `# Usage`) | 7874 B | 8056 B |
| `prompts/system.md` | różne (istota) | **17 888 B** | **19 770 B** |
| archiwum | — | `0cc04c08…`, 12 375 B | `b6686c53…`, 13 721 B |

Lista narzędzi (8, bez `submit_patch`), budżety (150 s / 30 wywołań / 60 tur / 5,25 min) i sampling
(temp 0,4, thinking 4096, `include_thoughts: true`) są **identyczne**. Oba archiwa rozpakowują się do
treści bit w bit zgodnej ze swoimi katalogami źródłowymi — sprawdzone `diff -rq`.

## Reguły w promptach — co ma kto

| cecha | ich V6.4 | moje V6.6 | uwaga |
| --- | --- | --- | --- |
| termin pierwszej edycji = tool call 4 | **TAK** (linie 7, 33, 51) | TAK | **pomysł ich** — przyjęty przeze mnie dziś |
| zakaz atrapy („never create a dummy edit") | **TAK** | TAK | **pomysł ich** |
| `submit_patch` usunięty + zdanie w prompcie | **TAK** („V6.4 does not expose `submit_patch()`") | TAK („There is no submit tool.") | **pomysł ich** |
| reguła o plikach roboczych → `/tmp` | TAK (z jawnym wyjątkiem na heredoc lokalizatora) | TAK + kontrprzykład `/tmp/repro.py` + pomiar 279,8 s | oni rozwiązują sprzeczność **wyjątkiem**, ja **usuwam** źródło |
| zakaz gołej nazwy pliku (lekcja z V6.1: 9/30 zniszczonych) | — | **TAK** | u mnie z pomiarem |
| **M2: ratunek po nieudanym `edit_file`** | **— (brak)** | **TAK** | zmierzone u mnie: 9 edycji pod rząd → 2, patch 0 → 1348 B |
| dowód przy M1 („31 calls") | — | TAK | uzupełnienie, nie nowa reguła |
| **V6.6: lokalizator bez pliku (inline `-c`)** | **— (nadal zapisuje `/tmp/locate.py`)** | **TAK** | patrz niżej — to główna różnica |
| dźwignia V6.5 (edycja bez pewności) | — | — | celowo nie ma jej w V6.6 (jedno ramię na raz) |

## Różnica, która ma zmierzony powód: pułapka pliku lokalizatora

Ich V6.4 nadal każe **najpierw zapisać plik** (`cat > /tmp/locate.py <<'LOCATE_PY' … python3
/tmp/locate.py …`), a ich builder pilnuje, że reguła o plikach roboczych **robi wyjątek** dla tego
heredoku (`the scratch-file rule does not resolve the locator heredoc exception`).

Moje V6.4 robiło to samo — i pełny przebieg 30 zadań pokazał, co z tego wynika:

| zadanie | wywołań | zachowanie | wynik |
| --- | --- | --- | --- |
| `fastapi_15588` | **3** | zapisał `/tmp/locate.py` i skończył | puste drzewo (243,8 s) |
| `fastapi_15745` | **3** | to samo | puste drzewo (340,6 s) |
| `rich_3043` | 4 | to samo | puste drzewo (319,8 s) |
| `httpx_3672` | 10 | to samo | puste drzewo (315,7 s) |

Cztery sesje (13 %) uznały gotowy skrypt za wykonaną pracę. Wersje bez kroku lokalizatora
(V3/V4/V5) miały **6** pustych drzew, V6.x ma **11**. Dlatego moje V6.6 usuwa plik konstrukcyjnie
(jedno polecenie, skrypt jako argument `-c`, issue na stdin), a nie apelem. Ich V6.4 tej pułapki
jeszcze nie adresuje.

## Strażniki buildera

| | ich `build_submission_v64.py` | mój `build_submission_v6.py` |
| --- | --- | --- |
| linii | 205 | 402 |
| `fail(...)` | 24 | 54 |
| kontrola | model, lista narzędzi, brak `submit_patch`, termin call 4, reguła plików roboczych + wyjątek heredoku, brak `submit_patch` w prompcie, osadzenie lokalizatora, budżety, thinking, ścieżka wyjścia | to samo **plus** strażnik sprzeczności, dowody pomiarowe, rozróżnienie wariantów V6.4/V6.5/V6.6 (blok lokalizatora z obcej wersji nie zbuduje się w żadną stronę) |

Ich builder jest równoważny dla **swojego** artefaktu — ma mniej strażników, bo mają jeden wariant,
nie trzy. Nie jest to zarzut, tylko różnica zakresu.

## Stan dowodowy (co jest zmierzone, a co nie)

| wersja | przebiegi | wynik |
| --- | --- | --- |
| ich V6.4 | **żadnego** | nieuruchomiony |
| moje V6.4 | mini (6 zadań) + pełny (30 zadań) | 10/30 = **dokładnie ten sam zbiór zadań co V6.3**, puste drzewa 11, G2 = 3 |
| moje V6.5 | **żadnego** (jutro) | dźwignia framingu edycji |
| moje V6.6 | **żadnego** (jutro) | dźwignia lokalizatora bez pliku |

To jest najważniejsza część uczciwego porównania: **żadna z porównywanych wersji nie ma wyniku
lepszego od drugiej, bo żadna nie została zmierzona jako lepsza.** Mój V6.4 jest zmierzony jako
*nie gorszy* od V6.3 (identyczny zbiór zadań), a ich V6.4 jest zestawem reguł, który w moim pomiarze
daje mechanizmy M1+M3+M4 (bez M2).

## Co z tego dla decyzji

1. Ich V6.4 jest **podzbiorem** reguł mojego V6.4 (brakuje M2), z innym rozwiązaniem sprzeczności o
   pliki (wyjątek zamiast usunięcia źródła) i bez pułapki lokalizatora rozwiązanej konstrukcyjnie.
2. **Jeśli tamta sesja ma własne V6.6 (albo cokolwiek nowszego niż `8eb94cd`), musi to wypchnąć** —
   inaczej porównanie „V6.6 vs V6.6" pozostaje niewykonalne, a ja mogę porównywać tylko z ich V6.4.
3. Jutrzejsze dwa przebiegi (V6.5 i V6.6) są rozstrzygające dla mojej strony; ich wersje nie mają
   żadnego przebiegu, więc nie mogą być argumentem w dyskusji o wyniku, dopóki ich nie uruchomią.
