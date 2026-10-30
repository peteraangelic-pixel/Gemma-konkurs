# ARC-AGI-3: lokalny kandydat oparty na pomiarach

**Status:** izolowany pakiet badawczy, tylko lokalny. To nie jest gotowy notebook konkursowy, nie został zintegrowany z repozytorium Smak-Domu-Konkurs i nie był uruchamiany w Kaggle. **Nie obiecuje wyniku 50+.**

Pakiet zawiera dwie małe, niezależne rzeczy:

- `dprime.py` — czystą implementację formuły priorytetu D′, żeby dało się testować regułę przydziału slotów bez GPU;
- `scorecard.py` i `audit_benchmark.py` — przeliczenie RHAE oraz audyt lokalnego `benchmark.json`.

To są testy logiki i artefaktów, nie symulacja ukrytych gier ani wynik konkursowy.

## Najważniejsza korekta wyniku

Stan odświeżony z gałęzi operacyjnej 29.10.2026:

| Submission | Co to było | Public score |
|---|---|---:|
| `#57737623` | v11 / fast line; cap 45k, `PLAN_COMMIT=0`, concurrency fix | **23.89** |
| `#57752672` | późniejszy stock Tufa, Qwen3.6-27B-FP8, `conc=28`, bez capa | **1.18** |
| `#57247568` | wcześniejszy duck v3 | **26.25** |

Zatem rozumiem „około 23” jako `#57737623`, ale **nowsza zakończona submission to 1.18**; aktualnie znane najlepsze COMPLETE to 26.25. To są różne warianty i nie wolno ich diagnozować jako jednego runu.

Dodatkowy odczyt artefaktów lokalnych:

- v13/27B smoke (`r110`): 10 gier, 48 min/gra, średnia **0.728**, 4 ukończone poziomy łącznie, 0 zwycięstw;
- v14/27B smoke (`r118`): 10 gier, 90 min/gra, średnia **0.273**, 2 ukończone poziomy łącznie, 0 zwycięstw;
- oficjalna `#57752672` pozostała osobną submission z wynikiem **1.18**. `r117`/`r118` dotyczą ukończonego kernel run/output-pick, nie nowego wyniku LB.

Obie smoke średnie są **offline i na 10 publicznych grach**, nie są wynikiem konkursowym. Zbieżnie z 1.18 pokazują jednak, że stock 27B-FP8 to słaby kierunek na podstawie dostępnych prób; zwiększenie czasu z 48 do 90 minut w pojedynczym smoke nie dowodzi regresji ani poprawy.

## Diagnoza v11 = 23.89

1. **Wynik sam w sobie mieści się w szumie.** Na porównywalnej bazie Franzen M2 opublikowane drawy miały średnią ok. **25.77**, SD ok. **3.93**; 23.89 to tylko ok. 0.48 SD poniżej średniej. Nie dowodzi to, że zmiana kodu obniżyła wynik.
2. **Cap 45k z `min_done=0` ma osobny, strukturalny błąd.** W logach v11 `g50t` zakończyła po 1499 s z 0/7 poziomów, `cn04` po 1609 s z 1/6, a `tn36` po 1692 s z 1/7. Zestawienie raportuje łącznie ok. **64 min i 243 600 tokenów** niewykorzystanych po przedwczesnym `ABANDON`. To nie wyjaśnia z pewnością całej różnicy punktowej, ale samo w sobie uzasadnia wyłączenie tej ścieżki.
3. **Mocniejsza zmierzona strategia alokacji to D′, nie zabijanie gier.** D′ zmienia kolejność otrzymywania czasu modelu i pozostawia gry aktywne. Opublikowane drawy na porównywalnej linii: 31.54, 30.74, 29.05, 24.77 (średnia ok. **29.0**). To jest obiecująca, lecz nadal nieduża i zaszumiona poprawa — nie 50+.
4. **Nie stackować niesprawdzonych mechanik.** Nie przenoszę z osobnego `duck-v13-mega` win-path replay, dead-skip ani offline playbooka: nowszy audyt stwierdza, że source search uzyskał 0.20 na LB, a niezależny held-out test 0/113 poziomów. Lokalny wynik playbooka 14 poziomów/9 gier nie jest transferem na LB.

