# Audyt pakietu Codexa na mojej gałęzi (v3-control / v3-slim), 01.11.2026

Wejście: 3 commity `295ee5e`, `956af48`, `7941ece` (Codex) na `arena/6d081d52-gemma-konkurs`,
17 plików w `arc-agi-3/peer-review/codex-v3-{control,slim}-20261101/`. Nic nie zmieniałem w tych
plikach; nic nie zgłosiłem; żadnej sesji GPU.

Wszystko poniżej jest **odtworzone lokalnie** narzędziem
`arc3_local_candidate/tools/audit_codex_v3_packet.py` (pełne wyjście:
`arc3_local_candidate/reports/audit-codex-v3-20261101.txt`).

---

## 1. Co sprawdziłem i co się zgadza co do cyfry

| twierdzenie pakietu | moje odtworzenie | zgodność |
|---|---|---|
| kontrola: 27,49667 | **27,496670817884922** (recompute 10/10 gier, 0 niezgodności) | ✅ |
| 33 ukończone / 69 poziomów | 33 / 69 | ✅ |
| 1877 akcji, w tym RESET-y | 1877, z tego **5 RESET** → 1872 non-reset | ✅ (1872 zgodne) |
| 1 703 530 tokenów | 1 703 530 (suma `generated_tokens` z historii) | ✅ |
| 10 × `gave_up`, brak crashy | 10 × `gave_up`, `crashed=[]` | ✅ |
| ~2880–2891 s na grę | maks. 2890,7 s | ✅ |
| slim: 17,35047 / 24 | **17,350468479169024**, 24 poziomy — odtworzone z wierszy `COMPARISON.json` na baseline'ach kontroli, 0 niezgodności | ✅ |
| udział akcji na niedokończonych 15,98 % → 34,14 % | 300/1877 = 15,983 %, 649/1901 = 34,140 % | ✅ |
| podgrupa „bez kierunkowych −4 / z kierunkowymi −5" | **−4 / −5 dokładnie** przy definicji „kontrola nie użyła ACTION1–4" (tn36 −2, s5i5 −3, su15 +1) | ✅ |

To jest, jak na pakiet recenzencki, **bardzo dobry poziom**: kontrolny benchmark jest dołączony
w całości (19 310 linii), więc odtwarza się wszystko, nie tylko wynik.

## 2. A/B jest naprawdę jedną zmienną — sprawdzone na źródle

- Oba notebooki mają **po 29 komórek** i różnią się **wyłącznie komórką 1**.
- W niej: `ARC3_VARIANT["env"]` dostaje `ARC3_MEMORY_SECTIONS: "slim"` (kontrola nie ma tego klucza),
  plus zmiana `name`. `git: d0d9717428bf`, `patch_files`, `patches` (0001 + 0002) i lista 10 gier — **identyczne**.
- Notebook ma w `setup_env` domyślnie `'ARC3_MEMORY_SECTIONS': 'off'`, więc kontrola jest realnie „off".
- `machine_shape`, obraz docker, datasety, modele (drafter + W4A16), konkurs — **identyczne** w obu `kernel-metadata.json`.

Czyli to jest czysty test jednej zmiennej na tym samym sprzęcie. Sam bym tego lepiej nie zbudował.

## 3. Werdykt „slim odrzucony" — popieram, z jednym zastrzeżeniem

Bootstrap po grach (20 000 resample, n=10, sparowane delty per gra):

```
delta wyniku   -10,146   95% CI [-19,29, -1,80]   P(delta<0) = 99,3%
delta poziomów  -0,90    95% CI [-1,60, -0,20]    P(delta<0) = 99,4%
```

Kierunek jest solidny, więc „nie rozwijać slim" jest decyzją właściwą. **Zastrzeżenie, którego
pakiet nie ma:** to jedna próba na ramię, a bootstrap próbkuje **gry, nie przebiegi** — wariancja
między kolejnymi uruchomieniami tego samego kodu nie jest w tym przedziale. Z naszych czterech
zapisanych przebiegów tej samej rodziny (`r085` 26,78 / `r093` 18,55 / `r110` 0,73 / `r118` 0,27)
wynika, że między-wariantowy rozrzut jest **większy niż cały efekt slim** −10,15. To nie podważa
odrzucenia (24 vs 33 poziomy, 6 gier w dół, 1 w górę), ale podważa zdanie „slim jest gorszy
o 10 punktów" jako precyzyjne. Uczciwa forma: **„slim jest gorszy, prawdopodobnie o 5–20 punktów"**.

## 4. Rozkład spadku — i to jest najciekawszy wynik tego pakietu

```
kontrola: wynik 27,50 | cap ukończeń 29,19 | strata na efektywności 1,69 (6 % capu)
slim:     wynik 17,35 | cap ukończeń 18,89 | strata na efektywności 1,54 (8 % capu)

utracona waga poziomów 31 | zyskana 4 | netto 27 z 210 możliwych
```

**Efektywność akcji slim jest *lepsza*, nie gorsza** (1,54 vs 1,69 straty). Cały spadek 10,15 pkt
to **utracone poziomy**, nie marnowane ruchy. Slim zużył przy tym *więcej* akcji (1901 vs 1877,
+1 %) i *więcej* tokenów (+2,9 %) — czyli nie „oszczędzał i przez to nie dokończył".

