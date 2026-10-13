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
| mini-screen 4 zadań | `submission-v6.zip` (V6.3, proza przed korektą) | `abf22bac2c67c639342f56e890fd77cb36c91811d07cf1c239c84ef28fa1216e` |
| pełny screening 30 zadań | `submission-v6.zip` (V6.3 + korekta prozy) | `650e1dba10c5b269c616a670255c3a585a57d750ce0f8428581ae65ea528f5c4` |
| **kanoniczny, odtwarzalny build** (pin submittera) | ten sam plik co wyżej, treść 5/5 identyczna | **`ea80bc16017c9ec92163fdd6533146106a41bf7b69d048cfa292cb21187070c3`** |

Uwaga o determinizmie (znalezione 2026-10-13): ZIP zapisywał czas modyfikacji `prompts/system.md`,
więc **każdy przebudowanie zmieniało SHA bez zmiany treści** — no-op rebuild dał `4ed7221e…` przy
`650e1dba…`, przy identycznej zawartości wszystkich 5 plików (zweryfikowane `diff -rq`). Pin SHA na
takim archiwum niczego by nie pilnował, więc packer ustawia teraz stały znacznik `1980-01-01` dla
wszystkich wpisów: dwa kolejne buildy dają `ea80bc16…`, a treść archiwum jest bit w bit ta sama, co
w pełnym przebiegu (dowód: rozpakowanie i `diff -rq` wobec `650e1dba…` — bez różnic).

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

## Wynik pełnego przebiegu 30 zadań (2026-10-13 03:30 UTC) i decyzja

Run `38330672815` (archiwum `650e1dba…`, treść identyczna z kanonicznym `ea80bc16…`) ukończył kernel,
ale jego krok commitu wyników padł — liczby odzyskano z artefaktu runu osobnym workflowem
`38347822030` (czysty transfer, bez GPU; rekord transferu z hashami:
`kaggle_results/v6-3-benchmark/fetch_summary.txt`).

| metryka | V6.2 | V6.3 (pełny) |
| --- | --- | --- |
| rozwiązane | 9/30 [16.7 %, 47.9 %] | **10/30 [19.2 %, 51.2 %]** |
| puste drzewa | 8 | **11** |
| z tego przedwczesne | 2 | **3** |
| śmierci na zegarze | 17 | 15 |
| pliki-śmieci (G1) | 0 | 0 |
| tylko dokumentacja (G3) | 1 | 0 |
| trafienia lokalizatora | 20/30 | 18/30 |
| średni czas zadania | 272.4 s | 252.7 s |

**Bramki: G1 PASS (0), G2 FAIL (3), G3 PASS (0).** Cel G4 (≤4 puste drzewa) chybiony (11).

### Decyzja: NIE WYSYŁAMY V6.3

Reguła decyzyjna zapisana wyżej (01:05 UTC, **przed** wynikami) wymaga G1–G3 = 0 w **obu** przebiegach.
G2 = 3 → warunek niespełniony → **submissji nie ma**. Decyzja jest mechaniczna i nie przesuwam progu po
fakcie w żadną stronę. Submitter potwierdza to niezależnie: `--require-gates v6-3-miniscreen,v6-3-benchmark`
→ `status: gate_blocked`, exit 7, `submission_created: false` (sprawdzone lokalnie 2026-10-13 04:44 UTC,
hash archiwum zgodny z pinem).

### Co obalił pełny przebieg

1. **Zmiany (a)+(c) nie usunęły klasy zer.** Pustych drzew jest **11**, o trzy więcej niż w V6.2, przy
   jednym zadaniu więcej rozwiązanych. Trzy sesje skończyły przed zegarem bez żadnej edycji:
   `rich_3105` (7 wywołań/43 s), `rich_3043` (8/110), `requests_6757` (12/211). To samo `rich_3105`
   w mini-screenie dojechało do zegara (22 wywołania/318 s) i też nie zapisało edycji — **sesja bez
   edycji to zachowanie modelu, nie skutek reguły (a)**.
