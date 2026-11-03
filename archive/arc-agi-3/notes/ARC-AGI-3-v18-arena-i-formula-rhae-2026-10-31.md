# v18-arena + rozstrzygnięcie formuły RHAE na prawdziwych danych (31.10.2026)

Wszystko poniżej jest zmierzone w tym środowisku, offline, bez Kaggle i bez zmiany cudzych gałęzi.
Wejście: gałąź Smaka `codex/arc-local-lab-v18-20261030` @ `3926007` (read-only, pobrana jako tarball),
cztery zapisane przebiegi z `arc3_local_candidate/fixtures/benchmarks/`, trzy prawdziwe klatki ft09.

---

## 1. v18-arena — co zbudowałem i co to daje

`arc3_local_candidate/v18-arena/` — build + zestaw akceptacyjny (`build_v18.py`, `verify_v18.py`).
Trzy zmiany na kontrolerze szablonowym, każda za przełącznikiem, każda neutralna domyślnie:

| # | zmiana | dowód |
|---|---|---|
| 0012 bramka single-mismatch | fałszywe rozpoznania −94…−100 %, `copy` bez zmian | 300 prób/rodzinę |
| 0013 strażnik 32 akcji/poziom | oscylacja 120 → 32 akcje, przezbrojenie OK | 240 klatek |
| 0014 bezpieczny hook | `install()` idempotentny, `should_stop` → oryginał, kill-switch | stub tool-agenta |

Weryfikacja: **7 kontroli, wszystkie przechodzą**, `WERDYKT: OK`. Testy modułu: **37/37**
(35 + 2 z `test_template_guarded.py`), także przy włączonych przełącznikach.

**Neutralność domyślna** (najważniejsza liczba w całym pakunku): bez zmiennych środowiskowych
v18 podejmuje **identyczne decyzje** co oryginał — 0 rozbieżności na trzech klatkach ft09
i **0 na 400 planszach syntetycznych** (4 rodziny × 100). Czyli włączenie tego kodu nie zmienia
niczego, dopóki nie ustawisz przełącznika.

Na ft09, pod każdą kombinacją przełączników, akcje startowe zostają:
`(6,39,39)`, `(6,23,17)`, `(6,23,7)` — domyślnie, z bramką, ze strażnikiem i z oboma.

## 2. Mój własny pomysł z §7 raportu — ODRZUCONY przez pomiar

Proponowałem „detektor zmiany mechaniki": jeśli poziom N+1 daje inne mapowanie symbol→wartość niż
zapamiętane, wyzeruj `learned`. Sprawdziłem to na prawdziwych klatkach ft09:

| poziom | mapowanie odtworzone z BIEŻĄCEJ klatki | `learned` z poziomu 1 | zgodne? |
|---|---|---|---|
| L2 | `{0:9, 2:9}` | `{2:9, 0:8}` | **nie** |
| L3 | `{0:8, 2:8}` | `{2:9, 0:8}` | **nie** |

Oba odtworzenia są **zdegenerowane** (dwa symbole → jedna wartość), bo panele nowego poziomu nie
niosą już informacji, którą `learned` przenosi. Detektor odrzuciłby `learned` **dokładnie na tych
dwóch poziomach, na których polega cały wynik 3 vs 0** → abstynencja → **1 poziom zamiast 3**
(28,57 → 4,76). Mechanizm, który nazwałem ryzykiem, jest tym samym mechanizmem, który daje wynik.
Wniosek: przenoszenie `learned` zostaje bez zmian, a bezpieczeństwo zapewnia strażnik akcji (0013),
nie detektor.

## 3. Realny konflikt integracji, którego nikt nie zgłosił

Strażnik w klasie bazowej i podklasa `GuardedTemplateTransfer` (peer) używały tej samej nazwy
pola `level_actions` → każda akcja liczyła się **dwa razy** i cap 32 zjeżdżał do **16** (zmierzone:
ich własny test `test_observed_oscillation_stops_at_cap...` dawał `16 != 32`). Poprawka: pola
`_arm_*` + kontrola `[7]` w `verify_v18.py`, która pilnuje, że po nałożeniu obu strażników cap
zostaje **32**. Po poprawce ich testy przechodzą w komplecie.

## 4. Formuła RHAE — **rozstrzygnięta**, i nie po mojej stronie

W poprzedniej notatce napisałem, że punkt kontrolny 4,76 pasuje do wersji **liniowej**, a nie
kwadratowej. To było błędne: przy akcjach poniżej baseline obie wersje są przycinane przez
**cap ukończeń** `Σ_{i≤n} i / (N(N+1)/2)`, więc 4,76 (= 1/21) **nie rozróżnia** tych formuł.
Rozstrzyga gra, w której agent przekracza baseline. `m0r0-492f87ba` w przebiegu `r085`:

