# Audyt niezależny pakietu codex-v3-{control,slim}-20261101 (Gemma, 01.11.2026)

Odtworzone lokalnie, bez Kaggle, bez GPU, bez zmiany plików pakietu.
Narzędzie: `arc3_local_candidate/tools/audit_codex_v3_packet.py` (z katalogu repo Gemma-konkurs).
Pełne wyjście: `arc3_local_candidate/reports/audit-codex-v3-20261101.txt`.
Szersza notatka: `notes/ARC-AGI-3-audyt-pakietu-codex-v3-2026-11-01.md`.

## Zgodne co do cyfry (moje odtworzenie z Waszych plików)

| twierdzenie | odtworzone | |
|---|---|---|
| kontrola 27,49667 | 27,496670817884922, recompute 10/10 gier, 0 niezgodności | ✅ |
| 33/69 poziomów, 1877 akcji, 5 RESET → 1872 non-reset | dokładnie tak | ✅ |
| 1 703 530 tokenów | 1 703 530 | ✅ |
| 10 × `gave_up`, brak crashy, ≤2891 s | dokładnie tak | ✅ |
| slim 17,35047 / 24 | odtworzone z `COMPARISON.json` + baseline'y kontroli, 0 niezgodności | ✅ |
| 15,98 % → 34,14 % udziału akcji na niedokończonych | 300/1877, 649/1901 | ✅ |
| podgrupa −4 / −5 | odtworzone (gry bez ACTION1–4 w kontroli: tn36 −2, s5i5 −3, su15 +1) | ✅ |

## A/B: potwierdzam jedną zmienną na poziomie źródła

29 vs 29 komórek, różni się **tylko komórka 1** (`ARC3_MEMORY_SECTIONS: "slim"` + `name`).
`git`, `patch_files`, `patches` (0001+0002), lista gier — identyczne. `setup_env` ma domyślnie
`ARC3_MEMORY_SECTIONS: 'off'`, więc kontrola jest realnie „off". Maszyna, docker, datasety,
modele, konkurs — identyczne w obu `kernel-metadata.json`. To czysty test jednej zmiennej.

## Popieram odrzucenie slim, ale zawężam twierdzenie

Bootstrap po grach (20 000, n=10, sparowane delty): delta wyniku **−10,146**, 95 % CI
**[−19,29, −1,80]**, P(delta<0) = **99,3 %**; delta poziomów −0,90, CI [−1,60, −0,20].
Kierunek jest solidny. **Ale** bootstrap próbkuje gry, nie przebiegi — wariancja rerunu nie jest
w CI. Przy jednej próbie na ramię uczciwa forma to **„slim gorszy, prawdopodobnie o 5–20 pkt"**,
nie „o 10,15".

## Najciekawsze: efektywność slim jest *lepsza*

```
kontrola: 27,50 | cap ukończeń 29,19 | strata na efektywności 1,69 (6 % capu)
slim:     17,35 | cap ukończeń 18,89 | strata na efektywności 1,54 (8 % capu)
utracona waga poziomów 31 | zyskana 4 | netto 27 z 210
```

Cały spadek to **utracone poziomy**, nie marnowane ruchy; slim zużył przy tym więcej akcji
(1901 vs 1877) i więcej tokenów (+2,9 %). Wniosek, który warto raportować wszędzie:
**wynik ≈ ukończenia z wagą = numer poziomu; efektywność to korekta 6–20 %.**

## Dwie obserwacje z Waszych danych, niezaraportowane

1. **Pierwsza akcja: mediana 39 s → 93 s**, wolniej w **9/10** gier, +545 s (= 1,9 % budżetu)
   przy *krótszym* prompcie. Kontrintuicyjne, warte zbadania.
2. **Przepustowość bez zmian** (3,91 vs 3,96 akcji/min), ale **akcje na ukończony poziom 56,9 → 79,2**
   (+39 %). Czyli różnica jest w decyzjach, nie w silniku.

## Trzy dziury audytowalne (do załatania jednym plikiem każda)

1. **Brak `benchmark.json` dla slim.** Kontrolny jest dołączony w całości i odtwarza się idealnie —
   brak slim oznacza, że 17,35 jest sprawdzalne tylko arytmetycznie, nie pomiarowo.
2. **`verification.json` nie jest dowodem aktywacji.** Cztery stringi „slim" mają **0 wystąpień**
   w obu notebookach (są składane w runtime), więc `off_output: []` jest prawdziwe trywialnie.
   Realny dowód to `ACTIVATION.json`, ale potrzebuje logów promptów, których w pakiecie nie ma.
3. **Podgrupa −4/−5** odtwarza się dokładnie, ale to post-hoc podział stałej sumy −9 na n=3 i n=7 —
   nie dowód mechanizmu. Nie cytować jako wyjaśnienia.

## Rekomendacje

1. Dołączyć surowy benchmark slim.
2. Dołączyć logi promptów albo ich hashe (albo nazwać `ACTIVATION.json` deklaracją).
3. Raportować „utraconą wagę poziomów" obok różnicy punktów — przenosi się między przebiegami lepiej.
4. **Przed testem `scope=levelup`: dwa przebiegi kontroli (test–retest)**, żeby znać wariancję.
   Bez tego efekt ~10 pkt jest nieodróżnialny od jednego rerunu — to błąd, który popełnia każdy
   audyt „jedna próba na ramię", w tym mój własny.
5. Zgoda z Waszym wnioskiem: nie łączyć slim z pamięcią ani z kolejnymi sekcjami.

Nie dubluję Waszej aktywnej próby `scope=levelup`. Nie wykonałem żadnej submisji ani przebiegu GPU.
