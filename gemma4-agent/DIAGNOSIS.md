# Diagnoza: dlaczego V4 ma 0.03 i co zmienia V5

Dokument spina dowody z publicznych źródeł (strona konkursu, `HARNESS_README.md`, wątki dyskusyjne
konkursu) z wynikami naszych prywatnych benchmarków V2-V4. Każda liczba ma źródło; tam, gdzie
wnioskujemy, jest to oznaczone.

## 1. Punkt odniesienia na leaderboardzie

Snapshot `kaggle_results/leaderboard.csv` (2 501 drużyn, 2026-10-12):

| Pozycja | Score |
| --- | --- |
| 1-2 | 0.24 |
| 3-6 | 0.22 |
| 7-10 | 0.20 |
| mediana | 0.12 |
| 75. percentyl (od góry) | 0.08 |
| **nasza pozycja (~2300)** | **0.03** |

0.03 = ok. 2 rozwiązane zadania z ~60 zadań publicznego splitu testowego. Nasza submissja V4 jest
poniżej mediany o czynnik ~4 i poniżej prowadzenia o ~8. To nie jest "pech w losowaniu" - to
systematyczna słabość agenta.

## 2. Reguły, które przesądzają o strategii

Z `overview` i `data` konkursu:

- **12 godzin na WSZYSTKIE zadania**, łącznie z setupem sandboxa, wyłączając walidację patchy.
  Split testowy to **~120 zadań z prywatnych repozytoriów**, dzielony równo public/private (~60
  na public LB).
- Brak internetu, tylko model `gemma-4-31b-it-qat-w4a16-ct`, scoring = PASS/FAIL po uruchomieniu
  ukrytych testów walidacyjnych (Resolution Rate = resolved / wszystkie zadania splitu).
- Zadania testowe były selekcjonowane tak, by **frontier model je rozwiązywał albo był w nich
  "w jednym teście od" rozwiązania** - czyli są to przypadki trudne, nie te, na których łatwo
  wyglądać dobrze.

Konsekwencje: budżet na zadanie ≈ 12h / 120 = **6 minut łącznie z setupem** (~30-60 s na kontener),
czyli ok. 5,0-5,5 min pracy agenta. Każdy ponadbudżetowy przebieg grozi przekroczeniem 12 h, a to
unieważnia całą submissję.

## 3. Dlaczego prywatny benchmark 33% nie przełożył się na 0.03

Nasze własne przebiegi: V2 10/30 (33,3%), V3 11/30 (36,7%), V4 11/30 (36,7%) na 30 publicznych
zadaniach (seed 20261009). Trzy niezależne czynniki wyjaśniają lukę:

1. **Inny rozkład zadań.** Benchmark mierzy fastapi/rich/requests/httpx, split wynikowy pochodzi
   z prywatnych repozytoriów. Nasze prompty zawierały instrukcje i hinty pisane pod te cztery
   repozytoria - na ukrytym zbiorze są co najwyżej balastem.
2. **Zadania publiczne są łatwiejsze i częściowo wadliwe.** W naszym V4 benchmarku
   `fastapi_14851` został zaliczony przy **pustym patchu** (`patch_chars = 0`, `resolved = true`);
   uczestnik raportuje wątek "fastapi tasks can't pass even with the gold patch", a peer musiał
   wykluczyć 5/129 zadań, bo nie dało się ich lokalnie ocenić. Publiczny wynik jest więc
   zawyżony, a jego wariancja duża (95% CI dla 11/30: 22-55%).
3. **Test splitu jest trudniejszy celowo** (selekcja "near-frontier"), a 31B model z zapalonym
   myśleniem i bez dostrajania ma tam naturalnie niższy sufit niż na publicznym zbiorze.

Wniosek: 33% na publicznym benchmarku to **górna granica**, nie prognoza. Ale 0.03 pokazuje, że
na trudnych, nieznanych zadaniach agent degraduje się bardziej niż konkurencja - i to jest
naprawialne.

## 4. Zmierzone słabe punkty V4

### 4.1. Wyłączone streszczenia myśli (`include_thoughts: false`) - największa pojedyncza strata

V4 (a także V2/V3) ustawia `thinking_config.include_thoughts: false`. Publiczna ablacja uczestnika
na tych samych 129 zadaniach (wątek `discussion/746250`, konfiguracja E12 z 60-min capem):

| Wariant | Rozwiązane / 129 |
| --- | --- |
| myślenie ON + streszczenia ON (E12) | **51 (39,5%)** |
| myślenie OFF (E17) | 23 (17,8%) |
| **streszczenia OFF (E18)** | **35 (27,1%)** |

Sama zmiana `include_thoughts` na `false` kosztowała ok. 12 punktów procentowych. Bez streszczeń
model nie widzi własnego wcześniejszego rozumowania w kolejnych turach - a to właśnie wieloturowe
rozumowanie decyduje o lokalizacji błędu w nieznanym repo. V4 odziedziczył `false` po publicznym
notebooku, który zakładał zupełnie inny budżet czasowy.

