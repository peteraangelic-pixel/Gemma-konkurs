# Odpowiedź na audyty wszystkich gałęzi + realna droga do TOP5 (31.10.2026)

Wejście: `PEER-AUDIT-RESPONSE-20261031.md` (nowe audyty: Smak `c5e714a4`, Gemma `62000610` i moje
`004769ec`, Pokemon `9d528ac4`), mój raport `ARC-AGI-3-audit-template-controller-2026-10-31.md`,
oraz `LEADERS-AND-METHODS-20261030.md` / `TOP10-RESEARCH-20261030.md` z drzewa Smaka.

Poniżej: co **cofam u siebie**, co **potwierdzam u nich**, jedna **rozbieżność liczbowa do
rozstrzygnięcia**, i osobna sekcja z odpowiedzią na pytanie o wersję na TOP5.

---

## 1. Co cofam u siebie (dwa błędy, oba zmierzone ponownie)

### 1a. „Fałszywe rozpoznanie kosztuje najwyżej 1 akcję" — zdanie było za mocne

Zarzut z audytu Pokemon (WABIT D) jest **słuszny** i mój pomiar to potwierdza na prawdziwym
module (`template_transfer.TemplateTransfer`), nie na opisie:

| model czasu | akcje kontrolera w 240 klatkach | stan |
|---|---:|---|
| komórka przyjmuje kolor na 1 klatkę i wraca (`alternate`) | **120** | bez strażnika = nieograniczone |
| to samo + strażnik 32 akcje/poziom | **32** | limit trzyma, przezbrojenie po zmianie poziomu działa |
| komórka wraca **przed** następną klatką (`instant`) | **1** | `rejected` następuje po pierwszej akcji |

Narzędzie: `arc3_local_candidate/tools/template_oscillation_probe.py` (`--mode alternate|instant`).

Wniosek, który poprawiam w swoim raporcie: ograniczenie „1 akcja" obowiązuje **tylko dla
niezgodności trwałej** (normalny przypadek: klik nie zadziałał). Jeżeli gra ma **przejściowy efekt
kliknięcia** (element wraca), predykcja waliduje się co klatkę, `rejected` **nigdy** nie następuje
i kontrola nie ma żadnego limitu. To nie jest kosmetyka: 120 akcji z 240 klatek zjada wspólny
budżet akcji i czasu, czyli mianownik punktacji i budżet tokenów.

Uwaga o różnicy liczb: peer raportuje **60 akcji w 60 klatkach**, ja **30 w 60** (120 w 240) —
różnica wynika z modelu czasu (u nich klik trafia i wraca w obrębie tej samej klatki, u mnie
komórka trzyma kolor jedną klatkę). **Mechanizm ten sam, wniosek ten sam: bez limitu pętla jest
nieograniczona.** Nie traktuję tego jako sprzeczności.

### 1b. `--gate` w docstringu bez implementacji w CLI — realny błąd mojego narzędzia

Naprawione. `--gate` **nakłada patch tekstowo** na wskazany plik polityki, więc przy okazji
sprawdza, czy `proposals/template-single-mismatch-gate.patch` w ogóle się nakłada (wzorzec musi
wystąpić dokładnie raz, inaczej twardy błąd). Reprodukcja na 300 próbach na rodzinę:

```
rodzina    oryginał            z bramką
copy       149 / 149 (100%)    149 / 149 (100%)
rotate     299 /  18 (6%)       17 /   3 (18%)
invert     300 /   0            0
random     297 /  23 (8%)        8 /   1 (12%)
```

To **liczby identyczne z peer review** (149/149, 17/3, 0, 8/1) uzyskane niezależną implementacją
(bramka zamiast osobnego pliku polityki) — czyli tabela nie zależy od tego, jak patch zaaplikowano.

---

## 2. Co potwierdzam u nich (i sprawdziłem sam)

- **42 testy = 35 + 5 + 2.** Przeliczone: `test_template_transfer.py` 35, `test_groups_and_router.py`
  5, `test_inspection_feedback.py` 2. Dodatkowo `test_template_guarded.py` 2, `test_diagnose_tool_loop.py`
  3, `test_transcript_stats.py` 5 → w katalogu zbiera się 52, a `test_selector_integrity.py` nie
  zbiera się bez `arcengine`. Moje „35/35" dotyczyło jednego pliku i było poprawne, ale niepełne.
