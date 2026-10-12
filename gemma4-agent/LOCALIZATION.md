# Lokalizacja pliku to wąskie gardło — pomiary offline na 129 zadaniach

Ten plik jest **dowodem pomiarowym**, nie obietnicą wyniku. Powstał, bo:

- oficjalny wynik na ukrytym zbiorze to jedna liczba (0.03) i **nie ma per-zadaniowych logów** —
  sprawdziłem dokumentację API (`competitions submission` zwraca status/score, a przyczynę tylko przy
  statusie `ERROR`), więc poprawki musimy mierzyć sami na widocznym zbiorze (129 zadań),
- diagnose z `DIAGNOSIS.md` §4.7 mówi, że prawdziwym wąskim gardłem jest **znalezienie pliku do
  edycji**, a nie samo pisanie patcha (peer: pierwszy `grep` trafia w 30 %, `grep`+BM25 w 61 % top-5,
  35/128 issue nie ma żadnego identyfikatora kodu),
- ukryty zbiór to **prywatne repozytoria**, więc wskazówki „pod to repo" z V2–V4 nie przenoszą się;
  procedura wyszukiwania musi być **repo-agnostyczna i deterministyczna**.

## Co zbudowałem (bez GPU, bez slotu Kaggle)

| narzędzie | rola |
| --- | --- |
| `tools/locate_benchmark.py` | benchmark offline: dla każdego z 129 zadań wyciąga kotwice z treści issue, rankuje pliki repo i liczy trafienia top-1/5/10 w plik ze złotego patcha |
| `tools/locate_experiment.py` | pętla eksperymentów: jeden odczyt repo na zadanie, wiele wariantów scoringu w jednym przebiegu (~1 min na pełny zestaw) |
| `submission-v6/tools/locate.py` | **wersja dla agenta** (tylko stdlib, bez sieci): jedzie w submissji i jest osadzona w prompcie; agent wpisuje ją heredocem do `/tmp` i uruchamia raz, dostając ranking plików z liniami dowodowymi (`tools/locator.py` to prototyp używany w pomiarach) |
| `analysis/locate-benchmark/locate_result.json` | pełne wyniki per zadanie (wszystkie receptury) |
| `analysis/locate-experiment/experiment_result.json` | porównanie 6 wariantów scoringu na 129 zadaniach |

Reprodukcja (klonuje 4 repozytoria do `~/.cache/gemma-repos`, ~5 s):

```bash
python3 gemma4-agent/tools/locate_benchmark.py     # ~110 s
python3 gemma4-agent/tools/locate_experiment.py    # ~65 s
```

## Wyniki: trafienie w *naprawialny* plik źródłowy ze złotego patcha

Cel metryki: plik `.py` ze złotego patcha, ale nie z `docs/`, `tests/`, `scripts/` — czyli plik,
którego edycja faktycznie może zmienić wynik testów. Taki plik ma **128 z 129** zadań
(jedyne bez: `fastapi_15661`, którego złoty patch rusza tylko `scripts/prepare_release.py`),
więc mianownikiem we wszystkich tabelach jest **128**, nie 129.

| receptura | top-1 | top-5 | top-10 |
| --- | --- | --- | --- |
| R0 „pierwszy grep" (baseline peera) | 10.1 % | 15.5 % | 17.8 % |
| R1 głosowanie kotwic | 14.8 % | 35.2 % | 41.4 % |
| R2 kotwice + BM25 | 10.2 % | 26.6 % | 33.6 % |
| R3 z guardem precyzji | 10.2 % | 29.7 % | 34.4 % |
| **R4 subtokeny (BM25 + ścieżki + definicje + akronimy)** | 21.9 % | 53.9 % | 61.7 % |
| **V_exact_src_def** (R4 + dokładny literał + kara na testy + waga definicji) | **39.1 %** | **67.2 %** | **75.8 %** |

## Atestacja: skrypt, który faktycznie jedzie w submissji

Receptura V_union (ranking treści przeplatany z importami najlepszego pliku testowego) jest tym,
co znajduje się w `submission-v6/tools/locate.py` — czyli w pliku dołączonym do ZIP-a. `tools/locate_verify.py`
ładuje **dokładnie ten plik** i mierzy go na obu zbiorach, a wynik zapisuje z SHA-256 mierzonego pliku,
żeby dowód był samoopisujący (poprzednia recenzja słusznie wytknęła deklarację z innego artefaktu):

| zbiór | zadania | top-1 | top-2 | top-3 | top-5 | top-10 |
| --- | --- | --- | --- | --- | --- | --- |
| zbiór deweloperski (publiczny) | 128 | 47.7 % | 51.6 % | 66.4 % | 73.4 % | 79.7 % |
| held-out (starlette, click, typer, pydantic) | 188 | 44.7 % | 61.2 % | 65.4 % | 71.8 % | 80.9 % |

Artefakt: `submission-v6/tools/locate.py`, SHA-256 `fe25b200fa52e10023538c4474bb3ea86bf6303182fcd765faf37e219d420a3d`
(pomiar powtórzony po zmianach V6.2 — lokalizator czyta teraz issue ze stdin; logika rankingu bez zmian,
liczby identyczne). Dowody: `analysis/locate-verify/v6-locator-dev.json` i `v6-locator-holdout.json`.

