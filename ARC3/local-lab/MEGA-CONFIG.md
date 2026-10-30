# MEGA-CONFIG — konkretna delta do v12 (baza 26,78), bez zmiany modelu

Wszystko poniżej to **zmiany konfiguracji**, nie nowy kod agenta. Kolejność = kolejność
wdrażania; każda ma własny oczekiwany zysk z pomiaru (`PLAN-50.md` §2.3 i §4).

Baza: `arc3-duck-v12` (bajty c45 + 2 linie concurrency). Baza pomiarowa: smoke 26,78.
Model: **8B, linia szybka** — nie 27B (zmierzone: −26,5).

---

## 1. ~~Okno czasu na grę~~ — **KOREKTA (29.10, po sprawdzeniu v13)**

Pierwotna wersja tego punktu twierdziła, że dźwignią jest podniesienie
`max_runtime_s_per_game` z 48 min. **To było błędne** i wynikało z czytania dev-smoke'a
jako submitu. Sprawdzone w notatniku v13 (cell 21):

```python
bm.n_passes = 4
if TRUE_SUBMISSION:
    bm.n_passes = 1
    bm.solver.concurrency = 10
    bm.solver.max_runtime_s_per_game = 532*60      # 8,9 h — cap jest, ale nie wiąże
```

Arytmetyka prawdziwego submitu:

| element | wartość |
|---|---|
| budżet notatnika | 32 400 s (9 h), asercja w kodzie |
| roster | 110 gier |
| concurrency (backend MAXREQ) | 10 |
| fal | 110 / 10 = **11** |
| efektywny czas na grę | 32 400 / 11 = **2 945 s ≈ 49 min** |

Czyli cap 532 min **nigdy nie wiąże** — wiąże liczba fal. Podnoszenie go nic nie daje.
Tym, co realnie wyznacza akcje na grę, jest **sekundy na akcję**:

```
akcje/gę = 2945 s / (s na akcję)
```

a `s/akcja` jest w każdym runie **liniowe w tokenach na akcję** (r = 0,99–1,00 na 10 grach):

| run | silnik | ms na token | mediana tok/akcję | s/akcję | akcje/gę (49 min) |
|---|---|---|---|---|---|
| r085 | 8B, bez capa | **17,2** | 647 | 12,9 | **228** |
| r110 | 8B, v13 cap 45k | 62,6 | 572 | 36,0 | 82 |
| r118 | 27B | 63,1 | 686 | 47,0 | 63 |

Dwie dźwignie, obie widoczne w tej tabeli:
1. **mniej tokenów na akcję** (mózg treściwszy: cap outputu, krótsze analizy),
2. **lepszy silnik** — ten sam model 8B ma 17,2 vs 62,6 ms/token w dwóch runach, czyli
   3,6× różnicy nie pochodzi z modelu ani z promptu.

Cel: 400+ akcji/gę wymaga ~370 tok/akcję przy r085-owym silniku; 600 akcji wymaga ~230.

## 2. Capy poddawania się — skalowane wagą poziomu

Dziś (domyślnie w c45/v12), wszystkie trzy działają jak „poddaj się po ~1 poziomie":

```
C45_LEVEL_TOKEN_CAP=40000
ARC3_ABANDON_TOKENS=60000
ARC3_STUCK_AUDIT_TOKENS=60000
ARC3_ABANDON_MIN_LEVELS=0
```

Poziom k płaci k jednostek, więc budżet na poziom powinien rosnąć z k:

```python
# w komórce, która ustawia C45 (przed importem harnessu)
os.environ["C45_LEVEL_TOKEN_CAP"] = str(40000)      # cap bazowy
os.environ["ARC3_LEVEL_TOKEN_CAP_SCALE"] = "k"       # cap_k = 40000*k  (jeśli patch to wspiera)
os.environ["ARC3_ABANDON_TOKENS"] = "0"             # 0 = wyłącz; okno czasu jest limitem
os.environ["ARC3_STUCK_AUDIT_TOKENS"] = "200000"    # audyt, ale nie zabijanie poziomu
os.environ["ARC3_ABANDON_MIN_LEVELS"] = "4"         # nie poddawaj przed 4. poziomem
```

