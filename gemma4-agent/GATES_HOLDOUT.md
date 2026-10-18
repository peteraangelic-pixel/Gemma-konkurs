# Repo holdout — co mierzymy, czym to nie jest, i bramki (zapisane 2026-10-18, przed wynikiem)

Pytanie, które user zadał przy wyborze: *czy 0,13 to pamięć promptu, czy realna naprawa?*
Odpowiedź uczciwa: **tego nie da się zmierzyć tym eksperymentem** i trzeba to powiedzieć wprost.
Wszystkie cztery repozytoria (fastapi, rich, requests, httpx) były używane do iterowania promptu przez
V6.x/V7/V8. Wykluczenie jednego z nich **nie tworzy holdoutu pamięci** — tworzy pomiar **wrażliwości
na skład zestawu**. To wciąż jest wartość, tylko inna:

> Jeśli wynik zależy od tego, ile w zestawie jest fastapi (53 % publicznego splitu), to 0,13 jest
> liczbą o tym składzie — a nie o naszej umiejętności naprawiania kodu.

## Co wiemy przed startem: wynik per repozytorium (V7-c, 30 zadań, V5 + zegar 8 min)

| repo | n | rozwiązane | wskaźnik | puste drzewa |
| --- | ---: | ---: | ---: | ---: |
| Textualize/rich | 10 | 6 | **0,60** | 2 |
| psf/requests | 3 | 1 | 0,33 | 1 |
| fastapi/fastapi | 16 | 3* | **0,13–0,19** | 4 |
| encode/httpx | 1 | 0 | 0,00 | 0 |
| razem | 30 | 10* | 0,33 | 7 |

\* Jedno „rozwiązanie" fastapi (`fastapi_14851`) miało **pusty patch** i `test_exit_code 0` —
to nie jest naprawa, to anomalia. Ta sama konfiguracja z V8 (też pusty patch) dała
`resolved=false`, więc werdykt tego zadania zmienia się przy identycznym, pustym diffie.
Traktujemy je jako **znany flake** i liczymy fastapi jako 2/16.

Czyli: **9 z 10 naszych wygranych to rich i requests**, a fastapi — połowa zestawu — jest naszą
najsłabszą częścią. To jest już odpowiedź, której szukaliśmy: nie „pamięć promptu", tylko
**nierówna umiejętność między repozytoriami**, i to jest kierunek następnej dźwigni.

## Cztery ekrany (po jednym na wykluczone repo)

| config | wykluczone repo | zadania (limit 30, cap = ile zostanie) | oczekiwany wskaźnik z V7-c na ocalałych |
| --- | --- | ---: | ---: |
| `screen-holdout-fastapi.json` | fastapi/fastapi | ~14 | (6+1+0)/14 = **0,50** |
| `screen-holdout-rich.json` | Textualize/rich | ~20 | (2+1+0)/20 = 0,15 |
| `screen-holdout-requests.json` | psf/requests | ~27 | (2+6+0)/27 = 0,30 |
| `screen-holdout-httpx.json` | encode/httpx | ~29 | (2+6+1)/29 = 0,31 |

Wszystkie: archiwum **`submission-v5.zip`** (jedno z 0,13), seed 20261009, concurrency 3,
`start_now: true`, `max_wait_minutes: 90`. Kolejność jak w tabeli — od najbardziej informacyjnego.

## Bramki (pre-rejestrowane, nie zmieniamy po fakcie)

**H1 — brak załamania.** Ekran fastapi-excluded ≥ **6/14** (0,43): na repozytoriach, na których
nie koncentrowała się nasza słabość, utrzymujemy ~połowę. Wniosek: 0,33 na ekranie jest realne,
a słabość jest cechą fastapi, nie całego harnessu.

**H2 — załamanie.** Ekran fastapi-excluded ≤ **3/14** (0,21). Wtedy nawet „łatwe" repozytoria nie
dają wyniku i 0,13 trzeba tłumaczyć składem zestawu, nie umiejętnością — a każdy kolejny ekran
używający fastapi jest bezużyteczny jako miara postępu.

**H3 — kompozycja vs trudność.** Jeśli rich-excluded ≈ 0,15, a fastapi-excluded ≈ 0,50, to
o wyniku decyduje **trudność repozytorium**, a nie kolejność ani seed. Wtedy następna dźwignia
musi dotyczyć fastapi: jego testy są obszerniejsze, a nasze sesje kończą się tam na 45 wywołaniach
albo na zegarze (14 z 16 sesji fastapi w V8 stanęło na zegarze).

**H4 — stabilność.** Wszystkie cztery ekrany w przedziale 0,20–0,40 → wynik jest niewrażliwy na
skład; wtedy dźwignia promptowa jest wyczerpana i zostaje budżet/narzędzia (zegar, liczba wywołań),
a nie treść promptu.

## Czego ten eksperyment NIE odpowie

- **Nie zmierzy pamięci promptu** — wszystkie cztery repozytoria były w pętli iteracji.
  Prawdziwy holdout wymagałby repozytoriów, których nigdy nie widzieliśmy, a publiczny split
  to dokładnie te cztery.
- **Nie przeskaluje 1:1 na oficjalny split** — 58 zadań oficjalnych ma nieznany skład; każdy ekran
  to 14–29 zadań, czyli ±20–30 pp CI. To jest pomiar kierunku, nie prognoza wyniku.
- **Nie powie, czy 0,13 wzrośnie** — mówi tylko, gdzie tracimy zadania.

## Budżet i bezpieczeństwo wykonania

- 90 zadań łącznie ≈ **2,2 h wall** przy zmierzonym przeplocie 2,8× → ≈ **4,4 h kwoty**.
  Kwota resetuje się w sobotę 2026-10-24 00:00 UTC; do tego czasu **zero GPU**.
- Kaggle pozwala na **2 równoległe sesje GPU batch** (dziś dwie próby padły na tym limicie:
  „Maximum batch GPU session count of 2 reached"). Dlatego ekrany idą **po jednym** — stage,
  trigger, wynik, następny. Narzędzie `tools/stage_screen.py` odmawia stagowania, dopóki
  `screen-v8.trigger` istnieje.
- Każdy ekran przechodzi przez te same dwa strażniki co dziś (`check_notebook_names.py`,
  `test_notebook_concurrency.py`) i przez nowy `test_holdout_selection.py`, który sprawdza, że
  wykluczone repo nie wraca tylnymi drzwiami przez zarezerwowane `fastapi_15588` ani przez
  nazwane `task_ids`.
