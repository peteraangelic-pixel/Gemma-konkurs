# Skąd wziąć pomiar — drabina przyrządów i co każdy rozstrzyga

Pytanie: „bo nie mam na to pomiaru — a skąd go wziąć?”. Poniżej cztery poziomy, od darmowego
do płatnego slotem, z **granicą rozdzielczości** każdego z nich. Kluczowa teza:

> Nie brakuje nam slotu. Brakuje nam **harnessu Ducka uruchomionego lokalnie z tanim modelem**.
> Slot mierzy z szumem ±2 pkt, a wartość v17 to +0,26…2,6 pkt — czyli **slot tej liczby nie zmierzy,
> nawet gdybyśmy mieli ich dziesięć**.

---

## 0. Zasada: mierz w jednostce, w której się punktuje

Reguła: `score = min(Σ s·w / Σ w, 100 × pokrycie)`, `s = min(115, (baseline/akcje)²·100)`
na **ukończony** poziom. Czyli jedyna jednostka, która cokolwiek znaczy, to
**ukończone poziomy na grę** (i ich koszt w akcjach). Akcje, tokeny i sekundy to koszty pośrednie.

Wniosek praktyczny: każdy pomiar niżej kończy się liczbą **poziomów/gre**, nie akcji.

---

## M0 — przyrząd deterministyczny (darmowy, **zrobiony**)

`bash tools/bootstrap_engine.sh` odtwarza silnik od zera z publicznych źródeł (2 wheele z PyPI
+ 25 gier z gałęzi Smaka), w ~4 s, i robi smoke na ft09. To znaczy, że pomiar jest powtarzalny
także po restarcie sandboxa (`/tmp` **nie** persystuje — poprzednia sesja to pokazała).

Co mierzy: zachowanie **samego kontrolera** na 25 grach publicznych, bez LLM. Zmierzone 31.10:

| gra | akcje kontrolera | poziomy | `cap_hits` | ms/akcję |
|---|---:|---:|---:|---:|
| ft09 | 25 | **3** | 0 | 1,4 |
| pozostałe 24 | **0** | 0 | 0 | — |

- abstynencja na 24/24 grach innych niż ft09 → kontroler **nie zabiera** akcji tam, gdzie nie umie;
- 1,4 ms vs **12,9 s** na akcję w r085 (LLM) → ~9000× taniej na krok; koszt czasu ≈ 0;
- bezpiecznik 32/poziom **nigdy nie trafił** → nie jest dźwignią, jest ubezpieczeniem.

Czego **nie** rozstrzyga: zachowania na ukrytym rostere (110 gier), interakcji z LLM
(czy fallback po abstynencji kosztuje turę) i **w ogóle wyniku** (poziomów nie da się przeliczyć
na punkty bez danych o rosterze).

## M1 — arytmetyka wyniku (darmowa, **zrobiona**)

Mamy per-grową tabelę r085 (10 gier dev, `PLAN-50.md` §2.2) i to, że r085 ↔ oficjalne **26,25**.
`leverage.py` liczy dokładnie tę formułę, którą rozlicza Kaggle (32/32 zapisanych `final_score`
odtworzone przez `verify_scoring.py`). Z tego: „+1 poziom na jednej grze w rostere” = **+0,26…2,6 pkt**
w zależności od liczby poziomów tej gry i tego, czy jest ograniczona pokryciem.

Czego **nie** rozstrzyga: **czy ft09-podobna gra jest w 110-growym rosterze i ile ich jest**.
Tej liczby nie ma w żadnym publicznym źródle — 25 gier publicznych to inny zbiór niż roster.

## M2 — shadow run z LLM-em na lokalnym silniku (darmowy poza tokenami; **to jest brakujący przyrząd**)

To jedyny przyrząd, który rozstrzyga „czy kontroler pomaga/szkodzi, gdy w pętli jest LLM”.
Wymaga dwóch rzeczy, których **nie ma w tym repo**:

1. harnessu Ducka (`ARC3-Inference`, ten sam, który notebook instaluje z datasetu) — da się go
   wyjąć z outputu notebooka;
