# 2026-10-14: dlaczego oba przebiegi V6.5 i V6.6 „umarły", i co z tego wynika

**Wniosek w jednym zdaniu: tygodniowy limit GPU na koncie (30 h) był wyczerpany, Kaggle odmówił
utworzenia obu kernelków, a CLI zwróciło przy tym kod wyjścia 0 — więc nasze narzędzie uwierzyło, że
kernel istnieje, i przez cztery minuty odpytywało o stan coś, czego nie było.**

Żadnych wyników V6.5 ani V6.6 nie ma i nie może być z tych prób — kernele **nigdy nie powstały**.
Werdykty R1–R4 z `GATES_V6_6.md` **nie zostały wydane** (brak danych). Zużycie kwoty: twarde, ale
tylko deklarowane przez Kaggle; dwie odrzucone próby nie spaliły żadnych godzin.

## Dowód (bez interpretacji)

1. Ponowna próba V6.5 z 03:03 UTC zapisała w `kaggle_results/v6-5-benchmark/run.json`:

   ```
   "push_exit_code": 0,
   "push_stdout_tail": "Kernel push error: Maximum weekly GPU quota of 30.00 hours reached.\n",
   "push_verified": false,
   "push_probe_raw": "404 Client Error: Not Found for url: .../GetKernelSessionStatus",
   "status": "kernel_not_found_after_push"
   ```

   To jest cały mechanizm w trzech linijkach: komunikat błędu na **stdout**, kod wyjścia **0**,
   `kernels status` na wskazanym `id` → **404**.

2. Sonda push v2 (CPU-only, bez kwoty GPU) dowiodła, że push sam w sobie działa: kernel
   `petersharps/gemma-push-probe-p2-20261014-030100` osiągnął `KernelWorkerStatus.COMPLETE`,
   a kernel z sondy v1 żyje pod slugiem wynikającym z **tytułu**
   (`petersharps/gemma-push-probe-20261014`, log pobrany bez problemu). Czyli limit, nie format.

3. `kernels list --mine --sort-by dateCreated` (03:01 UTC) pokazuje sondy normalnie, a między nimi
   i wczorajszymi przebiegami stoją dwa puste, bezimienne wiersze `[Private Notebook]` z datą
   2010-04-01 — ślad po odrzuconych pushach (rekord bez sluga). Obu kernele benchmarkowe
   (`…cb847599-20261014-024522`, `…b6686c53-20261014-024548`) **nie ma na liście**, a `kernels files`
   nic dla nich nie zwraca.

4. Reguła resetu (Kaggle, potwierdzona w dokumentacji i na forum): 30 h/tydzień, reset **w sobotę
   o 00:00 UTC**, czasem więcej („floating quota"). Okno, w którym jesteśmy, zaczęło się w sobotę
   2026-10-10 00:00 UTC. **Najbliższy reset: sobota 2026-10-17 00:00 UTC = 02:00 czasu polskiego.**

## Na co poszło 30 godzin (okno 10–17 października)

| Dzień | Przebiegi GPU na tym koncie |
|---|---|
| sob. 10-10 | benchmark 12:09 |
| pon. 10-12 | 08:07, 11:43, 14:20 |
| wt. 10-13 | 00:59, 01:08, 11:19, 12:34 (pełny V6.4, 169 min) |
| + | kernele ARC-AGI-3 (`arc-agi-3-llm-agent-qwen3-6-27b`, `arc3-duck`, T4) — **to samo konto, ten sam licznik** |

Pełny przebieg to ~2,5–2,9 h, mini-screeningi po kilkadziesiąt minut. 30 h schodzi przy takim
rytmie bez trudu — a od 02:45 UTC środa limit był już zerowy.

## Co naprawiliśmy (żeby to się nie powtórzyło)

1. `run_kaggle_v1_smoke.py`: po pushu **weryfikuje**, że `kernels status` zwraca
   `KernelWorkerStatus` (6 prób × 20 s). Brak → `kernel_not_found_after_push`, wyjście 6, **bez**
   czterogodzinnego pollowania.
2. Ten sam tool: jawny komunikat „quota … reached" → natychmiastowy status `gpu_quota_exceeded`
   (wyjście 7), bez czekania. Dziś zajęłoby to sekundy, a nie 2 minuty.
3. Ten sam tool: surowy output pushu (`push_stdout_tail`, `push_stderr_tail`) i surowa odpowiedź
   sondy (`push_probe_raw`) trafiają do `run.json` — poprzednio log job-a z komunikatem Kaggle był
   nieczytelny, co kosztowało godzinę diagnozy.
4. Ten sam tool: 404 w trakcie pollingu zapisuje się jako `kernel_not_found_during_poll`, a nie
   jako „Five consecutive Kaggle status API calls failed" — poprzedni komunikat zmylił diagnozę.
5. `fetch_kernel_outputs.py`: 404 (`NOT_FOUND`) nie jest już liczone jako awaria API (nie zjada
   budżetu 12 prób), najpierw próbuje endpointu danych (`kernels files`), po 6 nieudanych sondach
   zapisuje `kernel_never_appeared` zamiast czekać 3,5 h.

## Plan (obowiązuje nadal, tylko przesunięty)

1. **Sobota 2026-10-17 ok. 00:05 UTC (02:05 czasu polskiego):** odpalam ponownie V6.5 (trigger
   `v65-benchmark`), potem **~10 min później** V6.6 — rozsunięte, bo poprzednia para poszła 26 s
   od siebie i to była jedyna różnica względem działających pushów z 10-13.
2. Werdykty liczy `tools/analyze_v65_v66.py` z zamrożonymi progami R1–R4; zapis w
   `GATES_V6_5.md` / `GATES_V6_6.md` bez zmian.
3. Zwycięzca → przebieg potwierdzający → decyzja o zgłoszeniu (S1 ≥10/30, S2 puste ≤8,
   S3 G1=G3=0 ∧ G2≤1; G2=0 nie osiągnął żaden wer, w tym V4 = 0,03).
4. **Do soboty nie wydawać ani godziny GPU** na nic innego (w szczególności na kernele ARC-AGI-3) —
   dwa pełne przebiegi to ~6 h z 30 h.

## Czego to nie zmienia

Aktualny oficjalny wynik konkursu to nadal **0,03** (V4, ref 57045226). Żaden wer nie został
zgłoszony od 2026-10-08. Terminy: zgłoszenia 25 listopada, finał 2 grudnia 2026.
