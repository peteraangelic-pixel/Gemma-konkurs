# Gemma 4 Developer Agent — v1 MVP

Katalog zawiera źródła deklaratywnego agenta i gotowy artefakt `submission.zip` dla [Google — The Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent).

## Zawartość

- `submission/` — pliki pakowane do ZIP-a; `agent.yaml` trafia do katalogu głównego archiwum.
- `submission.zip` — artefakt do przesłania w Kaggle.
- `build_submission.py` — buduje ZIP oraz sprawdza układ, rozszerzenia, `!include`, model, narzędzia, skills i per-task `eval_config`.
- `SUBMISSION_LOG.md` — hipotezy, zmiany i wyniki leaderboardu.

Agent używa wyłącznie `gemma-4-31b-it-qat-w4a16-ct`, bez treningu wag i bez LoRA. Root fixer deleguje lokalizację do read-only `repo_analyzer`, korzysta z grafu kodu, wprowadza minimalną poprawkę, uruchamia test celowany, waliduje diff i dopiero wtedy woła `submit_patch()`.

## Budżet

`submission/eval_config.yaml` ustawia limit na **4 minuty, 35 wywołań narzędzi, 60 tur i 180 sekund na pojedynczą komendę** dla jednego zadania. Przy 129 zadaniach publicznego splitu 4 minuty oznaczają 8 h 36 min maksymalnego czasu pracy agentów, pozostawiając ok. 3 h 24 min z globalnego limitu 12 h na setup sandboxów i narzut. Liczba zadań ocenianych w ukrytym splicie może być inna; tę wartość warto zmienić po pierwszym pomiarze. `get_status()` pokazuje budżet bieżącego zadania, a nie łączny postęp globalny.

## Budowanie

Z katalogu repozytorium:

```bash
python gemma4-agent/build_submission.py
```

Archiwum zapisuje się jako `gemma4-agent/submission.zip`. Packer sprawdza, że root ZIP-a zawiera `agent.yaml` bez dodatkowego katalogu opakowującego, że ścieżki `!include` pozostają w katalogu submission, że wszystkie pliki mają dozwolone rozszerzenia i że każdy agent deklaruje właściwy model. Gdy PyYAML jest dostępny, sprawdza też składnię wszystkich YAML-i; budowanie ZIP-a poza tym nie wymaga zależności.

## Kandydat V2 — zachowujemy V1 jako baseline

Źródła V2 są oddzielone w `submission-v2/`, a artefakt testowy to `submission-v2.zip`. Dotychczasowy `submission.zip` pozostaje nietkniętym V1; nic tutaj nie składa oficjalnego submission. V2 utrzymuje ten sam `gemma-4-31b-it-qat-w4a16-ct`, bez treningu i bez LoRA, oraz testuje trzy powiązane usprawnienia: krótszą, bardziej egzekwowalną politykę budżetu (kontrola co ok. 8 wywołań, zakończenie eksploracji przed ostatnią ćwiartką czasu), wyłączenie przenoszenia myśli do kontekstu i mniejszy limit generacji, a także 5-minutowy **limit per-task**.

Budowanie V2 bez nadpisywania baseline:

```bash
python gemma4-agent/build_submission.py \
  --source-dir gemma4-agent/submission-v2 \
  --output gemma4-agent/submission-v2.zip
```

Pięć minut × 129 zadań publicznych to maksymalnie 10 h 45 min pracy agenta, czyli ok. 1 h 15 min rezerwy z globalnych 12 godzin na start i narzut. Liczba zadań ukrytego splitu może się różnić, więc tego limitu nie należy dalej zwiększać bez pomiarów.

Workflow `.github/workflows/gemma-kaggle-v2-benchmark.yml` uruchamia prywatny notebook na Kaggle L4x4 i ocenia deterministyczną próbę 30 zadań, warstwowaną proporcjonalnie według repozytorium (oczekiwane 16 FastAPI, 10 Rich, 3 Requests i 1 HTTPX), z ziarnem `20261009`; próba zawiera również dotychczasowe zadanie `fastapi_15588`. Limit to 5 min/zadanie, więc maksymalny czas pracy agentów w tej próbie wynosi 2 h 30 min; monitoring Kaggle kończy się po 4 h. Notebook nie tworzy konkursowego submission ani official score i nie pobiera 22-GB datasetu do GitHuba — korzysta z wejść zamontowanych przez Kaggle. Wynik zawiera oszacowanie odsetka rozwiązanych zadań i 95% przedział Wilsona. To screening, nie wiarygodny ranking: dla odniesienia zapisany publiczny top 10 ma score 0.20–0.24, a do mocniejszego porównania potrzebny będzie pełny publiczny split.

