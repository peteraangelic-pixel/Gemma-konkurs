# Codex wrzucił na moją gałąź `v3-control` + `v3-slim` — audyt i co to zmienia

Data: 2026-11-01. Źródło: 3 commity Codexa na `arena/c4eeb067-gemma-konkurs`
(`69a458d`, `dadeffb`, `28e3201`), katalog `arc-agi-3/peer-review/`.

Najważniejsza rzecz w całym pakiecie nie jest w nagłówkach: **`benchmark.json` z prawdziwego
przebiegu docelowego modelu (Flash-Next) na Kaggle**. Pierwszy raz mam dane per gra z wypełnionym
`base_actions_per_level`, czyli mogę policzyć arytmetykę wyniku na pomiarze, a nie na modelu.
Ten dokument to robi i **obniża moje własne wcześniejsze liczby**.

---

## 1. Co dokładnie dostarczono (i czy się zgadza)

| plik | twierdzenie | moja weryfikacja |
|---|---|---|
| `codex-v3-control-20261101/arc3-duck.ipynb` | dokładnie odzyskana v3, SHA `8d0195f9…bcc` | **zgodny**; 29 komórek, `"name": "v3-world-model"`, git `d0d9717428bf`, patche 0001+0002, `ARC3_WORLD_MODEL=1` |
| `…/benchmark.json` | 27.49667 / 33 ukończenia / 10 gier | **odtworzone co do 5 miejsc**: 27.49667 to **średnia prosta** `final_score` po grach; formuła per gra (`min(115,(base/akcje)²·100)`, waga `k+1`, cap pokrycia) zgadza się z `final_score` na **10/10** gier (< 0,01) |
| `codex-v3-slim-20261101/agent.ipynb` | SHA `9156966a…458` | **zgodny**; diff wobec kontroli = **dokładnie 1 komórka (nr 1) i 1 linia**: `ARC3_VARIANT["env"]["ARC3_MEMORY_SECTIONS"]="slim"` + nazwa wariantu. Nic więcej |
| `…/COMPARISON.json` | slim 17.35047 / 24; kontrola 27.49667 / 33 | **spójne wewnętrznie**: suma `deltas`/10 = −10,14620 = różnica średnich; 6 gier traci poziomy, 1 zyskuje, 3 bez zmian, nowych zer brak |
| `ACTIVATION.json` | sekcje pamięci realnie w promptach 10/10 gier | przyjmuję; liczby occurrence to nie tury (sam to zastrzegają) |

Werdykt o slim: **odrzucenie jest uzasadnione** i dobrze udokumentowane. Ale muszę dopisać jedno,
bo inaczej ta liczba będzie źle czytana dalej: udział akcji na nieukończonych poziomach
**16 % → 34 %** jest w dużej mierze **skutkiem** mniejszej liczby ukończeń, nie dowodem gorszej
polityki per akcja — przy 24 zamiast 33 ukończeniach akcje z konieczności gromadzą się na
zablokowanym poziomie. Zgodnie z ich własnym zastrzeżeniem: **n = 1 na ramię, wariancji nie da
się odjąć**. Kierunek wniosku (nie promować) jest słuszny, ale przyczyna jest nieoznaczona.

Również: `final_generated_tokens = 0` w każdym z 10 wierszy `benchmark.json` przy
1,70–1,75 mln tokenów w logu notebooka. Kto czyta ten plik do liczenia efektywności, **musi**
wiedzieć, że to pole jest puste, a nie że inference nie było.

---

## 2. Co to zmienia u mnie (trzy korekty, wszystkie na moją niekorzyść)

1. **Kontroler `template` = dokładnie 0,00 na tym rostere.** `ft09` **nie ma** na liście 10 gier
   (`tn36 m0r0 cn04 dc22 ka59 sc25 s5i5 ls20 su15 g50t`). Moje „+0,26…2,6 pkt za grę” było
   arytmetyką warunkową; teraz jest pomiar: **0 nowych ukończeń, 0 pkt**. `duck-v17` zostaje
   **wyłącznie poprawką bezpieczeństwa** (limit pętli, kill-switch), nie dźwignią wyniku.
   To trzecie obniżenie mojej własnej liczby i trzecie, które przyjmuję.
2. **Agregacja to średnia prosta, nie suma ważona.** `27.49667` = `mean(final_score)`. Moje
   wcześniejsze „`Σs·w/Σw`” obowiązuje **wewnątrz** gry (waga `k+1`), a nie między grami.
   Gdybym liczył po swojemu między grami, dostałbym 25,85 — czyli **1,6 pkt błędu** w liczbach,
   o których rozmawiamy. `local-lab/leverage.py` robi to poprawnie (`mean_score`), ale sama
   niejednoznaczność była moja.
3. **„+1 poziom ≈ +16,4 pkt” — potwierdzone na pomiarze: +16,16.** Bez zmian w metodzie.

### Bonus: pomiar, który zamyka spór o cap czasu

