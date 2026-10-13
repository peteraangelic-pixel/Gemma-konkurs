# Bramki V6.4 — zamrożone **przed** jakimkolwiek przebiegiem

**Data zamrożenia:** 2026-10-13, przed pierwszym uruchomieniem. Nic nie zostało uruchomione: żaden
trigger nie istnieje, nie powstał żaden submitter V6.4, GPU nie zostało użyte.

## Czym jest V6.4

V6.3 + **cztery reguły promptu**, każda przypięta do jednego zmierzonego mechanizmu z read-only
diagnozy kerneli V6.3 (`ANALYSIS_V6_3_MECHANISMS.md`):

| reguła | mechanizm, który naprawia | pomiar bazowy (V6.3, pełny przebieg) |
| --- | --- | --- |
| **M1** „No reading without writing” — pierwsze wywołanie po przeczytaniu pierwszego pliku to próba edycji; jeśli do wywołania 6 nie ma edycji, następne wywołanie **musi** być `edit_file`/`write_file` | brak jakiejkolwiek próby edycji | 7/30 sesji bez edycji; jedna zużyła 31 wywołań na `run_command`/`read_file`; dwie skończyły same po 41 s i 108 s; mediana pierwszej edycji 179 s z 315 s |
| **M2** „If an `edit_file` call does not change the file, do not repeat it” — jedna inna kotwica, potem `write_file` całego pliku | pętla nieudanych edycji | `fastapi_15030`: 9 wywołań `edit_file` pod rząd (212–307 s), diff nadal 0 znaków |
| **M3** „`submit_patch()` … at most once” — powtórzenie submitu to sygnał do edycji, nie do ponawiania | pętla submitu zjadająca limit tur | `requests_6757` 48 wywołań, `fastapi_14077` 44, `rich_3894` 42 → wszystkie trzy padły na limicie 60 tur |
| **M4** „Scratch files are never your answer” — przed pierwszą edycją wolno tylko heredok lokalizatora; po edycji skrypt `repro` w `/tmp` jest dozwolony, ale oceniany jest wyłącznie diff w repo | plik-pomocnik zamiast edycji | `fastapi_15745`: `write_file` → `/tmp/locate.py` o 279,8 s, zero edycji (pusty patch); **kontrprzykład**: `rich_3006` napisał `/tmp/repro.py` *po* edycji i zdał — reguła NIE może tego zabraniać |

### Piąta zmiana (scalona z pracy drugiej gałęzi) — usunięcie narzędzia `submit_patch`

Druga gałąź przygotowała offline kandydata V6.4 z dwiema zmianami: przesunięciem terminu pierwszej
edycji z call 8 na call 4 i **usunięciem `submit_patch` z `agent.yaml`**; jej własne zastrzeżenie
brzmiało: „usunięcie `submit_patch` zakłada, że harness przechwyci working-tree diff — to założenie
nie zostało zweryfikowane end-to-end". **Zastrzeżenie jest już nieaktualne: zweryfikowałem je
read-only na danych V6.3.**

| dowód (pełny przebieg V6.3) | liczba |
| --- | --- |
| zadania, które **ani razu** nie wywołały `submit_patch` | **17/30** |
| z nich: niepusty patch, który został **oceniony** | **8** (`rich_3052`, `fastapi_14873`, `fastapi_15588`, `fastapi_14186`, `fastapi_14262`, `requests_7309`, `fastapi_14482`, `fastapi_14458`) |
| z nich: **PASS** bez żadnego wywołania submitu | **2** — `fastapi_14873` (patch 1 681 znaków), `fastapi_14458` (1 361) |

Skoro harness ocenił i zaliczył zadania, w których nigdy nie wywołano submitu, narzędzie jest zbędne —
a sesje, które je miały, wpadały w pętle 48/44/42 wywołań i padały na limicie 60 tur. **Usunięcie
narzędzia likwiduje mechanizm M3 u źródła**, zamiast prosić model, żeby go unikał; dlatego przyjęte.
Usunięcie pociągnęło przepisanie prozy: prompt nie zawiera już **żadnego** `submit_patch()`
(strażnik packera to egzekwuje), a `agent.yaml` nie deklaruje narzędzia (drugi strażnik).

