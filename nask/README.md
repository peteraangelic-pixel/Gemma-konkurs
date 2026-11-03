# NASK Bug Bounty (hack.cert.pl) — projekt roboczy

Konkurs: **pierwszy polski państwowy bug bounty**, platforma <https://hack.cert.pl>,
edycja **11/2026: 03.11 – 30.11.2026**, pula edycji NASK **100 000 zł**, nagrody
**600–20 000 zł** za błąd (zależnie od programu, tieru i CVSS 4.0).

Ten katalog to **mój** warsztat do tego konkursu. Poprzedni projekt (ARC-AGI) jest
w `../archive/arc-agi-3/` — zamknięty, zostawiony dla historii.

## Od czego zacząć czytanie

| plik | co zawiera |
|---|---|
| [`SCOPE.md`](SCOPE.md) | zakres wszystkich 5 programów, zweryfikowany u źródła, z pułapkami |
| [`POMYSLY.md`](POMYSLY.md) | **jak wygrać** — pomysły uszeregowane po EV/dzień, w tym uczciwie o „Rust wszędzie” |
| [`PLAN.md`](PLAN.md) | plan dzień po dniu na 28 dni konkursu |
| [`AUDYT-POPRZEDNIEGO-REPO.md`](AUDYT-POPRZEDNIEGO-REPO.md) | co jest zepsute w repo `peteraangelic-pixel/NASK` (sprawdzone w kodzie) |

## Narzędzia (Python, zero zależności, 46 testów offline)

```bash
python3 nask/nask.py scope --list          # cały zakres
python3 nask/nask.py scope nask.pl         # czy host jest w scope
python3 nask/nask.py plan nask/plan.json   # tabela EV hipotez
python3 nask/nask.py mine bundle.js --host app.komunikator.narodowy.gov.pl
python3 nask/nask.py get https://www.gov.pl/          # domyślnie DRY-RUN
python3 nask/nask.py get https://www.gov.pl/ --send   # naprawdę wysyła
```

| moduł | rola |
|---|---|
| `tools/scope.py` | jedyne źródło prawdy o zakresie; nieznany host = ODMOWA |
| `tools/ratelimit.py` | token bucket wspólny dla procesów, **odmawia startu > 5 req/s** |
| `tools/fetch.py` | jedyna droga do sieci: scope + limiter + dziennik dowodów z SHA-256 |
| `tools/jsmine.py` | endpointy, parametry, pola typu `role`/`userId` z bundli JS |
| `tools/triage.py` | EV = nagroda × P(trafienie) × P(brak duplikatu), na dzień pracy |
| `tools/report.py` | generator zgłoszenia; **odmawia** wygenerowania bez PoC i wpływu |

Testy:

```bash
python3 -m pytest nask/tools/tests -q      # 46/46, bez sieci
```

## Twarde reguły (z regulaminu, nie z dobrych chęci)

1. **≤ 5 req/s** — limiter w repo ustawia 4,5 i nie pozwoli więcej.
2. **Tylko hosty z `scope.py`** — literówka w domenie to nie „brak nagrody”, a problem prawny.
3. **Zero DoS, zero testów obciążeniowych, zero spamu powiadomieniami.**
4. **Tylko własne konta.**
5. **Zgłoszenia wyłącznie przez formularz hack.cert.pl**, z PoC; dyskrecja do poprawki.

## Podział pracy

**Ja (agent):** kod i narzędzia, analiza offline otwartych źródeł `mwdb-core` / `n6portal`,
triage EV, generowanie raportów, przegląd dowodów.
**Ty:** rejestracja własnych kont, wysyłka żądań ze swojej maszyny lub Actions, kliknięcia
w przeglądarce tam, gdzie potrzebny zalogowany użytkownik, i **wysyłka zgłoszeń**.

Powód jest formalny: żądania do celów w scope muszą wychodzić spod Twojej
odpowiedzialności jako uczestnika konkursu (§4 regulaminu). Ja nie mam też dostępu
sieciowego do tych hostów z sandboxa.

## Realistyczne oczekiwania

Suma EV wszystkich 19 hipotez z `plan.json` to **≈ 9 900 zł** — nie 100 000. Jedna dobrze
udokumentowana luka IDOR to 4 000–9 000 zł, więc cel jest wart pracy, ale to nie jest
dochód, na którym można oprzeć budżet. Więcej w [`POMYSLY.md`](POMYSLY.md) §0.
