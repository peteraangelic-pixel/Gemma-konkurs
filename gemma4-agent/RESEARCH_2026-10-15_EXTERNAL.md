# Rekonesans zewnętrzny 2026-10-15 — co robi czołówka i gdzie jest nasza luka

Pytanie, na które odpowiada dokument: **„czego brakuje, żeby mieć znacznie więcej niż 0.13?"**
Przeszukane: 4 gałęzie siostrzane (`Pokemon` ×3, `Smak-Domu-Konkurs`), 6 repozytoriów konkurencji,
forum Kaggle (12 wątków + playbook `emiliodavola/kaggle-gemma-agent`), publiczne notatniki
(`lucifer19` Black Cat, `romanrozen`, `mizeroluckygall`, `zhukovoleksiy`, `nihilisticneuralnet`),
Reddit/Discord (patrz §7 — nic swojego dla tego konkursu).

Etykiety: **HOST** = wypowiedź organizatora, **3P** = relacja uczestnika, **POMIAR** = nasz pomiar,
**T** = tylko tytuł/zajawka wątku, treści nie czytałem (do domknięcia).

---

## 1. Twarde fakty o konkursie, które korygują nasze założenia

| Fakt | Źródło | Co to zmienia u nas |
| --- | --- | --- |
| **Publiczna LB = 58 zadań** (1 zadanie ≈ **0,017**); zbiór testowy ~120–129, dzielony równo (HOST, data page) | 3P, `743506` + wzór zaokrągleń; zgodne z 3 niezależnymi repo | nasze **0,13 = 7–8/58**; klaster 0,15 ≈ 9/58; lider 0,24 = 14/58. „Dużo w rankingu" to różnica **2–6 zadań**, nie 30 |
| **Ten sam pakiet, 4 submisje: 0,17 / 0,15 / 0,13 / 0,15** (autor 330. miejsca); cały rozkład LB daje się opisać dwoma rozkładami dwumianowymi (autor 1800.) | 3P, `748051` | pojedynczy wynik **nie jest** pomiarem; ±0,02–0,04 to szum. Bramki i wybór finałów muszą opierać się na powtórzeniach |
| 12 h na **cały** przebieg (setup wliczony, walidacja patchy poza); **przekroczenie = błąd CAŁEJ submisji**; zadania sekwencyjne; scorer czyta dokładnie `timeout_seconds, max_tool_calls, max_time_minutes, max_turns`; brak klucza = brak limitu; domyślnie HARNESS **60 min / 100 wywołań** | HOST, `743063`; playbook §2.9 | nasze 5,25 min/30 wywołań to świadomy wybór, ale cap wywołań jest **najniższy w stawce** (peers: 24, 40, 50, 55, 100) |
| **Ciasny cap kosztuje zadania:** Pathfinder 4 min → 0,08 vs bez capa 0,12; „przy 6-min capie tracimy **~45 % rozwiązań**, połowa zadań kończy się w 2–3 min, a te 8–15-minutowe to często te, które rozwiązujemy" | 3P: `mizeroluckygall` (za Black Cat), `749597` (Vaibhav, czeka na HOSTA) | największa niewykorzystana dźwignia: **zróżnicowany budżet** — łatwe kończyć wcześnie, trudnym dać dojść do końca, suma ≤ 12 h |
| **Porażki procesowe dominują**: 47 % porażek w dużym przebiegu lokalnym to timeouty i wyczerpanie budżetu; ~35–58 s na wywołanie; „wąskim gardłem jest czas, nie wiedza"; 3 zadania „rozwiązane" **bez edycji źródła** (metrika zawyżona bez kontroli no-patch) | 3P, playbook §10.9 (run_03) | mierzymy to samo: V6.4 **19/30 zgonów na zegarze**, **11/30 pustych drzew** |
| **LoRA działa w scoringu** (HOST, dziś): adaptery są aplikowane w forward pass (dowód z logprobs), scoring używa tego samego patched vLLM 0.19.1; `sample_submission` dotyka tylko **warstwy 0 z 60** — dlatego „nie działa"; hang KV-cache naprawiony (prompt 18k + adaptery = 13 s) | HOST, `749528` (Ryan Holbrook) | pogląd „adaptery są wycierane" (3P z 28.09) jest **nieaktualny**. LoRA = realna droga, ale musi objąć **wiele warstw** |
| **Nowe warianty modelu: 31B / 12B / E4B / E2B** (ten sam wariant w całej submisji, różne adaptery per agent). Motywacje HOSTA: więcej test-time compute (szybsza inferencja = więcej tur), **tańszy trening LoRA** (consumer GPU), więcej wyspecjalizowanych agentów. `ParallelAgent` **zepsuty** na ADK 1.36 (workaround: subagenty bez narzędzi) | HOST, `748287` | otwiera L5 (12B) i L4 (trening) bez własnego GPU |
| Kontekst: twardy sufit 32 768, **efektywny ~14 336** (kompakcja), z LoRA KV-cache maleje; `include_thoughts` może *wyłączać* rozumowanie zamiast tylko je ukrywać (wątek bez odpowiedzi HOSTA) | 3P + playbook §2.5/§10 | nasz prompt ~5k tokenów — bezpiecznie; `include_thoughts: true` u nas jest po bezpiecznej stronie |
| Higiena: **pliki testowe są resetowane przed gradingiem**, `pytest.ini`/`conftest.py` to pliki harnessu; pliki nieśledzone **wchodzą** do patcha (`git add -N .`); `sample eval_config` = 1 min/10 wywołań (stąd wczesne wyniki ~0); `submit_patch()` jest darmowy i kończy sesję | 3P, `Maukthik/gemma4` | nasze reguły V6.7 (scratch tylko `/tmp`, bez edycji testów) są zbieżne z tym, co robi reszta stawki |
| Operacyjne: kolejka 4×L4 4–9 h; **oczekująca submisja blokuje kolejne**; scoring 22–46 h | 3P, 4 wątki | planować submisje jak zasób, nie jak eksperyment |