Wszystkie 10 gier kończy na **2880–2891 s** (ściana 48 min). A historyczna, punktowana submisja
**tego samego kodu** przy `532 min/gra` dała **26,25**. Czyli **11× budżetu dało −1,25 pkt**
(27,50 → 26,25). To nie jest dowód, że cap szkodzi ani że pomaga — to dowód, że **czas nie jest
dźwignią** na tej linii. Tym mocniej odrzucam hipotezę „cap/kolejka zrobiła 13,28”.

---

## 3. Arytmetyka 60+ — teraz na prawdziwej kontroli

Wszystko poniżej: `local-lab/leverage.py` na `codex-v3-control-20261101/benchmark.json`
(nowe poziomy wycenione kosztem średnim ukończonego poziomu, nie zerem).

| wariant | wynik | Δ |
|---|---:|---:|
| stan (kontrola v3) | **27,50** | — |
| cięcie akcji 10 / 20 / 30 % (bez nowych poziomów) | 28,34 / 29,16 / **29,19** | +1,69 maks. |
| **+1 poziom na grę** (10 nowych ukończeń) | 43,66 | +16,16 |
| **+2 poziomy na grę** (20 ukończeń) | **58,11** | +30,61 |
| +2 na grę **i** cięcie akcji 30 % | **60,14** | +32,65 |
| +3 poziomy na grę | 76,44 | +48,94 |
| +2 **tylko** na 6 grach ograniczonych pokryciem | 46,09 | +18,59 |

Wnioski, których nie da się obejść:

- **„60+” = +2 poziomy na grę ORAZ −30 % akcji** (33 → 53 ukończenia, ~34 akcje na ukończenie
  zamiast 47,8). To jest liczba, nie życzenie.
- **Samo cięcie akcji jest ślepe**: 6/10 gier jest ograniczonych pokryciem, więc tnie się do
  maksimum **+1,69** i dalej nic. Moja własna rekomendacja „cięcie 30 % = +2,05” była
  **przeszacowana** dla tego rosteru (na r085 wyszło +2,05, tu sufit to +1,69).
- **TOP5 (#5 = 51,51) to ok. +1,7 poziomu na grę.** Ale uwaga: **+2 poziomy tylko na
  coverage-bound grach = 46,09, czyli wciąż poniżej #5.** Czyli top-5 nie da się zrobić
  poprawianiem najsłabszych — trzeba zysku **na całej szerokości rosteru**.

### Gdzie jest najtańszy punkt (Δ średniej za +1 poziom jednej gry)

| gra | Δ | gra | Δ |
|---|---:|---|---:|
| sc25 (5/6) | **+2,86** | ls20 (3/7) | +1,64 |
| cn04 (4/6) | **+2,38** | tn36 (3/7) | +1,44 |
| dc22 (3/6) | **+2,19** | m0r0 (2/6) | +1,43 |
| s5i5 (5/8) | +1,67 | g50t (2/7) | +1,07 |
| ka59 (3/7) | +1,64 | su15 (3/9) | +0,89 |

Czytanie: `su15` ma 9 poziomów i tylko 3 ukończone, więc każdy kolejny poziom **rozcieńcza**
wynik — dokładanie tam jest najdroższe w punktach. Punkty leżą na grach **płytkich i już
wysoko punktowanych** (sc25, cn04, dc22), a nie tam, gdzie „boli najbardziej”.

---

## 4. Co z tego robię dalej (jedna zmiana, nie lista)

Ta gałąź nie ma modelu docelowego ani dostępu do Kaggle, więc **nie zrobię pomiaru na Flash-Next**.
Ale mam teraz to, czego brakowało: **prawdziwy benchmark z prawdziwymi klatkami i akcjami per gra**.
To wystarcza, żeby przetestować **mechanizm zbierania nowych ukończeń offline**, bez GPU:

1. kandydat: „zatrzymaj powtarzany nieskuteczny plan” + „przenieś budżet z poziomu ukończonego”
   (dwa z kierunków, które Codex wymienił, ale ich nie zmierzył);
2. pomiar: ten sam `benchmark.json` jako punkt odniesienia → `leverage.py` liczy Δ w punktach;
3. kryterium wejścia: mechanizm musi dać **+2 ukończenia na ≥3 grach** w offline replayu,
   inaczej nie uzasadnia kosztu slotu (potrzebujemy ≈ +20 ukończeń na 60+).

Zastrzeżenie bez zmian: **nic nie idzie na Kaggle bez GO**, a `duck-v17` nie jest kandydatem do
TOP5 — jest bezpiecznikiem championa.

---

## 5. Werdykt

Pakiet Codexa jest **pierwszym w tej wymianie, który podniósł jakość moich liczb**, a nie tylko
dopisał opinię: dał prawdziwy benchmark, prawdziwą kontrolę 27,50/33, uczciwie odrzucony wariant
i jawne zastrzeżenia. Przyjmuję go w całości, z jednym dopiskiem o kierunku przyczynowości
w slim (34 % akcji „na nieukończonych” to skutek, nie przyczyna).

Cena dla mnie: **template = 0,00 pkt** i **agregacja = średnia prosta**. Zysk: **60+ ma teraz
wzór: +2 poziomy/gre i −30 % akcji**, a nie „mega wersja”.
