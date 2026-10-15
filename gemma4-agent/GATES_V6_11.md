# V6.11 — bramki i pre-registracja (zamrożone **przed** jakimkolwiek przebiegiem)

Stan na 2026-10-15 ~16:45 UTC. V6.11 **nie został uruchomiony ani wysłany**. Nic się nie stanie,
dopóki nie zostanie wypchnięty `gemma4-agent/kaggle_smoke/v611-benchmark.trigger`.

## Czym V6.11 jest

**V6.11 = V6.10 (kontrakt V6.7 + ewoluowany lokalizator V6.8 + inline V6.6) + ramię „budżet i konwersja".**

Dwie zmiany wobec V6.10 — i tylko dwie:

| | V6.10 (kontrola) | V6.11 (ramię) |
| --- | --- | --- |
| `eval_config.yaml` | 150 s / **30 wywołań / 60 tur / 5,25 min** | 150 s / **45 wywołań / 80 tur / 8,0 min** |
| prompt | 22 501 znaków | 23 400 znaków — cztery dopisane zdania (tekst kontraktu, lokalizator, próbkowanie bez zmian) |
| lokalizator | ewoluowany, inline | **identyczny** |
| artefakt | `523d43fb…`, 14 385 B | **`7b2beec1…`, 15 122 B** |

Cztery zdania dopisane w V6.11 (wszystkie w `prompts/system.md`):

1. **Budżet** — „8 minut i 45 wywołań" zamiast „5 minut i 30 wywołań" (zgodne z `eval_config.yaml`;
   packer wymusza tę zgodność).
2. **Kończ, gdy edycja jest na dysku** — „check it once if that is cheap, then stop even with minutes
   left. The 12-hour budget belongs to the whole run, not to your task".
3. **Ratunek przed pustym drzewem** — jeśli do wywołania 8 nie ma edycji: 10-liniowy repro w `/tmp`
   z tekstu issue, uruchom, edytuj plik z tracebacku; jeśli traceback nic nie wskazuje — edytuj
   najlepszego kandydata lokalizatora. „No session ends with an empty tree."
4. **Higiena edycji** — nigdy nie wysyłaj ponownie wywołania odrzuconego przez harness; trzymaj
   `old_string` krótki i dziel dużą edycję na kilka małych (pomiar publiczny: 105/524 odrzuconych
   wywołań `edit_file`/`write_file` z `mandatory input parameters are not present`, 47 z nich
   przez utratę granic długiego argumentu).

## Dlaczego budżet (pomiary, nie opinie)

