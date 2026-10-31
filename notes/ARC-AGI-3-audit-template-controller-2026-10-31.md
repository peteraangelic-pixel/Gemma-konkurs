# Audyt kontrolera szablonowego (pakiet 31.10) — co się broni, co nie, i co dalej

Data: 31.10.2026 · gałąź `codex/arc-local-lab-v18-20261030` (head `3926007`, commit modułu `f730639`,
wyniki `aec6c3e`, poprawki instrumentu `91f1ce9`) · audyt **read-only**, bez Kaggle i bez GPU.

Zakres: `START-HERE-REVIEW-20261031.md` + wszystko, na co wskazuje. Nie czytałem opisów jako
źródła prawdy — sprawdzałem kod i artefakty, a liczby przeliczałem.

---

## 1. Werdykt w trzech zdaniach

Rdzeń jest **prawdziwy i odtwarzalny**: ten sam notebook (hash `550eb185…` zgadza się), ta sama
sekwencja 25 akcji w dwóch niezależnych ścieżkach (harness Duck i offline'owy ewaluator na
prawdziwym `arcengine`), ta sama punktacja 28,57 = 6/21 z prawdziwych baseline'ów ft09, i realny
transfer reguły między poziomami, który odtwarza akcje 5 i 12 z nagrania. **Nie jest to jednak
generalizacja** — to jedna publiczna gra użyta w rozwoju, a mój stress test pokazuje, że na planszy
o tym samym wyglądzie, ale innej regule, kontroler odpala w 99–100% przypadków i myli się w 90–100%
(ratuje go tylko weryfikacja predykcji, kosztem jednej akcji). Znalazłem jedną bramkę, która tnie
te fałszywe rozpoznania o 94–100% **nie zmieniając ani jednej akcji na ft09** — propozycja w §5.

---

## 2. Co potwierdziłem twardo (z liczbami)

| twierdzenie | jak sprawdzone | wynik |
|---|---|---|
| notebook `agent.ipynb` = `550eb185…` | `sha256sum` | **identyczny** |
| „3 poziomy ft09 w 25 akcjach, bez LLM, ~4,8 s" | `harness-template-final` + `-repro/result.json` | 3 / 25 / 4,766 s i **4,813 s** — powtarzalne; `generated_tokens=0`, `api_calls=0` |
| 4+7+14 = 25 | `game-run.json` (`actions_per_level`) + trace | zgodne; przejścia poziomów dokładnie po 4., 11. i 25. akcji |
| testy modułu | `pytest tests/test_template_transfer.py` (numpy 2.4.6) | **35/35 zaliczone** |
| polityka w przebiegu = plik w repo | `policy_sha256 a948d087…` | = `template_transfer.py`; ewaluator = `benchmark_causal_explorer.py` (`36a8f0d5…`) |
| „25 zgodnych śladów backendów" | `public25-final-{portable,rust}.jsonl` | **75/75 identycznych trace** (25 gier × 3 polityki); template: 3 poziomy / 25 akcji / 25 trafień / 0 niezgodności |
| „abstynuje na 24 pozostałych grach" | j.w. | **potwierdzone**: 24 gry × 0 akcji |
| trace offline == przebieg w Duck | porównanie 25 pozycji | **25/25 identycznych** (x,y parami) |
| 28,57 % RHAE jest prawdziwe | baseline ft09 `[43,12,23,28,65,37]` z `metadata.json` | wagi = numer poziomu: (1+2+3)/21 = **6/21 = 28,571 %**; akcje 4/7/14 < 43/12/23 ⇒ efektywność 1,0 na każdym poziomie |
| wzór punktacji spójny na drugim punkcie | przebieg z 1 poziomem | 1/21 = **4,76** — zgadza się co do drugiego miejsca |
| A/B = jedna zmienna | porównanie patcha w obu notebookach | 3 patche bazowe **identyczne bajt w bajt**, `template` dokłada dokładnie 1 (`codex-template.patch`) |
| Rust = NumPy | port `rectangles.rs` do Pythona, 300 losowych plansz + 3 ramki ft09 | **0 rozbieżności**; akcje identyczne |
| baseline NumPy z ich pomiaru | mój pomiar na 256 prawdziwych ramkach ft09 | **0,278 s vs ich 0,292 s** — zgodne (5 %) |

**Transfer między poziomami — sprawdzony najciekawiej.** Bez stanu `learned` kontroler na
startowych ramkach poziomów 2 i 3 **abstynuje** (`None`). Z modelem przeniesionym z poziomu 1
(`{2:9, 0:8}`, center_symbol 0) zwraca **dokładnie** akcję nr 5 z nagrania `(x=23, y=17)` i akcję
nr 12 `(x=23, y=7)`. To nie jest deklaracja z README — to odtworzenie dwóch konkretnych kliknięć
z przebiegu. Czyli „przenoszenie reguły" jest realne i jest tym, co daje poziomy 2 i 3.

