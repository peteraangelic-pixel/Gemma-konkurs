# Druga gałąź i technika z projektu sąsiedniego (2026-10-14)

Dwa zadania: (1) sprawdzić najnowszą wersję z drugiej gałęzi konkursowej, (2) przyjrzeć się, jak
swojego agenta udoskonala sesja w projekcie Pokemon („500 mutacji itp.") i sprawdzić, co da się
przenieść. Efektem jest nowe ramię **V6.8** (`GATES_V6_8.md`), zbudowane i zwalidowane offline.

## 1. Druga gałąź: nic nowego, paczka identyczna z naszą

- Tip drugiej gałęzi: **`8eb94cd`** („Add offline V6.4 candidate package", 2026-10-13 08:53 UTC).
  Od naszej ostatniej recenzji (13.10) **nie doszedł ani jeden commit** — to nadal ich V6.4.
- Porównanie bajt w bajt z naszymi plikami:

| plik | ich `8eb94cd` | nasz | wynik |
| --- | --- | --- | --- |
| `tools/locate.py` | 7 874 B | `submission-v6.4/tools/locate.py` 7 874 B | **identyczny** (diff pusty) |
| `prompts/system.md` | 17 888 B / 237 linii | 17 888 B / 237 linii | **identyczny** (0 różniących się linii) |
| `configs/sampling.yaml`, `eval_config.yaml`, `agent.yaml` | — | — | identyczne |

Czyli „najnowsza wersja z drugiej gałęzi" = dokładnie to, co już mamy w `submission-v6.4`, i to,
co zrecenzowaliśmy 13.10 (`REVIEWS/2026-10-13-recenzja-drugiej-galezi-V64-poprawki.md`). Nie ma tam
nic do zaadoptowania — a ich lokalizator, budowany niezależnie, wyszedł identyczny z naszym, co jest
niezależnym potwierdzeniem, że ten komponent jest już dobrze zoptymalizowany ręcznie.

## 2. Technika z projektu Pokemon: wyszukiwanie populacyjne stałych

Z repo `peteraangelic-pixel/Pokemon` (gałąź `arena/c87f7a48-pokemon`, bardzo aktywna — v42.x z 14.10)
odczytane pliki: `SUBMISSION_LOG.md` (wpisy o ewolucji pokręteł), `tools/search_gen8.py`,
`tools/evolve_knobs_small.py`, `rust/src/bin/evolve_tempo.rs` (nagłówki, skrypty są tam tylko
placeholderami — pełne wersje przepadły w `/tmp`).

**Metoda w trzech punktach:**

1. **Szybki, deterministyczny evaluator.** Ich symulator gra 120 partii w 3 s (FFI/Rust), więc
   populacja 1000+ jest osiągalna; ewolucja 100 mutantów × 138 gier trwa 163 s na 4 workerach.
2. **Ewolucja populacyjna z kompozytowym fitness.** `SEARCH_SPACE` = 26 nazwanych stałych („pokręteł")
   z zakresami; start losowy, potem top-3 × mutacja gaussowska (rate 0.2, strength 0.15) + świeży
   losowy dopływ; selekcja po `fitness = 0.7*winrate + 0.2*prize_pace + 0.1*first_prize` — czyli
   **proces, nie tylko wynik** (średnie tempo zdobywania nagród).
3. **Wypieczenie zwycięzcy w artefakt.** `best_agent_gen8.py` = plik agenta z podmienionymi
   wartościami `os.environ.setdefault(...)`; potem pomiar na dwóch tierach („hard6" mały + „top50"
   większy), żeby mała próba nie decydowała o wysyłce.

Ich własne wnioski, których nie trzeba powtarzać: „v48 silne optimum lokalne, dalsze mutacje ±1 pp
szumu", „nasza ewolucja 200 decków znalazła 0.908 small-sample i 0.850 large-sample".

**Co się przenosi, a co nie.** Nie przenosi się sam model ML (mamy zamrożony model i brak danych
treningowych dla prywatnych repozytoriów) ani ich środowisko symulatora. Przenosi się **cała pętla**:
szybki offline evaluator + wyszukiwanie stałych + walidacja na drugim tierze + wypieczenie zwycięzcy.
Pasuje idealnie do jedynego komponentu, który u nas jest w pełni mierzalny offline na 128 zadaniach
ze złotymi łatkami: **lokalizatora**, którego kilkanaście stałych (BM25 `k1`/`b`, bonusy za ścieżkę,
nazwę, dokładny identyfikator, karę za testy, wagę przeplotu importów, wagi zapytania) było dotąd
dobranych ręcznie.

## 3. Co zostało zbudowane i zmierzone

`tools/evolve_locator.py` (nowe, ~600 linii) + `tools/screen_locator_impact.py` (nowe):

- model rankingu **jest** shippowanym artefaktem: kontrolowany przez `--selftest`, który porównuje
  kolejność pliku z kolejnością modelu na prawdziwych korpusach (15/15 zadań identycznych),
- cache cech dla 128 zadań dev i 104 zadań holdout (jedno wczytanie korpusu na zadanie, ~1,1 s na
  ocenę konfiguracji), więc 1200 ocen to 13 min na 2 rdzeniach,
- populacja 48 × 25 pokoleń, mutacja gaussowska wokół top-3, ten sam seed dla porównywalności,
- walidacja na zbiorze spoza dev + join z 30 zadaniami, których wyniki znamy.

| | dev fitness | dev top-1 | holdout fitness | holdout top-3 | holdout top-5 |
| --- | --- | --- | --- | --- | --- |
| ręczne (V6.4) | 0.5875 | 47,7 % | 0.5702 | 65,4 % | 74,0 % |
| ewoluowane (V6.8) | **0.6297** | **55,5 %** | **0.6462** | **74,0 %** | **83,7 %** |

Pełne tabele: `analysis/locator-evolve/validation.md`; ranking zwycięzcy:
`analysis/locator-evolve/best_config.json`; wpływ na znane zadania:
`analysis/locator-evolve/screen-impact.json`.

**Dwa błędy, które wyszły tylko dzięki kontrolom** (i dlatego są warte zapisania):

1. pierwsza wersja szukała także wag zapytania, których scorer nie używał → wypieczony plik nie
   realizował zmierzonej konfiguracji („martwe pokrętła");
2. model liczył idf na innym zbiorze plików niż `collect()` artefaktu (inna lista pomijanych
   katalogów), co przesuwało remisy w top-5.

Oba naprawione; po naprawie kontrola zgodności pliku z pomiarem przechodzi w 100 %.

## 4. Rekomendacja na sobotni reset (2026-10-17 00:00 UTC) — zaktualizowana po recenzji drugiej gałęzi

Cztery ramiona po ~5,6 h rozliczeniowych = ~22,4 h z 30 h tygodnia (zapas ~7,6 h na powtórkę):

| kolejność | ramię | dźwignia | artefakt | bramki |
| --- | --- | --- | --- | --- |
| 1 | **V6.7** | reguły kontraktu narzędzi (9/9 odrzuconych zapisów) | `df7364e2…` | `GATES_V6_7.md` |
| 2 | **V6.8** | stałe lokalizatora z wyszukiwania populacyjnego | `8c816fc8…` | `GATES_V6_8.md` |
| 3 | **V6.5** | framing edycji | `cb847599…` | `GATES_V6_5.md` |
| 4 | **V6.10** | kontrakt + ewoluowany lokalizator + inline (kandydat) | `523d43fb…` | `GATES_V6_10.md` |

Co zmieniło się wobec wersji z 18:30: **V6.6 wypada z czterech przebiegów** (jego dźwignia jest
w V6.10 i w V6.9), a **V6.10 wchodzi jako kandydat** — bo rzadkim zasobem jest slot dobowy na
zgłoszenie, nie godzina GPU. V6.9 (`c99f3d81…`) zostaje zbudowany i gotowy, ale **nie jest
w pierwszej czwórce**: daje ten sam test kombinacji co V6.10 przy słabszej treści (bez kontraktu
i bez ewoluowanego lokalizatora), więc ma sens dopiero, jeśli V6.10 wypadnie źle, a V6.5 i V6.6
będą wyglądać dobrze.

**Kolejność startów ma znaczenie:** V6.7 i V6.8 startują pierwsze (największa wartość informacyjna),
V6.5 trzeci, V6.10 ostatni — jeśli po trzech przebiegach okaże się, że któryś z levers wyraźnie
szkodzi, kandydata można jeszcze zbudować inaczej przed czwartym startem (koszt: jedna przebudowa
bez GPU).