2. **Trafienia lokalizatora spadły 20 → 18/30**, choć skrypt lokalizatora się nie zmienił
   (`fe25b200…`). Przy pustym patchu to pole nie ma danych, więc różnica jest szumem przebiegu.
3. **Wariancja między przebiegami:** `rich_3006` w mini-screenie zginął na zegarze (4 wywołania/318 s),
   a w pełnym przebiegu został **rozwiązany**. Ten sam seed i praktycznie to samo archiwum → mini-screen
   nie przenosi się 1:1, pojedyncze zadania to ruletka.
4. `fastapi_14487` (oczekiwanie O2) nie zrobił diffu dokumentacyjnego, ale i tak nie powstała żadna
   edycja — 27 wywołań, 320 s, patch 0. Mechanizm zaliczony, wynik nie.

### Wniosek dla następnej wersji (bez obietnic)

Naprawa mechanizmu bez naprawy *umiejętności wykonania edycji w budżecie* nie podnosi wyniku: V6.3 jest
o jedno zadanie lepszy od V6.2 i równy V5 (10/30), przy większej liczbie zer. Kierunek na kolejną wersję
musi wynikać z analizy, **dlaczego sesja kończy się bez edycji** — a do tego potrzebny jest transkrypt
sesji, którego ten przebieg nie zostawił (log kernela nie był pobierany, bo jego krok ma `if: failure()`,
a kernel zakończył się sukcesem).

## Incydent 2026-10-13: commit workflow cofnął pracę na branchu (naprawione)

Commit wyników mini-screenu (`49ee5e0`, autor `github-actions[bot]`) **skasował** z branchu:
`tools/submit_kaggle_v63_once.py`, `.github/workflows/gemma-kaggle-v63-official-submit.yml`,
strażniki w `build_submission_v6.py`, poprawki w `tools/make_v6_prompt.py` i cofnął
`submission-v6.zip` do buildy `abf22bac…`.

**Mechanizm (błąd w moim workflow, nie w GitHubie):** krok „Commit … summary to this branch" robił
`git fetch` + `git reset --soft origin/$GITHUB_REF_NAME` + `git add <pliki wyników>` + `git commit`.
`reset --soft` przenosi **tylko** wskaźnik HEAD, a indeks zostaje na drzewie z momentu checkoutu tego
jobu (`1d30a11`, sprzed commitów, które doszły w trakcie działania kernela), więc commit wyników
odtworzył **stare** drzewo plus pliki wyników i tym samym wycofał wszystko, co zostało wypchnięte
w międzyczasie. To ten sam błąd, który 2026-10-12 przewrócił krok commitu V6.2 — wtedy uznałem go za
problem `pull --rebase`, a „naprawa" (`reset --soft`) była gorsza od choroby.

**Naprawa:** wszystkie workflow (v6, v62-fetch, v63-mini, v63-benchmark, v63-submit) mają teraz
bezpieczną kolejność: `git fetch` → skopiowanie wyników do `/tmp/keep` → `git reset --hard
origin/$GITHUB_REF_NAME` (drzewo **z remote**) → wklejenie wyników z `/tmp/keep` → regeneracja
historii → `git rm` pliku-trigger → commit i push. Weryfikacja: brak wykonywalnego `reset --soft`
w repo, wszystkie pliki YAML parsują się poprawnie.

**Odtworzenie po takim cofnięciu** (jeśli zajdzie ponownie — kolejny commit wyników pełnego
przebiegu powstanie jeszcze ze starego kroku, bo job czyta plik w momencie startu):

