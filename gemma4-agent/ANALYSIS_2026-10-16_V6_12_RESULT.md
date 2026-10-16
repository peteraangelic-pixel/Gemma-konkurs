# V6.12 — wynik oficjalny 0,08 (ref `57247888`): co wiemy, czego nie wiemy, co dalej

Stan: 2026-10-16 ~19:30 UTC. Odczyt read-only (poll `38954361766`), bez żadnego nowego uploadu.

## Wynik

| data wysyłki (UTC) | ref | wersja | public score |
| --- | --- | --- | ---: |
| 2026-10-10 14:51 | `57045226` | V4 | 0,03 |
| 2026-10-14 15:58 | `57188055` | V5 | **0,13** |
| **2026-10-16 00:05** | **`57247888`** | **V6.12** | **0,08** |

Kontekst tablicy (poll 19:22 UTC): **2 964 drużyny**, mediana **0,130**, p25 **0,080**, p75 0,170,
p90 0,180, p99 0,200, lider 0,24. Nasz wiersz rank 1460 pokazuje **0,13** (tablica trzyma najlepszy
wynik, nie ostatni). Czyli: V6.12 wylądował **dokładnie na p25**, V5 jest **na medianie**.

## Czego NIE wolno z tego wywnioskować

**Nie da się przypisać 0,08 jednemu czynnikowi.** V6.12 różnił się od V5 w pięciu miejscach naraz —
to był nasz błąd procesowy, nie brak danych:

| # | element | V5 (0,13) | V6.12 (0,08) | uwaga |
| --- | --- | --- | --- | --- |
| 1 | prompt | **5 370 znaków** | **23 406 znaków** (4,4×) | kontrakt V6.7 + lokalizator + inline + deadline'y + reguły konwersji V6.11 |
| 2 | `submit_patch` | **zarejestrowane** | **usunięte** | hipoteza „harness sam zbierze diff" — patrz niżej |
| 3 | `tools/locate.py` | brak | ewoluowany lokalizator, inline | 500 mutacji, wygrany na holdoucie offline |
| 4 | `name`/`description` | `gemma4_fast_repair` | `gemma4_locator_repair` | kosmetyka, ale zmienia nagłówek konfiguracji |
| 5 | `eval_config.yaml` | 150 s / 45 / 80 / 5,25 min | **identyczne parametry** | zweryfikowane parsowaniem, różnią się tylko komentarze |
| 6 | `configs/sampling.yaml` | 0,4 / 0,95 / 40 / 16 384 | **identyczne** | `diff` pusty |

Jedno jest już wykluczone na podstawie naszych własnych pomiarów: **usunięcie `submit_patch` nie
tłumaczy spadku** — ekrany V6.4, V6.6, V6.7, V6.9, V6.10 rozwiązywały zadania (10–11/30) bez tego
narzędzia, czyli ścieżka „harness zbiera diff drzewa roboczego" działa. Zostają więc: długość treści
promptu i reguły pacingu.

## Główny podejrzany (i dlaczego to nie jest wymówka)

V6.12 odziedziczył po V6.4–V6.10 **twarde deadline'y**: pierwsza edycja **do wywołania 4**, koniec
szukania na 14, koniec pracy na 18 — plus od V6.11 „**finish as soon as your intended edit is on
disk**". Te reguły powstały, żeby naprawić dominantę ekranu: **11/30 pustych drzew** (V6.4) i 6/30
(V5). Na ekranie wyglądały dobrze. Ale na ukrytym splicie „zero pustych drzew" nie jest celem samym
w sobie: sesja, która przestaje weryfikować po pierwszej edycji, zamienia *pewną zerówkę* na
*niepewną jedynkę*, a przy okazji **przestaje uruchamiać test i poprawiać własny błąd** — czyli
oddaje pętlę, w której SWE-benchowe naprawy faktycznie się udają. 0,05 = ok. 3 zadania z 58
publicznych.

Uczciwa nuta: dostępne szumy (ten sam pakiet publicznie: 0,13/0,15/0,17/0,15) to ±0,02, a nasze
0,05 to ~2,5× tyle — ale to nadal **jeden przebieg jednej paczki**, więc mówimy „prawdopodobnie
regresja", nie „dowód na konkretną regułę".

## Wniosek operacyjny (zgodny z pre-registracją z `GATES_V6_12.md`)

Pre-registracja mówiła: „≤ 0,09 → regresja: wrócić do konfiguracji klasy V5 i przescrenować przed
kolejną wysyłką". Realizacja, z jedną zmianą strategii:

1. **Baza wraca do V5** (5 370 znaków promptu, `submit_patch` zarejestrowane, brak lokalizatora) —
   to jedyna konfiguracja z dodatnim, powtarzalnym wynikiem oficjalnym.
2. **Od teraz jedna dźwignia na submisję.** Slot dzienny jest darmowy i nie zużywa naszej kwoty GPU,
   a jedynym wiarygodnym pomiarem wyniku jest Kaggle, nie 30-zadaniowy ekran (V4 11/30 → 0,03,
   V5 10/30 → 0,13 — ekran nie jest forecastem).
3. **GPU tylko do pytań o bezpieczeństwo zegara** (średni czas zadania vs limit 12 h), nie do
   rankingu wariantów.
4. Kandydaci na drabinkę (kolejność wg siły dowodów):
   - **V7-a: V5 + ewoluowany lokalizator** — jedyna dźwignia zmierzona offline na holdoucie
     (transfer, nie dopasowanie), i tania: zamienia pętle grepów na jedno wywołanie, więc oddaje
     czas na naprawę. Zero nowych reguł pacingu.
   - **V7-b: V5 + jedno zdanie „puste drzewo = zero"** (bez deadline'ów i bez „finish early") —
     celuje w 20 % sesji, które są zerami z definicji.
   - **V7-c: V5 + zegar 8 min bez „finish early"** — **dopiero po** zmierzeniu średniej na ekranie,
     bo limit 12 h zeruje całą submisję (host `743063`), a publiczna konfiguracja 0,18 (8 min)
     dowodzi tylko, że *jakiejś* paczce się to mieści.

## Higiena przy okazji (incydent, żeby się nie powtórzył)

Dwa pierwsze „ticknięcia" pollingu nie odpaliły Actions, bo commit z `[skip ci]` w opisie **pomija
workflow push** — a właśnie tak opisane były commity triggera. Trzeci, bez tego tokenu, ruszył
natychmiast. Reguła: **commit, który ma odpalić workflow, nie może zawierać `[skip ci]`** (dotyczy
także przyszłych uzbrojeń triggera wysyłki; workflow zapisu paragonu używa `[skip ci]` celowo, żeby
nie zapętlić się na własnym commicie).

## Kolejny krok

Slot dzienny otwiera się o **2026-10-17 00:05 UTC** (= 02:05 czasu Warszawskiego), w tym samym
momencie co reset kwoty GPU (00:00 UTC). Rekomendacja: uzbroić **V7-a** (V5 + lokalizator, jedna
dźwignia) i równolegle na GPU zmierzyć **zegar** na bazie V5, żeby V7-c przestał być zakładem.