**Sprzeczność zgłoszona przez drugą gałąź, naprawiona:** reguła M4 („nie twórz plików”) kolidowała
z krokiem 2 (heredoc `cat > /tmp/locate.py`). Nowe brzmienie mówi wprost: „**Poza pojedynczym
heredokiem lokalizatora w kroku 2** nigdy nie twórz pliku, który ma ci pomóc…".

### Weryfikacja ich paczki (plik po pliku, gdy ją wypchnęli) i scalenie terminu call 4

Druga gałąź wypchnęła paczkę commitem `8eb94cd` („Add offline V6.4 candidate package"). Weryfikacja:

| sprawdzenie | wynik |
| --- | --- |
| SHA archiwum vs deklaracja `0cc04c08…` | **zgodny** |
| archiwum vs katalog źródłowy | **identyczne** (`diff -rq`, 5 plików) |
| `tools/locate.py` vs V6.3 | **identyczny** (deklaracja prawdziwa) |
| `configs/sampling.yaml`, `eval_config.yaml` vs V6.3 | **identyczne** (deklaracja „limity bez zmian" prawdziwa; mój pierwszy test dał fałszywy alarm przez własną literówkę w nazwie pliku) |
| `agent.yaml` | `submit_patch` usunięty — ta sama konkluzja, którą już scaliliśmy |
| ich builder `build_submission_v64.py` | deterministyczny (stały czas ZIP, `create_system=3`, flaga UTF-8 0x800, `external_attr`), egzekwuje dokładny zbiór narzędzi, brak `submit_patch`, budżety 30/60/5.25, treść archiwum i CRC |

**Termin pierwszej edycji — zmiana decyzji, przyjęte.** Wcześniej odłożyłem call 4 jako niepomierzony;
po zobaczeniu ich pełnego brzmienia przyjmuję je, z dwóch powodów merytorycznych: (1) zawiera
**zakaz atrapy edycji** („never create a dummy edit merely to satisfy the deadline") — a recenzent
prosił dokładnie o wymóg **zamierzonej** zmiany; bez tego zakazu próg jest grą w statystyki,
z nim jest wymogiem; (2) okazało się, że próg ma **ostry, policzalny baseline**: w V6.3 mediana
pierwszej edycji wypadła na **wywołaniu nr 10**, a w terminie call 4 zmieściło się **3/30** zadań.
Nowe brzmienie (scalone): termin call 4 + zakaz atrapy + moja reguła ratunkowa M2 + moja reguła M4.

**Uczciwie o koszcie tego scalenia:** dwa ramiona (ich call 4, mój call 6/8) zostały zastąpione
jednym, więc ten przebieg nie rozstrzygnie, „czy 4 lepsze od 8". Rozstrzygnie natomiast, czy próg
w ogóle działa — bo mierzymy rozkład indeksu wywołania pierwszej edycji, nie tylko średnią.

**Uczciwa uwaga o „koktajlu":** paczka V6.4 zmienia naraz kilka rzeczy i sama w sobie nie przypisze
efektu pojedynczemu przełącznikowi — dokładnie tak, jak ostrzegła druga gałąź. Różnica jest w tym,
że **nasz instrument to mierzy per mechanizm**: po przebiegu z samych ścieżek policzymy osobno
pokrycie edycji (M1), najdłuższą serię `edit_file` (M2), liczbę `submit_patch` (M3 — oczekiwane 0,
bo narzędzia nie ma) i zapisy o ścieżce absolutnej (M4). Koktajl jest więc akceptowalny **tylko
dlatego**, że umiemy rozłożyć wynik na składowe; gdybyśmy tego nie mieli, należałoby rozbić paczkę.

**Czego V6.4 NIE zmienia:** budżet 30 wywołań, 60 tur, 150 s na komendę, 5,25 min sesji, timeout
testów 45 s, `thinking_budget` 4096, skrypt lokalizatora. Zmiana budżetu myślenia to osobny
eksperyment (wymóg recenzji) i nie jest tu mieszana.

## Tożsamość artefaktu (weryfikowalna)

| element | wartość |
| --- | --- |
| archiwum | `gemma4-agent/submission-v6.zip`, **13 427 B**, sha256 `b5db88b8d393e92dc03ef8de7e97af42370e033b91d7ed4b3a25a38d771e2603` |
| odtwarzalność | dwa kolejne buildy = ten sam hash (stały znacznik ZIP 1980-01-01); kontrola negatywna: podmiana jednej reguły wywala build |
| prompt | 18 966 znaków (V6.3: 17 603); wobec V6.3: **+4 linie reguł, przepisana proza o submicie** (dokładnie cztery reguły; jedna linia zmieniona: „optional” → „optional, and you may call it at most once”) |
| lokalizator | `tools/locate.py` `fe25b200fa52e100…` **bez zmian**, bajt w bajt taki sam w ZIP i w repo |
| zamrożony prompt V6.3 | `gemma4-agent/candidates/v6-3/prompts-system.md` (17 603 znaków, sha256 `423da01cc4ddc019…`) — żeby archiwum V6.3 pozostało audytowalne |
| packer | `build_submission_v6.py` + 4 strażniki reguł, 4 strażniki pomiarów, zakaz `submit_patch` w `agent.yaml`, zakaz `submit_patch()` w promptcie; kontrole negatywne obu sprawdzone |
| notebook | `kaggle_smoke/gemma-agent-benchmark-v6.ipynb` regenerowany dla `3843c878` |

**Uwaga o odtwarzaniu V6.3:** obecny packer egzekwuje reguły V6.4, więc **nie odtworzy** archiwum
V6.3 — to celowe (V6.3 nie jest kandydatem do wysyłki: G2 = 3). Archiwum V6.3 jest zamrożone
w historii (`3ee7dd2`) i nadal zapięte pinem w `submit_kaggle_v63_once.py`; gdyby ktoś odpalił tamten
workflow, uploader odmówi z `archive_hash_mismatch` (exit 2) — czyli bezpiecznie, nie wysyłkowo.


## Ile dokładnie różni się moja wersja od paczki drugiej gałęzi (stan: 2026-10-13 09:20 UTC)

Odpowiedź krótka: **dzielą nas dwa mechanizmy z czterech i dwa zadania z 30 — ale to różnica
w pokryciu mechanizmów, nie w wyniku. Żadna z wersji nie była mierzona, więc żadna nie jest
„lepsza" w sensie wyniku; jest lepsza w sensie tego, ile zmierzonych przyczyn zer adresuje.**

| mechanizm (puste drzewa w V6.3) | ich paczka `0cc04c08` | mój kandydat `b5db88b8` |
| --- | --- | --- |
| **M1** brak próby edycji — 7/30 | **TAK** (termin call 4 + zakaz atrapy) | **TAK** (ich brzmienie, przyjęte) |
| **M2** pętla nieudanych `edit_file` — 1/30 (`fastapi_15030`, 9 wywołań) | **nie** — brak jakiejkolwiek reguły ratunkowej | **TAK** (inna kotwica, potem `write_file` całego pliku) |
| **M3** pętla `submit_patch` — 2/30 | **TAK** (narzędzie usunięte) | **TAK** (to samo) |
| **M4** plik-pomocnik zamiast edycji — 1/30 (`fastapi_15745`) | **nie** — reguła wprost pozwala na inne pliki w `/tmp` („If any other scratch file is needed, put it under `/tmp`"), czyli dopuszcza zachowanie, które opróżniło to zadanie | **TAK**, ale wąsko: zakaz tylko *zastępowania* edycji plikiem; po edycji `repro` w `/tmp` jest dozwolony |
| **pokrycie pustych drzew** | **9/11** | **11/11** |
| różnica w zadaniach | — | **2/30 = 6,7 pp próbki** były gwarantowanymi zerami z przyczyn, których ich wersja nie adresuje |

**Co to daje, a czego nie daje:** 6,7 pp to udział zadań, które w V6.3 spłonęły na mechanizmach M2/M4 —
to **górna granica** potencjalnej korzyści, nie prognoza wyniku. Nie mamy dowodu, że zamknięcie
mechanizmu zamienia się w punkt: V6.3 miał o jedno rozwiązanie więcej niż V6.2 przy jednocześnie
**większej** liczbie zer, więc samo „mniej zer" nie przełożyło się wtedy na wynik.

**Czego nie wolno mi przypisać sobie:** termin call 4 z zakazem atrapy to **ich** pomysł
i najlepsza pojedyncza zmiana w tej paczce; bez niego moja wersja stałaby na progu call 6/8.
Przyjąłem go w całości, z podpisem w `GATES_V6_4.md` i w historii commitów.

**Gdzie ich wersja jest lepsza lub równa:** prompt jest o ~1,5 tys. znaku krótszy (17 888 vs 19 378,
+8,3 % u mnie — koszt nieistotny dla modelu, ale to ich zaleta), ich builder ma równoważne strażniki
(dokładny zbiór narzędzi, budżety, CRC, determinizm), a ich łagodniejsza reguła o plikach
tymczasowych **okazała się mieć rację**: dopuszcza wzorzec, którego użyło rozwiązane `rich_3006`.
Właśnie dlatego **zaweziłem swoją regułę M4** zamiast ją zostawiać w formie zakazu — ich wersja
wskazała koszt, którego nie zmierzyłem przed wypchnięciem.

**Różnica netto, w jednym zdaniu:** mój kandydat adresuje 4 z 4 zmierzonych mechanizmów, ich 2 z 4;
przy czym gdyby ich paczkę uzupełnić o regułę M2 i wąską wersję M4, byłaby równoważna. Różnica jest
więc w pracy włożonej w diagnozę, nie w jakości samego pomysłu na V6.4.

## Bramki (hard — bez zmian wobec V6.3)

- **G1** pliki-śmieci w diffie = 0
- **G2** przedwczesne puste drzewa (patch 0 i sesja < 280 s) = 0
- **G3** diffy wyłącznie dokumentacyjne = 0
- **G4** puste drzewa ≤ 4 — raportowane, **nie** bramkuje

## Nowa metryka mechanizmu **M5** (raportowana osobno, **nie** bramkuje wyniku)

- **pokrycie edycji** = zadania z ≥ 1 wywołaniem `edit_file`/`write_file` (liczone read-only
  z `trace-operations.json` po przebiegu). **Baseline V6.3: 23/30. Cel: ≥ 27/30.**
- **dodatkowo: rozkład indeksu wywołania pierwszej edycji.** Baseline V6.3: mediana na wywołaniu **10**, w terminie call 4 zmieściło się **3/30** — cel ≥ 12/30.
- raportowane razem: mediana czasu pierwszego zapisu (baseline 184,6 s), najdłuższa seria
  `submit_patch` (baseline 48), zapisy o ścieżce absolutnej (baseline `/tmp/locate.py`, `/tmp/repro.py`).

M5 mierzy **mechanizm**, nie wynik; przy n=30 nie uprawnia do twierdzenia o przewadze punktowej.

## Pre-registered oczekiwania (falsyfikowalne — zapisane przed przebiegiem)

1. **E1**: sesji bez jakiejkolwiek próby edycji ≤ 3/30 (baseline 7/30).
2. **E2**: `submit_patch` **nie pojawi się ani raz** w ścieżkach — narzędzia nie ma w `agent.yaml` (baseline: 48/44/42 wywołania).
3. **E3**: co najwyżej jedna sesja z serią ≥ 3 nieudanych edycji (baseline: `fastapi_15030`, 9 pod rząd).
4. **E4**: w ścieżkach brak zapisu o ścieżce absolutnej poza repo (baseline: `/tmp/locate.py`).
5. **E5**: mini-screen **nie jest prognozą** wyniku — rozstrzyga pełny przebieg (dowód z V6.3:
   `rich_3006` zginął na zegarze w mini, a w pełnym został rozwiązany).
6. **E6**: jeśli po przebiegu pokrycie edycji nadal wynosi ≤ 23/30, to **reguły promptu nie zmieniają
   zachowania** i następnym dźwigniom (telemetria, parametry, architektura) poświęcamy osobny test —
   bez ponownego „dokładania reguł".

## Plan przebiegów — **wymaga Twojego zatwierdzenia; nic nie zostało uruchomione**

1. **Mini-screen 6 zadań mechanizmowych:** `rich_3105` (M1 szybki), `rich_3043` (M1 średni),
   `fastapi_15030` (M2), `requests_6757` (M3), `fastapi_15745` (M4), `fastapi_14077` (M3 przy
   zadaniu rozwiązanym) — outdir `v6-4-miniscreen`, ~1/5 kosztu pełnego przebiegu.
2. **Pełny screening 30 zadań**, seed `20261009`, ten sam dobór zadań co V3–V6.3 — outdir
   `v6-4-benchmark`; startuje po zaliczeniu G1–G3 w mini-screenie **albo** po wyjaśnieniu porażki,
   nigdy „przy okazji” innego commita.

Reguła operacyjna z 13.10: plik-trigger wyłącznie w osobnym commicie; `git add -A` nigdy nie dotyka
`kaggle_smoke/*.trigger`.

## Reguła decyzyjna o submissji (zamrożona **przed** wynikami)

Submissja V6.4 następuje wtedy i tylko wtedy, gdy: (1) G1–G3 = 0 w **obu** przebiegach; (2) pełny
przebieg ≥ 9/30; (3) slot dzienny wolny; (4) użytkownik wyraźnie zatwierdza. Ponadto:

- **V6.4 nie ma submittera i mieć go nie będzie, dopóki (1) i (2) nie są spełnione.** Bez
  zapiętego pliku nie da się wysłać niczego przypadkiem — to celowe, po dwóch wpadkach z pinem SHA.
- Gdy warunki zajdą, submitter V6.4 (`submit_kaggle_v64_once.py`, pin `3843c878…`, komunikat „V64”,
  bramki `v6-4-miniscreen,v6-4-benchmark`) powstaje **w tym samym commicie co decyzja**, i dopiero
  wtedy `compare_screenings.py` dostaje wiersze `V6.4-mini`/`V6.4` (wcześniej walidator CI95 słusznie
  wymagałby wierszy bez wyników i czerwieniłby repo).

## Uczciwe zastrzeżenie

V6.4 nie obiecuje wyższego wyniku. Testuje cztery mechanizmy, które w V6.3 produkowały
**gwarantowane zera**. Jeśli E1–E4 przejdą, a liczba rozwiązań nie wzrośnie, to nadal użyteczna
wiedza: wiemy, że problem nie leży w regułach promptu. Jeśli E1–E4 nie przejdą, reguły są
nieskuteczne w tej formie i wracamy do projektowania — z tym samym, niemodyfikowanym progiem.

## Skąd ta wersja i co z pracą drugiej gałęzi

Paczka V6.4 drugiej gałęzi (sha256 `0cc04c08f16b3ee965bf449af5ed8599eb4b18876f593f98f01de82bec37d514`,
pliki `submission-v6.4.zip`, `V6_4_PREPARATION.md`, `build_submission_v64.py`) **nie została
zcommitowana ani wypchnięta** — jej własna notatka to potwierdza, a `git ls-remote` pokazuje na
`arena/6d081d52-gemma-konkurs` nadal tip `7a10a03` z 2026-10-12 07:17. Dlatego nie da się jej
porównać plik po pliku: praca istnieje w sandboxie tamtej sesji, nie w repozytorium.

Stan scalenia na dziś: **przyjęte i zweryfikowane** — usunięcie `submit_patch` oraz naprawa
sprzeczności o `/tmp/locate.py`; **odłożone** — termin call 4 jako osobne ramię. Prośba do drugiej
sesji: wypchnąć swoją paczkę (choćby na jej własną gałąź), żeby dało się zrobić uczciwy `diff`
plików `agent.yaml`, `prompts/system.md` i skryptu budującego zamiast opierać się na opisie.

## Dopisane po scaleniu (nadal przed przebiegiem)

**E7 (nowe):** liczba zadań z pierwszą edycją w terminie call 4 wzrośnie z 3/30 do **≥ 12/30**.
**E8 (nowe):** żaden scenariusz nie okaże się „atrapą" — sprawdzane pośrednio: zadania, w których
pierwsza edycja dotyczy pliku niebędącego kandydatem lokalizatora **i** patch jest pusty na koniec,
raportowane jako podejrzenie gry w próg (V6.3: 0 takich).

**Paczka drugiej gałęzi zostaje w historii jako alternatywa**, nie jako kandydat do przebiegu:
`gemma4-agent/submission-v6.4.zip` (`0cc04c08…`) + `submission-v6.4/` + `build_submission_v64.py` +
`V6_4_PREPARATION.md`. Kandydatem do uruchomienia jest **wyłącznie** `submission-v6.zip`
(`f4e1edcb…`), bo tylko on zawiera wszystkie cztery reguły mechanizmu razem z ich terminem.
Jeśli kiedyś zechcemy rozdzielić ramiona, ich paczka jest gotowym, zweryfikowanym punktem wyjścia.