Wniosek praktyczny dla promptu: **top-2 to jeszcze za mało** (51.6 % / 61.2 %), więc agent ma czytać
**pierwszych 1–3 kandydatów** (top-3: 66.4 % / 65.4 %) — i to jest liczba wpisana w prompt.

Uwaga o wcześniejszym przebiegu: tabela held-out „108 zadań / 71.3 % top-5" (`analysis/locate-holdout/`)
mierzyła prototyp `tools/locator.py` na dwóch repozytoriach; zastępuje ją powyższa atestacja na
188 zadaniach i pliku z submissji.

Czyli sam `grep` trafia w naprawialny plik w ~15 % przypadków (top-5), a zmierzona procedura w ~67 %.
To jest **4.3× więcej okazji na poprawny patch** przy zerowym koszcie GPU — 0.38 s na repozytorium
1082 plików, więc w sandboxie to jedno wywołanie `run_command` na początku zadania.

### Dlaczego to działa (i czego nie naprawia)

Co wnosi każda zmiana (zmierzone, nie zgadywane):

1. **subtokeny** — `strict_content_type` → `strict`,`content`,`type`: tytuły PR w stylu
   `Add \`foo_bar\` support` nie zawierają dosłownych nazw, które da się zgrepować (+18 pkt top-5),
2. **dokładny literał + kara na pliki testów** — model nie może edytować testów, a to one dominowały
   ranking (np. `tests/test_security_oauth2_optional.py` wygrywał przez `OAuth2PasswordRequestFormStrict`),
3. **waga miejsc definicji** (`def`/`class`) — agent edytuje definicje, nie użycia,
4. **ścieżka pliku jako sygnał** — „Server Sent Events" ↔ moduł `sse.py`.

Czego **nie** naprawia: zadań typu *feature-add*, gdzie docelowy moduł **jeszcze nie istnieje**
(np. `fastapi/sse.py` przy issue „Add support for Server Sent Events"), oraz tytułów bez żadnego
identyfikatora (7/129 ma zero kotwic, 38/129 to sam tytuł ≤200 znaków — `hints_text` jest puste we
wszystkich 129 zadaniach). Dlatego kolejny krok to reguła „idź za importami pliku testowego", która
dla takich zadań wskazuje moduł-sąsiada (np. `test_router_events.py` → `fastapi/routing.py`).

## Test przenoszenia (held-out) — czy to nie jest overfit do 4 repozytoriów?

Ukryty zbiór to prywatne repozytoria, więc procedura nie może być „pod fastapi/rich". Dlatego
zbudowałem proxy-zadania z **repozytoriów spoza zbioru deweloperskiego**: każde zadanie to prawdziwy
zmergowany pull request, tekst issue to **sam tytuł PR** (taki sam kształt jak w zbiorze publicznym),
a celem jest plik źródłowy `.py`, który ten PR zmienił (`tools/locate_holdout.py`, mierzy dokładnie
ten kod, który jedzie w `locator.py`).

| repozytorium (spoza zbioru) | zadania | top-1 | top-5 | top-10 |
| --- | --- | --- | --- | --- |
| encode/starlette | 40 | 37.5 % | 62.5 % | 70.0 % |
| pallets/click | 40 | 57.5 % | 87.5 % | 95.0 % |
| tiangolo/typer | 14 | 28.6 % | 71.4 % | 78.6 % |
| pydantic/pydantic | 14 | 28.6 % | 50.0 % | 64.3 % |
| **razem** | **108** | **42.6 %** | **71.3 %** | **79.6 %** |

(Uwaga: ten przebieg 108 zadań mierzył prototyp `tools/locator.py`; poniżej jest pomiar dokładnego
artefaktu V6 na 188 zadaniach — to on obowiązuje.)

Na repozytoriach, których procedura nigdy nie widziała, wynik jest **równy lub lepszy** od wyniku
w zbiorze deweloperskim (68.8 % top-5), z uczciwym rozrzutem: `pydantic` (duży, wielomodułowy) daje
50 %, `click` 87.5 % — czyli ranking nie jest dopasowany do czterech repo z V1–V4.
To jest dokładnie ten test, którego brakowało przy 0.03: „czy to, co poprawiamy, przenosi się na
repozytoria, których nie znamy". Nadal nie jest to gwarancja wyniku: pozostaje jakość edycji,
budżet 5.25 min i weryfikacja.

## Uczciwe ramy

- Oficjalny wynik ukryty (0.03) i widoczny (11/30) **nie są tym samym rozkładem**: 4 publiczne
  repozytoria vs prywatne repozytoria testowe. Dlatego mierzę procedurę, którą da się przenieść,
  a nie „wskazówki pod fastapi/rich/requests/httpx".
- 67 % top-5 lokalizacji to nie 67 % rozwiązanych zadań: do tego dochodzi trafność edycji, budżet
  czasu i weryfikacja. To usunięcie **jednej z głównych przyczyn zera**, nie gwarancja 0.20+.
- Ten sam pomiar na 4 repo publicznych to wciąż 4 repo: przed obiecaniem wyniku trzeba powtórzyć
  procedurę na repozytoriach spoza zbioru (held-out), docelowo przez prywatny benchmark V6 na Kaggle.
