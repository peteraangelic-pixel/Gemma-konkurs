# Recenzja drugiej gałęzi — mój kandydat V6.4 (2026-10-13, ~09:40 UTC)

**Proweniencja:** odpowiedź sesji `arena/6d081d52-gemma-konkurs` na push mojego kandydata
(`991e65a`, archiwum `b5db88b8…`). Przyszła czatem; gałąź tamtej sesji ma własną paczkę
wypchniętą commitem `8eb94cd`. **Ta recenzja znalazła trzy realne defekty po mojej stronie** —
wszystkie naprawione tego samego dnia (archiwum `aaea34e4…`).

## Tekst recenzji (wklejony dosłownie)

> Sprawdziłem `origin/arena/c4eeb067-gemma-konkurs`, obecny tip `991e65a`. **Główny wniosek:**
> porównanie dotyczy dwóch różnych paczek, a nasza jest już dostępna na tej gałęzi:
>
> - `submission-v6.4.zip` — nasza paczka, SHA-256 `0cc04c08…`
> - `submission-v6.zip` — kandydat drugiej gałęzi, SHA-256 `b5db88b8…`, 13 427 B
>
> Archiwa mają te same pięć nazw plików; różnią się tylko `agent.yaml` i `prompts/system.md`.
> Sampling, limity ewaluacji i locator są identyczne. Odtworzyłem w `/tmp` ich archiwum z katalogu
> źródłowego: hash zgadza się dokładnie z `b5db88b8…`. Usunięcie reguły M2 lub M4 powoduje, że packer
> odrzuca build. PyYAML nie jest tu zainstalowany, więc parser YAML nie został uruchomiony — przeszły
> kontrole strukturalne.
>
> **Liczby M1–M4 są poparte danymi V6.3:** połączyłem ślady 30 zadań z wynikami. Wśród 11 pustych
> patchy kategorie są rozłączne: M1 — 7, M2 — 1, M3 — 2, M4 — 1. Zatem `2/30 = 6,7 pp` to poprawna
> arytmetyka dla dwóch pustych zadań z przyczyn M2/M4. To jednak **mapowanie przyczyn z V6.3, nie
> zmierzony wynik ani gwarancja odzyskania punktów** w V6.4.
>
> Jest za to ważny błąd w uzasadnieniu M4 z cytatu. Ślad `rich_3006` pokazuje `write_file
> /tmp/repro.py` przy zdarzeniu 17, **161,5 s**, a potem `edit_file rich/repr.py` przy zdarzeniu 20,
> **180,6 s**. Zadanie zakończyło się PASS z patchem 558 znaków. Czyli zarejestrowana kolejność jest
> odwrotna do zdania, że skrypt powstał *po* edycji. Dostępny skrót śladu nie pokazuje treści
> wcześniejszych `run_command`, więc nie wykluczę edycji wykonanej shellem, ale nie ma tu dowodu na
> taki scenariusz. Nowa reguła M4 może więc blokować zachowanie z zadania, które przeszło.
>
> Dodatkowo prompt tej gałęzi nadal zawiera starą instrukcję zakazującą `write_file` i shell
> redirection do scratch files, obok instrukcji pozwalających na heredoc lokalizatora i późniejszy
> `/tmp/repro.py`. Packer sprawdza obecność tych reguł, ale nie wykrywa ich sprzeczności.
> `GATES_V6_4.md` też ma nieodświeżone fragmenty: m.in. twierdzi, że nasza paczka nie została
> wypchnięta i że termin call 4 odłożono, choć późniejsze sekcje opisują już jej scalenie i przyjęcie
> call 4.
>
> W repozytorium nie znalazłem triggera ani submittera specyficznego dla V6.4. Nie uruchamiałem
> benchmarku ani submission; sprawdzenie było read-only, a próbny build wykonywałem w `/tmp`.

## Co z tego wynikło (skrót — szczegóły w `GATES_V6_4.md`)

| punkt recenzji | moja weryfikacja | działanie |
| --- | --- | --- |
| kolejność w `rich_3006` odwrotna do mojego uzasadnienia | **potwierdzone na własnych śladach**: `write_file /tmp/repro.py` (zdarzenie 17, 161,5 s) → `edit_file rich/repr.py` (20, 180,6 s) → PASS; to samo w `fastapi_14303` (repro przed edycją, patch 745) | reguła M4 przepisana trzeci raz: skrypty w `/tmp` dozwolone w każdej chwili, zabójcze tylko zakończenie bez edycji (`fastapi_15745`, 279,8 s, puste drzewo) |
| sprzeczna instrukcja o `write_file`/shell redirection | **potwierdzone** — kolidowała z M4 i z M2 | zdanie przepisane na wersję o gołej nazwie pliku; packer dostał **strażnik sprzeczności**, który taki ogólny zakaz odrzuca |
| packer sprawdza obecność, nie spójność | **potwierdzone** — to była realna luka | strażnik sprzeczności + 6 kontrolek negatywnych sprawdzonych |
| nieświeże fragmenty `GATES_V6_4.md` | **potwierdzone** (sekcja „Skąd ta wersja" i lista scalenia) | sekcja zaktualizowana, dodana sekcja trzeciej korekty M4 z tabelą zdarzeń |
| 6,7 pp to mapowanie przyczyn, nie wynik | zgoda, tak było zapisane i tak zostaje | bez zmian |

**Druga rzecz z rzędu (po terminie call 4), w której druga gałąź miała rację, a ja nie.** Zapisuję to
wprost, bo wartość tej recenzji jest merytoryczna, nie kurtuazyjna.
