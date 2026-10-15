# Plan SFT/LoRA (dźwignia post-trainingowa) — stan 2026-10-15

**Cel:** przekroczyć płaskowyż promptowania. Publiczne pomiary (patrz `RESEARCH_2026-10-15_EXTERNAL.md`)
mówią, że sam scaffold/prompt kończy się w okolicach 0,10–0,14 — czyli tam, gdzie jesteśmy (0,13) —
a wpisy powyżej 0,18 trenowały model. Konkurs **pozwala** dołączyć adaptery PEFT LoRA
(`adapters/<nazwa>/`), a HOST potwierdził 2026-10-15 (wątek `749528`), że adaptery **są aplikowane
w scoringu**; przykładowy adapter wyglądał na ignorowany tylko dlatego, że dotyka **warstwy 0 z 60**.

## Co jest zbudowane (CPU, zero GPU)

| plik | co robi |
| --- | --- |
| `tools/build_sft_dataset.py` | z 129 publicznych zadań (`tasks.jsonl` + `snapshots/`) buduje przykłady chat: system = prompt V6.11, user = treść issue + **kandydaci z naszego shippowanego lokalizatora**, assistant = złoty patch ograniczony do plików, które dotyka. Wyjście: `sft_train.jsonl` / `sft_holdout.jsonl` (split deterministyczny po hashu `instance_id`, co 5. = holdout) + `sft_meta.jsonl` + `sft_summary.json` |
| `tools/make_sft_notebook.py` | generuje `kaggle_smoke/gemma-lora-sft-v1.ipynb`: fingerprint wheelhouse’u → klon repo → budowa danych → **canary** → QLoRA → sprawdzenie na holdoucie → spakowanie archiwum (bez wysyłki) |
| `kaggle_smoke/gemma-lora-sft-v1.ipynb` | wygenerowany notebook; `SMOKE = True` domyślnie, żeby pierwszy przebieg był tani |

Test danych wykonany lokalnie na atrapie repozytorium (1 zadanie syntetyczne): złoto w top-1
lokalizatora, cel = poprawny diff, format wiadomości zgodny. **Na prawdziwych 129 zadaniach
nie był jeszcze uruchomiony** (dane konkursowe są tylko na Kaggle).

## Bramki (pre-registracja)

1. **G-canary** — losowy adapter rank-8 na **wszystkich** warstwach `q_proj`/`o_proj` musi ruszyć
   top-5 logprobów o > 0,05 nata (albo zmienić zwycięzcę). Jeśli nie ruszy: **STOP**, trening
   byłby wyrzuconymi godzinami. (Bramka jest w notebooku jako `SystemExit`.)
2. **G-holdout** — na zadaniach odłożonych adapter musi **pobić wersję bez adaptera na tych samych
   promptach** (para: ten sam model, `disable_adapter()`, greedy). Mierzymy odsetek wygenerowanych
   patchy dotykających pliku złotego.
3. **G-screen** — dopiero po 1 i 2 adapter wchodzi do paczki V6.11 i przechodzi **ten sam
   oficjalny ekran 30 zadań** co każde ramię promptowe (bramki w `GATES_V6_11.md`).
4. **G-pack** — packer (`build_submission_v6.py`) ma **zamknięty zbiór 5 plików** i celowo odrzuca
   `adapters/`. Trzeba dodać świadomy tryb `--with-adapters` (z kontrolą rozmiaru, ranku ≤ 16,
   jednego adaptera) **przed** jakąkolwiek submisją z adapterem. Notebook buduje archiwum sam i
   tylko drukuje sha256.

## Konfiguracja treningu (v1)

- QLoRA 4-bit (nf4, double-quant), **rank 8**, `lora_alpha 16`, dropout 0, `target_modules =
  [q_proj, k_proj, v_proj, o_proj]` na **wszystkich** warstwach (nie tylko warstwie 0 — to był błąd
  przykładu), lr 1e-4, cosine, 1–2 epoki, batch 1 × grad-accum 4, `max_seq_length 4096`,
  gradient checkpointing.
- Powód małego ranku: **z adapterem kurczy się KV cache** (wątek `749191`/`744331`; HOST: vLLM
  dobiera rozmiary z submisji). Jeden adapter, rank ≤ 16.
- Model: na start **31B** (ten sam, co w submisji, więc pomiar jest porównywalny). Warianty 12B/E4B
  (dopuszczone 2026-10-15) to osobne, późniejsze ramię — szybsza inferencja = więcej tur, ale
  nieznany spadek jakości.

## Budżet i koszt (30 h GPU/tydzień, reset sobota 00:00 UTC; L4×4 liczy się ×2)

| krok | szacunek | uwaga |
| --- | --- | --- |
| ekran V6.11 + kontrola V6.10 (sobota) | ~9,6 h | priorytet: to odpowiada na pytanie „budżet czy nie" |
| canary + budowa danych | ~0,5 h | CPU + serwowanie; można zrobić w tym samym notebooku |
| QLoRA na 129 przykładach, rank 8, 2 epoki | ~2–4 h | `SMOKE=True` najpierw (~10 min) |
| G-holdout (generowanie na ~25 zadaniach, 2× model) | ~1–2 h | tanie, bo bez harnessu |
| G-screen adaptera (30 zadań) | ~5,6 h | dopiero po 1–3 |

## Ryzyka i czego nie obiecujemy

- **Nie wiemy, czy trening pomoże** — 12. miejsce na LB twierdzi, że finetuning nikomu nie pomógł;
  autor 0,17 twierdzi odwrotnie. Nasza różnica: trenujemy **na własnym zadaniu** (lokalizacja →
  patch), na publicznych zadaniach z tego samego rozkładu, i mierzymy na odłożonych.
- **Przeuczenie do 129 publicznych zadań**: dlatego holdout i ekran, oraz 1–2 epoki (nie 10).
- **Regulamin/dane**: dane publiczne konkursu są dozwolone; „external data" — przed użyciem czegokolwiek
  spoza zbioru konkursowego trzeba przeczytać §External Data (wątek `742807` ma odpowiedź HOSTA
  o dystylacji; `749585` czeka na odpowiedź o trajektoriach z Claude/GPT — **nie używamy ich**).
- **Kontekst**: efektywne okno ~14,3 tys. tokenów; nasze przykłady SFT celowo pokazują maksymalnie
  3 pliki × 8 tys. znaków + issue ≤ 12 tys. znaków.

## Następne kroki

1. Sobota: `v611-benchmark.trigger`, potem `v610-benchmark.trigger` (`GATES_V6_11.md`).
2. W tej samej dobie: notebook `gemma-lora-sft-v1.ipynb` z `SMOKE=True` (canary + 6 zadań,
   ~10–20 min) — to rozstrzyga, czy droga LoRA w ogóle działa u nas end-to-end.
3. Jeśli canary przejdzie: `SMOKE=False`, trening, G-holdout, potem decyzja o `--with-adapters`
   w packerze i o ekranie adaptera.