---

## 3. Co się nie broni / wymaga poprawki w opisie

1. **`final_score: 0.0` przy 3 ukończonych poziomach** (`game-run.json`). Pole harnessu jest
   bezużyteczne w tym przebiegu (nie wywołano `finish_game()`, bo `final_score` nie było `None`).
   Ich `result.json` liczy wynik osobno i poprawnie, ale **tego pola nie wolno cytować** jako
   „0 punktów" ani jako punktacji.
2. **Temperatura nie jest zweryfikowana w parze.** `paired-comparison.json` sam mówi
   `temperature_verified: 0`, a `control-ft09/result.json` ma `temperature: None`. HYBRID-RESULT
   wymienia „temperatura 0" po obu stronach — to nadmiar: po stronie kontroli to nie jest
   zapisane. Wniosek o +3 poziomy tego nie łamie, ale A/B nie jest w 100 % czyste.
3. **„75 przebiegów" trzeba czytać jako 25 gier × 3 polityki**, nie 75 przebiegów kontrolera.
   Liczba `identical_traces: 75` jest prawdziwa, ale nie mówi nic o jakości polityki — tylko o
   równoważności backendów (którą dodatkowo potwierdziłem portem).
4. **Brak hasha drzewa `ARC3-Inference`** w `result.json` (jest tylko hash notebooka). Nie da się
   z artefaktów dowieść, że lokalny `--source` był dokładnie tym, co wnosi patch notebooka;
   wnoszę z `build_duck_variants.py`, że tak, ale to nie jest zapisane.
5. **`install()` w `template_hook.py` nie jest idempotentny** — drugie wywołanie opakuje już
   opakowane `analyze` (rekurencja). W praktyce wołane raz, ale to mina na przyszłość.
6. **Hook sprawdza `should_stop()` przed czymkolwiek**, czego oryginalny `analyze` nie robi
   (zweryfikowane na `tool_agent.py` z r033). Różnica jest mała (harness i tak nie woła analizy po
   stopie), ale to zmiana semantyki harnessu, nie tylko „dodatek po modelu".
7. **Kontroler omija transcript.** W trybie controller-only `transcript.txt` jest pusty, więc
   25 akcji istnieje tylko w `history` — audytowalność spada; dobrze, że `game-run.json` jest.

---

## 4. Ryzyko fałszywego rozpoznania — zmierzone, nie ocenione „na oko"

Syntetyczne plansze w geometrii ft09, ta sama struktura paneli i pieczęci, ale **inna reguła**
(300 prób na rodzinę; narzędzie: `tools/template_false_positive_probe.py`):

| rodzina | rozpoznań | z tego trafnych (poprawny kolor) |
|---|---|---|
| `copy` (reguła, którą kontroler zna) | 149/300 | **149 — 100 %** |
| `rotate` (obrót 90°) | 299/300 | 18 — 6 % |
| `invert` (zamiana kolorów) | 300/300 | 0 — **0 %** |
| `random` (brak reguły) | 297/300 | 23 — 8 % |

Czytanie: **kontroler nie odróżnia „to nie jest zadanie kopiowania" od „to jest"**. Odpala prawie
zawsze, gdy na planszy jest układ paneli; o pomyłce dowiaduje się dopiero po kliknięciu (weryfikacja
predykcji w następnej ramce). Koszt jest **ograniczony do jednej akcji na poziom**, bo po
niezgodności `rejected=True` blokuje wnioskowanie do końca poziomu — to dobra własność projektu
i sprawdziłem ją w kodzie. Ale: **jedno złe kliknięcie może skończyć grę** w grach, gdzie klik
jest nieodwracalny. Przy 24 grach, na których moduł dziś abstynuje, to nie boli; przy szerszym
wpięciu — boli.

Ograniczenie metody: plansze są syntetyczne, więc to nie jest rozkład z rosteru. Prawdziwy test
(24 gry × wszystkie poziomy) wymaga `arcengine`, którego nie ma na PyPI — patrz §6.

## 5. Propozycja: bramka „dokładnie jedna niezgodna komórka" (zmierzona)

Jedna zmiana w gałęzi `stamp`: zamiast brać **pierwszą** niezgodną komórkę, wymagaj, by była
**dokładnie jedna** (inaczej abstynencja). Patch: `proposals/template-single-mismatch-gate.patch`.

| rodzina | oryginał | z bramką | efekt |
|---|---|---|---|
| `copy` | 149 / 100 % | **149 / 100 %** | zero kosztu |
| `rotate` | 299 / 6 % | 17 / 18 % | −94 % fałszywych |
| `invert` | 300 / 0 % | **0** | −100 % |
| `random` | 297 / 8 % | 8 / 12 % | −97 % |

