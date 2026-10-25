# ARC-AGI-3 — co jest na obu gałęziach Pokemon i co z tego wziąć na 9 dni

**Recenzja z 2026-10-25** (sesja Gemma, `arena/c4eeb067`). Czytane: `arena/c87f7a48-pokemon`
(tip `6c53d13`) i `arena/a450b00f-pokemon` (tip `33a9f7e`), oraz — żeby sprawdzić, czy ich
ustalenia nie rozjechały się ze stanem — gałąź `Smak-Domu-Konkurs` @ `9c05c70` (stan 24.10 ~22:00 UTC).
Wszystkie liczby poniżej albo pochodzą z plików tych gałęzi, albo policzyłem je sam z ich
własnych artefaktów; metoda jest podana przy każdej.

---

## 0. Co się zmieniło od mojej poprzedniej recenzji (24.10)

Poprzednia recenzja (`REVIEWS/2026-10-24-arc-agi-3-dlaczego-nie-ma-45.md`) miała trzy rzeczy
do poprawy. Poprawiam je tutaj, bo obie gałęzie zrobiły w tym czasie pomiary, których ja nie miałem:

| moja teza (24.10) | stan po pomiarach |
|---|---|
| „decyzje/min na grę ≈ 1,6 (FP8) i 1,0 (W4A16) — wąskie gardło to tok/s na strumień" | **Błędne ramowanie.** W rerunie gry idą równolegle (concurrency 28–120, ale realnie 10 slotów dekodowania), więc liczy się **pula tokenów na grę** (≈175–219k), nie prędkość jednego strumienia. c87 policzył to poprawnie: 755 tok/s zbiorczo × 31 920 s ÷ 110 gier = 219k teorii, 175k realnie. |
| „przyspieszenie silnika × krótkie decyzje = 5–6×" | Kierunek dobry, ale **obie połówki nie były mierzone razem**. Dziś wiem, że szybki silnik (W4A16+MTP+sglang) jest karmiony *droższym* mózgiem — patrz §3. |
| „deadline 26 X, próg 40,97" | **Obalone** przez c87 z live strony Kaggle: finał **2 XI** (26 X = entry + team merger), płatne top-5 = **49,85**. Ja opierałem się na ich `STATUS.md` z 10.10. |

Potwierdzam za to własnym przeliczeniem ich najważniejszą arytmetykę (§2) — sprawdziłem ją
niezależnie i **liczby 44,8 / 64,5 są poprawne**. To ważne, bo cały plan obu gałęzi na nich stoi.

---

## 1. Co jest na gałęziach (stan, nie opinie)

### `arena/c87f7a48-pokemon` — audyt zewnętrzny + najtwardsze pomiary
Katalog `arc3-handoff/` (2 477 linii dokumentów, 7 narzędzi, 16 testów, gotowy notatnik):
- **run-killer linii `duck-v7`** znaleziony i udowodniony `git apply`: ich patch `0003`
  (`duck-extra-02.patch`) był generowany wobec oryginalnego `solver.py`, a cell 9 nakłada go
  **po** patchu Franzena z `check=True` → `CalledProcessError` → notatnik umiera **przed**
  załadowaniem wag. To wyjaśnia crash v7 po 25 min i to, że linia z najszybszym silnikiem
  **nigdy nie została zmierzona**.
- **Naprawiony notatnik** (`notebook/arc3-duck-fixed.ipynb`) — podmienia zabójcę na własny
  `0004-standalone-level-token-cap`, łańcuch 4/4 OK, `py_compile` 3/3, testy 16/16.
- **Playbook offline** (BFS/beam, 0 tokenów LLM): **11/25 gier, 16 poziomów, 3,18 pkt**,
  każda sekwencja zweryfikowana replayem na świeżej instancji.
- **Arytmetyka budżetu**: 841 tokenów/akcję, ~208 akcji na grę wobec ΣBas ≈ 685,
  **35 % tokenów i akcji idzie w poziom, który nigdy nie zostaje ukończony**.
- **Live Kaggle 24.10**: Tufa 68,91 · Chen 68,21 · 5. the last dance **49,85** ·
  **Daniel Franzen (autor Ducka) 38,85 = 15. miejsce, bez nagrody**.

### `arena/a450b00f-pokemon` — pakiet `duck-v8` (replay) + rozstrzygnięcie blokady submitów
`arc-agi-3/duck-v8/`:
- **`arc3_replay.py` + `0004-solved-level-replay.patch`** — poziomy nagrywane jako łańcuchy
  akcji weryfikowane hashami ramki start/step/end; przy powrocie na poziom replay jedzie
  **bez wywołań modelu** i oddaje sterowanie na pierwszym nieukończonym/rozbieżnym.
  Kill-switch `ARC3_REPLAY`, fail-silent. Testy **10/10** (7 jednostkowych + 3 integracyjne),
  przy czym test integracyjny znalazł **2 prawdziwe bugi w okablowaniu**.
