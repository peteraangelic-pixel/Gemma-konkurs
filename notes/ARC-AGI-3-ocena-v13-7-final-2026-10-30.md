# Ocena duck-v13-7-final (Smak, `arena/5ed750ef-…`) — 30.10.2026

Read-only wobec zdalnej gałęzi; wszystko sprawdzone lokalnie, offline, bez Kaggle.
HEAD gałęzi w chwili audytu: **`de57e4d8`** (13:50Z); katalog `arc-agi-3/duck-v13-7-final`.

## 1. Co to jest

`v13-7-final` = `v13-6-final` + **patch 0010 `dyn-level-budget`**, przeniesiony **bajt w bajt**
z handoffu drugiej sesji: sha256 `736b09cf…` identyczny z
`arc-v16-package/patches/0009-dyn-level-budget.patch` (ich numeracja 0009) **oraz** z
`duck-extra-07.patch`, który wyciągnąłem wcześniej z ich notebooka v16-naj.

**DORMANT na submisji**: wariant trzyma `ARC3_LEVEL_TOKEN_CAP: "0"`, a moduł ma
`enabled = static_cap > 0`, więc całe drzewo zachowuje się jak v13.6.

## 2. Co odtworzyłem (a czego nie brałem na słowo)

| twierdzenie | moja kontrola | wynik |
|---|---|---|
| budownik odtwarza notebook | `build_v137_final.py --prev v13.6 … --out …` + `cmp` | **bajt w bajt**: 41 komórek, 758 240 B |
| metadata | `cmp` z wysyłką | identyczne, `petersharps/arc3-duck-v13-7-final` |
| `verify_v13.py --bundle r033 --tests` | uruchomione lokalnie (stuby `requests`/`PIL`) | **ALL CHECKS PASSED** (39 kontroli: 10/10 patchy, kompilacja, 12+6+11 testów, self-pace 22/14, `cmp` rekonstrukcji, 16/16 dyn) |
| „cell-diff vs v13.6 = {1,2,12,14,15,33,40}" | mój własny diff komórek | **dokładnie tak**; poza rejestracją patcha i etykiet `v13.6→v13.7` **żadnej zmiany semantycznej** |
| wariant env nietknięty | porównanie dict `ARC3_VARIANT` | zero różnic env; dochodzi tylko `/kaggle/duck-extra-08.patch` + `0010-dyn-level-budget.patch` |
| uśpienie | audyt różnicowy: moduł z r033 po 0001–0009 vs moduł po 0010, **8 000 decyzji na przypadek**, 5 konfiguracji (CAP=0, DYN_CAP=0 × resety 0/1/3, min_done 0/3) | **identyczne decyzje** (`KEEP_GOING`/`RESET_LEVEL`/`ABANDON`) — dormancja i wierna kontrola A/B potwierdzone |
| wnętrze modułu | czytane: `peek` czyste, `step` jedyny mutujący, RESET darmowy, ABANDON po resetach i ≥1,5× cap i ≥`MIN_DONE` | zgodne z opisem |

Narzędzie: `arc3_local_candidate/tools/audit_dyn_budget.py`
(`benchmarks …` / `logic <pre> <post>`).

## 3. Czy motywacja patcha jest prawdziwa — moje liczby z realnych benchmarków

Korpus: `benchmark.json` z r085/r093/r110/r118 = **40 gier**, tokeny per akcja z historii,
granice poziomów z `actions_per_level`.

