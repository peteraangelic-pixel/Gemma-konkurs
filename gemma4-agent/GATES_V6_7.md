# V6.7 — bramki i pre-registracja (zamrożone **przed** jakimkolwiek przebiegiem)

Stan na 2026-10-14 ~16:45 UTC. V6.7 **nie został uruchomiony ani wysłany**. Powstał w oknie
oczekiwania na wynik V5 (ref `57188055`, PENDING od 15:58:54 UTC), z surowego śladu wywołań
pełnego przebiegu V6.4 — czyli z danych, których wcześniejsze analizy nie miały, bo podsumowania
śladów zapisują same nazwy narzędzi, a nie argumenty.

## Czym V6.7 jest

**V6.7 = V6.4 + jedna dźwignia (L4): zgodność z kontraktem narzędzi harnessu.**

Baza jest celowo V6.4, nie V6.5/V6.6: każde z trzech ramion sobotniego resetu wnosi dokładnie jedną
zmianę wobec wspólnego przodka, więc wynik da się przypisać. V6.7 **nie** zawiera klauzuli
„zrób edycję, nawet jeśli nie jesteś pewien" (V6.5) ani inline'owego lokalizatora (V6.6).

| | V6.4 | V6.7 |
| --- | --- | --- |
| artefakt | `submission-v6.zip`, `aaea34e4…`, 13 455 B | `submission-v6.7.zip`, **`df7364e2…`, 13 959 B** |
| prompt | 19 310 znaków (obecny generator; kopia w `submission-v6.4/` ma 17 888 znaków — patrz „Rozbieżność" niżej) | **21 983 znaków** |
| reguły | M1–M4 | M1–M4 + 7 reguł kontraktu (poniżej) |
| lokalizator | heredoc do `/tmp` + `python3 /tmp/locate.py` | bez zmian |

## Dowód, na którym to stoi (raport `analysis/diagnostics-2026-10-14/v64-raw-calls.md`)

Liczniki z całego przebiegu (30 zadań): `edit_calls_with_ok_result` 41,
`edit_calls_with_error_like_result` 49, `comment_only_commands` **32**,
`read_file_beyond_line_800` **29**.

| # | reguła w prompcie | pomiar, który ją uzasadnia | zadania |
| --- | --- | --- | --- |
| 1 | sufit 30 wywołań **odrzuca** pracę; traktuj call 20 jako ostatni punkt, w którym liczy się poprawka | `Tool call budget exhausted (30 calls)` jako odpowiedź na pierwsze `edit_file` | `fastapi_14851` (wywołanie 32), `fastapi_14487` (31), `fastapi_14953` (2×) |
| 2 | komentarz nie kończy sesji; kończ wiadomością bez wywołania narzędzia | 32 wywołania `run_command` z samym komentarzem (`# Final`, `# Done.`), 8 w jednej sesji | `fastapi_14297` i in. |
| 3 | pomiń `start_line`/`end_line`, jeśli nie pochodzą z `grep -n` | 29 odczytów poza końcem pliku; 6× wiersze 4470–4520 ~1000-wierszowego pliku | `fastapi_14851` |
| 4 | `write_file` nie pisze poza `/workspace` — używaj heredoka `cat > /tmp/... <<'EOF'` w `run_command` | `Path traversal detected: '/tmp/repro.py' escapes workspace root.` | `fastapi_14186`, `fastapi_14303`, `requests_7309` |
| 5 | po `Target string occurs N times` nie wysyłaj tego samego napisu — rozszerz kontekst | `FileEditError: Target string occurs 2 times in fastapi/param_functions.py` | `fastapi_14262` |
| 6 | udana edycja pliku resetowanego przez grader (m.in. `tox.ini`) jest **niewidoczna**; poprawka należy do źródeł importowalnych | dwa udane `edit_file` w `tox.ini`, każde potwierdzone diffem, drzewo ocenione jako puste | `requests_6757` (złoto: `src/requests/compat.py`, `src/requests/utils.py`) |
| 7 | „dokończ zgłoszenie, nie szukanie": po pierwszej edycji pokryj każdy nazwany przypadek | wszystkie 8 sesji, które dotknęły dobrego pliku i przegrały, zużyły 30 wywołań albo przekroczyły 315 s (lub oba) | koszyk R (8 zadań) |

Dodatkowo reguła 4 **koryguje zdanie odziedziczone po V6.4/V64E** („`write_file` i przekierowanie
shella są oba w porządku dla scratchu"), którego surowe ślady nie potwierdzają. Zdanie zostało
zachowane zgodnie z zasadą append-only, a korekta stoi bezpośrednio po nim; docelowo oba zdania
należy scalić w kolejnej rewizji.

## Największy pojedynczy defekt przebiegu: 9/9 odrzuconych zapisów poza repo

Trzecia iteracja raportu (run `38599233973`, commit `7ad1066`, licznik
`write_file_outside_workspace: 9`) wypisała obserwację **każdego** zapisu poza katalogiem roboczym.
Wynik jest jednoznaczny: **wszystkie 9 zostały odrzucone** tym samym błędem, a to 9 z 30 sesji (30 %):

| zadanie | ścieżka | co się stało dalej |
| --- | --- | --- |
| `fastapi_15588` | `/tmp/locate.py` (7 271 zn.) | koniec sesji, **puste drzewo** (3 wywołania) |
| `fastapi_15745` | `/tmp/locate.py` (7 874 zn.) | jw. — po odrzuceniu już tylko `cd /workspace` |
| `rich_3043` | `/tmp/locate.py` (7 824 zn.) | jw., **puste drzewo** |
| `httpx_3672` | `/tmp/locate.py` (7 824 zn.) | kontynuowała (grep/find/czytania), **puste drzewo** |
| `fastapi_14186` | `/tmp/issue.txt` (1 001 zn.) | kontynuowała, patch 813 znaków, koszyk R |
| `fastapi_14303` | `/tmp/repro.py` (971 zn.) | kontynuowała, patch 1 634 znaki, koszyk R |
| `requests_7309` | `/tmp/repro.py` (952 zn.) | kontynuowała, patch 692 znaki, koszyk R |
| `rich_2725` | `/tmp/repro.py` | **rozwiązane** (1 099 znaków) |
| `rich_3894` | `/tmp/repro.py` | **rozwiązane** (497 znaków) |

Kanonada błędu, identyczna w każdym z 9 przypadków:

```
{"status": "error", "error_type": "FileWriteError",
 "error_message": "Path traversal detected: '/tmp/locate.py' escapes workspace root."}
```

**Nasz prompt sam to spowodował.** Zdanie odziedziczone po V64E mówi wprost: „Always give a scratch
file an absolute `/tmp/...` path; `write_file` and shell redirection are both fine for that" —
model wybierał `write_file`, a harness odrzuca każdą ścieżkę poza `/workspace`. Dlatego reguła 4
V6.7 podmienia to zdanie (dopiskiem, zgodnie z append-only) na jawną korektę kontraktu.

## Korekta przesłanki V6.6 (pułapka lokalizatora) — potwierdzona

`GATES_V6_6.md` opisuje cztery sesje (`fastapi_15588`, `fastapi_15745`, `rich_3043`, `httpx_3672`)
jako te, które „napisały `/tmp/locate.py` i skończyły, jakby gotowy skrypt był pracą". Surowy ślad
pokazuje coś innego: każde z nich wywołało `write_file: filepath=/tmp/locate.py`, zapis został
**odrzucony**, a trzy sesje skończyły się natychmiast po odmowie. Skrypt nigdy nie powstał, więc
opisany mechanizm („gotowy skrypt uznany za pracę") nie wystąpił; wystąpiło odrzucenie zapisu.

Wniosek dla decyzji: naprawa V6.6 (jedno polecenie, zero plików) usuwa ten tryb awarii, ale **nie**
dlatego, że model „uznawał skrypt za pracę" — dlatego, że w V6.6 nie ma już żadnego pliku do
napisania. V6.7 regułą 4 adresuje ten sam tryb niezależnie, w ogólniejszej formie (obejmuje też
`/tmp/repro.py` i `/tmp/issue.txt`, czyli 5 pozostałych przypadków). Adnotacja dodana do
`GATES_V6_6.md`.

## Kontrole negatywne (wszystkie przechodzą)

Nowe, powtarzalne narzędzie: `python3 gemma4-agent/tools/negative_controls_v6.py --variant v67`.

- kontrola pozytywna: nietknięte drzewo buduje się i sha256 = `df7364e2…` (zgodny z zapisanym zipem),
- 10 kontroli negatywnych, każda usuwa/zmienia jedną frazę i **build musi się wywalić**:
  sufit wywołań, komentarze, „dokończ zgłoszenie", `write_file` poza workspace, wymyślone zakresy
  linii, `tox.ini`, pomiar M4 (`279.8 s`), zakaz atrapy, ostrzeżenie o gołych nazwach plików,
  oraz wstrzyknięcie tekstu V6.6 do drzewa V6.7 (mieszanie wariantów).
- Dwie kontrole **nie zadziałały za pierwszym razem** i to była ich wartość: packer nie przypinał
  zdania o `tox.ini` (dopisane do `V67_REQUIRED`), a kontrola mieszania wariantów wstrzykiwała
  frazę z wielkiej litery, przez co nie łamała guardu (poprawiona fraza dokładna).

## Czego V6.7 NIE twierdzi

- Nie jest zmierzony: żadnego przebiegu, żadnego score. To ramię na reset 2026-10-17 00:00 UTC.
- Reguły 1–7 to naprawa **marnotrawstwa i sprzeczności**, nie nowa zdolność modelu. Sukces = mniej
  pustych drzew i mniej zadań zabitych przez wyczerpany budżet — nie „więcej poprawnych łatek".
- Liczby w prompcie są cytatami z jednego przebiegu (30 zadań); nie są forecastem.
- Poprawa R (8 zadań, dobry plik, zły patch) zależy od reguły 7, która jest najsłabiej zmierzona
  z całej siódemki.

## Rozbieżność i higiena, do naprawy później

- Kopia `submission-v6.4/prompts/system.md` (17 888 znaków) jest starsza niż tekst, który produkuje
  obecny generator (19 310) — V64E przeredagował zdanie o scratchu po zbudowaniu tamtej kopii.
  Shippowane V6.5/V6.6 (20 222 / 19 770) są już po V64E. Zip V6.4 pozostaje zamrożony; przy
  następnym przebiegu V6.4 trzeba by go zbudować z obecnego generatora i **nie porównywać** wprost
  z historycznym `aaea34e4…`.
- Plan sobotni: trzy ramiona (V6.5, V6.6, V6.7) × ~5,6 h rozliczeniowych = ~17 h z 30 h tygodnia.
  Kolejność startów bez zmian; decyzja o tym, które ramię dostać ma pełny przebieg, po wynikach.

## Odtworzenie

```
V6_VARIANT=v67 python3 gemma4-agent/tools/make_v6_prompt.py
python3 gemma4-agent/build_submission_v6.py --source-dir gemma4-agent/submission-v6.7
python3 gemma4-agent/tools/negative_controls_v6.py --variant v67
```

## Pre-registracja oczekiwań (zapisana przed przebiegiem)

Przebieg: workflow `gemma-kaggle-v67-benchmark.yml` (gotowy), ten sam zestaw 30 zadań i ten sam
seed `20261009` co V3/V4/V5/V6.1–V6.4, więc porównanie jest 1:1. Start dopiero po pushu
`gemma4-agent/kaggle_smoke/v67-benchmark.trigger` — plik **nie istnieje**, workflow sam nic nie robi.

| # | predykcja (mierzalna) | V6.4 (referencja) | próg dla V6.7 |
| --- | --- | --- | --- |
| R1 | odrzucone zapisy poza repo, licznik `write_file_outside_workspace` z surowych śladów | **9** | **0** |
| R2 | puste drzewa (`patch_chars = 0`) | 11 | **≤ 7** |
| R3 | bramki jakości: G1, G3 | 0, 0 | **0, 0** |
| R4 | bramka G2 (puste drzewo i sesja < 280 s) | 3 | **≤ 1** |
| R5 | `comment_only_commands` z surowych śladów | 32 | **< 32** |
| R6 | rozwiązane zadania | 10/30 | **≥ 11** (najsłabsza predykcja, kierunkowa) |

R1 jest predykcją mechanizmową i nie zależy od score: jeśli reguła 4 nie działa, licznik zostanie
> 0 i dźwignia jest obalona niezależnie od wyniku. R6 jest celowo słabe — reguły 1–7 naprawiają
marnotrawstwo, nie jakość łatek, więc „więcej rozwiązanych" nie jest tym, co V6.7 obiecuje.

Polecenia po przebiegu:

```
python3 gemma4-agent/tools/analyze_v65_v66.py --folder v6-7-benchmark --tag V6.7 \
    --reference v6-4-benchmark --expect-solved 11 \
    --out gemma4-agent/kaggle_results/v6-7-benchmark/verdict.md
```

Do liczników R1/R5 potrzebny jest surowy ślad nowego kernela: workflow diagnostyczny
(`gemma-kaggle-v64-diagnose.yml`) wskazany na nowy kernel — bez tego R1/R5 zostają niezmierzone.