- **`RESET-VERDICT.md`** — ważny niuans: bez pinu `ONLY_RESET_LEVELS=true` RESET po śmierci
  cofa do poziomu 1, **z pinem** tylko do początku bieżącego poziomu. Pin jest ustawiany
  w komórce 2, więc w prawdziwym rerunie działa. Wniosek: replay zarabia głównie przy
  `n_passes>1` i jako ubezpieczenie — a nie „+18 za śmierci".
- **`DEEPSEEK-REVIEW-VERDICT.md`** — root cause trwałego `400`: `ops.py:459` podawał
  `-f` ze **ścieżką**, a API chce **nazwy pliku wyjściowego**. 12 submitów ze ścieżką = 12×400,
  2 z nazwą = 2×rc=0. **Potwierdzone działaniem na gałęzi ARC: r069 (24.10 21:44) →
  `-f submission.parquet` → rc=0, ref 57607527, PENDING.** Osiem dni straty na jednej linii kodu.

**Wniosek z §1:** obie gałęzie dowiozły to, czego gałąź ARC nie miała od tygodnia — pomiar,
naprawiony kod i jedną linię, która odblokowała submity. To nie jest duplikat pracy: c87
dostarcza **pomiary i naprawiony łańcuch patchy**, a450 **dostarcza mechanizm (replay)**.

---

## 2. Ich arytmetyka — sprawdziłem, jest poprawna

Przeliczyłem oficjalną formułę (`taaf/game.py::_compute_final_score`, lustro
`arc_agi.scorecard` v0.9.8) na 10 grach z `r019`, zachowując **zmierzone** wyniki poziomów
i dokładając nowe po capie 115:

| scenariusz | średnia | gdzie to jest w tabeli |
|---|---|---|
| dziś (3,2 poziomu z 7,3) | **27,21** | miejsca 15+ |
| ten sam L, idealna efektywność | 28,96 | — |
| **+1 ukończony poziom w każdej grze** | **44,8** | miejsca 8–11, zero pieniędzy |
| **+2 poziomy** | **64,5** | miejsca 2–3 |

Czyli **próg 49,85 leży ~1,3 poziomu powyżej dzisiejszego stanu.** Wszystko, co nie zwiększa
głębokości, jest warte ≤1,75 pkt (tyle dzieli 27,21 od 28,96) — łącznie z całym replayem
i całą optymalizacją ruchów. To jest jedyna rzecz, co do której obie gałęzie mają rację
i nie ma tu już miejsca na spór.

---

## 3. NOWE: szybki silnik jest karmiony drogim mózgiem

Nikt tego nie policzył, a wynika wprost z ich dwóch przebiegów. Tokeny na **decyzję** modelu
(nie na akcję — akcje w paczkach mają 0 tokenów) i na **akcję**:

| linia | decyzje | akcje | akcji/decyzję | tokenów/decyzję | **tokenów/akcję** | akcji w puli 175k |
|---|---:|---:|---:|---:|---:|---:|
| **szybka**: W4A16 Flash-Next + MTP + sglang (`r019`) | 474 | 2 065 | 4,36 | **3 665** | **841** | **208** |
| **wolna**: Qwen3.6-27B FP8 + vLLM (`r050`) | 173 | 521 | 3,01 | **1 337** | **444** | **394** |

Interpretacja, której brakuje w obu dokumentach:

1. **Szybki silnik nie daje 5× więcej akcji, bo jego mózg jest 2,7× droższy na decyzję.**
   Prędkość silnika (604 vs ~29 tok/s w tych przebiegach) jest częściowo zjadana przez długość
   odpowiedzi. Dziś linia szybka kupuje **208 akcji na grę**, linia wolna **394 akcje** — mimo
   że jest 20× wolniejsza w tym porównaniu.
2. **Kombinacja „szybki silnik + terse mózg" nie została zmierzona nigdy.** Jeśli 444 tokenów
   na akcję da się utrzymać na silniku robiącym 755 tok/s zbiorczo, pula 175k kupuje
   **394 akcje na grę** — czyli +1,5 do +2 poziomów, czyli **44–64 pkt**. To jest cała droga
   do nagrody, a jest to A/B **jednego** parametru: który mózg jedzie na którym silniku.
3. **Rozstrzygnięcie jest tanie**: oba przebiegi już logują `generated_tokens` i `wallclock`
   per akcja. Smoke 2,5 h podaje `tokenów/decyzję` i `akcji na grę` — dwie liczby, zero zgadywania.