- **`final_score: 0` pochodzi z `base_actions_per_level=None`** — zgadza się z tym, co napisałem:
  tego pola nie cytować, wynik bierze się z `result.json` / `rhae_score_pct`.
- **4,8 s zawiera rozpoznawanie w pętli**, nie tylko kliknięcia — mój zapis („controller-only
  4,766 s / 4,813 s") był zgodny; nie twierdziłem nic o 600×.
- **28,57 to wynik lokalny jednej gry** przy pokryciu 3/6 poziomów — tak, i tak samo napisałem.
- **141,7k → 186k = +31,3 %** (nie 16 %) — arytmetyka się zgadza, to błąd innego audytu.
- **Pochodzenie bazy `template`**: dokładnie odzyskana **v3**, nie v13.x — zgoda; ja weryfikowałem
  to od strony bajtowej (3 patche bazowe identyczne, +1 `codex-template.patch`).

---

## 3. Jedna rozbieżność liczbowa, której nikt nie rozstrzygnął: formuła RHAE

- peer: `min((baseline/akcje)², 1.15)`,
- ja: `min(baseline/akcje, 1)` z wagą poziomu = numer poziomu, suma / 21.

**Test rozstrzygający, dostępny w ich własnych danych:** punkt kontrolny jednego poziomu
(`1 × 1/21`) daje **4,76** w wersji liniowej. Wersja kwadratowa z capem 1,15 dałaby
`1,15/21 = 5,48`. Zarejestrowany wynik to 4,76 → **wersja liniowa jest zgodna z danymi, kwadratowa
nie**. Ale to nadal domysł co do implementacji, bo `arcprize/ARC-AGI-3` zwraca **404** (sprawdzone
dziś), a `arcengine` pozostaje niedostępny. Dla ft09: 3 poziomy = **28,571 %** (liniowa) vs
**32,857 %** (kwadrat + 1,15). Do decyzji: nigdzie nie cytować tych liczb bez założenia formuły.

---

## 4. Czego nikt nie zmierzył (stan na dziś)

1. **Prawdziwej gry z oscylacją** — wszystkie wabiki (mój i peer) są syntetyczne.
2. **Kosztu strażnika 32 na grach wymagających >32 akcji kontrolera** — nieznany; dlatego strażnik
   musi być przełącznikiem (`ARC3_TEMPLATE_ACTION_GUARD=32`), nie stałą.
3. **Zachowania hybrydy z docelowym serwerem** (Flash-Next/SGLang) — pakiet sam tego nie ukrywa.
4. **Wpływu któregokolwiek z patchy na wynik Kaggle** — zero pomiarów, i tak ma zostać do osobnej zgody.

---

## 5. „Jaką lepszą wersję zrobisz, która będzie w TOP5?" — odpowiedź bez obietnic

### 5a. Arytmetyka, która przesądza sprawę

Z `TOP10-RESEARCH-20261030.md` (odczyt leaderboardu 30.10, nie moja estymacja):

| miejsce | zespół | punkty |
|---|---|---:|
| 1 | Yi-Chia Chen @ Fields Model | **75,56** |
| 2 | Tufa Labs | **70,02** |
| 5 | the last dance | **51,51** |
| 10 | 復活の混テキスト | **46,82** |

Nasze najlepsze: **26,25**. Do TOP5 brakuje **~25 pkt, czyli ~2×**.

Kontroler szablonowy na ft09 daje 28,57 % **jednej** gry. Przy ~110 grach w zestawie i średniej
po grach to **≈0,26 pkt** całości. Gdyby nawet odpalał idealnie na **wszystkich 25** publicznych
grachach, to nadal rząd **~6 pkt**, nie 25. **Dopieszczanie szablonu nie może dać TOP5 — to nie
kwestia jakości patcha, tylko pokrycia.** Każdy, kto obiecuje TOP5 z tej ścieżki, myli „3 vs 0 na
jednej grze" z wynikiem konkursowym.

Przeliczenie celu: 26,25 % ≈ ~2,6 pkt poziomowego na grę (z 21), 51,51 % ≈ ~10,8 z 21. Realny cel
na TOP5 to **mniej więcej podwojenie liczby poziomów na grę**, a nie lepsze rozpoznawanie paneli.

### 5b. Co zbuduję — w kolejności zmierzonej wartości, nie w kolejności „fajności"

**Krok 1 — `v18-arena` (bezpieczna kompozycja, nie wzrost wyniku).**
`v13.7-final` + szablon za przełącznikiem + bramka single-mismatch + strażnik akcji na poziom
(z przezbrojeniem) + idempotentny `install()` + `should_stop()` w oryginalnej kolejności.
Kryteria akceptacji, wszystkie mierzalne offline: **25/25 śladów bez zmian**, ft09 **3 poziomy /
25 akcji**, bramka 0 fałszywych na `invert`, strażnik trzyma i przezbraja (test w tym repo).
Oczekiwany zysk punktowy: **0 do +0,26**. To jest ubezpieczenie 26,25, nie dźwignia.

**Krok 2 — pamięć rozwiązanych poziomów + poprawka przycinania historii (dźwignia z dowodem).**
Jedyna publiczna technika z wynikiem **bezpośrednio nad naszym**: notebook `lalalia` deklaruje
**31,46** i opisuje patch pamięci, aktualizowany wtedy, gdy przycinanie historii wymusza ponowny
odczyt. To **+5,2 pkt** względem naszych 26,25 i jest to zmiana pamięci/budżetu, którą da się
zmierzyć offline na naszych nagranych trace'ach (tokeny na grę, liczba ponownych odczytów,
liczba poziomów). To mój kandydat numer jeden na „lepszą wersję".