2. jednego taniego endpointu modelu (najlepiej ten sam 8B — inny model zmienia 12,9 s/akcję
   i porównanie przestaje być sparowane).

Projekt (sparowany, deterministyczny po stronie kontrolera):

```
dla każdej z 25 gier publicznych, seed 731, budżet 200 akcji:
  A: ARC3_TEMPLATE=0  → zapisz pełny trakt (klatka, akcja) → levels_A
  B: ARC3_TEMPLATE=1  → ten sam seed i budżet          → levels_B
  log per gra: hijack_games, akcje kontrolera, akcje LLM, sekundy
Δlevels = Σ(levels_B − levels_A) / 25
```

Bo kontroler jest deterministyczny, różnica pochodzi **tylko** z hijacków — więc Δ jest
interpretowalne (w przeciwieństwie do różnicy dwóch przebiegów LLM). Koszt: 25 gier × 2 ramiona
× ~200 akcji; przy 27B to godziny, przy 8B ~2–4 h.

## M3 — prawdziwa submisja A/B (1 slot na ramię, 3 h, **wymaga GO i Kaggle**)

Mierzy to, czego nie zmierzy nic innego: zachowanie na **prawdziwym rostere 110 gier**.
Ale rozdzielczość jest fatalna:

| Δ, którą chcemy wykryć | σ proxy (r085 ↔ LB) | potrzebne przebiegi na ramię |
|---|---:|---:|
| 0,26 pkt (v17, 1 gra) | ~2 pkt | **~118** |
| 2,6 pkt (v17, sufit) | ~2 pkt | ~2 (na granicy szumu) |
| ≥ 5 pkt | ~2 pkt | 2 |
| ≥ 25 pkt (TOP5) | ~2 pkt | 1 (widać od razu) |

Czytanie: **małe dźwignie są niemierzalne przez slot, duże są mierzalne od razu.** Dlatego
pytanie „TOP5?” nie potrzebuje submisji — potrzebuje jednego lokalnego przebiegu, w którym
widać +1,5 poziomu na grę. A pytanie „czy v17 nie psuje championa?” potrzebuje M2, nie M3.

Gdyby jednak slot leciał: z outputu kernela bierzemy `benchmark.json` i liczymy
`python3 ARC3/local-lab/analyze_run.py benchmark.json --target 50` oraz
`python3 ARC3/local-lab/leverage.py benchmark.json`; parowanie po `game_id`, nie po średniej.

---

## Reguła decyzyjna dla v17 (ustalona **przed** pomiarem)

1. M0: hijack na grach nie-copy = **0/24** → warunek wstępny spełniony.
2. M2: jeśli `Δlevels ≥ 0` na 25 grach **i** żadna gra nie traci poziomu → v17 idzie jako
   **poprawka bezpieczeństwa championa** (`ARC3_TEMPLATE=1`).
   Jeśli którakolwiek gra traci poziom → zostaje `ARC3_TEMPLATE=0` i v17 nie jedzie wcale.
3. M3 tylko jako check „czy nie ma katastrofy”; **nie** jako dowód zysku.
4. TOP5: nie jest decyzją o v17. Wymaga nowej dźwigni ≥ +1,5 poziomu/gre, której nie ma
   w żadnej z pięciu gałęzi — i to jest jedyny powód, dla którego „nie mam pomiaru na TOP5”
   jest zdaniem prawdziwym, a nie wymówką.

---

## Czego tu nie da się uruchomić (sprawdzone, nie założone)

- **kaggle.com jest nieosiągalny z tego sandboxa** (`curl https://www.kaggle.com` → kod 000;
  brak `~/.kaggle`), więc M3 musi puścić człowiek albo inny runner.
- **brak kluczy do modelu** → M2 trzeba puścić tam, gdzie są sekrety (Kaggle secrets / Twoja maszyna).
- `/tmp` nie persystuje → dlatego `bootstrap_engine.sh` jest w repo, a nie „w głowie”.