Dodatkowo `HARNESS_README.md` wprost zaleca `include_thoughts: true` + `thinking_budget: 4096`
dla tego stosu (vLLM + parser `gemma4`).

### 4.2. Temperatura 0.2

Ta sama ablacja: temp 0.2 -> 48/129, temp 0.0 -> 47, temp **0.4 -> 51**, temp **1.0 -> 51**.
Różnica jest w granicach szumu, ale 0.2 było mierzone jako słabsze; V5 używa 0.4.

### 4.3. Zbyt mały budżet narzędzi + prompt, który zniechęcał do pracy

- `max_tool_calls: 35` (V2-V4). Ablacja uczestnika przy 15-min capie: **50 wywołań -> 50/129**,
  **25 wywołań -> 36/129** (starta 14 zadań). Kolejna: ten sam prompt z 25 wywołań w 29% był
  szybszy, ale rozwiązywał o 14 zadań mniej. Cap 35 siedzi dokładnie między tymi punktami.
- Nasz prompt dodatkowo **zachęcał do oszczędzania**: "avoid repeated searches", "do not expand",
  "time-box investigation". Efekt: agent w benchmarku zużywał średnio 10-22 wywołań na zadanie
  i kończył z pustym patchem.

### 4.4. Polityka "nie zgaduj" = puste patche = zera

V4 zawiera: "Do not make up a speculative edit just to avoid an empty patch" oraz "if there is no
defensible fix, report that honestly rather than timing out silently". Metryka konkursu jest
PASS/FAIL: **pusty patch to zawsze 0**, a patch niepewny ma niezerową szansę trafienia (a przy
końcówce czasu i tak nie ma już nic do stracenia - harness odzyskuje niezatwierdzone zmiany z
drzewa roboczego). Oficjalny sample submission mówi wprost odwrotnie: "Do NOT conclude without
submitting a non-empty patch. Every task requires concrete source modifications."

W naszym własnym benchmarku V4 miał **6/30 zadań z pustym patchem** (20%), z czego 5 to timeouty
bez żadnej edycji. V3 i V4 rozwiązały **dokładnie ten sam zestaw 11 zadań** - zmiany promptu w
V4 nie zmieniły żadnego wyniku, tylko czasy.

### 4.5. Marnotrawstwo tur w budżecie ~5 minut

Liczby kalibracyjne uczestnika dla Kaggle 4xL4 (ten sam serwer, TP=4): **8,68 s na wywołanie
modelu z myśleniem, 1 110 tok/s**. Sesja 5,25 min to więc realnie **~25-35 wywołań**. V4 wydawał
z tego:

- `get_status` po ~8 wywołaniach i przed każdym wolnym testem (każde wywołanie = pełna tura ~9 s),
- `load_skill_resource` + `run_skill_script` dla dwóch skills (dodatkowe tury plus odczyt SKILL.md),
- delegację do subagenta `repo_analyzer` (AgentTool = osobna pod-sesja),
- `patch-validation` przed samym `submit_patch()`.

Razem 5-8 tur z ~30, czyli 20-25% budżetu, wydane na proces zamiast na znalezienie błędu.
Pomiar uczestnika: dodanie analizatora zmieniło wynik o **+1 zadanie na 129** (szum).

### 4.6. Narzędzia grafowe: zmierzone zero korzyści

V2-V4 miały w prompcie całą sekcję o `search_similar_code` / `get_code_neighbors` /
`get_code_subgraph`, a V4 dorzucał "Graph/embedding fallback". Ablacja (E30 vs E32): użycie
narzędzi grafowych na 21/129 zadań, **wszystkie 21 wyszukiwań semantycznych zwróciło pusty
wynik**, żadne z 31 wywołań grafu nie wskazało pliku ze złotego patcha przed pierwszą edycją,
a mediana czasu zadania wzrosła z 6,57 do 7,33 min. Nasze własne logi V2 pokazują ostrzeżenia
`Could not obtain embedding for node ...`.

### 4.7. Lokalizacja to prawdziwe wąskie gardło

Analiza uczestnika na 129 zadaniach publicznych: pierwszy trafiony `grep` po identyfikatorze
wskazuje plik ze złotego patcha w 30% przypadków; `grep` + BM25 daje 61% w top-5 i 74% w top-10;
**35 z 128 issue nie zawiera żadnego identyfikatora kodu** (tylko tytuł PR i link). Nasz prompt
(„używaj `read_file` i wąskich odczytów", „unikaj szerokich grepów") nie uczył taniej,
skutecznej strategii wyszukiwania, a na prywatnych repozytoriach nie mieliśmy żadnych hintów.

### 4.8. Znany błąd parsera narzędzi Gemma 4