## Kandydat V3 — wynik prywatnego screeningu (bez official submission)

V3 pozostaje odizolowany w `submission-v3/` i `submission-v3.zip`; V1/V2 nie zostały nadpisane. Ten sam model Gemma 4 31B QAT i ustawienia samplingu; V3 zmienił pacing oraz cap per-task z 5:00 na 5:15. Prywatny przebieg Kaggle [`38008647994`](https://github.com/peteraangelic-pixel/Gemma-konkurs/actions/runs/38008647994) zakończył się poprawnie: **11/30 (36,7%)**, 95% Wilson CI **[21,9%, 54,5%]**, na tych samych 30 taskach i seedzie co V2. V2 uzyskał **10/30 (33,3%)**, CI **[19,2%, 51,2%]**. V3 wygrał dwa taski (`rich_3718`, `fastapi_14873`) i przegrał jeden (`rich_2725`); wynik netto to tylko +1. Przedziały mocno się nakładają, więc to nie dowodzi trwałej poprawy. V3 to screening publicznej próbki, **nie official score i nie został zgłoszony do konkursu**. GPU quota usage pozostało niepotwierdzone.

Przy 129 taskach cap V3 wynosi teoretycznie 11h17m15s, pozostawiając 42m45s z globalnych 12 h na setup/narzut; ukryta liczba tasków może być inna. Nie zwiększać go bez pełnego sprawdzenia budżetu.

## Kandydat V4 — prompt recovery (hipoteza; bez benchmarku i official submission)

V4 jest kopią V3 w `submission-v4/`, z tym samym modelem, narzędziami, samplingiem i capem 5:15. Zmienia tylko instrukcje operacyjne: po braku embeddingu przechodzi do lokalnego odczytu źródeł zamiast powtarzać tę samą ślepą ścieżkę grafową; dodaje ostrożne mapy katalogów dla czterech repozytoriów z próby; oraz „no-edit salvage” około 90 s przed końcem — przerwanie szerokiej eksploracji i próba minimalnej poprawki tylko wtedy, gdy kod ją uzasadnia. Nie wolno zgadywać zmiany tylko po to, by uniknąć pustego patcha.

Hipotezy wynikają z logów V2 (brak embeddingów dla `rich` i `fastapi`, cztery timeouty bez patcha) oraz z małej różnicy V2/V3; nie są jeszcze dowodem na wzrost score. **V4 nie był uruchamiany na GPU ani wysłany do Kaggle.** Nie zmieniałem V3 ani oficjalnego ZIP-a. Zbudowany `submission-v4.zip` ma SHA-256 `3543c4f66521d8db95e04940140a4b360bd36a988622bff691ad9a16bd3c4c48`; packer, składnia YAML z PyYAML 6.0.3 i test CRC ZIP-a przeszły.

Budowanie V4 bez nadpisywania pozostałych wersji:

```bash
python gemma4-agent/build_submission.py \
  --source-dir gemma4-agent/submission-v4 \
  --output gemma4-agent/submission-v4.zip
```

## Odczyt statusu Kaggle przez GitHub Actions

Workflow `../.github/workflows/gemma-kaggle-poll.yml` wykonuje wyłącznie odczyt: listuje statusy naszych submissionów i pobiera publiczną tabelę leaderboardu konkursu `gemma-4-developer-agent`. Wyniki zapisuje w `gemma4-agent/kaggle_results/` (`summary.md`, `summary.json`, CSV) i commit-uje z powrotem na gałąź sesji. **Nie przesyła nowego ZIP-a ani nie zużywa dziennego limitu submissionów.**

Workflow wymaga sekretu Actions `KAGGLE_API_TOKEN` przypisanego do repozytorium `Gemma-konkurs` albo sekretu organizacji udostępnionego temu repozytorium. Aby uruchomić go na gałęzi sesji, zmień i wypchnij `gemma4-agent/kaggle_results/poll.trigger`; taki push jest wyzwalaczem. Wartość klucza nigdy nie trafia do plików wynikowych. Opcjonalna zmienna repozytorium Actions `KAGGLE_TEAM` (dokładna nazwa zespołu/użytkownika z tabeli) pozwala wskazać nasz wiersz leaderboardu.

To konkurs naprawy oprogramowania, nie turniej gier: Kaggle może udostępnić statusy, publiczny score i leaderboard, ale nie ma tu „ostatnich 7 meczów” ani replayów agentów przeciwników do pobrania. Poll dodatkowo wyszukuje publiczne notatniki konkursowe opublikowane przez członków top-10 i zapisuje ich metadane; są to dobrowolne publikacje, niekoniecznie kod użyty w ocenianym submission. Cudze prywatne ZIP-y i prompty nie są dostępne z leaderboardu. Pełne porównanie wariantów agenta wymagałoby ewaluacji tych wariantów na tym samym zestawie tasków w środowisku z Gemmą na 4×L4; standardowy runner GitHub Actions nie zapewnia takiego GPU.

## Weryfikacja względem specyfikacji

Sprawdziłem `HARNESS_README.md` oraz `sample_submission/` dostępne w GitHub `origin/main` pod commitem `813b3d072b909918a6cee72060b0cc85c1874cf8` (m.in. blob `HARNESS_README.md` `1b068740db714b8766e8f9c880fd8f03a53de161`) i porównałem je ze stroną konkursu. Zastosowane kontrakty:

- `agent.yaml` w root ZIP-a; zamknięte rozszerzenia plików `.yaml/.yml/.md/.txt/.py/.json/.safetensors`.
- `agent_tool` w formie mapowania `config_path` + `skip_summarization`; wspólny dozwolony model dla root i subagenta.
- `eval_config.yaml` pod kluczem `evaluation:`; per-task limit, bo `get_status()` nie raportuje sumy globalnej.
- `search_similar_code` dostaje nazwę symbolu (klasa/funkcja/moduł), nie zdanie w języku naturalnym — tak działa offline resolver z README.
- Phase 2 resetuje pliki testowe i konfiguracje runnera; `submit_patch()` oraz `get_status()` są bezpłatne, a `submit_patch()` należy wykonać jako ostatnie narzędzie po weryfikacji.

ZIP przeszedł lokalne sprawdzenie struktury i składni YAML, a oba skrypty skills przeszły smoke test na tymczasowym repo Git. Oficjalny `HARNESS_README.md` opisuje lokalny test przez `swegemma eval` z `tasks.jsonl`, `snapshots/`, submission directory i sandboxem (`docker` lub `subprocess`); można wskazać pojedynczy `--task-id` do szybkiego dry-run. **Nie uruchomiłem jeszcze `adk-submission.compile_submission` ani `swegemma eval`**: w dostępnej kopii repo są `tasks.jsonl` i fragmenty grafów/wheels, ale nie ma `snapshots/`, wykonywalnych pakietów `swegemma`/`adk-submission`, Docker runtime ani wag/endpointu Gemma; `docker` też nie jest dostępny w tym workspace. To brak środowiska dla end-to-end, nie ograniczenie do Twojego PC — można uruchomić taki test w notebooku Kaggle z datasetem i modelem przypiętymi do konkursu albo w lokalnym środowisku z pełnym harness/snapshot/model setup. Nie kopiowałem do submission żadnych plików z 22-GB datasetu ani adapterów z przykładowego submission.

## Jednozadaniowy dry-run w Kaggle (gdy środowisko harnessu jest dostępne)

1. Utwórz notebook przypięty do konkursu; dołącz jego dataset (w tym `tasks.jsonl` i `snapshots/`) oraz model `gemma-4-31b-it-qat-w4a16-ct`. Włącz konkursowy L4x4 i internet pozostaw wyłączony.
2. Przekaż `submission.zip` do notebooka jako input (np. prywatny Kaggle Dataset utworzony w przeglądarce), rozpakuj go do katalogu roboczego. Do ręcznego uploadu przez stronę Kaggle API key nie potrzeba.
3. Zmień ścieżki na faktyczne mount pointy notebooka i uruchom jeden publiczny task:

```bash
swegemma eval \
  --tasks /kaggle/input/<competition-data>/tasks.jsonl \
  --snapshots-dir /kaggle/input/<competition-data>/snapshots \
  --submission-dir /kaggle/working/v1 \
  --results-dir /kaggle/working/results/v1-smoke \
  --sandbox subprocess \
  --task-id <instance_id-z-tasks.jsonl> \
  --max-tool-calls 35 \
  --max-time-minutes 4 \
  --concurrency 1
```

Katalog `/kaggle/working/v1` musi zawierać `agent.yaml` bezpośrednio w root. Sprawdź wynik w `results/v1-smoke/summary.json`, patchu i logu taska. Jeśli w notebooku nie ma polecenia `swegemma`/pakietów harnessu, nie instaluj ich z internetu — potrzebne są oficjalne runtime packages z pełnego środowiska konkursowego.