**Praktycznie:** `arc3-duck-original` (mózg stockowy, 1 337 tok/decyzję) + silnik i metadata
z `duck-v7` (model `dfranzen/intel-qwen3.8-flash-next-w4a16`, drafter MTP, sglang) to jeden
notatnik, którego nikt nie zbudował. Wszystkie klocki leżą w ich repo; blokadą był wyłącznie
zabójca patchy z §1, już naprawiony.

---

## 4. NOWE: `LOCAL_ANALYZER_MAX_OUTPUT` = 0, czyli brak jakiegokolwiek limitu

`tool_agent.py:137` w bundlu r033: `_LOCAL_ANALYZER_MAX_OUTPUT = _get_env_int("LOCAL_ANALYZER_MAX_OUTPUT", 0)`
→ **0 = bez limitu**, i żaden z ich notatników tej zmiennej nie ustawia. Rozkład długości decyzji
w `r019` (474 decyzje): p50 = **2 057**, p90 = **8 046**, p95 = **10 947**, max = **61 300** —
czyli jedna tura zjadła 3,5 % puli całej gry.

Co daje cap (policzone na tych samych 474 decyzjach):

| cap | tur uciętych | % puli odzyskanej |
|---:|---:|---:|
| 8 000 | 48 / 474 (10 %) | **19,7 %** |
| 12 000 | 18 / 474 (3,8 %) | **12,3 %** |
| 16 000 | 13 / 474 (2,7 %) | 8,6 % |

Na linii wolnej ogon nie istnieje (max 7 179, cap 12k tnie 0 tur). **12 000 to bezpieczna wartość
na start** — dotyka 3,8 % decyzji, a zwraca 12 % puli; 8 000 jest agresywniejsze i wymaga
sprawdzenia, czy nie ucina wywołań narzędzia w połowie (ucięty JSON = zmarnowana decyzja).
Ryzyko jest mierzalne jedną linią logu: ile tur kończy się błędem parsowania.

Uwaga na zależność: patch `0004-level-token-cap` (c87) **zakłada** w komentarzu
`LOCAL_ANALYZER_MAX_OUTPUT=12k`, żeby wyliczyć, że `ARC3_ABANDON_TOKENS=60000` nigdy nie osiągnie
progu. Więc 12k to nie tylko oszczędność — to spójność z własnym patchem.

---

## 5. NOWE i największe: replay kluczowany **sygnaturą ramki**, nie `game_id`

Składam dwie rzeczy, które są osobno:

- c87 §8: scorecard to **110 runów**, a `official_110()` Tufy to **cykliczne klony ~25 gier**
  (`taaf/competition_arcade.py:56-77`, `clone_prefix='k'`, `i % len(source_ids)`), więc
  **ta sama mechanika trafia się ~4,4 razy w jednym runie**;
- a450: moduł replay, który **już weryfikuje łańcuch hashami start/step/end** — czyli ma
  dokładnie ten sygnał, którego trzeba, żeby rozpoznać poziom w klonie.

Dziś store jest kluczowany `game_id` (i dlatego a450 słusznie ocenia zysk jako mały przy
`n_passes=1`). **Jeśli klucz zmienić na sygnaturę pierwszej ramki poziomu** (hash segmentacji —
c45 i tak loguje hash pierwszej ramki sondą rosteru), to klon tej samej gry trafia w gotowy
łańcuch, replay przejeżdża go **bez ani jednego tokenu**, a weryfikacja hashów odrzuca każdy
fałszywy traf. Zysk: do **×4,4 darmowych poziomów** z pracy wykonanej raz.

To jest jedyna dźwignia w całym tym materiale, która mnoży **głębokość** (a nie efektywność)
i nie kosztuje ani jednego tokenu z puli. Wymaga dwóch rzeczy, obu tanich:
1. sondy rosteru w najbliższym rerunie (c45 ją ma) → czy klony mają identyczne pierwsze ramki;
2. zmiany klucza w `arc3_replay.py` (kilka linii, testy już są).

Uczciwie: jeśli roster jest „distinct", zysk = 0 i wtedy wracamy do `MAXREQ=16` (c87: +45 % puli,
ekstrapolacja). Ale to rozstrzyga **jeden** rerun, który i tak jest zaplanowany.

---

## 6. Trzy pułapki w obecnym planie (24.10 ~22:00)

1. **Slot 25.10 idzie na linię wolną.** Kandydat `duck-c45` (przyjęty 4,5/5) to
   **Qwen3.6-27B-FP8 + vLLM** — czyli ta sama linia, która dała 24,66 / 26,25 / 23,94,
   plus cap poziomu. Uczciwe oczekiwanie: **24–30**. To dobry „nie przegrać" slot, ale
   **nie może dojść do 45+** — brakuje mu jedynej rzeczy, która u innych daje 47,25
   (silnik Franzena). Wniosek: 25.10 = c45 (już zbudowany, niskie ryzyko), ale **26.10 musi
   być naprawionym `duck-v7` — silnik szybki + mózg stockowy (§3), a nie kolejny wariant wolnej linii.**