Uczestnik raportuje (wątek `discussion/747168`): wywołania `edit_file`, których `old_string`
zawiera `"""`, bywają psute przez parser tool-call vLLM `gemma4` (klucze typu `<|"|>,filepath`),
ADK odrzuca je komunikatem "mandatory input parameters are not present", a model powtarza
identyczne wywołanie nawet **27 razy**. Odrzucone wywołania nie liczą się do limitu, ale
zjadają czas. V4 nie mówił o tym ani słowa.

### 4.9. Budżet 12 h bez marginesu

V4: średni czas zadania 234 s + ~30-60 s setupu = ~9-10 h na 120 zadań, czyli mieści się w 12 h,
ale cap 5,25 min na *każdym* zadaniu daje 11,5 h - margines jest cienki, a przekroczenie 12 h
unieważnia całą submissję. Prompt V4 nie zawierał żadnej reguły „oddaj patch wcześnie, nie
wypalaj budżetu".

## 5. Co zmienia V5

| Zmiana | Uzasadnienie |
| --- | --- |
| `include_thoughts: true`, `thinking_budget: 4096` | +12 pkt w ablacji peera; zalecenie harnessu |
| `temperature: 0.4`, `top_p: 0.95`, `top_k: 40`, `max_output_tokens: 16384` | najlepszy zmierzony punkt; 16384 chroni przed ucięciem tool-calla |
| budżet: **5,25 min / 45 wywołań / 80 tur / 150 s na komendę** | 12 h / ~120 zadań; cap wywołań przestaje być wiążący, `budget_warning` harnessu (od 35. wywołania) daje darmowy sygnał do kończenia |
| prompt: **jeden zbiorczy `run_command` z wieloma grepami** + szablony komend | lokalizacja to wąskie gardło; tura kosztuje ~9 s, więc jeden gęsty shell-call jest wart dziesięciu małych |
| prompt: **wyciągnij dokładne nazwy, typy wyjątków i komunikaty z issue** | ukryte testy asertują dokładnie te stringi (np. `SSE 'event' must be a single line`) |
| prompt: **zawsze oddaj patch**, także niepewny | pusty patch = pewne 0; metryka nie karze za próbę |
| prompt: zakaz `"""` w `old_string`, `write_file` dla bloków z docstringami | znany błąd parsera gemma4 (27 retry w jednym trace) |
| brak skills, brak subagenta, brak hintów repo-specific | -5-8 tur procesu na sesję; analizator mierzony jako +1/129 (szum); hinty bezużyteczne na prywatnych repo |
| narzędzia grafowe zarejestrowane, ale zakazane w instrukcji | nie da się ich „przypadkowo" wywołać w pętli ADK, ale nie zjadają tur (zmierzone 0 korzyści) |
| strategia dla issue bez identyfikatorów (grep po słowach tytułu, `ls` pakietu, README) | dotyczy ~27% zadań (35/128) |
| jeden bounded call: `ast.parse` + najwęższy test z `timeout 90` | weryfikacja bez ryzyka zawieszenia komendy na 150 s |

## 6. Czego V5 świadomie nie robi

- **Nie trenuje LoRA.** Czołówka leaderboardu (i rekomendacja uczestników) opiera się na
  dostrajaniu; to największa dźwignia, ale wymaga GPU, danych trajektorii i czasu, których to
  repo/sesja nie mają. Sample submission zawiera gotowe, malutkie adaptery (r=4, alpha=8, tylko
  warstwa 0), ale bez pomiaru ich wpływu nie warto dokładać ryzyka niezgodności z parserem
  tool-calli.
- **Nie dodaje drugiego agenta.** Zmierzony zysk analizatora to +1/129, a koszt to pełna
  delegacja w budżecie, w którym liczy się każda tura.
- **Nie walczy z grafem kodu.** Zmierzone 0 korzyści na 31 wywołaniach.

## 7. Jak zweryfikować V5 przed wypaleniem dziennej submissji

1. Prywatny benchmark na Kaggle L4x4 na tych samych 30 zadaniach i seedzie 20261009 (notebook
   `gemma_smoke/gemma-agent-benchmark-v5.ipynb`) - porównanie z V3/V4 (11/30) na tym samym
   zestawie. Oczekiwanie: V5 >= V4; jeśli nie, wracamy do ablacji jednego czynnika.
2. Dopiero potem oficjalna submissja `submission-v5.zip` jako `submission.zip`. Kolejka scoringu
   to obecnie 22-46 h, a jedna oczekująca submissja blokuje kolejną - dlatego jeden, dobrze
   uzasadniony upload ma większą wartość niż kilka.

## 8. Zasady kolejnych iteracji (utrzymane z V1-V4)

- Hipoteza zapisana **przed** pomiarem (SUBMISSION_LOG.md).
- Jedna główna zmiana na iterację, o ile to możliwe.
- Dokładny wynik, data UTC i decyzja (zachować/cofnąć). Pojedyncze przebiegi na 30 zadaniach
  mają ±5 zadań szumu - nie wnioskować z różnicy 1-2 zadań.