## 2. Co mówi czołówka (wątki z ostatnich 5 dni)

- **„The top of the leaderboard is dominated by those who trained LoRA's"** (`748051`, 10↑):
  autor (0,17): „**jedyny sposób, by przejść 0,17–0,18, to trenować LoRA**"; „więcej orkiestracji,
  skills, promptów i agentów w końcu staje się zbędne — **proste agenty z dobrymi ograniczeniami
  działają lepiej**"; „skills i subagenty? **Not really**"; „sufit bez LoRA to **0,18–0,20**".
  Kaggle'owe L4: „jakieś 15 h/tydzień" — „ludzie na szczycie prawie na pewno mają GPU poza Kaggle".
- **Kontra (12. miejsce, htn):** „chyba **żadna** z czołowych submisji nie poprawiła się przez
  finetuning". **Ayush (454.):** „ten konkurs jest o post-trainingu, nie o inżynierii harnessu;
  rozkład wyjść modelu nie da się wiele zmienić, a harness go dodatkowo ogranicza".
- **Byron (1800.):** cały rozkład LB wyjaśnialny szumem — „**nikt jeszcze niczego nie rozgryzł**".
- Wątki nierozczytane (tylko tytuły, **T**): „**Stronger models barely beat Gemma 4 31B in this
  harness** — teacher comparison on 124 public tasks" (→ dystylacja z mocniejszych modeli daje mało),
  „**Some training tasks can't be solved from the task text alone**" (skomentował **Yurnero, lider
  0,24**), „**fastapi tasks can't pass even with the gold patch**" (16 h temu).

## 3. Co wynika z porównania z NASZYMI pomiarami

1. **Nasza lokalizacja jest 2,5× lepsza od wszystkiego, co jest publicznie zmierzone:**
   oficjalny bench (129 zadań): TF-IDF recall@1/@5 = 0,21/0,50 (najlepsze), embeddingi 0,05/0,21,
   PPR 0,08/0,26; **nasz lokalizator: 0,555/0,672 (dev) i 0,510/0,740 (holdout)**.
   Innymi słowy: **nie brakuje nam znajdowania pliku** — brakuje konwersji na działającą edycję.
2. **Konwersja to nasze wąskie gardło, nie retrieval:**
   - V6.4: **19/30 zgonów na zegarze**, **11/30 pustych drzew**; V5: 9/30 i 6/30;
   - w koszyku N V6.4 **5 z 11 sesji miało złoto już na #1 i nie wykonało żadnej edycji**;
   - nasze sesje **nie kończą się same**: średnio 19,7 wywołania i 298 s (V6.4) przy capie 30/315 s
     — to znaczy, że pożerają cały cap i giną w połowie pracy (mediana 14,5 s/wywołanie, p90 80 s).
