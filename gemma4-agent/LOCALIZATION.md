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
| `tools/locator.py` | **wersja dla agenta** (tylko stdlib, bez sieci): agent zapisuje go do `/tmp`, uruchamia raz z treścią issue i dostaje ranking plików z liniami dowodowymi |
| `analysis/locate-benchmark/locate_result.json` | pełne wyniki per zadanie (wszystkie receptury) |
| `analysis/locate-experiment/experiment_result.json` | porównanie 6 wariantów scoringu na 129 zadaniach |

Reprodukcja (klonuje 4 repozytoria do `~/.cache/gemma-repos`, ~5 s):

```bash
python3 gemma4-agent/tools/locate_benchmark.py     # ~110 s
python3 gemma4-agent/tools/locate_experiment.py    # ~65 s
```

## Wyniki: trafienie w *naprawialny* plik źródłowy ze złotego patcha

Cel metryki: plik `.py` ze złotego patcha, ale nie z `docs/`, `tests/`, `scripts/` — czyli plik,
którego edycja faktycznie może zmienić wynik testów (125/129 zadań ma taki plik).

| receptura | top-1 | top-5 | top-10 |
| --- | --- | --- | --- |
| R0 „pierwszy grep" (baseline peera) | 10.1 % | 15.5 % | 17.8 % |
| R1 głosowanie kotwic | 14.8 % | 35.2 % | 41.4 % |
| R2 kotwice + BM25 | 10.2 % | 26.6 % | 33.6 % |
| R3 z guardem precyzji | 10.2 % | 29.7 % | 34.4 % |
| **R4 subtokeny (BM25 + ścieżki + definicje + akronimy)** | 21.9 % | 53.9 % | 61.7 % |
| **V_exact_src_def** (R4 + dokładny literał + kara na testy + waga definicji) | **39.1 %** | **67.2 %** | **75.8 %** |

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

## Uczciwe ramy

- Oficjalny wynik ukryty (0.03) i widoczny (11/30) **nie są tym samym rozkładem**: 4 publiczne
  repozytoria vs prywatne repozytoria testowe. Dlatego mierzę procedurę, którą da się przenieść,
  a nie „wskazówki pod fastapi/rich/requests/httpx".
- 67 % top-5 lokalizacji to nie 67 % rozwiązanych zadań: do tego dochodzi trafność edycji, budżet
  czasu i weryfikacja. To usunięcie **jednej z głównych przyczyn zera**, nie gwarancja 0.20+.
- Ten sam pomiar na 4 repo publicznych to wciąż 4 repo: przed obiecaniem wyniku trzeba powtórzyć
  procedurę na repozytoriach spoza zbioru (held-out), docelowo przez prywatny benchmark V6 na Kaggle.