**Bezpośrednia korekta po sprawdzeniu a450 v13:** notebook ma `USE_PRIORITY_SCHEDULING=True` i 10 aktywnych strumieni, ale używa innego `priority_value` niż zmierzona formuła D′ (`ARC3_PRIORITY_PACE=0`). Czyli v13 ma scheduler priorytetowy, lecz nie jest to D′. Ustawia `bm.n_passes=1` zarówno w submission, jak i smoke; `dead_skip` wymagający passu ≥4 jest więc nieosiągalny, a reklamowany replay w passach 2–20 nie dotyczy competition runu. Preloaded playbook może nadal zadziałać przy dopasowanym ID i hashach startowej planszy, ale pokrycia hidden rosteru nie wykazano. Uruchomiony przeze mnie verifier v13 bez bazowego bundle przeszedł kontrole statyczne, lecz jawnie pominął patch-chain tests.

## Co realnie ma sens dalej

1. **Najpierw naprawić konfigurację bezpieczeństwa:** na tym samym modelu i runnerze wyłączyć token cap/terminalny `ABANDON`, nie zmieniając promptu, serwowania, pamięci ani plan-commit. W aktualnym kodzie sprawdzić dokładnie, czy `cap=0` rzeczywiście wyłącza cały patch; nie zakładać, że znaczy „limit zero tokenów”.
2. **Dopiero jako osobny etap dodać D′** na potwierdzonym API schedulera. Zachować model i parametry serwowania bez zmian. W szczególności nie utożsamiać liczby uruchamianych gier (`concurrency`) z limitem aktywnych strumieni modelu (`MAXREQ`/`MAX_ACTIVE_STREAMS`) — ich relacja zależy od konkretnego runnera.
3. **Przed jakimkolwiek Kaggle runem/submissionem** zweryfikować bundle, patch chain, przełączniki i ścieżkę smoke. Ten pakiet nie wywołuje Kaggle API. Wymagana jest osobna wyraźna zgoda na Kaggle run lub submission.

W `candidate.json` etapy są rozdzielone właśnie po to, by nie mieszać naprawy capa z D′ i móc stwierdzić, co naprawdę zostało zmienione. Moduł schedulera nie jest podpięty do runnera — integracja wymaga właściwego checkoutu ARC i testu zgodności jego API.

## Dlaczego nie Rust + Rayon

Na tej ścieżce wąskim gardłem jest inferencja modelu, nie segmentacja: wcześniejszy pomiar wynosi ok. **6077 ms na model call** wobec **0.178 ms** dla segmentacji na CPU (różnica ok. 34 tys. razy). Ponadto ukryte gry nie mają lokalnych źródeł do przeszukiwania. Rust/Rayon nie tworzy informacji o ukrytych zasadach gry, więc nie zwiększa tu szans na 50+. Formuła schedulera i scorecard są krótkie, używają biblioteki standardowej Pythona i pasują do istniejącego runnera. 5950X/64 GB można wykorzystać do analizy dużych logów lub badań offline, ale takie wyniki nie będą LB.

## Nowe narzędzia: metryka jako funkcja celu (30.10)

Audyt paczki `duck-v17-action-efficiency` (szczegóły: `notes/ARC-AGI-3-audit-v17-action-efficiency-2026-10-30.md`)
zostawił jedną trwałą rzecz: pomiar tego, co naprawdę jest punktowane.

- `tools/action_efficiency.py` — medianа akcji na ukończony poziom, rozkład poziom po poziomie,
  oraz bramka `compare before.json after.json` (kod wyjścia 1, gdy zmiany **nie** należy wysyłać:
  wynik nie wzrósł, ukończenie spadło albo mediana akcji poszła w złą stronę).
- `tools/score_decomposition.py` — rozkład wyniku na **efektywność** (akcje na ukończonym
  poziomie) i **ukończenie** (część wagi poziomów), z dwoma sufity górnymi.

Na czterech prawdziwych nagraniach (r085, r093, r110, r118) wiążącym ograniczeniem jest
**ukończenie**, nie liczba akcji: r085 przy wyniku 26,78 ma 95,2% efektywności na ukończonych
poziomach i 29,8% ukończenia; sufit „akcje jak człowiek" to +3,01, sufit „wszystkie poziomy"
to +62,03. To odwraca tezę, że jedyną dźwignią jest mniej akcji.

```bash
python -m arc3_local_candidate.tools.action_efficiency run benchmark.json
python -m arc3_local_candidate.tools.action_efficiency compare before.json after.json
python -m arc3_local_candidate.tools.score_decomposition benchmark.json
```

