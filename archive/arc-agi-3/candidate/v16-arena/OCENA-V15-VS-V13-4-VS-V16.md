# Ocena: v15 (Gemma) vs v13.4-unified (Smak/Arena) vs v16-arena (ten katalog)

Data: 30.10.2026. Wszystko poniżej sprawdzone **lokalnie i offline**, na kopiach z gałęzi
odczytanych przez API GitHuba. **Zero Kaggle, zero GPU, zero submisji, zero zmian na remote.**
Gałęzie: Gemma `arena/c4eeb067` @ `07bf05e0`, Smak `arena/5ed750ef` @ `f04c3e73`.

## 1. Co faktycznie jest w każdej wersji (sprawdzone, nie z dokumentów)

| element | v15 (Gemma) | v13.4-unified (Smak) | v16-arena |
|---|---|---|---|
| komórek | 37 | 39 | **42** |
| patchy w łańcuchu | 6 plików extra (0001,0002,0004,0005,0006,0007) | 7 plików extra (+0008 relative escalate) | **8 plików extra** (+0009 D′) |
| PLAN_COMMIT / conc | 1 / 10 | 1 / 10 | 1 / 10 |
| `ESCALATE_ACTIONS` | 20 | 20 | 20 |
| `ARC3_ESCALATE_RELATIVE` | **brak** | 1 (max(20, 1,2×baseline), cap 2) | 1 |
| `ARC3_OPENER_COMMIT_HINT` | 1 | 1 | 1 |
| patch 0007 (log win-path) | tak | tak | tak |
| guard hooka sondy | tak | tak | tak |
| sonda budżetu (przed biegiem) | **brak** | tak | tak |
| sonda rosteru (po biegu) | tak, plik `roster_probe.jsonl` | tak, `roster_probe_runs.jsonl` | tak, `roster_probe_runs.jsonl` |
| D′ / priorytet slotu | fabryczny `priority_value` | fabryczny `priority_value` | **D′ za przelacznikiem** |
| przebudowa z buildera = bajt z gałęzi | tak | tak | tak (własny builder) |
| własny verifier offline | tak | tak (`verify_v13.py --bundle --tests`) | tak (`verify_v16.py`, ten sam wzorzec) |

Różnice, które **nie** są kosmetyczne:

1. **v15 nie ma patcha 0008.** Eskalacja w v15 jest absolutna (20). v13.4/v16 odpala ją dopiero
   powyżej ludzkiego baseline'u; na r085 daje to 8 wstrzyknięć i 0 przedwczesnych wobec 60 i 25/32
   przy sztywnym 20. To jest jedyny zmierzony mechanizm, który w v13.4 jest ostrzejszy niż w v15.
2. **v15 nie ma sondy budżetu.** Bez niej „cap/udział = 11×” (110 gier × 532 min przy 10 slotach)
   jest niewidoczne do końca biegu, a to najbardziej prawdopodobna przyczyna głodzenia ogona rosteru.
3. **v15 nadpisuje plik sondy hooka c45.** Jej sonda po biegu pisze `roster_probe.jsonl` — ten sam
   plik, który hook w komórce 26 otwiera w trybie dopisywania. v13.4/v16 rozdzieliły nazwy
   (`roster_probe_runs.jsonl`), więc oba zbiory przeżywają.
4. **v15 nie ma jego verifiera z r085 w łańcuchu** (u niej testy pakietu to 3 sprawdzenia:
   łańcuch patchy, playbook, próg). To nie błąd, ale słabsza brama niż u v13.4.

## 2. Weryfikacja, którą przeprowadziłem w tej sesji

| rzecz | wynik |
|---|---|
| v14: builder → notebook | bajt-identyczny z gałęzią (36 komórek, 722 437 B) |
| v15: builder → notebook | bajt-identyczny z gałęzią (37 komórek, 729 138 B) |
| v15: `tests/test_v15_package.py` + `tools/test_probes.py` | 3/3 + 4/4 OK |
| v13.3-arena: builder → notebook | bajt-identyczny (36 komórek, 721 437 B) |
| v13.4-unified: builder → notebook | bajt-identyczny (39 komórek, 734 766 B) |
| v13.4: `verify_v13.py --bundle r033 --tests` | **ALL CHECKS PASSED** (8/8 patchy, 12+6+11 testów, sondy, playbook 14/14, switch w obie strony) |
| v16: builder → notebook | bajt-identyczny (42 komórki, 755 857 B) |
| v16: `verify_v16.py --bundle r033 --tests` | **ALL CHECKS PASSED** (9/9 patchy, 12+6+21+11 testów, sondy 7/7, `switch-off == priority_value` na spatchowanym drzewie) |

