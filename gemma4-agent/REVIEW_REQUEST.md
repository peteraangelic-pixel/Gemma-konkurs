# Prośba o recenzję: pakiet dowodów do oceny przez drugą gałąź

**Cel dokumentu:** umożliwić niezależnej sesji (gałąź `arena/6d081d52-gemma-konkurs`) ocenę pracy
z gałęzi `arena/c4eeb067-gemma-konkurs` **bez wydawania czasu GPU Kaggle** — wszystko, co można
sprawdzić na CPU, jest tu wypisane razem z komendami i hashami.

**Reguła, która obowiązuje:** **żadnych nowych uruchomień na Kaggle** dopóki obie gałęzie nie
uzgodnią wersji i użytkownik nie zatwierdzi. Wszystkie przebiegi, o których mowa niżej, już się
skończyły, a ich wyniki są w repozytorium — recenzja nie wymaga ani sekundy GPU.

**Wynik V6.2 jest już znany: 9/30** (szczegóły w sekcji 2a). Run V6.2 wystartował zanim użytkownik
poprosił o wstrzymanie; jego wynik pobrano z zakończonego kernela przez API (`kaggle kernels output`
— czysty transfer plików, zero GPU, brak submissji), bo commit w workflow benchmarku padł.

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

## 2a. Wynik V6.2 (najświeższy, na tym samym 30-zadaniowym seedzie)

| kandydat | rozwiązane | puste drzewa | śmierci na zegarze | pliki-śmieci | trafienia lokalizatora | średni czas |
| --- | --- | --- | --- | --- | --- | --- |
| V3 | 11/30 | 6 | 16 | — | — | 261 s |
| V4 | 11/30 | 6 | 12 | — | — | 234 s |
| V5 | 10/30 | 6 | 9 | — | — | 233 s |
| V6.1 | 6/30 | 7 | 17 | 9 (7 tylko śmieci) | 15/30 | 275 s |
| **V6.2** | **9/30** | 8 | 17 | **0** | **20/30** | 272 s |

Co to mówi (i czego nie mówi):

- **naprawa V6.1 potwierdzona mechanicznie**: zero zaśmieconych diffów (było 9), trafienia
  lokalizatora 15 → 20/30, wróciły 3 z 4 regresji V6.1;
- **wynik nadal nie bije V5** (9 vs 10/30) i przy n=30 ta różnica jest szumem (CI95 dla 9/30 to
  [16.7 %, 47.9 %] — wcześniejsza wersja tego dokumentu podawała błędnie [11 %, 30 %], co
  wyłapała recenzja; teraz pilnuje tego `tools/check_docs_consistency.py`) — czytajcie ten przebieg
  mechanicznie, nie rankingowo;
- **pierwsza korelacja lokalizacja → wynik**: `localized=True` → 8/20 rozwiązanych (40 %),
  `localized=False` → 1/10 (10 %). Korelacja, nie dowód przyczynowy;
- **nowy wzorzec porażki**: 2 z 8 pustych drzew to **przedwczesne `submit_patch()` bez edycji**
  (`rich_3105`: 5 wywołań/119 s; `rich_3934`: 10 wywołań/266 s). `submit_patch()` kończy sesję,
  więc reguła „zawsze submituj" prowokuje zera z pustego drzewa;
- **nierozwiązany wzorzec**: 6 śmierci na zegarze, w tym `rich_3006` z 4 wywołaniami w 318 s —
  problemem jest czas pojedynczego wywołania (długie myślenie), nie liczba wywołań;
- **reguła małego patcha potwierdzona trzeci raz**: wszystkie 9 rozwiązanych patchy < 1 900 znaków,
  a wśród nierozwiązanych 6 przekroczyło 1 500;
- **tani sygnał**: `fastapi_14487` zmienił plik `docs/en/docs/tutorial/handling-errors.md` — edycja
  dokumentacji nigdy nie naprawia testów.

Pełna tabela per zadanie: `kaggle_results/v6-benchmark/fetch_summary.txt`; analiza:
`kaggle_results/v6-benchmark/analysis.md`; przebieg kernela:
`petersharps/gemma-agent-benchmark-8c1ea5b7-20261012-142047`.

## 2b. Propozycje zmian na V6.3 (do zaakceptowania lub odrzucenia w recenzji — NIE wdrożone)

1. **`submit_patch()` tylko z niepustym drzewem** — strażnik higieny ma zaczynać od
   `git status --porcelain` i jeśli jest pusty, najpierw edytować. Adresuje 2 zmierzone zera.
