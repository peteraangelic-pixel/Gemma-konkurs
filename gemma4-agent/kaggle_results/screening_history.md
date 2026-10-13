# Historia screeningów: co każdy wynik zmienił

Pełne przebiegi: te same 30 zadań i seed 20261009. Mini-screen V6.3 to 4 zadania z tej
samej próbki (diagnozowane przypadki), więc jego wiersz czyta się jako test mechanizmu,
nie jako oszacowanie wyniku. Kolumny diagnostyczne istnieją dopiero od V6.1.

| kandydat | rozwiązane | CI95 Wilsona | puste drzewa (zero edycji) | z tego przedwczesne | śmierci na zegarze | pliki-śmieci | tylko dokumentacja | trafienia lokalizatora | średni czas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V3 | **11/30** | [21.9 %, 54.5 %] | 6 | 2 | 16 | 0 | 0 | — | 261.3 s |
| V4 | **11/30** | [21.9 %, 54.5 %] | 6 | 1 | 12 | 0 | 0 | — | 233.8 s |
| V5 | **10/30** | [19.2 %, 51.2 %] | 6 | 1 | 9 | 0 | 0 | — | 232.7 s |
| V6.1 | **6/30** | [9.5 %, 37.3 %] | 7 | 1 | 17 | 9 | 0 | 15/30 | 275.4 s |
| V6.2 | **9/30** | [16.7 %, 47.9 %] | 8 | 2 | 17 | 0 | 1 | 20/30 | 272.4 s |
| V6.3-mini | **0/4** | [0.0 %, 49.0 %] | 4 | 0 | 4 | 0 | 0 | 0/4 | 318.4 s |
| V6.3 | **10/30** | [19.2 %, 51.2 %] | 11 | 3 | 15 | 0 | 0 | 18/30 | 252.7 s |

## Zmiany statusu między kolejnymi kandydatami

Porównanie liczy się **wyłącznie na zadaniach wspólnych** — inaczej mini-screen
zaraportowałby jako straty zadania, których w ogóle nie uruchamiał.

- V3 → V4: +0 (—), -0 (—)
- V4 → V5: +1 (rich_2725), -2 (fastapi_14851, fastapi_14873)
- V5 → V6.1: +0 (—), -4 (rich_3043, rich_3518, rich_3882, rich_3894)
- V6.1 → V6.2: +4 (fastapi_14873, rich_3518, rich_3882, rich_3894), -1 (rich_3006)
- V6.2 → V6.3-mini: +0 (—), -0 (—) — na 4 wspólnych zadaniach (V6.2: 30, V6.3-mini: 4 uruchomionych)
- V6.3-mini → V6.3: +1 (rich_3006), -0 (—) — na 4 wspólnych zadaniach (V6.3-mini: 4, V6.3: 30 uruchomionych)

### V6.1: zadania z plikami-śmieciami w diffie

- wszystkie: rich_3934, rich_3894, rich_3043, fastapi_14873, fastapi_15588, fastapi_14459, fastapi_14262, fastapi_14482, fastapi_15745
- **bez żadnej edycji kodu: rich_3934, rich_3894, fastapi_14873, fastapi_15588, fastapi_14459, fastapi_14482, fastapi_15745**

### V3: puste drzewa (6)

- fastapi_14851, rich_3105, fastapi_14186, requests_6757, fastapi_14262, fastapi_15745

### V4: puste drzewa (6)

- fastapi_14851, rich_3105, fastapi_15030, fastapi_14186, requests_6757, fastapi_15745

### V5: puste drzewa (6)

- rich_3934, fastapi_14851, fastapi_14266, rich_3105, fastapi_14873, fastapi_15745

### V6.1: puste drzewa (7)

- fastapi_14851, fastapi_14266, rich_3518, rich_3105, fastapi_14186, rich_3882, requests_6757

### V6.2: puste drzewa (8)

- rich_3934, fastapi_14851, fastapi_14266, rich_3105, rich_3006, fastapi_14186, requests_6757, fastapi_15745

### V6.3-mini: puste drzewa (4)

- rich_3105, rich_3934, rich_3006, fastapi_14487