3. **Nasz cap wywołań (30) jest najniższy w stawce**, a społeczność mówi wprost: wąskim gardłem jest
   czas/proces, a nie wiedza (≈45 % rozwiązań ginie przy 6-min capie). Nie znaczy „podnieść cap
   wszystkim": znaczy **skończyć łatwe zadania wcześnie i dać trudnym dojść do końca** (suma ≤ 12 h!).
4. **Publiczny konsensus o sufitach:** dokładanie orkiestracji/skills/subagentów → ~0,10–0,14
   (my tu jesteśmy); sam prompt/scaffold → sufit 0,18–0,20 (według autora 0,17); powyżej — według
   większości — **post-training**, choć 12. miejsce twierdzi, że finetuning wcale nie pomógł.
5. **Nasze narzędzie pomiarowe ma wadę, którą potwierdza konkurent:** 16/30 naszego ekranu to
   `fastapi`, a wątek „fastapi tasks can't pass even with the gold patch" (**T**) sugeruje, że część
   z nich jest **nierozstrzygalna** — wtedy poprawa na nich nie może się pokazać, a bramki
   (np. „rozwiązane ≥ 12/30") mierzą także szum harnessu. Wnioski dla bramek w §5.

## 4. Ranking dźwigni (od najwyższego oczekiwanego zysku na godzinę GPU)

| # | Dźwignia | Dowód | Koszt | Ryzyko |
| --- | --- | --- | --- | --- |
| **L1** | **Budżet zróżnicowany + kontrakt „skończ"**: cap 8–9 min i 45–60 wywołań, ale **twarde** reguły: po edycji na dysku kończ sesję (tekst bez wywołania), stop szukania po wywołaniu X, wczesne porzucenie gdy brak kandydata | Vaibhav: −45 % rozwiązań przy 6-min capie; Pathfinder 0,08→0,12; run_03: 47 % porażek procesowych | 1 przebieg (5,6 h) | przekroczenie 12 h = **0**; mitygacja: mierzyć sumę wall-clock i utrzymać średnią |
| **L2** | **Konwersja lokalizacja→edycja**: po przeczytaniu kandydata obowiązkowy **repro w `/tmp`** (2 wywołania: heredoc + uruchomienie), potem edycja; „no empty tree" jako twardy warunek zamknięcia; anty-powtórki (`git grep` exit 1 wraca jako pusty komunikat) | POMIAR: 5/11 sesji N z gold na #1 i zero edycji; Black Cat: powtórki tego samego wywołania 10–80× | 1 przebieg | żadne (treść promptu) |
| **L3** | **Analyzer sub-agent** (read-only, własny mały budżet, `skip_summarization`) | Black Cat: 0,08 (single) → **0,10** (+analyzer, 5 min/40 wywołań); romanrozen 0,12 z analyzerem | 1 przebieg | koszt kontekstu/ czasu |
| **L4** | **Post-training (SFT/LoRA)** na 129 publicznych zadaniach (`problem_statement` + gold `patch` + `test_patch`) i na naszych rozwiązanych trajektoriach; QLoRA **rank 8–16, attention-only, wiele warstw** (nie tylko warstwa 0!) | HOST `749528` (adaptery działają), HOST `748287` (12B = tańszy trening), Maukthik: rank-32 all-layer niestabilny na W4A16 | 2–4 sesje notebookowe + ~10–20 h GPU | największy projekt; grozi przeregulowaniem do 129 publicznych zadań |
| **L5** | **Wariant 12B** zamiast 31B (szybsza inferencja → więcej tur w tym samym zegarze) | HOST `748287` (wprost sugeruje) | 1 przebieg A/B całej submisji | nieznany spadek jakości; nikt publicznie nie zmierzył |
| **L6** | **Skills** (`repo-navigation`, `verify-fix` = `py_compile` + odrzucanie śmieci w diffie) | playbook §2.2/§2.7; „26/46 patchy z plikami-śmieciami" | tanie, ale kosztuje kontekst co turę | niski |
| **L7** | Dystylacja z Claude/GPT | legalność pytana (`749585`, `742807` — jest odpowiedź HOSTA do przeczytania) | poza sandboxem (brak kluczy API) | wątek „stronger models barely beat Gemma 4 31B" (**T**) sugeruje mały zysk |

Odrzucone z uzasadnieniem: edycje plików testowych (resetowane przed gradingiem), „ParallelAgent"
(zepsuty na ADK 1.36), scratch w repo (wchodzi do patcha).

## 5. Propozycja zmiany sobotniego planu (do decyzji)

Zamiast 4 ramion promptowych (~22,4 h, które przy wariancji ±0,02–0,04 i tak nie rozstrzygną
„które jest lepsze"):

- **2 ramiona, ten sam seed 20261009, 30 zadań (~11 h):**
  - **A = V6.11 „budżet + konwersja"** = V6.7 (kontrakt) + L1 + L2, tj. cap 8–9 min / 45–60 wywołań,
    reguła „kończ po edycji", obowiązkowy repro w `/tmp`, twarde „no empty tree";
  - **B = kontrola**: V6.8 (albo V6.10) bez zmian.
- **Bramki ramienia A (pre-registracja przed przebiegiem):**
  - zakończenia z **niepustym drzewem ≥ 24/30** (V6.4: 19/30),
  - **zgony na zegarze ≤ 6/30** (V6.4: 19/30),
  - **suma wall-clock sesji ≤ 4,5 h/30 zadań** (projekcja 12 h przy 120 zadaniach — twardy warunek
    bezpieczeństwa; przy 58 zadaniach margines jest ogromny),
  - rozwiązane **≥ 12/30** i **żadnego regresu na zadaniach z kontrolą gold**,
  - raportować osobno: puste drzewa, wywołania/sesję, zakończenia własne vs ucięte.
- **Bramki ekranu do naprawy:** wykluczyć z porównań zadania, na których **gold nie przechodzi**
  (nie „rozwiązane bez edycji źródła" — playbook §10.9), bo inaczej mierzymy szum harnessu.
- **Reszta doby:** przygotowanie danych SFT z 129 zadań publicznych (notebook bez GPU) → potem
  QLoRA (L4×4) i dopiero wtedy submisja z adapterem.

## 6. Submisje

- 1/dzień, 2 finały; oczekująca submisja blokuje kolejną; scoring 22–46 h.
- Przy wariancji ±0,02–0,04 **nie ma sensu wysyłać tego samego pakietu dwa razy** ani wybierać
  finałów po jednym wyniku — trzeba mieć 2–3 powtarzalne pomiary albo wysyłać **różne** warianty
  i porównywać.

## 7. Reddit / grupy / Discord

- Reddit: brak treści o tym konkursie (jedyne trafienia dotyczą hackathonu Gemma 4 / unsloth i są
  nieaktualne). Cała wymiana odbywa się na **forum Kaggle** i na **oficjalnym Discordzie**
  (link w wątku `742815`), do którego nie mam dostępu bez konta — jeśli chcesz, to jest jedyne
  źródło, którego nie wyeksplorowałem.
- Gałęzie siostrzane (`Pokemon`, `Smak-Domu`) — techniki do przeniesienia:
  - **weryfikacja przez replikację**: w `a450b00f` dodatnie +11 pp z gałęzi `c87f7a48` **nie
    replikowało się** na 600 grach (0,203, parytet z TUNED) → „nie wysyłać". To ta sama lekcja, którą
    sami zapłaciliśmy przy ewolucji lokalizatora (runy #1–#3 unieważnione);
  - **early abandon** (`7911f950`, ARC-AGI-3: „goal classifier + early abandon + adaptive
    exploration") — porzuć przebieg, który po X tokenach nie ma postępu, i **uwolnij budżet**; krytyka
    z `Smak-Domu`: abandon przez RESET gry nie zwalnia slotu (musi być naprawdę tańszy niż gra);
  - **klasyfikacja celu przed działaniem** (typ zadania → inna strategia) — u nas odpowiednikiem
    byłby tani klasyfikator typu issue w pierwszym wywołaniu (bug/test/docs/feature).

---

### Źródła

Kaggle: `748051`, `749528`, `749597`, `749585`, `748287`, `743063`, `743506`, `742815`, `749191`,
`749224`; playbook `emiliodavola/kaggle-gemma-agent` §2, §10.8, §10.9; repo: `Gosling-dude`,
`rlawoals0529`, `Maukthik`, `bansal1600`, `usp787`, `rishaviitd`; publiczne notatniki: `lucifer19`
(Black Cat, 209 przebiegów), `romanrozen`, `mizeroluckygall`, `zhukovoleksiy`, `nihilisticneuralnet`.
Gałęzie siostrzane: `Pokemon@a450b00f` (tip `21f919d`), `Pokemon@7911f950` (tip `53a11a8`),
`Smak-Domu-Konkurs@5ed750ef` (tip `b08f8e8`).

## 8. Weryfikacja i uzgodnienie z opinią drugiej gałęzi (2026-10-15, po jej lekturze)

Cztery twierdzenia z jej przeglądu sprawdziłem u źródła; dwa przyjąłem bez zmian, dwa skorygowałem.

| twierdzenie drugiej gałęzi | weryfikacja | decyzja |
| --- | --- | --- |
| Zakaz narzędzi grafowych może być nieaktualny (270/314 zapytań zwraca wyniki) | **potwierdzone** w wątku `748323` (autor odtwarza 314 wywołań przez 4 buildy na CPU); tam też: „czy to pomaga rozwiązywać zadania — **nie testowaliśmy**", odpowiedzi mają medianę **5 763 znaki**, async nadal brakuje | **odłożone jako osobne ramię warunkowe** (jedno wywołanie, tylko gdy lokalizator nie wskazuje kandydata). Nie wchodzi do V6.11: nasz lokalizator (top-1 55,5 %) jest 2,5× lepszy od najlepszego publicznego benchu (TF-IDF 0,21), a odpowiedź grafu zjada ~40 % efektywnego kontekstu |
| Odrzucone edycje realnie marnują budżet (105/524, „część zadań powtarzała identyczne wywołanie") | **potwierdzone i mocniejsze niż w przeglądzie**: 105/524 = 20 %, pochodzi z 15 zadań, 6 z nich daje 85 %, a **47 z 105 straciło granice długiego argumentu**; autorzy widzą, że notebook Budget-Fit ostrzega przed docstringami w `old_string` | **przyjęte jako reguła V6.11**. Uwaga: nasz prompt **już miał** zakaz docstringów w `old_string` (dodany wcześniej) — dopisaliśmy więc tylko połowę „nie wysyłaj ponownie odrzuconego wywołania" + liczby jako uzasadnienie |
| `max_output_tokens: 16384` jest ryzykowne (publiczny 0,18 używa 8192) | Brak dowodu w naszych danych: żaden z naszych przebiegów nie pokazał błędu kontekstu/długości. Wątek `748323` potwierdza natomiast, że **od 8 października `include_thoughts: false` nie wyłącza rozumowania, tylko je ukrywa** (semantyka zmieniła się między buildami bez zmiany wersji) — to unieważnia część starych interpretacji ablacji | **bez zmian** (jedna dźwignia na raz); ryzyko monitorowane: przy następnej diagnostyce szukamy w śladach błędów typu „maximum context"/truncation. Zmiana 16384 → 8192 to kandydat na osobne ramię |
| Prosty single-agent lepszy niż dokładanie subagentów | **przyjęte i to koryguje moją własną listę**: w `RESEARCH` §4 miałem analyzer jako L3 na podstawie starszego pomiaru Black Cat (0,08 → 0,10). Sprzeczny, nowszy pomiar sparowany (27/70 single vs 16/70 coder+analyzer) + publiczna konfiguracja 0,18 = **single agent** | **L3 usunięte z rankingu**; do V6.11 nie wchodzi żaden subagent |
| LoRA: canary przed treningiem, ryzyko KV cache | zgodne z moim §1 i §4 (HOST `749528`, wątki `744331`/`749191`) | **canary zaimplementowany** w `tools/make_sft_notebook.py` jako twarda bramka (`SystemExit`, jeśli adapter ignorowany); rank 8, attention-only, jeden adapter |
| Gałęzie siostrzane: brak replikacji / smoke przeszacowuje | zgodne z moim odczytem (§7) | bez zmian |

Czego **nie** przyjąłem: (a) „najpierw sprawdzić checksum wheelhouse'u po wersji" — 748323 pokazuje,
że wersja nie zmienia się między buildami, więc fingerprint robimy **po hashu plików** (to samo
zalecenie, ostrzejsza implementacja); (b) włączenia grafów „na wszelki wypadek" — bez pomiaru
kosztu kontekstu to zakład, nie dźwignia; (c) traktowania 0,18/0,20 z publicznych notebooków jako
celu do kopiowania — to pojedyncze wyniki przy wariancji ±0,02–0,04 (ten sam pakiet: 0,17/0,15/0,13/0,15).