## Audyt reguł eskalacji i budżetu poziomu (30.10)

- `tools/escalation_audit.py` — ile razy reguła eskalacji wtrąca się do kontekstu i ile z tych
  wtrąceń jest przedwczesnych (próg poniżej ludzkiego baseline'u). Cztery reguły: absolutna 20,
  20+cap2, względna (0008) i self-pace (0009).
- `tools/audit_dyn_budget.py` — dwuczęściowy audyt patcha dyn-level-budget: `benchmarks` liczy
  na realnych nagraniach, ile ukończonych poziomów przekracza statyczny cap i jak koncentruje się
  marnotrawstwo; `logic <pre> <post>` porównuje decyzje modułu adaptacyjnego z wersją statyczną
  (8 000 decyzji na konfigurację, ścieżka uśpiona i kontrola `ARC3_DYN_CAP=0`).
- `fixtures/benchmarks/{r085,r093,r110,r118}.json` — cztery prawdziwe `benchmark.json`
  (kernel_output_pick z gałęzi operacyjnej, ~1,6 MB razem), żeby oba audyty dało się powtórzyć
  bez dostępu do cudzych artefaktów.

```bash
python -m arc3_local_candidate.tools.escalation_audit \
    arc3_local_candidate/fixtures/benchmarks/{r085,r093,r110,r118}.json
python -m arc3_local_candidate.tools.audit_dyn_budget benchmarks \
    arc3_local_candidate/fixtures/benchmarks/*.json
```

Ustalone liczby (odtwarzalne z fixtures):

| reguła | r085 (32 poziomy) | r093 (27) | r110 (4) | r118 (2) |
|---|---|---|---|---|
| absolutna 20 | 67 wtrąceń / 26 przedwcz. | 72 / 23 | 8 / 4 | 3 / 1 |
| 20 + cap 2 (to leci w submisji) | 42 / 26 | 39 / 23 | 5 / 4 | 2 / 1 |
| względna 1,2× (0008) — tylko replay | **8 / 0** | **10 / 0** | 3 / 0 | 2 / 0 |
| self-pace (0009) | **22 / 14** | 22 / 13 | 5 / 4 | 2 / 1 |

Wniosek: względna jest najlepsza **tam, gdzie widzi baseline**; w submisji baseline jest ukryty
(`base_actions_per_level = None` w `taaf/game.py`), więc degeneruje się do 42/26. Self-pace jest
jedyną regułą, która w biegu, który się liczy, faktycznie różni się od „20" — ale to oszczędność
interwencji, nie wzrost punktów.

Budżet poziomu: w korpusie 40 gier **14 ukończonych poziomów kosztowało >45k** tokenów (max
88 114), a mediana **64,5%** tokenów gry idzie na poziomy, których gra nie ukończyła. Reguła
adaptacyjna `cap = clamp(max(static, mediana×4), …)` przy uzbrojeniu 60 000 włącza się w 16/40
gier i **tylko poluzowuje** (0/16 ciaśniej), więc arming ma sens przy **20 000**, nie 60 000.

## Testy lokalne

Wymagany jest tylko Python 3.10+; bez CUDA, Kaggle API, GPU i dodatkowych pakietów:

```bash
python -m unittest discover -s arc3_local_candidate/tests -t . -v
python -m arc3_local_candidate.audit_benchmark /ścieżka/do/benchmark.json --per-game
```

W sandboxie: **19/19 testów zaliczonych**, `compileall` OK. Audyt istniejących artefaktów r110 i r118 odtworzył zapisane średnie (`0.727991` i `0.273354`) z **0 rozbieżnościami**. Jeżeli audyt zgłasza różnicę między przeliczonym a zapisanym `final_score`, zakończy się kodem 2. Offline score z tego narzędzia pozostaje wyłącznie kontrolą zgodności scorecardu.

## Granica celu

Na porównywalnej bazie średnia wynosiła ok. 25.77 (SD 3.93), a zmierzona średnia D′ ok. 29.0. Próg top-5 z raportu 28.10 to 51.04. **Nie ma wiarygodnego, zmierzonego mechanizmu, który w kilka dni przenosiłby tę linię z ok. 29 do ponad 50.** Można przygotować bezpieczniejszy i lepiej alokujący czas wariant; nie można uczciwie zagwarantować 50+.
