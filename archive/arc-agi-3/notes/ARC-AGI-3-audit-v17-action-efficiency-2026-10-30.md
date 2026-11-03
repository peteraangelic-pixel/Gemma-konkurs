# Audyt: duck-v17-action-efficiency (3 nowe pliki z gałęzi Smak-Domu-Konkurs)

Data: 2026-10-30. Audyt **offline**: kod uruchomiony lokalnie, żadnego Kaggle, GPU, submisji
ani zmian na remote. Gałąź `arena/5ed750ef-smak-domu-konkurs`, commit `283a36b8` („Add files
via upload”). Pobrane przez GitHub API, bez przełączania gałęzi.

## 1. Co dokładnie przyszło

| plik | rozmiar | status |
|---|---:|---|
| `arc3_duck-v17-action-efficiency.zip` | 44 762 B | sha256 `936f5bd68d28…aa00f89`; 20 plików w środku |
| `action_efficiency_layer.py` (w katalogu głównym repo) | — | **bajt w bajt to samo** co w zipie |
| `agent.py` (w katalogu głównym repo) | — | **bajt w bajt to samo** co w zipie |

Czyli „3 nowe pliki” = 2 luźne kopie plików, które już są w zipie, + sam zip. Nic poza tym
nie doszło. W zipie: `ARC3/duck-v17-action-efficiency/` (STATUS, README, warstwa, agent, sim,
testy, eval, wyniki, RAPORT.html), `ARC3/REVIEWS/…audyt…md`, `AVX512/` (5 plików C + raport),
`README.md`, `PUSH_INSTRUCTIONS.md`. **Paczka nigdy nie została wypchnięta na osobną gałąź**,
mimo że `PUSH_INSTRUCTIONS.md` to zakłada — leży w katalogu głównym gałęzi roboczej.

## 2. Co odtworzyłem (liczby się zgadzają)

```
python3 test_layer.py        -> 7/7
python3 run_eval.py 12       -> REACTIVE RHAE 3.80 / 1337 akcji na poziom / 75% solved
                                PLANNER  RHAE 40.06 / 233 akcje na poziom / 100% solved
```

Wynik jest deterministyczny i zgadza się z `STATUS.md` co do liczby. **To nie jest jednak
pomiar tej warstwy** — i tu zaczyna się problem.

## 3. Pięć ustaleń, wszystkie sprawdzone w kodzie lub pomiarem

### 3.1 Nagłówek mierzy agenta, nie warstwę (najpoważniejsze)

`run_eval.py` importuje wyłącznie `sim.GAMES` i `agent.{ReactiveAgent, PlannerAgent}`:

```
$ grep -l PlanCache *.py        -> action_efficiency_layer.py test_layer.py
$ grep -l ConvergedGuard *.py   -> action_efficiency_layer.py test_layer.py
$ grep -l BudgetLedger *.py     -> action_efficiency_layer.py test_layer.py
```

`PlanCache`, `ConvergedGuard`, `BudgetLedger` i `HarnessHook` **nie są użyte nigdzie poza
własnym plikiem i własnymi testami**. Zatem „RHAE 3.80 → 40.06” to `PlannerAgent` (ręcznie
napisany solver: BFS po mapie, tablica efektów, portfolio hipotez porządkowania) kontra
`ReactiveAgent` (greedy). Trzy mechanizmy, które paczka reklamuje jako gotowe do wpięcia,
mają **zero zmierzonych dowodów**, a 7/7 zielonych testów dotyczy kodu, którego ewaluacja nie
wywołuje. To dokładnie ten wzorzec, który paczka sama nazywa „testy zielone przy martwej
funkcji” — tyle że tutaj funkcja jest martwa w pomiarze, nie w teście.

### 3.2 „12 seedów” nie wnosi statystyki

Wszystkie 12 seedów daje identyczny wynik (`±0.00` w każdym wierszu `results.json`), bo
`_make_level()` w `sim.py` korzysta z numeru poziomu, nie z seeda (`random.Random(level * 77 + 5)`).
Seed trafia tylko do `self.rng`, którego żaden z agentów nie używa do rozgrywki. „12 seedów,
deterministyczne” = jeden przebieg policzony 12 razy.

### 3.3 40,06 to średnia z czterech gier, z których dwie są zerowe

Per gra: `keydoor 115.00` (sufit 1.15), `pushblock 45.23`, `switchorder 0.00`, `colorclicks 0.00`.
Mediana po grach: **22,6**, nie 40. Cały wynik powyżej baseline bierze się z jednej gry na
suficie capu. (Cap 1.15 jest zgodny z dokumentacją ARC Prize — sprawdzone; w nagraniach
harnessu Duck widać cap ukończenia, który w tych plikach i tak dominuje.)