**A. Statyczny cap rzeczywiście tnie poziomy, które gra inaczej kończy.** (twierdzenie #1)

| cap | ukończone poziomy droższe niż cap |
|---|---|
| 45 000 | **14** (m.in. g50t 88 114, m0r0 84 597, su15 68 648, dc22 66 607) |
| 60 000 | **13** |
| 90 000 | 1 (su15 91 043) |

To jest **mocny, policzalny argument za patchem**: przy 45k czternaście ukończonych poziomów
zostałoby przerwanych co najmniej jednym RESET-em. Ich zdanie „statyczny cap ranił drogie
prawie-ukończone poziomy" **potwierdzone**.

**B. Koncentracja marnotrawstwa.** (twierdzenie #2) Mediana w korpusie: **64,5%** tokenów gry
idzie na poziomy, których gra nigdy nie ukończyła; maks **100%** (r093/g50t, r110 po kilka gier).
To *więcej* niż 35% z docstringu 0004. Ale ich konkretne „tn36 86% / ls20 91%" **nie odtwarza się
na moim korpusie**: r085 tn36 = 92,9%, a ls20 = **10,7%** (r093: 3,6%). Te dwie liczby pochodzą
z ich przebiegu **r019** (są cytowane w komentarzu kodu w r033) — źródła, którego nie mam.
Kierunek potwierdzony, cytaty nieprzenośne.

**C. Kluczowe zastrzeżenie do mechanizmu — i jedna konkretna poprawka.**

Algorytm: `cap = clamp(max(static_cap, mediana × 4), cap_min, cap_max)`.
Ponieważ w środku jest `max(static_cap, …)`, cap **nigdy nie jest niższy od wartości
uzbrojenia** — reguła z konstrukcji tylko **poluzowuje**, nie dociska. Sprawdzone empirycznie
na korpusie przy proponowanym uzbrojeniu 60 000:

- reguła **w ogóle się nie włącza** w **24 z 40 gier (60%)** — tam, gdzie gra ukończyła mniej niż
  2 poziomy, nie ma mediany i cap zostaje statyczny. A to dokładnie ta populacja, która pali
  100% tokenów na nieukończonym poziomie (r110/r118: 0 ukończonych poziomów).
- w pozostałych 16 grach: cap **15 na 16 luźniejszy**, ani razu ciaśniejszy; mediana capa
  **128 612**, maks 150 000.

Czyli **0010 w konfiguracji „uzbrój 60 000" realizuje tylko motywację #1, a nie #2**: chroni
drogie poziomy w grach, które już produkują, i nie dotyka marnowania w grach, które nic nie
kończą.

**Poprawka, która nie wymaga ani linii kodu:** uzbroić **nisko** — `ARC3_LEVEL_TOKEN_CAP`
`0 → 20000` (albo 15000). Wtedy:
- gry bez historii dostają cap 20k + 1 darmowy RESET ⇒ ~40k zamiast 60–90k na poziom, którego
  i tak nie skończą (to jest właśnie docisk, którego dziś nie ma),
- gry produktywne dostają `mediana×4` = 46k–150k (mediany kosztów ukończonych poziomów w moim
  korpusie: 11,5k–72,3k ⇒ capy od ~46k do 150k), czyli ochronę, o którą chodzi w #1.

Dwie uwagi do samej dokumentacji patcha:
1. Docstring twierdzi, że „cheap game is cut much sooner than a flat 45k ever would" — przy
   obecnym kodzie **niemożliwe** (patrz `max(static_cap, …)` powyżej); trzeba to albo poprawić
   w opisie, albo uzbroić nisko, jak wyżej.
2. Drabina RESET mnoży **po** clampie, więc cap może przekroczyć `cap_max`
   (150 000 × 1,5 = 225 000 po jednym resecie). Kosmetyka, ale opis „clamp 45k–150k" jest
   wtedy nieścisły.

## 4. Kompozycja z moim v17-arena — sprawdzona

`v13.7` (10 patchy) + mój `0010-priority-dprime` (D′) na czystym r033:
**aplikuje się czysto i kompiluje**; pliki są rozłączne (`arc3_level_budget.py` vs
`priority_scheduler.py`). Na tym drzewie: 38 testów plan-commit/względnej/D′ **OK**,
16/16 dyn-budget **OK**, self-pace 22/14 **OK**, 11/11 win-path **OK**.
Czyli da się, ale **nie w jednym biegu**: reguła jednej zmiennej — albo cap (0010), albo
priorytet slotu (D′), nie oba.

## 5. Werdykt

**Warto, z jednym warunkiem.** v13-7-final jest rzetelnie zrobiony: budownik odtwarzalny,
`verify` przechodzi u mnie bez poprawek, diff komórek dokładnie taki, jak deklarują, dormancja
potwierdzona różnicowo, patch to naprawdę ich bajty. Jako **slot 30.10** jest bezpieczny —
na submisji to v13.6 (jedna komórka więcej, zero zmiany zachowania).

Warunek: **nie uzbrajać 0010 na 60 000.** Wartość 60 000 zamienia mechanizm w „podnieś cap
produktywnym", a obiecuje „utnij marnotrawstwo". Właściwe uzbrojenie to **20 000** (możliwie
15 000) i wtedy mierzyć — osobno — czy (a) nie tracimy ukończeń drogich poziomów
(14 ukończeń >45k w moim korpusie jest realnym ryzykiem), i (b) czy gry bez historii kończą się
szybciej i oddają slot.

Czego **nie** mogę powiedzieć: ile to da punktów. Nie ma ani jednego przebiegu z uzbrojonym
capem; wszystko powyżej to arytmetyka na cudzych przebiegach i jeden przesączony argument
(14 ukończeń > 45k). Zero obietnic.

## 6. Drobiazgi do posprzątania u nich

- `tools/verify_v13.py` kontrola nr 129 ma etykietę „slug: kernel-metadata points at
  **v13-6-final**", a asercja sprawdza `v13-7-final` — etykieta została z poprzedniej wersji
  (test przechodzi, myli tylko czytelnika).
- `README` mówi „41 komórek, 758 240 B" — zgadza się; „10 patchy" — zgadza się.
- Slug `petersharps/arc3-duck-v13-7-final` jest nowy i unikalny — tu nie ma kolizji; ryzyko
  nadpisania dotyczy starszych slugów, na które celują kernele Gemmy.