To jest niezależne potwierdzenie liczby, którą pokazałem u siebie na czterech przebiegach:
**wynik ≈ liczba ukończonych poziomów z wagą = numer poziomu; efektywność to korekta 6–20 %.**
Wniosek dla strategii: każda zmiana, która nie zwiększa liczby ukończeń, nie ma jak dać punktów —
a każda, która je zmniejsza (jak slim: −9 poziomów), kosztuje podwójnie na wysokich poziomach
(samo s5i5 5→2 to −12 z 21 wagi tej gry).

## 5. Czego z tego pakietu **nie** da się sprawdzić (uczciwie)

1. **Surowy `benchmark.json` dla slim nie jest dołączony** — jest tylko kontrolny. Liczby per poziom
   slim (te, z których liczy się 17,35) są więc **niesprawdzalne**: potwierdzam arytmetykę, nie pomiar.
   To jedyna poważna luka audytowalna. Wystarczy dołożyć plik — kontrola pokazuje, że to działa.
2. **`verification.json` nie jest dowodem aktywacji.** Cztery stringi „slim" występują **0 razy**
   w obu notebookach (są składane w runtime z `_SLIM_MEMORY_SECTIONS`), więc `off_output: []`
   jest prawdziwe trywialnie. Realny dowód to `ACTIVATION.json` (wystąpienia sekcji per gra:
   12, 8, 11, 11, 17, 13, 11, 13, 6, 17) — ale te liczby wymagają logów promptów, których w pakiecie
   **nie ma**. Z kodu potwierdzam jedno: mechanizm sekcji istnieje i `slim` faktycznie zawęża
   listę do World model + Plan; nie potwierdzam, że w tych dziesięciu przebiegach był niesiony.
3. **1 752 216 tokenów** dla slim pochodzi z logu notebooka; suma w benchmarku to 0 (`final_generated_tokens=0`
   to znany artefakt eksportu, pakiet sam to kwalifikuje).
4. **„25 → 10 zaobserwowanych błędów"** — bez `control-snapshot-errors.json` w pakiecie nie sprawdzę;
   pakiet sam uczciwie pisze, że to dolna granica i nie znaczy „lepszy agent".

## 6. Dwie rzeczy, których autorzy nie zaraportowali, a widać je w ich danych

1. **Slim wolniej dochodzi do pierwszej akcji: mediana 39 s → 93 s, wolniej w 9/10 gier**,
   łącznie +545 s, czyli **1,9 % budżetu** (10 × 48 min). Przy mniejszym prompcie! To kontrintuicyjne
   i warte zbadania (kolejność/struktura promptu, nie jego długość).
2. **Przepustowość bez zmian**: 3,91 vs 3,96 akcji/min. Czyli spadek nie jest „silnikiem wolniej",
   a decyzjami: **akcje na ukończony poziom 56,9 → 79,2** (+39 %).

Trzecia uwaga metodologiczna: podgrupa „bez kierunkowych −4 / z kierunkowymi −5" odtwarza się
dokładnie, ale jest **post-hoc podziałem stałej sumy −9** na grupy n=3 i n=7 — nie wnosi dowodu
mechanizmu, tylko opis. Nie należy tego cytować jako wyjaśnienia.

## 7. Rekomendacje dla pakietu (kolejność wg wartości)

1. **Dołączyć `benchmark.json` dla slim** — bez tego każdy audyt zewnętrzny kończy się na arytmetyce.
2. **Dołączyć logi promptów albo ich hashe** (albo zgodzić się, że `ACTIVATION.json` jest deklaracją).
3. **Raportować „utraconą wagę poziomów"** obok różnicy wyniku — to liczba, która przenosi się
   między przebiegami lepiej niż punkty (u nich −27/210).
4. **Przed testem `scope=levelup` zmierzyć wariancję**: dwa przebiegi **kontroli** (test–retest)
   na tym samym notebooku. Bez tego efekt rzędu 10 pkt jest nieodróżnialny od jednego rerunu,
   a to dokładnie ten błąd, który popełnia każdy audyt „jedna próba na ramię".
5. **Nie łączyć** slim z pamięcią ani z kolejnymi sekcjami — zgoda z ich własnym wnioskiem.

## 8. Co to znaczy dla mojej linii pracy

- Ten pakiet jest o **pamięci w prompcie** na modelu docelowym; moje `v18-arena` jest o **kontrolerze
  szablonowym** na ft09. To różne dźwignie i nie kolidują — ale wniosek z §4 jest wspólny i ważniejszy
  niż oba: **punktuje się ukończenia, nie ruchy**.
- Dla mojego kroku 2 (pamięć/cache) oznacza to twardy warunek: zanim dodam mechanizm pamięci,
  muszę mieć **dwa przebiegi kontroli**, inaczej nie odróżnię +5 pkt od szumu.
- Nie dubluję ich aktywnej próby `scope=levelup` (ich README wprost o to prosi).

## 9. Stan plików

- Nowe: `arc3_local_candidate/tools/audit_codex_v3_packet.py`,
  `arc3_local_candidate/reports/audit-codex-v3-20261101.txt`, ta notatka.
- Pliki Codexa **nietknięte** (0 modyfikacji), moja wcześniejsza praca nietknięta
  (`diff -rq` wobec kopii sprzed `reset --hard` — bez różnic).
- Żadnej zgody na submisję nie użyłem i o nią nie występuję.