### 3.4 Ablacja: PlanCache działa tylko wtedy, gdy poziom jest powtarzany

Wpiąłem warstwę w ich własne simy (ten sam harness co `run_eval.py`, 12 przebiegów):

| konfiguracja | keydoor | switchorder | pushblock | colorclicks | TOTAL | trafienia cache |
|---|---:|---:|---:|---:|---:|---:|
| reactive (ich baseline) | 7.86 | 0.00 | 1.45 | 5.89 | 3.80 | — |
| + `ConvergedGuard` | 18.01 | 15.51 | **0.00** | 4.42 | 9.48 | 0 |
| + guard + cache, reset co seed | 18.01 | 15.51 | 0.00 | 4.42 | 9.48 | **0** |
| + guard + cache, współdzielony w całym runie | 28.95 | 22.29 | 0.00 | 45.64 | 24.22 | 99 |

Czytanie: guard sam daje 3.80 → 9.48 (i **psuje** `pushblock` 1.45 → 0.00). Cache daje
9.48 → 24.22 **tylko** wtedy, gdy ten sam poziom jest odtwarzany w kolejnym seedzie — bo
wtedy stan startowy i cała ścieżka są identyczne. Przy pierwszym kontakcie z grą (warunek
konkursu) cache ma **0 trafień**, czyli jest obojętny. W harnessie Duck dokładnie tę funkcję
pełni już patch 0006 (win-path replay z weryfikacją ramek) plus playbook 14 poziomów — więc
`PlanCache` nie wnosi nowej dźwigni, tylko jej słabszą kopię.

### 3.5 Mechanizmy nie pasują do architektury Duck

- `ConvergedGuard.filter(candidates)` zakłada **listę kandydatów**. W Duck model zwraca jedną
  akcję na request; wygenerowanie listy kandydatów to dodatkowe tokeny, czyli dokładnie ten
  koszt, który metryka karze.
- Duck **ma już** guard stanu: `noop_repeat_guard.py` kluczowany po
  `(poziom, hash wnętrza planszy, sygnatura akcji)` z jednorazowym obejściem („model może
  upierać się przy swoim”). `ConvergedGuard` banuje ostatni wybór na 40 kroków **bez** obejścia
  — w pętli LLM to narzędzie tępe.
- `BudgetLedger.pick_game` zakłada **szeregowy** harmonogram (obserwuj → działaj → następna gra).
  Duck prowadzi 10 gier współbieżnie, a bramka priorytetu wpuszcza grę dopiero przy przycięciu
  kontekstu. Wiążącym ograniczeniem jest wallclock i tokeny (cap 532 min), nie liczba akcji.
  Wzór `completed/(used+200)` przy zerowych ukończeniach degeneruje się do „najmniej akcji
  najpierw”, czyli głodzi gry, które wymagają eksploracji.

## 4. Co z tego wynika dla samej metryki — i to jest jedyny trwały zysk

`level_score = min(1.15, (human/ai)²)`, waga = numer poziomu, nieukończony poziom = 0.
Rozkładam to na dwa niezależne składniki: **efektywność** (akcje na ukończonym poziomie)
i **ukończenie** (jaka część wagi poziomów została zdobyta). Zaimplementowane w
`arc3_local_candidate/tools/score_decomposition.py`, sprawdzone na czterech prawdziwych
nagraniach Duck (te same, z których korzysta audyt gałęzi):

| nagranie | wynik | efektywność na ukończonych | ukończenie | sufit „akcje jak człowiek" | sufit „wszystkie poziomy" |
|---|---:|---:|---:|---:|---:|
| r085 | 26,78 | 95,2% | 29,8% | 29,79 (**+3,01**) | 88,81 (**+62,03**) |
| r093 | 18,55 | 81,1% | 23,4% | 23,45 (+4,90) | 75,26 (+56,71) |
| r110 | 0,73 | 26,2% | 1,4% | 1,41 (+0,68) | 23,92 (+23,19) |
| r118 | 0,27 | 12,9% | 0,6% | 0,58 (+0,31) | 11,43 (+11,16) |

W każdym z czterech nagrań **wiążącym ograniczeniem jest ukończenie, nie liczba akcji** —
o rząd wielkości. Na r085 (wynik 26,78, czyli poziom najlepszej submisji) gracz AI jest już
przeciętnie *bardziej* efektywny niż człowiek na poziomach, które kończy (mediana stosunku
human/ai = 1,27; mediana 37 akcji na ukończony poziom), a traci na tym, że nie kończy
37 z 69 poziomów.