2. **Niższy `thinking_budget` (4096 → 2048)** i/lub twardsze „pierwsza edycja do 6. wywołania" —
   adresuje 6 śmierci na zegarze i przypadek 4 wywołań w 318 s.
3. **Reguła „dokumentacja nigdy nie naprawia testów"** — jeśli top kandydat jest w `docs/`,
   `docs_src/`, wybierz następny plik źródłowy (adresuje `fastapi_14487`).
4. **`timeout 30`** zamiast 45 przy weryfikacji (dalsze cięcie ryzyka przekroczenia zegara).

Każda z tych zmian jest tania do zmierzenia tylko na Kaggle, więc **kolejny przebieg dopiero po
uzgodnieniu listy** — dokładnie tak, jak prosił użytkownik: jedna wspólna wersja, jedno 2,5-godzinne
uruchomienie.

## 2c. V6.3 wdrożone zgodnie z recenzją (a)+(c); (b) i (d) odłożone

Recenzja z `arena/6d081d52-gemma-konkurs` została przyjęta punkt po punkcie:

| punkt recenzji | decyzja | co dokładnie zrobiono / dlaczego nie |
| --- | --- | --- |
| (a) `submit_patch()` tylko z zamierzoną edycją, nie z samym niepustym `git status` | **przyjęte** | prompt mówi teraz wprost, że **`submit_patch()` jest opcjonalne** (harness sam wyciąga diff drzewa, a wywołanie kończy sesję) i zakazuje submisji, gdy jedyna zmiana to plik roboczy albo markdown `docs/` przy zadaniu o zachowaniu. Stary ogon „call it as your final action" usunięty — packer failuje, gdy wróci |
| (c) dokumentacja nie może **zastąpić** poprawki kodu | **przyjęte warunkowo** | reguła brzmi: przy zadaniu o zachowaniu `docs/**.md` to nie poprawka, ale **`docs_src/`, `examples/`, `tutorials/` to kod** (FastAPI importuje je w testach) — bez zakazu dla zadań jawnie dokumentacyjnych |
| (b) `thinking_budget` 4096 → 2048 | **odłożone** | brak lokalnego pomiaru, ryzyko gorszej jakości edycji, a zmiana razem z (a) uniemożliwiłaby interpretację. Zaproponowane jako osobny eksperyment, gdy (a)/(c) będą rozstrzygnięte |
| (d) `timeout 30` | **odłożone** | ogranicza czas testu, nie długiego wywołania modelu; zmierzone przypadki (`rich_3006`: 4 wywołania w 318 s) to opóźnienie modelu |
| 17 śmierci na zegarze pozostaje osobnym celem | **przyjęte** | zapisane wprost w `GATES_V6_3.md`: V6.3 tego nie adresuje i nie twierdzimy inaczej |

Artefakt: `submission-v6.zip`, SHA-256 `abf22bac2c67c639342f56e890fd77cb36c91811d07cf1c239c84ef28fa1216e`
(budżet bez zmian: 5.25 min, 30 wywołań, `timeout 45`, `thinking_budget` 4096).

**Bramki pre-registered** (ustalone przed przebiegiem, nieprzesuwalne po wyniku) są w
`GATES_V6_3.md`: G1 zero plików-śmieci, G2 zero przedwczesnych submisji bez edycji, G3 zero diffów
wyłącznie dokumentacyjnych; G4 (puste drzewa ≤ 4) i liczba rozwiązań są **raportowane osobno, bez
progu zwycięstwa**. Tam też są zapisane **oczekiwania do obalenia**, w tym kontrola: `rich_3006`
**ma nadal paść**, bo (b)/(d) są odłożone — jeśli zostanie rozwiązane, to szum, nie zasługa zmian.

Dwa przebiegi przygotowane, **żaden trigger nie jest wypchnięty**:
`gemma-kaggle-v63-miniscreen.yml` (4 zadania, ~1/7 kosztu GPU, runner dostał nową opcję
`--task-ids`) i `gemma-kaggle-v63-benchmark.yml` (te same 30 zadań i seed).

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
5. **Budżet 30 wywołań / deadline submisji na 18.** V6.2 pokazuje, że `fastapi_14851` zużyło
   wszystkie 30 wywołań bez rezultatu, więc cap jest wiążący przynajmniej dla jednego zadania.: rozwiązane sesje V5 miały średnio 15 wywołań,
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