```
git fetch origin arena/c4eeb067-gemma-konkurs

git checkout COMMIT_SHA -- gemma4-agent/build_submission_v6.py gemma4-agent/tools/make_v6_prompt.py \
    gemma4-agent/tools/submit_kaggle_v63_once.py gemma4-agent/submission-v6/prompts/system.md \
    gemma4-agent/GATES_V6_3.md .github/workflows/gemma-kaggle-v63-official-submit.yml

python3 gemma4-agent/build_submission_v6.py           # odbudowa kanonicznego archiwum
sha256sum gemma4-agent/submission-v6.zip              # oczekiwane ea80bc16017c9ec9…
python3 gemma4-agent/tools/check_docs_consistency.py  # spójność przedziałów CI95
```

gdzie `COMMIT_SHA` to commit ratunkowy opisany w historii (pierwszy po incydencie, zawierający
wszystkie wymienione pliki). **Uwaga:** przy odtwarzaniu nigdy nie dodawaj z powrotem plików
`kaggle_smoke/*.trigger` — ich wypchnięcie odpala workflow.

## Przebieg zdarzeń V6.3 — zapis faktów, nie interpretacji

| kiedy (UTC) | co się stało |
| --- | --- |
| 00:58:53 | start mini-screenu (`38329901183`, commit `1d30a11`, archiwum `abf22bac…`) |
| 01:05–01:08 | commit `1c5fd55`: 4 poprawki prozy + **przypadkowe odpalenie pełnego przebiegu** (patrz niżej) |
| 01:08:12 | start pełnego screeningu `38330672815` (commit `1c5fd55`, archiwum `650e1dba…`, 30 zadań) |
| 01:30:36 | koniec mini-screenu: **0/4 rozwiązanych, 4/4 puste drzewa, 4/4 śmierci na zegarze (średnio 318.4 s)**, G1–G3 czyste |
| 01:31 | commit wyników `49ee5e0` cofa pracę na branchu (incydent wyżej) |

### Wynik mini-screenu i co obalił

- **G1–G3: PASS** (pliki-śmieci 0, przedwczesne submisje 0, diffy wyłącznie dokumentacyjne 0).
- **O1 OBALONE**: `rich_3105` i `rich_3934` nadal kończą z pustym drzewem. Reguła (a) usuwa
  przedwczesną submissję (V6.2: 5 wywołań/119 s i 10/266 s), ale **nie zamienia jej na edycję** —
  sesje trwają teraz do zegara (22 wywołania/318 s i 15/318 s) i wciąż nie powstaje żaden diff.
  Zysk punktowy na tych dwóch zadaniach: **zero, tak jak w V6.2**.
- **O2 SPEŁNIONE**: `fastapi_14487` nie produkuje diffu dokumentacyjnego — produkuje pusty
  (26 wywołań, 320 s). Bramka mechanizmu zaliczona, wyniku brak.
- **O3 SPEŁNIONE**: `rich_3006` nadal pada na zegarze (4 wywołania/318 s — identycznie jak w V6.2).
- `trafienia lokalizatora 0/4` **nie** dowodzą porażki lokalizatora: przy pustym patchu nie ma pliku,
  w który mógłby trafić — pole jest funkcją patcha, nie osobnym pomiarem.

### Błąd proceduralny po mojej stronie

Plik-trigger pełnego przebiegu powstał w tym samym commicie co poprawki prozy i wszedł do repo przez
`git add -A`. **Jego wypchnięcie automatycznie odpaliło pełny screening w 01:08 — przed poznaniem
wyniku mini-screenu** (01:30), mimo że opis commita `1c5fd55` twierdził, że trigger nie jest jeszcze
wypychany. Zapisana procedura mówiła: pełny przebieg tylko po zaliczeniu G1–G3 **albo** po wyjaśnieniu
porażki. Formalnie G1–G3 są zaliczone, więc przebieg nie jest nieuprawniony — ale **nie został
uzależniony od wyniku mini-screenu**, jak zakładano. Reguła operacyjna: plik-trigger nigdy nie wchodzi
w `git add -A`; osobny commit zawierający wyłącznie trigger.

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
