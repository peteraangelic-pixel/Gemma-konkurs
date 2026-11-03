# Praca sieciowa na GitHub Actions — jak to uruchomić i czego mi NIE wysyłać

## Krótka odpowiedź na Twoje pytanie

**Nie potrzebuję Twoich loginów ani haseł. Nigdy.** Ani do hack.cert.pl, ani do
`mwdb.cert.pl`, ani do komunikatora. Hasło wklejone w czacie jest już spalone —
zostaje w historii rozmowy, w logach i poza Twoją kontrolą. Jeśli kiedykolwiek
poproszę Cię o hasło, to znaczy, że coś poszło bardzo źle albo to nie ja.

To, czego realnie potrzebuję, to **dwa różne poziomy dostępu**, i oba załatwiamy
bez wymiany sekretów na czacie.

## Poziom 1: praca anonimowa (to jest 90% roboty, zero sekretów)

Większość tego, co daje pieniądze w tym konkursie, nie wymaga logowania:
pobranie stron i bundli JS, analiza offline kodu `mwdb-core`, rekonesans,
sprawdzenie CORS. To wszystko robi workflow **bez żadnych sekretów**:

**Actions → `nask-recon` → Run workflow** (gałąź `arena/6d081d52-gemma-konkurs`).

Co się wtedy dzieje:
1. najpierw idą testy offline i kontrola scope (jeśli scope się rozjedzie z
   regulaminem, rekonesans **nie wystartuje**),
2. potem ~20 żądań z prędkością 4,5 req/s, wyłącznie do hostów z `scope.py`,
3. wynik: `recon.json` + `evidence.jsonl` (z SHA-256 każdej odpowiedzi) jako
   artefakt do pobrania, plus tabela w podsumowaniu uruchomienia.

Koszt: ~1 minuta runnera. Zero ryzyka, limit zachowany, wszystko w scope.

## Poziom 2: testy uwierzytelnione (potrzebne konto, NIE hasło)

Tu wchodzi jedna reguła z regulaminu, której nie da się obejść: §6 pkt 1 mówi,
że funkcje za logowaniem wolno testować **tylko z własnych kont**. To znaczy, że:

1. **Ty** rejestrujesz konto (np. na `mwdb.cert.pl`) — to zwykła rejestracja,
   nie wymaga ode mnie niczego.
2. **Ty** logujesz się w swojej przeglądarce i kopiujesz **nagłówek Cookie**
   z DevTools → Network → dowolne żądanie → `Cookie: ...`.
3. **Ty** wklejasz go jako **sekret GitHub Actions**:
   `Settings → Secrets and variables → Actions → New repository secret`
   - nazwa: `NASK_COOKIE_MWDBCERTPL`
   - wartość: `session=...`
4. Od tej pory workflow dokłada ten nagłówek do żądań **do tego jednego hosta**
   (`credentials.ALLOWED_HOSTS` pilnuje, żeby nie poszedł nigdzie indziej).

**Ja tego ciasteczka nie widzę** — jest maskowane w logach Actions, a `fetch.py`
nie zapisuje go do dziennika dowodów (jest na to osobny test:
`test_credentials_never_reach_evidence`). Gdy skończymy, usuwamy sekret jednym
kliknięciem i ciasteczko przestaje istnieć.

Nazwa sekretu = `NASK_COOKIE_` + host bez kropek i myślników, wielkimi literami:
`mwdb.cert.pl` → `NASK_COOKIE_MWDBCERTPL`. Pełna lista dozwolonych hostów jest
w `tools/credentials.py`.

### Czego NIE robić

- **Nie wklejaj mi hasła do hack.cert.pl.** Nie jest mi do niczego potrzebne:
  zgłoszenia wysyłasz sam przez formularz, pod swoim nazwiskiem (§4 regulaminu).
- **Nie wklejaj hasła do żadnego z celów.** Wystarczy ciasteczko sesji i tylko na
  czas testów.
- **Nie dawaj mi tokenu GitHub z uprawnieniami do repo.** Do uruchamiania
  workflow wystarczy, że klikniesz „Run workflow”; nie potrzebuję Twojego tokenu.

## Co Actions realnie daje, a czego nie

| zadanie | Actions? | dlaczego |
|---|---|---|
| rekonesans, pobranie bundli JS | **tak** | normalne wyjście do internetu, limit 5 req/s zachowany |
| analiza offline kodu `mwdb-core` | **tak** | tak naprawdę to robię lokalnie, ale Actions da 2 rdzenie i czysty obraz |
| testy uwierzytelnione z własnym ciasteczkiem | **tak**, przez sekret | logowanie robisz Ty, workflow tylko dokłada nagłówek |
| „znajdź luki, przeskanuj wszystko” | **nie** | §8 poz. 10 i 14: testy obciążeniowe i raporty z automatów są wykluczone |
| wysłanie zgłoszenia | **nie** | wymaga Twojego konta i Twojej decyzji |
| uruchomienie `mwdb-core` w Dockerze | **nie w Actions** | potrzebne dwa konta i trwały stan; rób lokalnie na 5950X |

## Co znajdziesz w artefakcie

`recon.json` — dla każdego celu: status, rozmiar, `server`, fingerprint technologii,
lista bundli; dla każdego bundla: wyciągnięte endpointy, parametry i „gorące pola”
(`userId`, `role`, `is_verified`, `tenant_id`…). To **nie są podatności** — to lista
miejsc, które trzeba otworzyć ręcznie i sprawdzić, czy serwer pilnuje uprawnień.

`evidence.jsonl` — jeden wiersz na żądanie: czas, URL, program, tier, status,
SHA-256 treści. To jest materiał dowodowy do raportu; bez niego PoC trzeba
odtwarzać od zera.

## Czego nie zrobię bez Twojej zgody

Nie uruchamiam niczego, co wysyła żądania modyfikujące stan (POST/PUT/DELETE) poza
jawnym `--send` / interakcją w przeglądarce po Twojej stronie. `recon.py` składa
wyłącznie żądania GET.
