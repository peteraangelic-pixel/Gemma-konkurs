# Prośba o recenzję: pakiet dowodów do oceny przez drugą gałąź

**Cel dokumentu:** umożliwić niezależnej sesji (gałąź `arena/6d081d52-gemma-konkurs`) ocenę pracy
z gałęzi `arena/c4eeb067-gemma-konkurs` **bez wydawania czasu GPU Kaggle** — wszystko, co można
sprawdzić na CPU, jest tu wypisane razem z komendami i hashami.

**Reguła, która obowiązuje do końca recenzji:** żadnych nowych uruchomień na Kaggle. Wyjątek:
run V6.2 ([`38262206820`](https://github.com/peteraangelic-pixel/Gemma-konkurs/actions/runs/38262206820))
został wystartowany 2026-10-12 14:20 UTC, **zanim** użytkownik poprosił o wstrzymanie; kernel już
wykonywał się na maszynach Kaggle i `kaggle` CLI nie udostępnia anulowania, więc pobranie jego
wyniku nie kosztuje dodatkowego compute. Ten wynik jest **wyłącznie diagnostyczny** i sam z siebie
nie jest podstawą do żadnej submissji.

---

## 1. Co jest przedmiotem oceny

| element | ścieżka | SHA-256 |
| --- | --- | --- |
| kandydat V6.2 (ZIP) | `gemma4-agent/submission-v6.zip` | `8c1ea5b71a61b4d58a6b023596761abb9af37908af6d0ef441347353a2f860b8` |
| definicja agenta | `gemma4-agent/submission-v6/agent.yaml` | — |
| prompt | `gemma4-agent/submission-v6/prompts/system.md` (16.3 KB, zawiera cały lokalizator) | — |
| lokalizator (skrypt w ZIP-ie) | `gemma4-agent/submission-v6/tools/locate.py` | `fe25b200fa52e10023538c4474bb3ea86bf6303182fcd765faf37e219d420a3d` |
| budżet | `gemma4-agent/submission-v6/eval_config.yaml` (150 s / 30 wywołań / 60 tur / 5.25 min) | — |
| sampling | `gemma4-agent/submission-v6/configs/sampling.yaml` (T 0.4, thinking 4096, thoughts ON) | — |
| packer + guardy | `gemma4-agent/build_submission_v6.py` | — |
| generator promptu | `gemma4-agent/tools/make_v6_prompt.py` | — |

Gałąź ma też kandydatów V5 (`submission-v5.zip`, `282b1446…`) i V1–V4 (nietknięte).

## 2. Twierdzenia i ich proweniencja — to jest sedno recenzji

| # | twierdzenie | wartość | proweniencja | jak to obalić |
| --- | --- | --- | --- | --- |
| 1 | lokalizator trafia w naprawialny plik ze złotego patcha (zbiór dev, 128 zadań) | top-1 47.7 %, top-2 51.6 %, top-3 66.4 %, top-5 73.4 %, top-10 79.7 % | **zmierzone**, `analysis/locate-verify/v6-locator-dev.json`, artefakt `fe25b200…` | `python3 gemma4-agent/tools/locate_verify.py --locator gemma4-agent/submission-v6/tools/locate.py --mode dev` |
| 2 | to samo poza zbiorem dev (188 zadań: starlette, click, typer, pydantic) | top-1 44.7 %, top-2 61.2 %, top-3 65.4 %, **top-5 71.8 %**, top-10 80.9 % | **zmierzone**, `analysis/locate-verify/v6-locator-holdout.json` | jak wyżej z `--mode holdout --repo ... --tasks-per-repo 40` |
| 3 | zwykły pierwszy `grep` trafia w 15.5 % (top-5) | 15.5 % | **zmierzone**, `analysis/locate-benchmark/locate_result.json` (receptura `R0_first_grep`) | `python3 gemma4-agent/tools/locate_benchmark.py` |
| 4 | kara na pliki testów + dokładny literał + waga definicji podnoszą ranking | 39.1 % top-1 / 67.2 % top-5 → 68.8 % / 79.7 % po dodaniu importów | **zmierzone**, `analysis/locate-experiment/experiment_result.json` | `python3 gemma4-agent/tools/locate_experiment.py` |
| 5 | V5 na tym samym 30-zadaniowym seedzie | 10/30, CI95 [19.2 %, 51.2 %], 6 pustych patchów, 5 z nich zginęło na zegarze | **zmierzone**, `kaggle_results/v5-benchmark/` | artefakty w repo |
| 6 | V6.1 na tym samym seedzie | 6/30, 9/30 diffów zanieczyszczonych, 7 bez edycji kodu, 61 008 znaków śmieci | **zmierzone**, `kaggle_results/v6-1-benchmark/` | artefakty w repo |
| 7 | rozwiązane patche V5 były < 1 900 znaków, a > 2 000 znaków → 0/6 | 823 znaki średnio vs 2 127 | **zmierzone**, `kaggle_results/v5-benchmark/analysis.md` | przeliczyć z `agent_benchmark_result.json` |
| 8 | oceniany jest diff drzewa roboczego, nie tylko `submit_patch()` | harness: `git add -N . && git diff --binary HEAD` | **z dokumentacji harnessu** (`git show c0256ba:HARNESS_README.md`, l. 231–235, 346–361, 569–575) | ponownie przeczytać te linie |
| 9 | `include_thoughts: true` wart ~12 pkt, temp 0.4 ≈ 1.0 > 0.2, 50 wywołań > 25 | — | **odziedziczone od peera** (dyskusja 746250), u nas **niepowtórzone** | brak lokalnej replikacji — traktować jako hipotezę |
| 10 | publiczny screening 30 zadań NIE przewiduje wyniku ukrytego | V3/V4/V5 10–11/30 przy oficjalnym 0.03 | **zmierzone** (0.03 = ref 57045226) | — |

Poprzednia recenzja słusznie wyłapała, że deklarowałem wynik held-out z innego artefaktu niż
wysyłany; dlatego **oba pomiary wyżej zostały ponownie wykonane na obecnym pliku `fe25b200…`**
i pliki dowodowe zapisują hash mierzonego pliku.

## 3. Znane tryby porażki (i co zostało naprawione)

1. **V5: puste drzewo** — 6/30 zadań bez żadnej edycji; reguła „zawsze `submit_patch()`" nie mogła
   tego naprawić, bo `submit_patch()` **kończy sesję**, a harness i tak wyciąga diff drzewa.
   Naprawa (V6.2): twarde deadline'y — edycja na dysku do 8. wywołania, koniec szukania na 14.,
   submisja na 18.
2. **V6.1: zaśmiecony diff** — agent zapisywał gołe nazwy (`issue.txt`, `locate.py`, `repro.py`),
   które lądują w `/workspace`. 9/30 diffów to śmieci, 7 bez edycji kodu, a śmieci **unieważniły**
   ochronę przed pustym diffem. Naprawa (V6.2): **zero `write_file`** — skrypt i issue jadą jednym
   `run_command` z heredocami do `/tmp`, lokalizator czyta issue ze **stdin**, plus obowiązkowy
   strażnik `git status --porcelain` + `rm -f` przed `submit_patch()`.
3. **Korekta własnej hipotezy**: śmierć na zegarze **nie** jest sama w sobie fatalna (V3: 16/30
   takich sesji i 11/30 rozwiązanych, bo liczy się diff drzewa). Fatalna jest śmierć **bez użytecznej
   edycji**. Dlatego reguła V6.2 nie brzmi „mniej czytać", ale „edycja na dysku najpóźniej w 8.
   wywołaniu".

## 4. Checklist weryfikacyjny (CPU, ~10 minut, bez Kaggle)

```bash
git fetch origin arena/c4eeb067-gemma-konkurs
git checkout arena/c4eeb067-gemma-konkurs

# 1. Packer: kompletność plików, YAML, budżet, thinking ON, osadzenie lokalizatora, strażnik higieny
python3 gemma4-agent/build_submission_v6.py

# 2. Atestacja lokalizatora na WYSYŁANYM pliku (dev ~45 s, held-out ~20 s)
python3 gemma4-agent/tools/locate_verify.py --locator gemma4-agent/submission-v6/tools/locate.py --mode dev
python3 gemma4-agent/tools/locate_verify.py --locator gemma4-agent/submission-v6/tools/locate.py \
    --mode holdout --repo encode/starlette --repo pallets/click --repo tiangolo/typer \
    --repo pydantic/pydantic --tasks-per-repo 40

# 3. Czy blok heredocowy WYCIĄGNIĘTY Z PROMPTU faktycznie działa?
python3 - <<'PY'
import re, subprocess, sys, pathlib
prompt = pathlib.Path('gemma4-agent/submission-v6/prompts/system.md').read_text()
script = re.search(r"```python\n(.*?)\n```", prompt, re.S).group(1)
pathlib.Path('/tmp/from_prompt.py').write_text(script + "\n")
pathlib.Path('/tmp/smoke/pkg').mkdir(parents=True, exist_ok=True)
pathlib.Path('/tmp/smoke/pkg/routing.py').write_text("def check_content_type(x):\n    return x\n")
r = subprocess.run([sys.executable, '/tmp/from_prompt.py', '--root', '/tmp/smoke', '--top', '3'],
                   input="Add `strict_content_type` checking\n", text=True, capture_output=True)
print(r.returncode, r.stdout[:300])
PY

# 4. Macierz receptur lokalizacji (opcjonalnie, ~2 min)
python3 gemma4-agent/tools/locate_benchmark.py && python3 gemma4-agent/tools/locate_experiment.py
```

Punkty 1–3 powinny przejść bez błędów; punkt 2 musi dać liczby z tabeli wyżej.

## 5. Otwarte pytania — o atak recenzenta (w kolejności ważności)

1. **Reguła decyzyjna o submissji.** Proponuję, żeby kandydat zasługiwał na slot dopiero gdy na
   wspólnym 30-zadaniowym seedzie: (a) `touched_files` **nie zawiera** żadnego pliku spoza źródeł,
   (b) `tasks_with_empty_patch` ≤ 3, (c) `resolved ≥ 14/30`. To arbitralne progi — proszę o atak:
   czy (c) nie jest zbyt wysoki/zbyt niski przy CI ±17 pkt? Czy zamiast progu na wyniku nie lepiej
   patrzeć na licznik popraw/regresji względem V5 (test McNemara na parach zadań)?
2. **Czy w ogóle iść z V6, czy wysłać „najbezpieczniejszy" wariant?** V5 = 10/30 z 6 pustymi
   drzewami; jeśli V6.2 usunie puste i zaśmiecone diffy, ta sama mechanika powinna pobić V5 **na
   ukrytym zbiorze** nawet przy równym wyniku na publicznym. Czy to rozumowanie jest poprawne?
3. **Czy lokalizator jest wart swoich 3 wywołań?** Recall zmierzony (73 % dev / 72 % held-out), ale
   **wkład end-to-end nie jest zmierzony** — V6.1 tego nie rozstrzyga (zaśmiecone diffy), a na A/B
   bez GPU nas nie stać. Czy recenzent widzi tańszy sposób rozstrzygnięcia (np. licznik
   `localization_hits` w V6.2 jako proxy, porównanie z 15/30 z V6.1)?
4. **Prompt 16.3 KB z osadzonym skryptem**: czy to nie jest ryzyko „rozmycia instrukcji"? Alternatywa:
   skrócić skrypt (top-8 → top-6, bez linii dowodowych) i/lub skrócić listę reguł. Co byś wyciął?
5. **Budżet 30 wywołań / deadline submisji na 18.**: rozwiązane sesje V5 miały średnio 15 wywołań,
   ale V5 miało też zadanie z 32 wywołaniami i 5 000-znakowym patchem (nieudane). Czy obniżony cap
   nie ucina długiego ogona zadań, które wymagają więcej pracy?
6. **Odziedziczone ustawienia bez lokalnej replikacji** (punkt 9 tabeli): które z nich jest
   najryzykowniejsze i warte najpierw taniej weryfikacji?
7. **Zgodność ZIP-a z harnessem**: czy `tools/locate.py` w archiwum (plik nie-YAML) i `!include`
   w `agent.yaml` na pewno nie zostaną odrzucone? (Wcześniejsza recenzja to sprawdziła — proszę o
   potwierdzenie po zmianach V6.2.)

## 6. Czego NIE proszę o ocenę

- Kandydatów V1–V4 i ich workflowów (nietknięte; V4 ma zamknięty wynik 0.03).
- Oficjalnej submissji — **jej nie będzie** bez nowej, wyraźnej zgody użytkownika.
- Jakości benchmarku publicznego jako predyktora (to już wiemy: nie przewiduje; patrz twierdzenie 10).
