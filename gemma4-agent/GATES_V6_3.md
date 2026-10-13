# Bramki jakości V6.3 — pre-registered 2026-10-12, PRZED jakimkolwiek przebiegiem V6.3

Ten plik istnieje po to, żeby **nie przesuwać progów po zobaczeniu wyniku** (wymóg recenzji z
gałęzi `arena/6d081d52-gemma-konkurs`). Zasady:

1. Bramki jakości raportuje się **osobno** od liczby rozwiązanych zadań.
2. Progi są zamrożone poniżej; zmiana wymaga nowego pliku i nowego przebiegu, nie edycji wstecz.
3. Przy n=30 **liczba rozwiązanych zadań nie jest dowodem przewagi** — raportujemy ją z CI95 i z
   parami wygranych/przegranych względem V5, bez twierdzeń o istotności.

## Zakres zmian w V6.3 (przyjęte z recenzji)

- **(a) zakaz submisji bez zamierzonej edycji** — `submit_patch()` jest **opcjonalne**, bo harness
  sam wyciąga diff drzewa (`git add -N . && git diff`), a jego wywołanie **kończy sesję**. Reguła:
  nie submituj, jeśli jedyna zmiana to plik roboczy albo markdown `docs/` przy zadaniu o
  zachowaniu programu.
- **(c) dokumentacja nie jest poprawką** — markdown w `docs/` nie może zmienić wyniku testów; przy
  zadaniu o zachowaniu trzeba otworzyć moduł źródłowy. Wyjątek: zadania jawnie dokumentacyjne.
  Pliki w `docs_src/`, `examples/`, `tutorials/` to **kod** (FastAPI importuje je w testach), więc
  liczą się jak źródło.
- **(b) obniżenie `thinking_budget` 4096 → 2048** — **ODŁOŻONE** (brak lokalnego pomiaru, ryzyko
  gorszej jakości edycji, zmiana razem z (a) utrudniłaby interpretację).
- **(d) `timeout 30`** — **ODŁOŻONE** (ogranicza testy, nie długie wywołanie modelu; nie trafia w
  zmierzoną przyczynę).
- **17 sesji kończących się na zegarze pozostaje osobnym, nierozwiązanym celem** — V6.3 go nie
  adresuje i nie udajemy, że adresuje.

## Tożsamość artefaktów (weryfikowalna)

| przebieg | archiwum | SHA-256 |
| --- | --- | --- |
| mini-screen 4 zadań | `submission-v6.zip` (build V6.3) | `abf22bac2c67c639342f56e890fd77cb36c91811d07cf1c239c84ef28fa1216e` |
| pełny screening 30 zadań | `submission-v6.zip` (build V6.3 + korekta prozy) | `650e1dba10c5b269c616a670255c3a585a57d750ce0f8428581ae65ea528f5c4` |

Różnica między tymi buildami to **wyłącznie proza promptu** — 11 zmienionych linii (poprawione
„45 tool calls" → 30, usunięte zduplikowane zdanie w kroku 6, dwa punkty sklejone kontynuacją
linii w źródle Pythona rozdzielone). Zweryfikowane `difflib.unified_diff` na zawartości obu
ZIP-ów: **żadna reguła, próg, bajt skryptu ani konfiguracja się nie zmieniły**, więc wynik
mini-screenu opisuje ten sam mechanizm, który mierzy pełny przebieg. Powód poprawki: przegląd
własnego promptu wykrył, że tekst obiecywał budżet 45 wywołań, gdy harness tnie na 30.

## Bramki (hard) — raportowane per przebieg

| bramka | definicja operacyjna | próg |
| --- | --- | --- |
| **G1** brak plików-śmieci | żaden `touched_files` nie zawiera `issue.txt`, `locate.py`, `repro.py` | = 0 |
| **G2** brak przedwczesnych submisji bez edycji | puste drzewo (`patch_chars == 0`) **oraz** sesja zakończona przed 280 s | = 0 |
| **G3** brak diffów wyłącznie dokumentacyjnych | wszystkie dotknięte pliki to `docs/**.md`/`.rst` i żaden nie jest kodem źródłowym | = 0 |

## Metryki raportowane, ale NIE bramkujące (bez progów zwycięstwa)

| metryka | rola |
| --- | --- |
| **G4** liczba pustych drzew | cel orientacyjny ≤ 4 (V6.2: 8) — **nie** warunkuje wysyłki |
| **R** rozwiązane zadania + CI95 Wilsona | raportowane osobno, bez progu |
| **P** pary wygrane/przegrane vs V5 na tych samych zadaniach | opisowo (McNemar przy n=30 nie rozstrzyga) |
| **L** trafienia lokalizatora (`localized`) | diagnostyka mechanizmu, nie wynik |