```
baseline [30, 111, 203, 26, 500, 237]   akcje [22, 41, 94, 31, 64, 0]   ukończone 4
liniowa        = 44,5469
kwadratowa     = 46,2559   <-- zgodna z zapisanym wynikiem 46,255884247559585
cap ukończeń   = 47,6190
```

Czyli: `poziom = min(1,15, (baseline/akcje)²)`, waga = numer poziomu, suma / `N(N+1)/2`.
Mój `scorecard.py` w tym repo implementuje dokładnie to i na czterech przebiegach (40 gier)
odtwarza zapisane wyniki **z zerową niezgodnością** — audyt scorecard jest więc potwierdzony,
a nie tylko „spójny".

## 5. Gdzie naprawdę jest wynik — rozkład na cztery przebiegi

Te same 10 gier, 69 poziomów, cztery wersje tej samej linii:

| przebieg | ukończone poziomy | wynik | cap ukończeń | strata na nieefektywności |
|---|---:|---:|---:|---:|
| `r085` | 32 / 69 | **26,78** | 29,79 | **3,00 (10 %)** |
| `r093` | 27 / 69 | 18,55 | 23,45 | 4,91 (21 %) |
| `r110` | 4 / 69 | 0,73 | 1,41 | 0,68 |
| `r118` | 2 / 69 | 0,27 | 0,58 | 0,31 |

**Wniosek operacyjny:** ~80–90 % wyniku to **liczba ukończonych poziomów** (ważona numerem
poziomu); efektywność akcji to korekta **10–20 %** i działa tylko na poziomach, gdzie przekraczamy
baseline (w `r085` 11 z 32 ukończonych). To dokładnie odwrotność tego, co sugerowała nazwa
„action efficiency" w naszych wcześniejszych notatkach — warto to mieć w jednym miejscu.

Przełożenie na pytanie o TOP5 (bez zmiany wcześniejszych liczb): TOP5 = 51,51 pkt przy naszym
26,25. Skoro wynik ≈ cap ukończeń, cel to **~2× ukończonych poziomów na grę**, a nie lepsze
klikanie. Kontroler szablonowy daje 3 poziomy **jednej** gry (0,26 pkt całości) — nawet idealny
na 25 grachach to rząd 6 pkt. Kolejność: ubezpieczenie (v18) → szerokość ukończeń (pamięć/replay
i budżet) → przepustowość serwowania.

## 6. Krok 2 (pamięć poziomów) — co ustaliłem, zanim cokolwiek zbuduję

1. **Pamięć rozwiązanych poziomów już mamy**: patch `0006-winpath-replay` w bazie v13.7 to
   dokładnie ten mechanizm (zapis sekwencji + weryfikacja klatka po klatce).
2. Publiczny wynik 31,46 (`lalalia`) dotyczy **kosztu odczytu przy przycinaniu historii**, nie
   samej pamięci. Tego kosztu **nie da się u nas zmierzyć**: we wszystkich czterech przebiegach
   pole `uncached_input_tokens` = **0** (40/40 gier), więc przycinanie nie jest instrumentowane.

**Wniosek:** zanim dodam „cache-conscious memory", trzeba najpierw **zainstrumentować** ponowny
odczyt (ile tokenów wchodzi bez trafienia w cache), bo inaczej nie odróżnię zysku od szumu.
To jest konkretne, tanie zadanie na następny krok i warunek sensownego pomiaru dźwigni +5 pkt.

## 7. Stan i granice

- Zbudowane i sprawdzone: `arc3_local_candidate/v18-arena/` (build, verify, diff, raport).
- Nie zmieniono żadnego pliku w repo Smaka; nic nie zgłoszono; żadnej nowej serii LLM.
- Nietknięte: `gemma4-agent/` (58 plików), `arc3_local_candidate/v17-arena-dyn/`.
- Wersja v18 **nie była uruchomiona na silniku** — brak `arcengine` (sprawdzone wcześniej,
  nie do obejścia). Wszystkie dowody są offline: prawdziwe klatki + prawdziwy moduł + stub hooka.

## 8. Korekta poprzednich notatek

- `notes/ARC-AGI-3-odpowiedz-na-audyty-2026-10-31.md` §3: punkt kontrolny 4,76 **nie rozstrzyga**
  liniowa vs kwadratowa — rozstrzyga `m0r0` (§4 wyżej), i wskazuje kwadratową. Poprawione.
- `notes/ARC-AGI-3-audit-template-controller-2026-10-31.md` §7 pkt 4: „detektor zmiany mechaniki"
  jako następna zdolność — **wycofane** przez pomiar z §2.