Uwaga metodologiczna: `verify_v13.py` w czystym sandboxie wymaga `requests` i `PIL` do importu
`tool_agent`. Użyłem **atrap testowych** (`/tmp/arc3-v134-test-shims`: `requests` rzucający przy
jakimkolwiek POST, `PIL.Image.Resampling` jako stałe). To pozwala importować moduł i testować
czystą logikę, ale **nie** dowodzi, że notebook wykona się na Kaggle — do tego potrzebny jest
prawdziwy bundle i osobna zgoda na run.

## 3. Nowy pomiar, którego nikt wcześniej nie zrobił: czy D′ zmienia decyzje?

`tools/dprime_ordering_replay.py` odtwarza z zapisanych `benchmark.json` (r085, r093, r110, r118 —
10 publicznych gier każdy) to, co widzi scheduler, i porównuje ranking fabryczny vs D′ w 43 próbkach
co 5 minut:

- **top-3 identyczne tylko w 2/43 próbkach (5%)** → przełącznik jest żywy, nie jest atrapą;
- korelacja rangowa z **realnym** wynikiem gry: legacy **+0,19**, D′ **+0,20** (średnia z 4 nagrań);
- D′ najczęściej wciąga do top-3 `cn04`, `dc22`, `su15`, `sc25` — czyli gry o niższym zmierzonym
  koszcie tokenów na ukończony poziom.

Interpretacja, bez upiększania: **D′ realnie zmienia alokację, ale te nagrania nie pokazują, żeby
zmieniał ją lepiej.** Wynik z nagrania powstał przy starej alokacji, więc korelacja to tylko
sanity check kierunku, nie prognoza. Pozytywnym dowodem pozostają publikowane drawy
(31,54 / 30,74 / 29,05 / 24,77, średnia ~29,0 wobec ~25,8, n=4) — mały, zaszumiony sygnał,
który przy SD ~3,9 nie odróżnia się od szumu na poziomie pojedynczego biegu.

## 4. Werdykt i rekomendacja slotów

**Najlepszy z istniejących, gotowych notebooków: v13.4-unified.** To v15 plus trzy rzeczy, które
v15 nie ma (relatywny spust, sonda budżetu, nierozjeżdżające się pliki sondy), przy tym samym
łańcuchu zmierzonym i własnym verifierze z r085.

**v16-arena to nie „lepsza wersja”, tylko kontrolowany eksperyment.** Jego wartość polega na tym,
że różni się od v13.4 **jedną** linią env i jedną łatką, a pomiar (sonda + `dprime_metering.jsonl`)
jedzie w tym samym biegu. Ma sens tylko wtedy, gdy ktoś świadomie chce zmierzyć D′ w konkursie.

Propozycja (decyduje GO użytkownika, nic nie zostało wysłane):

| slot | propozycja | uzasadnienie |
|---|---|---|
| następny | **v13.4-unified** | najwięcej zweryfikowanych, zmierzonych elementów; najniższe ryzyko nieoczywistej regresji |
| kolejny | v16-arena **albo** v13.4 ×2 (draw) | v16 mierzy jedyną dźwignię o sufcie >50 (`commit(plan)` × alokacja); draw mierzy wariancję |
| potem | flip **najsłabszego** elementu wg meteringu | np. `ARC3_ESCALATE_RELATIVE=0` (kontrola absolutna) albo `HISTORY_ASSISTANT_TURNS` ↓, jeśli sonda budżetu pokaże głodzenie |

Czego **nie** twierdzę: że v16 da 50+. Zmierzona linia to ~26 (submisja `#57247568`, 26,25) przy
bazie ~25,8 i prognozach 26–31 z czterech sesji. D′ jest jedynym znanym mechanizmem, który w
publikowanych drawach podnosi tę linię o ~3 punkty, ale przy SD ~3,9 to nie jest rozstrzygnięcie.

## 5. Ryzyka v16, których nie da się usunąć offline

1. **Interakcja z hintem i relatywnym spustem** — kierunek każdego elementu zmierzony osobno,
   łącznie nie. Mitygacja: metering w tym samym biegu + kill-switche.
2. **Pace ≈ 0 na starcie** — dopóki gra nie ukończy poziomu, D′ pracuje na referencji 30k;
   przy rosterze, gdzie większość gier nie kończy poziomu, D′ sortuje w dużej mierze po
   głębokości i „cierpliwości”, a nie po zmierzonym tempie. Widać to w meteringu (`runs_with_a_cleared_level`).
3. **Brak wspólnego zegara** (gdy `ARC3_MAX_ACTIVE_STREAMS=0`, bramka nie istnieje) — D′ działa
   wtedy na ścieżce fallback z φ=1, bez fazy końcowej.
4. **Niesprawdzony runtime** — łańcuch patchy zweryfikowany na r033; inna rewizja bundla może
   zmienić kontekst. Guard hooka i try/except w sondach ograniczają skutki do „skipped”, ale
   nie do zera.