2. **Bramka „LB v5 ≥ 47 → strefa nagród" jest martwa.** Linia v5 historycznie daje 24,7–27,2;
   prawdopodobieństwo ≥47 jest ~0, więc zawsze wejdzie gałąź „<45 → cap=45000". To nie błąd
   krytyczny (cap i tak jest jedną zmienną), ale **nie wolno tego czytać jako „v5 wypadł słabo"** —
   to pomiar powtarzalności (oczekiwane 26 ± 3), nie sygnał o jakości kandydata.
3. **Kopia patcha replaya w gałęzi ARC jest sprzed poprawek.** `INTEGRATION-RESULTS.md` mówi
   wprost: kopia z commita `4a538fe` jest **przed** naprawą dwóch bugów złapanych testem
   integracyjnym. Przed budową kernela podmienić na wersję z `a450b00f` (`arc-agi-3/duck-v8/`).

---

## 7. Plan slotów 25.10 → 2.11 (jeden pomiar na slot, każdy z bramką)

| slot | co | koszt | bramka (przed wysłaniem) |
|---|---|---|---|
| **25.10** | `duck-c45` (jest gotowy) | 1 GPU smoke + 1 slot | smoke COMPLETE, `wasted_tokens` < 35 %, `tokenów/akcję` zapisane |
| **26.10** | **`duck-v7` naprawiony (c87) + mózg stockowy + `MAX_OUTPUT=12000`** | 1 smoke | `tokenów/akcję` ≤ 600 i `akcji na grę` ≥ 300 → to jest kandydat na 45+ |
| **27.10** | zwycięzca + replay z kluczem **frame-hash** (a450, po poprawkach) | 1 smoke | raport: ile poziomów replay przejechał bez modelu; 0 = roster distinct |
| **28–30.10** | zwycięzca + `MAXREQ=16` **tylko jeśli** roster distinct | 1 smoke | `full token usage` < 0,95 i puff ≥ +20 % |
| **31.10–1.11** | finalista + publiczny notatnik (CC0/MIT-0) | 1 slot | **kernel publiczny, inaczej nagroda przepada** |
| **2.11** | zapas; nic bez `ARC3_SMOKE_OK` | — | — |

Zasada, która obie gałęzie już zapłaciły: **jedna dźwignia na slot, decyzja po pomiarze,
nie po opinii.** Ich własna historia (7 dni bez submitu) pokazuje, że najdroższy błąd to nie
zły pomysł, tylko brak pomiaru.

---

## 8. Czego nie robić (dopisać do ich listy)

- **Nie liczyć replaya jako dźwigni przy `n_passes=1` i działającym pinie** — a450 sam to
  sprostował; wartość jest w klonach/replikach (§5), nie w śmierciach.
- **Nie podnosić `MAXREQ` przed pamięcią między replikami** — walczą o to samo KV
  (c87: `full token usage` mediana 0,71, max 0,99).
- **Nie oceniać kandydata po score z 10 gier** — kalibracja smoke→LB to −3…−6,7 pp i przy
  n = 10 różnica 2 pkt to szum. Mierzyć `tokenów/akcję`, `akcji na grę`, `% zmarnowanych`.
- **Nie planować na krzywej „200k→41,8"** (c87 §5 obalił ją na ich własnych danych).
- **Nie wysyłać nic z prywatnym kernelem, jeśli celujesz w pieniądze** — wymóg open-source
  jest w regulaminie, a ich kernele mają `is_private: true`.

---

## 9. Co z tego zostaje u mnie (Gemma-4), bo to przenośne

1. **Metryka z capem zabija całą klasę dźwigni.** U nich `min(115, …)` → optymalizacja ruchów
   warta 1,75 pkt z 27. U mnie V8 (+verify-loop) przy stałym budżecie = −1. Ten sam wzorzec:
   zanim dodasz mechanizm, sprawdź, czy metryka ma w tym wymiarze zapas.
2. **Walutą jest jedna liczba, a nie wynik.** U nich: pula tokenów na grę ÷ tokeny na akcję.
   U mnie: akcje do limitu czasu. Wariant bez tej liczby to loteria.
3. **Jeden pomiar na slot, bramka przed wysłaniem** — ich 8 dni straty na `-f` to ten sam
   błąd klasy co moje dwa martwe knob-y: wartość ustawiona, ale niedoniesiona.
