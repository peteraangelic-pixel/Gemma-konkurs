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

## 4. Rekomendacja na sobotni reset (2026-10-17 00:00 UTC) — PRZEPISANA 2026-10-15

**Ta sekcja jest nieaktualna jako plan.** Cztery ramiona promptowe (V6.7 → V6.8 → V6.5 → V6.10)
mierzyłyby dźwignie, które nie dotykają największej zmierzonej dziury: **konwersji lokalizacji na
edycję i budżetu per zadanie**. Rekonesans zewnętrzny z 2026-10-15 (`RESEARCH_2026-10-15_EXTERNAL.md`)
dał na to trzy niezależne pomiary, a nasze własne dane to potwierdzają (V6.4: 12/30 sesji kończy
się dokładnie na capie wywołań, 19/30 na zegarze, 11/30 z pustym drzewem; 5 z 11 sesji koszyka N
miało złoto na #1 i nie wykonało żadnej edycji).

Nowy plan na sobotę (szczegóły i bramki w `GATES_V6_11.md`):

| kolejność | ramię | co testuje | artefakt | bramki |
| --- | --- | --- | --- | --- |
| 1 | **V6.11** | budżet V5 (45 wywołań / 80 tur / 8 min) + cztery reguły konwersji | `7b2beec1…` | `GATES_V6_11.md` (R1–R5, S1–S2) |
| 2 | **V6.10** | kontrola: ten sam układ na starym budżecie 30/60/5,25 | `523d43fb…` | `GATES_V6_10.md` |
| 3+ | rezerwa | V6.7 / V6.8 / V6.5 (stare ramiona) albo kolejna iteracja V6.11 | — | — |

Historia decyzji: wersja z 18:30 (V6.7 → V6.8 → V6.5 → V6.10) zakładała, że wąskim gardłem jest
lokalizacja i higiena narzędzi. Lokalizacja jest zmierzona i **lepsza niż wszystko publiczne**
(top-1 55,5 % / top-3 67,2 % na dev, 51 % / 74 % na holdoucie, wobec najlepszego publicznego benchu
TF-IDF 21 % / 50 %), a mimo to nie przekłada się na wynik — więc kolejne ramiona promptowe to
doskonalenie nie-tego-zaworu. V6.9 (`c99f3d81…`) nadal istnieje i nie jest w pierwszej dwójce.

**Kolejność startów ma znaczenie:** V6.11 startuje pierwszy, bo odpowiada na pytanie, czy wracamy
do budżetu V5 — jeśli tak, cała reszta planu (łącznie z sobotnim doborem kandydata) się upraszcza.
V6.10 jako kontrola uruchamia się drugi, na tym samym seedzie i tych samych 30 zadaniach.