| pomiar | wartość | źródło |
| --- | --- | --- |
| V5 oficjalnie przy budżecie **45 wywołań / 80 tur / 5,25 min** | **0,13** | nasz wynik, ref `57188055` |
| wszystkie ramiona V6.x od tego czasu | 30 wywołań / 60 tur | `eval_config.yaml` w V6.4–V6.10 |
| V6.4: sesje, które skończyły się **dokładnie na capie wywołań** | **12/30** | `kaggle_results/v6-4-benchmark/agent_benchmark_result.json` |
| V6.4: zgony na zegarze / puste drzewa | **19/30** / **11/30** | j.w. |
| konkurent: cap 4 min → 0,08; bez capa → 0,12 | +0,04 | publiczny notebook Pathfinder (3P) |
| konkurent: przy capie 6 min ginie **~45 % rozwiązań** („zadania 8–15-minutowe to często te, które rozwiązujemy") | — | wątek `749597` (3P, czeka na odpowiedź HOSTA) |
| publiczna konfiguracja z 0,18 | 8 min / 28 wywołań | notebook Budget-Fit (3P) |
| odrzucone wywołania edycji | 105/524 (20 %) | wątek `748323` (3P, odtworzone na CPU) |

## Bramka bezpieczeństwa 12 h (najważniejsza)

Limit 12 h obejmuje **cały przebieg** i jego przekroczenie **wyzerowuje całą submisję** (HOST,
`743063`). Cap 8 min sam w sobie NIE jest bezpieczny — bezpieczna jest **średnia**:

    120 zadań × (średnia 3,5 min + 0,5 min setup) = 8,0 h    <- cel
    120 zadań × (średnia 5,0 min + 0,5 min setup) = 11,0 h   <- jeszcze się mieści
    120 zadań × (cap 8,0 min + 0,5 min setup)     = 17,0 h   <- zeruje submisję

Dlatego pre-registrujemy **S1/S2** i traktujemy je jako warunek koniunkcji z R1–R5:

- **S1: średni czas zadania ≤ 5,0 min** (V6.4: 4,97 min przy capie 5,25 — czyli cap był wiążący,
  a mimo to średnia była blisko granicy; V6.11 musi zejść, nie wejść wyżej).
- **S2: suma wall-clock 30 zadań ≤ 2,5 h.**
- Jeśli S1/S2 nie przejdą, cap wraca do 5,5 min, ZANIM cokolwiek pójdzie do Kaggle.

## Pre-registracja oczekiwań

Przebieg: workflow `gemma-kaggle-v611-benchmark.yml` (gotowy, nie odpalony), te same 30 zadań
i seed `20261009` co V3–V6.4. **Kontrola to V6.10 na starym budżecie** (`gemma-kaggle-v610-benchmark.yml`),
żeby różnica dotyczyła budżetu i reguł, a nie lokalizatora ani tekstu kontraktu.

| # | miara | V6.4 | V6.10 (kontrola) | próg dla V6.11 |
| --- | --- | --- | --- | --- |
| R1 | rozwiązane zadania | 10/30 | zmierzone tym samym przebiegiem | **≥ 13/30** |
| R2 | puste drzewa (zero edycji) | 11 | „ | **≤ 6** |
| R3 | sesje zakończone **same** (nie cap, nie zegar) | — (do policzenia) | „ | **≥ 10** |
| R4 | odrzucone wywołania edycji | nie mierzone | „ | **≤ 5 % wywołań edycji** (mierzone `diagnose_agent_commands.py`; jeśli narzędzie tego nie izoluje, raportujemy zbiorczo i mówimy to wprost) |
| R5 | średni czas zadania | 4,97 min | „ | **≤ 5,0 min (S1)**; suma ≤ 2,5 h (S2) |

Dodatkowo raportujemy osobno, bez progu: rozkład liczby wywołań, czasy, bramki jakości G1/G3
(pliki-śmieci, diffy wyłącznie dokumentacyjne) i liczbę sesji, które skończyły się własną decyzją
po edycji na dysku.

## Czego V6.11 NIE twierdzi

- To **jeden przebieg na 30 zadaniach**: ±2–3 zadania to szum (publicznie: ten sam pakiet dał
  0,17/0,15/0,13/0,15 na 58-zadaniowej LB, czyli ±0,02–0,04). Sukces R1 nie jest dowodem na +0,05
  oficjalnie, porażka nie jest dowodem regresu.
- **Nie zmienia modelu, narzędzi, próbkowania ani lokalizatora** — jeśli V6.11 wygra, przypisujemy
  to budżetowi i regułom konwersji, nie „lepszemu lokalizatorowi".
- Nie włącza narzędzi grafowych. Wątek `748323` pokazuje, że od 8 października grafy **zwracają
  wyniki** (270/314 wywołań), ale „czy to pomaga rozwiązywać zadania — nie testowaliśmy", a każda
  odpowiedź to ~5,8 tys. znaków, przy efektywnym kontekście ~14,3 tys. tokenów. To osobne ramię
  (warunkowe: jedno wywołanie tylko wtedy, gdy lokalizator nie wskazuje kandydata), nie część V6.11.
- Prompt ma **23 400 z 24 000** znaków limitu packera: kolejne reguły muszą **zastępować**, nie
  dopisywać, albo limit trzeba podnieść świadomą decyzją (kontekst ~14,3 tys. tokenów dzielimy
  z historią sesji).

## Kolejność na sobocie (2026-10-17 00:00 UTC)

1. `v611-benchmark.trigger` → V6.11 (ramię) — ≈2,8 h wall, 5,6 h kwoty GPU.
2. `v610-benchmark.trigger` → V6.10 (kontrola na starym budżecie) — ≈2,0 h wall, 4,0 h kwoty.
3. Dopiero potem decyzja o kolejnych przebiegach (rezerwa: V6.7/V6.8/V6.5 — cztery stare ramiona
   przestają być pierwszym wyborem, bo żadne z nich nie dotykało budżetu, a to największa niewiadoma).
4. Równolegle, bez GPU: pipeline SFT/LoRA (`SFT_PLAN.md`) — dane z 129 publicznych zadań, canary na
   logprobs, dopiero potem trening na L4×4.

## Odtworzenie

```
V6_VARIANT=v611 python3 gemma4-agent/tools/make_v6_prompt.py
python3 gemma4-agent/build_submission_v6.py --source-dir gemma4-agent/submission-v6.11
python3 gemma4-agent/tools/negative_controls_v6.py --variant v611     # 1 kontrola pozytywna + 11 negatywnych
```
