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