I najważniejsze: **na ft09 bramka nie zmienia nic** — poziom 1 daje `(6,39,39)`, poziom 2
`(6,23,17)`, poziom 3 `(6,23,7)`, czyli wszystkie trzy akcje startowe z nagrania zostają.

Zastrzeżenie, które trzeba powiedzieć przed wdrożeniem: bramka zakłada, że zadanie ma **jedną**
brakującą komórkę. Jeśli w rosterze są warianty „popraw kilka komórek", bramka je odetnie.
Dlatego proponuję ją jako **osobny przełącznik** (`ARC3_TEMPLATE_REQUIRE_SINGLE_MISMATCH=1`)
i pomiar na tych samych 25 grach, a nie jako cichą zmianę domyślną.

## 6. Czego nie mogłem sprawdzić (uczciwie)

- **Prawdziwej repliki silnika**: `arcengine` nie ma na PyPI (sprawdzone), a pliki gier importują
  właśnie jego. Dlatego nie powtórzyłem 25 akcji na prawdziwym ft09 — powtórzyłem je na
  **zapisanych ramkach** i na poziomie zgodności trace'ów ofline↔harness.
- **Pomiaru Rust**: brak `cargo` w tym środowisku. Zweryfikowałem **równoważność algorytmu**
  (port linia w linię, 0 rozbieżności) i **stronę NumPy pomiaru** (0,278 s vs 0,292 s), ale samego
  „33×" nie zmierzyłem. To twierdzenie pozostaje ich pomiarem, nie moim.
- **Zachowania na poziomach 4–6 ft09** i na głębszych poziomach pozostałych 24 gier.

## 7. Rekomendacja

1. **Wniosek „3 vs 0" jest prawdziwy i dobrze zaraportowany** — łącznie z uczciwym „to nie ślepy
   test". Nie zmieniać tego w komunikacji poza jedno: dopisać, że temperatura kontroli nie jest
   zapisana.
2. **Nie cytować `final_score` z `game-run.json`** (jest 0,0 mimo 3 poziomów) — tylko
   `result.json` / `rhae_score_pct`.
3. **Wdrożyć bramkę z §5 jako przełącznik**, zmierzyć na 25 grach: czy `copy` zostaje 100 % i czy
   fałszywe spadają. To najtańsza dostępna poprawa bezpieczeństwa wpięcia.
4. **Następna zdolność na innej rodzinie** — konkret, który ma sens po tym audycie: nie „kolejny
   szablon", a **detektor zmiany mechaniki** (poziom N+1 vs N: jeżeli rozkład kolorów/rozmiarów
   elementów zmienia się istotnie, wyzeruj `learned` i wymagaj ponownego potwierdzenia). Dziś
   `learned` przeżywa zmianę poziomu bezwarunkowo — a to jest dokładnie ten mechanizm, który dał
   poziomy 2–3 i jednocześnie jest jedynym miejscem, gdzie nieświeży model może kliknąć w złą
   komórkę. Da się to zmierzyć bez GPU i bez nowych gier.
5. **Nie zgłaszać notebooka** bez osobnej zgody — zgody nie ma i nie o nią tu występuję.

---

## 8. Korekta po audytach z gałęzi Pokemon (`9d528ac4`) i peer review — 31.10

**Cofam bezwarunkowe zdanie z §1: „ratuje go tylko weryfikacja predykcji, kosztem jednej akcji".**

Zmierzone na prawdziwym `TemplateTransfer` (`tools/template_oscillation_probe.py`):

| model czasu | akcje w 240 klatkach |
|---|---:|
| komórka trzyma oczekiwany kolor 1 klatkę i wraca | **120** (bez limitu) |
| to samo + strażnik 32 akcje/poziom | **32** (przezbrojenie po zmianie poziomu OK) |
| komórka wraca przed następną klatką | **1** (`rejected` po pierwszej akcji) |

Czyli ograniczenie do jednej akcji działa **tylko przy niezgodności trwałej**. Przy przejściowym
efekcie kliknięcia `rejected` nigdy nie następuje i kontrola nie ma limitu — zarzut z audytu
Pokemon jest słuszny. Rekomendacja: strażnik akcji na poziom jako **przełącznik**
(`ARC3_TEMPLATE_ACTION_GUARD=32`), nie stała, bo koszt na grach wymagających >32 akcji kontrolera
nie jest zmierzony.

**Poprawka narzędzia:** `--gate` z §5 był opisany w docstringu, ale nieistniejący w CLI. Teraz
działa i jednocześnie weryfikuje, że patch się nakłada. Tabela z §5 odtwarza się co do liczby
(149/149, 17/3, 0, 8/1) — zgodnie z niezależną reprodukcją peer review.

Pełna odpowiedź na wszystkie audyty: `notes/ARC-AGI-3-odpowiedz-na-audyty-2026-10-31.md`.
