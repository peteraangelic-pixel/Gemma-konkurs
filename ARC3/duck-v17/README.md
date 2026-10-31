# duck-v17: champion v3 + kontroler `template` + guard

Jeden artefakt, nie lista pomysłów. Baza jest **zmierzonym championem v3** (26,25), do którego
dokładamy przetestowany kontroler `template` i warstwę bezpieczeństwa z audytu peerów.

## Skład

| plik | rola |
|---|---|
| `arc3-duck-v17.ipynb` | **to jedzie na Kaggle** (634 419 B, sha256 `76b57100…b519795`), 30 komórek, zmieniona 1 (kom. 8 = patch) |
| `src/base-v3-template.ipynb` | notebook autora (`codex/arc-local-lab-v18-20261030`), sha256 `550eb185…d5fa` = champion v3 + kontroler; **nie ruszamy** |
| `src/vendor/codex_template_guarded.py` | warstwa guard (limit 32 propozycji/poziom + `ARC3_TEMPLATE`), źródło dla patcha |
| `tools/build_v17.py` | deterministyczny build: 3 podmiany, przeliczenie licznika hunka, wstawienie 4. pliku |
| `tools/extract_module.py` | wyciąga moduły **z gotowego notebooka** (gramy tym, co leci, nie kopią) |
| `tests/test_v17_package.py` | 11 testów na efekt: bajty, arytmetyka hunków, `git apply`, cap, kill-switch, slug |
| `kernel-metadata.json` | własny slug `petersharps/arc3-duck-v17-champion-template` |

## Skąd wziąć pomiar

`MEASUREMENT.md` — drabina M0–M3 (co jest darmowe, co wymaga harnessu z LLM-em, co slotu)
+ reguła decyzyjna ustalona **przed** pomiarem. Przyrząd odtwarza się jedną komendą z publicznych
źródeł (także po restarcie sandboxa — `/tmp` nie persystuje):

```bash
bash tools/bootstrap_engine.sh      # silnik + 25 gier + smoke ft09 (25 akcji / 3 poziomy)
```

## Build i testy

```bash
python3 tools/build_v17.py                       # -> arc3-duck-v17.ipynb
python3 -m pytest -q tests/test_v17_package.py    # 11 passed
python3 tools/extract_module.py arc3-duck-v17.ipynb /tmp/v17
```

## Zachowanie

- `ARC3_TEMPLATE=1` (domyślnie): kontroler rozwiązuje plansze o strukturze kopiowania; limit 32
  propozycji na poziom przerywa oscylację (kontrprzykład: 60 akcji / 0 sprzeczności).
- `ARC3_TEMPLATE=0`: hook nie jest instalowany, `analyze` = oryginał championa v3.
- Po trafieniu limitu kontroler zwraca `None` → hook robi fallback do LLM (gra nie umiera).

## Zmierzone

| co | wynik |
|---|---|
| ft09 modułem wyjętym z notebooka | 25 akcji / 3 poziomy |
| gry z poziomem | 1/25 (tylko ft09) |
| `cap_hits` na 25 grach publicznych | **0** (bezpiecznik, nie dźwignia) |
| patch | nakłada się na czyste drzewo, 4 hunki, liczniki zgodne z ciałem |

## Czego to NIE robi

Nie jest kandydatem do TOP5: 26,25 + 0,26…2,6 = 26,5…28,9 przy progu #5 = 51,51. Szczegóły
i arytmetyka: `REVIEWS/2026-10-31-odpowiedz-na-audyt.md`. Nic tu nie idzie na Kaggle bez GO.