### V6.3: puste drzewa (11)

- rich_3934, fastapi_14851, fastapi_14266, fastapi_14487, rich_3043, rich_3105, fastapi_15030, fastapi_14459, requests_6757, fastapi_15745, httpx_3672

## Bramki jakości V6.3 (pre-registered 2026-10-12, przed przebiegiem)

Bramki są **osobne od liczby rozwiązanych zadań** i nie przesuwa się ich po zobaczeniu wyniku.

- **V6.3-mini**: G1 brak plików-śmieci: PASS (0); G2 brak przedwczesnych submisji bez edycji: PASS (0); G3 zero diffów wyłącznie dokumentacyjnych: PASS (0); G4 cel: puste drzewa <= 4 (jest 4); wynik zgłaszany osobno: 0/4 CI95 [0.0 %, 49.0 %]
- **V6.3**: G1 brak plików-śmieci: PASS (0); G2 brak przedwczesnych submisji bez edycji: FAIL (3); G3 zero diffów wyłącznie dokumentacyjnych: PASS (0); G4 cel: puste drzewa <= 4 (jest 11); wynik zgłaszany osobno: 10/30 CI95 [19.2 %, 51.2 %]

- **reguła decyzyjna z GATES_V6_3.md** (G1=G2=G3=0 w obu przebiegach i ≥9/30 w pełnym): **NIESPEŁNIONA -> submissja zablokowana** — powody: V6.3: G2=3

## Werdykt pre-registered oczekiwań (V6.3-mini)

Zapisane w GATES_V6_3.md **przed** przebiegiem; werdykt liczony maszynowo z JSON-a.

- **O1** `rich_3105` i `rich_3934` kończą z edycją na dysku (nie pustym drzewem) i G2 = 0: **OBALONE** — puste drzewa rich_3105, rich_3934, przedwczesne 0
- **O2** `fastapi_14487` bez diffu wyłącznie dokumentacyjnego: **SPEŁNIONE** (docs-only: 0)
- **O3** `rich_3006` (kontrola) nadal pada na zegarze: **SPEŁNIONE** — gdyby został rozwiązany, byłby to sygnał szumu, nie sukcesu zmian (a)/(c)

Skutek OBALONEGO O1: zmiana (a) usuwa przedwczesną submissję bez edycji (G2 = 0), ale **nie zamienia jej na edycję** — te sesje nadal kończą z pustym drzewem, tyle że po wyczerpaniu zegara. Zysk punktowy na tych zadaniach: nadal zero. Bezpośredni zapis tego wniosku: GATES_V6_3.md, sekcja o przebiegu zdarzeń.

## Reguły interpretacji (wyuczone na tych przebiegach)

1. **Śmierć na zegarze nie przekreśla zadania** — oceniany jest diff drzewa roboczego, także gdy
   sesja padnie przed `submit_patch()` (dowód: V3 miał 16/30 takich sesji i 11/30 rozwiązanych).
2. **Przekreśla ją brak użytecznej edycji** — V5 (6 pustych drzew) i V6.1 (7 drzew bez edycji kodu,
   bo diff wypełniły pliki robocze) to dwa różne objawy tej samej przyczyny.
3. **Publiczny screening 30 zadań nie przewiduje ukrytego wyniku** (V3/V4/V5: 10–11/30 przy
   oficjalnym 0.03), ale z diagnostyką per zadanie niezawodnie wskazuje mechanizmy porażek.
4. **Bramki jakości raportuje się osobno od wyniku** i ustala przed przebiegiem; próg na
   liczbie rozwiązań nie jest dowodem przewagi przy n=30 (V5 vs V6.2: przedziały nachodzą).
5. **Przedziały CI95 w tabeli są liczone z JSON-ów** (`score_ci95_wilson` jest dodatkowo
   kontrolowane przy generowaniu). Prozy nie wolno przepisywać ręcznie — pilnuje tego
   `python3 gemma4-agent/tools/check_docs_consistency.py` (wykrył realną rozbieżność
   [11 %, 30 %] vs [16.7 %, 47.9 %] w V6.2).