**Krok 3 — przepustowość serwowania.** Publiczny opis Keitha Tysera (starszy wariant): 114 → 236
tok/s i lokalny wynik 3,23 → 6,76 — czyli u autora **~2× przepływności ≈ ~2× wyniku**. Zespół
„faster machine is all you need" jest **3.** z 58,59. To jedyna znana dźwignia o skali potrzebnej
do TOP5, ale **nie zmierzę jej w tym środowisku** — potrzebny docelowy serwer i zgoda.

**Krok 4 — szerokość mechanizmów symbolicznych** (biblioteka reguł: obrót/odbicie/permutacja
kolorów/AND-OR itd. z wymogiem dokładnej zgodności na wszystkich panelach). Ma sens inżyniersko,
ale przy pokryciu 1/25 gier to **nadal rząd pojedynczych punktów**.

### 5c. Czego nie zrobię

- **Nie powiem „ta wersja będzie w TOP5"** — nie mam na to dowodu, a arytmetyka z 5a mówi, że
  zmiany, które mogę zweryfikować offline, dają najwyżej pojedyncze punkty.
- **Nie zgłoszę notebooka** bez osobnej zgody i nie policzę „przewidywanych +0,26/+0,3 pkt" jako wyniku.
- **Nie nazwę jednostkowych testów wzrostem wyniku** — testy chronią przed regresją, nie punktują.

### 5d. Co realnie może dać TOP5 (i czego do tego potrzebuję)

Warunek konieczny: **~2× poziomów na grę** (z ~1,7 na ~3,4 średnio). To problem długiego horyzontu:
utrzymanie kontekstu, pamięć stanu gry i dyscyplina budżetu, nie rozpoznawanie szablonów. Dlatego
kolejność 1→2→3 powyżej, a nie odwrotnie. Do kroku 3 potrzebuję docelowego serwera i zgody na
pomiary; do kroku 2 wystarczy to repo i nagrane trace'y.

---

## 6. Stan artefaktów po tej rundzie

- `tools/template_false_positive_probe.py` — `--gate` zaimplementowany i zweryfikowany (tabela §1b).
- `tools/template_oscillation_probe.py` — nowy: pętla oscylacji + strażnik + przezbrojenie (§1a).
- `proposals/template-single-mismatch-gate.patch` — bez zmian, aplikuje się na `template_transfer.py`.
- Raport z 31.10 — poprawiony w §8 (cofnięcie zdania o jednej akcji).
- Nic nie zgłoszono, nic nie wysłano na Kaggle, żadnej zmiany w cudzych gałęziach.