## Kolejność przebiegów (do zatwierdzenia przez użytkownika)

1. **Mini-screen 4 zadań** (~1/7 kosztu pełnego przebiegu):
   `rich_3105`, `rich_3934` (przedwczesne submisje), `fastapi_14487` (diff dokumentacyjny),
   `rich_3006` (**kontrola**).
2. **Pełny screening 30 zadań** na tym samym seedzie `20261009`, tylko jeśli mini-screen przejdzie
   G1–G3 albo wyjaśni porażkę.

## Pre-registered oczekiwania — zapisane PRZED wynikiem, żeby dały się obalić

1. `rich_3105` i `rich_3934`: **oczekujemy edycji na dysku** (nie pustego drzewa) i **G2 = 0** na
   tych zadaniach. Jeśli nadal kończą bez edycji, reguła (a) jest nieskuteczna w tej formie.
2. `fastapi_14487`: **oczekujemy braku diffu wyłącznie dokumentacyjnego** (G3). Zadanie może nadal
   nie zostać rozwiązane — bramka dotyczy mechanizmu, nie wyniku.
3. `rich_3006` (kontrola): **(b) i (d) są odłożone, więc oczekujemy, że to zadanie nadal padnie na
   zegarze.** Jeśli zostanie rozwiązane, to dowód przeciwko przypisaniu skutku zmianie (a)/(c) —
   czyli szum, nie sukces zmiany. Ten punkt jest w pliku celowo: to test na nasze własne
   przywiązanie do hipotezy.
4. Pełny przebieg: **żadnej deklaracji przewagi nad V5** przy n=30. Sukces = G1–G3 zaliczone
   + wynik nie gorszy niż V5 o więcej niż 2 zadania. Porażka = którakolwiek z G1–G3 złamana
   → wracamy do projektowania, nie do wysyłki.

## Reguła decyzyjna o submissji — zapisana 2026-10-13 01:05 UTC, PRZED wynikami V6.3

Użytkownik upoważnił sesję: „zrób submission z tej wersji, jeśli uznasz to za stosowne".
Żeby to upoważnienie nie zamieniło się w uznaniowość po fakcie, próg jest **zamrożony tutaj**:

Submissja V6.3 (`submission-v6.zip`, SHA-256 `650e1dba10c5b269c616a670255c3a585a57d750ce0f8428581ae65ea528f5c4`,
komunikat „V63", plik stagingowany jako `submission.zip`) **następuje wtedy i tylko wtedy, gdy**:

1. mini-screen: G1 = G2 = G3 = 0 na wszystkich 4 zadaniach;
2. pełny screening: G1 = G2 = G3 = 0;
3. pełny screening: rozwiązane ≥ **9/30** (czyli nie gorzej niż V6.2 i w granicy jednego zadania od V5);
4. slot dzienny wolny (brak submissji w ciągu 24 h — pilnuje `submit_kaggle_v63_once.py`);
5. `--require-gates v6-3-miniscreen,v6-3-benchmark` przechodzi (bramka jest wbudowana w uploader,
   więc warunki 1–2 nie mogą zostać pominięte przez pomyłkę).

**Jeśli któryś punkt nie przejdzie — submissji NIE MA**, niezależnie od tego, jak dobre wydają się
inne liczby. Uzasadnienie merytoryczne submissji (przy spełnionych warunkach): obecny wynik
oficjalny 0.03 pochodzi z artefaktu V4, który na tej samej próbce produkował 6 pustych drzew;
V6.3 usuwa dwie zmierzone klasy zer (sesja bez edycji, diff z plików-śmieci) i podnosi trafienia
lokalizatora, więc oczekiwana wartość na ukrytym zbiorze jest wyższa niż V4 — nawet jeśli próbka
publiczna tego nie rozstrzyga przy n=30. **Nie twierdzę, że V6.3 pobije V5**; twierdzę, że jest
pierwszym kandydatem bez zmierzonej klasy zer, a to jest jedyna dźwignia, jaką mamy.

## Kiedy w ogóle rozważać oficjalną submissję

Dopiero gdy: G1–G3 zaliczone w **obu** przebiegach (mini + pełny), mechanizm nie produkuje zer z
pustego drzewa, a użytkownik wyraźnie zatwierdzi upload. Slot dzienny jest jeden, kolejka 22–46 h,
a V5/V6.2 są na tej próbce statystycznie nierozróżnialne — więc wysyłka bez zaliczonych bramek to
loteria, nie strategia.