Wniosek: teza paczki „jedyna dźwignia to mniej akcji” **nie jest prawdziwa dla tego harnessu**.
Prawdziwa jest dla ich mikro-środowisk, bo tam każdy poziom jest 3–4 kratki od startu, a baseline
„człowieka” to 1,3 × najkrótsza ścieżka policzona tym samym kodem. Obie liczby są poprawne —
mówią o różnych rzeczach.

Zastrzeżenie, które musi tu zostać: oba sufity to **górne ograniczenia**, nie prognozy.
Sufit „wszystkie poziomy” zakłada, że późniejsze poziomy kosztują tyle, co wcześniejsze
(nieprawda), a sufit „akcje jak człowiek” zakłada, że trudniejsze poziomy dadzą się wyrównać
(niekoniecznie).

## 5. Co warto z paczki wziąć

1. **Dyscyplina pomiaru jako funkcja celu** — i to jest zaimplementowane:
   `arc3_local_candidate/tools/action_efficiency.py` liczy medianę akcji na ukończony poziom,
   rozkład poziom-poziomie i bramkę `compare before.json after.json` (kod wyjścia 1, gdy
   zmiany **nie** należy wysyłać: wynik nie wzrósł, ukończenie spadło albo mediana akcji
   poszła w złą stronę). To jest dokładnie ich postulat, tylko na prawdziwych plikach.
2. **Pułapka „obiekt pod graczem jest zasłonięty”** — prawdziwa i warta zapamiętania dla
   agentów wnioskujących o postępie z pikseli (fałszywy progres → pętla 2-krokowa). W harnessie
   Duck nie występuje, bo postęp pochodzi z silnika (`levels_completed`), nie z domysłu o
   znikającym obiekcie.
3. **Raportowanie przegranych gier równie głośno jak wygranych** — dobra praktyka, utrzymana.

## 6. Czego nie wziąć

Wpięcia `HarnessHook` w `llm_policy.py`. Powody z §3.4–3.5: cache jest funkcjonalnie tym, co
już robi patch 0006; guard jest słabszy od istniejącego `NoopRepeatGuard`; ledger zakłada
architekturę, której ten harness nie ma, a jego polityka głodzi eksplorację. Do tego doszłaby
zmiana, której nie da się zmierzyć offline przed slotem.

## 7. Czy to jest lepsze od v15 / v13.4 / v16?

Nie w tej samej klasie — i sam autor paczki pisze to uczciwie. Rozdzielam osie:

| | v13.4 / v15 / v16 | duck-v17-layer |
|---|---|---|
| co to jest | pełny notebook konkursowy na prawdziwych grach | warstwa + mikro-środowiska |
| model | Qwen3.8-Flash-Next W4A16 + SGLang | żadnego |
| pomiar | łańcuch patchy, testy, replay r085, sondy | RHAE offline, 4 mikro-gry, deterministyczne |
| wynik konkursowy | ma historię submisji (best 26,25) | nie ma i nie może mieć |
| gotowość do slotu | wysoka (v13.4: 43 kontrole offline; v16: 43 + D′) | zerowa (dead code w pomiarze) |

**Rekomendacja bez zmian: nie budować v18.** Slot: v13.4-unified; potem v16-arena (jedna
zmienna, mierzalna) albo powtórka v13.4. Każda zmiana przechodzi przez
`action_efficiency.py compare` **i** `score_decomposition.py`; jeśli wiążącym ograniczeniem
zostaje ukończenie, to kolejny patch powinien atakować ukończenie (np. alokację czasu na gry,
które stoją na poziomie 0), nie liczbę akcji.

## 8. Czego nie zweryfikowałem

- Liczb leaderboardu z §„Stan konkursu” (TOP-1 75,56, TOP-2 70,02, TOP-3 58,59, deadline 2.11) —
  to twierdzenia z dokumentów paczki; Kaggle API nie było używane, więc ich nie potwierdzam.
- Żadnego GPU, żadnego gatewaya, żadnego submitu — zgodnie z ograniczeniami sesji.
- `AVX512/` (5 plików C + raport): wątek ortogonalny do konkursu, nie audytowałem pomiarów;
  sandbox ma AVX-512, ale nie odtwarzałem ich liczb.
- Plików `RAPORT.html` i `sim.py` nie analizowałem linia po linii poza tym, co potrzebne do
  powyższych wniosków.
