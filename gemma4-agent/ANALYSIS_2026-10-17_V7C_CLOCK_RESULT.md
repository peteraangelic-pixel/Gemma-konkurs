# V7-c — wynik ekranu zegara: **8 minut nic nie daje** (2026-10-17)

Uruchomienie: kernel `petersharps/gemma-agent-benchmark-907b8648-20261017-000507`, start 00:05 UTC,
koniec 02:40 UTC. Artefakt pod testem: `907b8648…` = V5 z **jedną** zmienioną wartością
(`max_time_minutes 5.25 → 8.0`); `agent.yaml`, `configs/sampling.yaml` i `prompts/system.md`
bajt w bajt V5. Ten sam seed (`20261009`), te same 30 zadań.

## Wynik

| miara | V5 (cap 5,25 min) | **V7-c (cap 8 min)** | delta |
| --- | ---: | ---: | ---: |
| rozwiązane | 10/30 | **10/30** | **0** |
| średni czas zadania | 232,7 s | **261,2 s** | **+28,5 s (+12 %)** |
| łączny czas 30 zadań | 6 981 s | 7 836 s | +855 s |
| mediana czasu | — | 244,5 s | — |
| zadania dobijające do capa | — | **3/30** | — |
| puste drzewa | 6/30 | **7/30** | +1 |
| średnia liczba wywołań | — | 21,2 | — |
| najdłuższe zadanie | — | 495,9 s | — |

Zadania, które zmieniły status: V7-c **wygrał** `fastapi_14851`, **przegrał** `rich_3882` — czyli
dokładnie wymiana jeden-za-jeden, zero netto.

## Bramki (pre-rejestrowane w `GATES_V7_C.md`)

| bramka | próg | zmierzone | werdykt |
| --- | --- | --- | --- |
| **Z1** średni czas | ≤258 s bezpieczne przy 150 zadaniach; 259–330 s tylko przy ~120 | **261,2 s** | **środkowy przedział**: przy 150 zadaniach 12,1 h = przekroczenie limitu 12 h |
| **Z2** suma 30 zadań | ≤3,0 h | 2,18 h | ✅ |
| **Z3** dobijanie do capa | raport | 3/30 (V6.4: 12/30 przy capie 30 wywołań) | zegar nie jest wąskim gardłem |
| **Z4** puste drzewa | raport | 7/30 (V5: 6/30) | bez poprawy |
| **Z5** rozwiązane | nie jest kryterium | 10/30 | — |

## Wniosek: **dźwignia zegara jest martwa**

Podniesienie capa o 52 % kupiło **+28,5 s średniego czasu na zadanie i dokładnie zero dodatkowych
rozwiązań**, za cenę 12 % dłuższego przebiegu i ryzyka przekroczenia limitu 12 h przy większym
splincie. To nie jest szum w jedną stronę — to spójny obraz z wcześniejszą diagnozą V5: **tylko 5 z 30
sesji V5 kończyło się na zegarze**, a resztę kończyło coś innego (limit wywołań, własna decyzja,
puste drzewo). Skoro sesje nie są ograniczone zegarem, więcej zegara nic nie kupuje.

To zamyka największe otwarte pytanie w naszym planie i **skreśla kandydata V7-c jako dźwignię**.
Publiczne sygnały (konfiguracja 0,18 na 8 minutach, „cap 6 min gubi 45 % rozwiązań") dotyczyły
**innych paczek** — paczek, których sesje prawdopodobnie dobijały do capa. Nasza nie dobija.

## Co to znaczy dla kolejnych kroków

1. **Nie wysyłamy zegara 8 min.** Limit zostaje na 5,25 min (V5), bo daje ten sam wynik taniej.
2. **Wąskim gardłem jest konwersja, nie czas**: 7/30 sesji kończy się z pustym drzewem, a 18/30 zadań
   nie zostało rozwiązanych w żadnym z ośmiu przebiegów. Następne dźwignie muszą dotyczyć
   *przejścia od rozpoznania do poprawki* (V7-b to jedno zdanie w tę stronę) i *jakości patcha*,
   a nie budżetu.
3. **Zostaje ~11 h kwoty** (licznik L4×4 ×2: ekran ≈10 h) na kanarek LoRA — jedyną dźwignię
   z potencjałem jakościowym, nie czasowym.