Jeśli patch nie zna `LEVEL_TOKEN_CAP_SCALE`, minimalna wersja: `C45_LEVEL_TOKEN_CAP=120000`
(cap na poziom, nie na grę) + `ARC3_ABANDON_TOKENS=0`.
**Zmierzony punkt odniesienia:** przy *tym samym* budżecie 200 akcji, ale bez porzucania
poziomów w połowie, średnia rośnie 26,8 → 35,6 (+8,8). To najtańsze 9 punktów w całym planie.

## 3. Cap odpowiedzi modelu — 12% paliwa z powrotem

```
LOCAL_ANALYZER_MAX_OUTPUT=12000
```

Dziś 0 = bez capa; p90 = 8 046, max = 61 300 tokenów na turę. Cap 12k ucina 3,8% tur i
oddaje ~12% puli (≈ +24 akcje na grę przy 8B). Uwaga: to nie może iść razem ze zmianą
modelu ani silnika — inaczej nie przypiszesz zysku.

## 4. Watchdog wentyla (chroni przed −19)

Nie jest to optymalizacja „na plus" (+3 maks.), tylko bezpiecznik przed klifem
(2× bazowych akcji na wszystkich poziomach = 26,8 → 7,5). Zasada:

```
jeśli poziom zużył > 2 × baseline_actions i nie ma postępu → RESET poziomu, nie gry
```

`ONLY_RESET_LEVELS=true` **musi** być ustawione przed konstrukcją klienta `arc_agi`
(inaczej RESET cofa do poziomu 1). W r085 dwa takie poziomy (ls20 poz. 3: 222 vs 73;
tn36 poz. 2: 171 vs 72) kosztowały ~25 pkt na tych dwóch grach.

## 5. Bramki GO/NO-GO (lokalne, bez GPU)

Przed wysłaniem slotu, na 10 grach dev:

| bramka | próg | jak sprawdzić |
|---|---|---|
| punktacja nie rozjechana | `verify_scoring.py` = 32/32 | `python3 verify_scoring.py` |
| głębokość | mediana poziomów ≥ 4 | `analyze_run.py benchmark.json` |
| akcje | akcje/gę ≥ 400 | to samo |
| brak głodzenia | 0 gier `cancelled` z < 1,5× baseline na poz. 1–2 | to samo |

Jeśli głębokość nie rośnie, a akcje są ≥ 400 → ściany na poziomach 3+ są **rozumowania, nie
czasu**, i wtedy dalsze dokładanie budżetu nie ma sensu (trzeba zmiany polityki: plan-commit,
otwieracze z kodu gier, głębokość przed szerokością).

## 6. Czego nie robić (zmierzone)

| pomysł | efekt |
|---|---|
| 27B / większy model | −26,5 (0,27 vs 26,78): 47 s/akcję zamiast 12,9 |
| rekonstrukcja patchy v11 | −2,9 (23,89 vs 26,25) |
| cap 45k tokenów na grę | −26,0 (0,73 vs 26,78) |
| gonić efektywność akcji | max +3,0; przy 1,5× baseline już −13,5 |
| search assist jako solver głębokich poziomów | nie skaluje się (patrz `PLAN-50.md` §3.4) |
| `n_passes > 1` / best-of-k | niemożliwe w rerunie (brama daje jedno środowisko na grę) |

## 7. Kolejność slotów (4 pozostałe: 30.10, 31.10, 1.11, 2.11)

1. **slot 30.10** — v12 bez zmian (baza 26,78). Sens: potwierdzić, że linia żyje po 1,18
   i 0,27; bez tego reszta jest zgadywaniem. W logu sprawdzić **ms/token** i `akcje/gę`:
   jeśli wyjdzie ~60 ms/token zamiast ~17, to silnik jest wolny i żadna zmiana polityki
   tego nie naprawi.
2. **slot 31.10** — M1+M2 (okno + capy). Jedna hipoteza: „akcje są wąskim gardłem".
3. **slot 1.11** — M3+M4 na zwycięzcy z (2).
4. **slot 2.11** — najlepsza złożona konfiguracja, wysłana rano, nie wieczorem.

Warunek konieczny każdego slotu: smoke ≥ 26 (baza) **i** akcje/gę ≥ 400 w benchmarku.
