# Weryfikacja raportu drugiej gałęzi (2026-10-16) — co potwierdzone, co nie

Wejście: raport z gałęzi `arena/6d081d52-gemma-konkurs` (autor: sesja „Arena Agent"), przekazany
przez użytkownika 2026-10-16. Zgodnie z zasadą tej sesji **żadne twierdzenie z drugiej gałęzi nie
wchodzi do decyzji, dopóki nie zostanie odtworzone naszymi artefaktami** — poniżej wynik próby
odtworzenia, pozycja po pozycji.

Stan tamtej gałęzi w chwili sprawdzania: `d45c781` (poll, 19:23 UTC) → jedyne nowe commity od
13 X to dwa polle; **żadnych nowych artefaktów, planów ani paczek**.

## 1. Tabela screeningów — 7 z 8 wierszy zgadza się co do liczby

| wersja | ich liczba | nasze artefakty | zgodność |
| --- | ---: | --- | --- |
| V2 | 10/30, 259,3 s | `SUBMISSION_LOG.md`: 10/30, 7 779,6 s / 30 = **259,3 s** | ✅ |
| V3 | 11/30, 261,3 s | `v3-benchmark/agent_benchmark_result.json`: 11/30, **261,3 s** | ✅ |
| V4 | 11/30, 233,8 s | `v4-benchmark`: 11/30, **233,8 s** | ✅ |
| V5 | 10/30, 232,7 s | `v5-benchmark`: 10/30, **232,7 s** | ✅ |
| V6.1 | 6/30, 275,4 s | `v6-1-benchmark`: 6/30, **275,4 s** | ✅ |
| **V6.2** | **10/30**, 272,4 s | `v6-benchmark`: **9/30**, 272,4 s; `v6-benchmark/analysis.md`: „V6.2: **9/30**" | ❌ **błąd +1** |
| V6.3 | 10/30, 252,7 s | `v6-3-benchmark`: 10/30, **252,7 s** | ✅ |
| V6.4 | 10/30, 298,4 s | `v6-4-benchmark`: 10/30, **298,4 s** | ✅ |

Średnie zgadzają się do dziesiątej części sekundy — czyli czytali te same przebiegi. Jedyna różnica
liczbowa to V6.2, zawyżone o jedno zadanie.

## 2. Twierdzenia o zachowaniu V6.4 — potwierdzone naszymi artefaktami

| ich twierdzenie | nasz pomiar | zgodność |
| --- | --- | --- |
| 18 z 30 zadań nierozwiązanych we wszystkich przebiegach | policzone z 7 JSON-ów z danymi per zadanie: **dokładnie 18/30** | ✅ |
| V3 i V4 rozwiązały ten sam zbiór zadań | zbiory identyczne (11 zadań, `set == set` = True) | ✅ |
| edycja do call 4 udała się 1/30 | `ANALYSIS_V6_4_FULL.md`: „pierwsza edycja w repo w call 4: **1/30** — E7 OBALONE" | ✅ |
| 11 pustych patchy | JSON: `patch_chars == 0` → **11/30**; `ANALYSIS_V6_4_FULL.md`: „11 pustych drzew" | ✅ |
| 19/30 zadań trwało ≥ 300 s | JSON: **19/30** | ✅ |
| 8 zadań bez żadnej edycji kodu repozytorium | `ANALYSIS_V6_4_FULL.md`: pokrycie edycji **w repo** 22/30 → **8 bez** | ✅ (dwie różne metryki: 11 = pusty patch, 8 = brak edycji w repo) |
| mediana pierwszej edycji przy call 12 / 176,5 s | nasza zarejestrowana metryka to **mediana pierwszego zapisu = call 10** (zapis dowolny, z `/tmp`); 12 dla „tylko repo" jest prawdopodobne, ale **nie mamy tego w artefaktach** | ⚠️ nieodtworzone (inna definicja metryki) |

## 3. FFI / multiprocessing — twierdzenie o plikach NIE sprawdza się

Raport mówi o „istniejącym `gemma4-agent/PERFORMANCE_FFI_ASSESSMENT.md`" i „prototypie
`gemma4-agent/submission-v3-mp.zip`". Sprawdzenie:

```
git rev-list --all --objects | grep -iE "ffi_assess|v3-mp|multiproc"   ->  pusto
```

**Oba pliki nigdy nie istniały w tym repozytorium** (żadna gałąź, żadna historia). Nie ma ich też na
`arena/6d081d52`. Jeśli istnieją, to wyłącznie w niecommitowanym sandboxie tamtej sesji — a zgodnie
z naszą zasadą **artefakt nieobecny w repo nie istnieje do planowania**. Wniosek: sekcja FFI nie
dostarcza niczego sprawdzalnego. Ich własny wniosek („FFI nie przyspieszy inferencji Gemmy") jest
zresztą zgodny z fizyką: wąskim gardłem jest model, nie CPU sandboxa.

## 4. Twierdzenia zewnętrzne — nowe dla nas, nieoznaczone jako niezweryfikowane u nich

| twierdzenie | status |
| --- | --- |
| Budget-Fit: 28 wywołań / 8 min / 80 tur / 240 s / 8192 wyjścia / edycja do call 12; publicznie **0,18** | mamy to już w `RESEARCH_2026-10-15_EXTERNAL.md` (§8) — zgodne |
| Budget-Aware z widocznym **0,22** | **nowe**, nie mamy tego w naszym researchu; nie możemy odtworzyć (brak dostępu do Kaggle) |
| sparowany screening 31 zadań: Budget-Fit **9/31**, Budget-Aware **9/31**, warianty z dodatkowymi narzędziami **8/31** i wolniejsze | **nowe**, nieodtwarzalne u nas |
| średnie czasy tych wariantów → **11,63–11,99 h dla 120 zadań** | **nowe i decyzyjne**: 11,63 h / 120 = **5,82 min/zadanie z setupem**, czyli ~5,3 min samej sesji ≈ **318 s** |
| LoRA: organizator potwierdza stosowanie adapterów; przykład z submisji dotykał tylko warstwy 0 | mamy w researchu (§8) — zgodne |
| niezależny test: loss spadł, ale Rich lokalnie **4/32 → 2/32** | **nowe**; dokładnie dlatego nasz plan SFT ma bramkę **G-holdout** (adapter musi pobić bazę na odłożonych zadaniach), a nie „niższy loss" |

**Najważniejszy punkt:** liczba 11,63–11,99 h/120 to zewnętrzne, niezależne potwierdzenie naszych
bramek Z1/Z2 — zegar 8 min **nie jest bezpieczny automatycznie**, a wartość ~318 s na zadanie wpada
dokładnie w środkowy przedział Z1 („bezpieczne tylko przy ~120 zadaniach"). Czyli: pytanie, które
zadaje uzbrojony ekran V7-c, jest właściwym pytaniem.

## 5. Co z tego zmieniamy w naszym planie

- **Dziś nic.** Oba runy (V7-b na 00:05 UTC, V7-c na 00:05 UTC) są uzbrojone i nie ruszamy ich.
- **Ich rekomendacja nr 1** („prostsza pętla naprawy: pojedynczy agent, ~28 wywołań, wczesna edycja)
  pokrywa się z V7-b, który jest już uzbrojony — z jedną różnicą: V7-b nie zawiera **procedury
  odzyskiwania po odrzuconym `edit_file`**, a to jest nasza własna, zmierzona dźwignia (105/524
  odrzuconych wywołań, 47 z powodu utraty granic długiego argumentu, wątek `748323`).
  Kandydat na **V7-d jako pojedyncza dźwignia** — decyzja po wyniku V7-b, nie teraz.
- **Rekomendacja nr 2** (bramka 12 h) = nasz uzbrojony V7-c, z pre-rejestrowanymi progami.
- **Rekomendacja nr 3** (LoRA jako osobny eksperyment, canary → holdout) = nasz `SFT_PLAN.md`;
  ich dodatkowa obserwacja („loss spadł, wynik lokalny spadł") **wzmacnia** bramkę G-holdout.
- **Rekomendacja nr 4** (FFI/mp osobno) — bez zmian: nie ma artefaktu, nie ma czego mierzyć.

**Czego ich raport nie daje:** przepisu na 0,24. Mówią to sami i to jest zgodne z naszym stanem wiedzy.
