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

## Kiedy w ogóle rozważać oficjalną submissję

Dopiero gdy: G1–G3 zaliczone w **obu** przebiegach (mini + pełny), mechanizm nie produkuje zer z
pustego drzewa, a użytkownik wyraźnie zatwierdzi upload. Slot dzienny jest jeden, kolejka 22–46 h,
a V5/V6.2 są na tej próbce statystycznie nierozróżnialne — więc wysyłka bez zaliczonych bramek to
loteria, nie strategia.
