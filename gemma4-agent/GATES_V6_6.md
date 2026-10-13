# V6.6 — bramki i pre-registracja (zamrożone **przed** jakimkolwiek przebiegiem)

Stan na 2026-10-13 ~18:30 UTC. V6.6 **nie został uruchomiony**. Powstał po pełnym przebiegu V6.4
(10/30, identyczny zbiór zadań co V6.3), którego analiza wskazała defekt konstrukcyjny, nie tekstowy.

## Czym V6.6 jest

**V6.6 = V6.4 + jedna dźwignia (L2): krok lokalizacji nie tworzy pliku.**

Wszystkie reguły M1-M4, brak `submit_patch`, termin call 4 z zakazem atrapy, sampling, limity,
lokalizator (ten sam skrypt, ta sama treść poza komentarzem `# Usage`) — **bez zmian**. Nie ma tu
dźwigni z V6.5 (framing edycji) — jedno ramię na raz.

| | V6.4 | V6.6 |
| --- | --- | --- |
| artefakt | `submission-v6.zip`, `aaea34e4…`, 13 455 B | `submission-v6.6.zip`, `b6686c53…`, 13 790 B |
| prompt | 19 310 znaków | 19 769 znaków |
| wywołanie lokalizatora | `cat > /tmp/locate.py <<'LOCATE_PY' … LOCATE_PY` + `python3 /tmp/locate.py … <<'ISSUE_EOF'` | `python3 -c "$(cat <<'LOCATE_PY' … LOCATE_PY)" --root . --top 8 <<'ISSUE_EOF'` — **jedno polecenie, zero plików** |

## Dowód, na którym to stoi (pełny przebieg V6.4, 30 zadań)

| zadanie | wywołań | co zrobiła sesja | wynik |
| --- | --- | --- | --- |
| `fastapi_15588` | **3** | `run_command`, `run_command`, `write_file /tmp/locate.py` | puste drzewo (243,8 s) |
| `fastapi_15745` | **3** | `run_command`, `run_command`, `write_file /tmp/locate.py` | puste drzewo (340,6 s) |
| `rich_3043` | 4 | 3 × `run_command` + `write_file /tmp/locate.py` | puste drzewo (319,8 s) |
| `httpx_3672` | 10 | 5 × `run_command`, 4 × `read_file` + `write_file /tmp/locate.py` | puste drzewo (315,7 s) |

Cztery sesje (13 %) napisały skrypt lokalizatora i **nigdy nie edytowały repozytorium**; dwie
skończyły po trzech wywołaniach, jakby gotowy skrypt był pracą. Wersje bez kroku lokalizatora
(V3/V4/V5) miały **6** pustych drzew, V6.x ma **11**. `fastapi_15745` tracił w ten sposób drugi raz
z rzędu (w V6.3 zostawił tylko `/tmp/locate.py`, 279,8 s).

Hipoteza V6.6: to nie jest brak dyscypliny modelu, tylko **pułapka w instrukcji** — prompt każe
najpierw stworzyć plik, a zapis pliku zaspokaja poczucie „coś już zapisałem". Usunięcie pliku usuwa
pułapkę konstrukcyjnie, bez apeli.

## Sprawdzone przed wypchnięciem (nie „powinno działać")

1. **Test end-to-end na bloku wyciągniętym z gotowego promptu**: blok skopiowany znak w znak
   z `submission-v6.6/prompts/system.md` (ze skryptem i tekstem issue podstawionym w miejsca
   znaczników) uruchomiony na testowym repozytorium wypisał ranking
   (`1. pkg/module.py (score 4.3)`, linie L3/L7), **exit 0**, i **nie utworzył `/tmp/locate.py`**.
2. **Siedem kontrolek negatywnych** — każda wywala build V6.6:
   przywrócenie zapisu pliku lokalizatora; usunięcie pomiaru pułapki (4 sesje); wstawienie bloku
   lokalizatora z V6.4 (mieszanie wersji); wstawienie bloku inline do drzewa V6.4 (mieszanie
   w drugą stronę); doklejenie dźwigni V6.5 (dwa ramiona naraz); rozjechanie skryptu w drzewie
   wobec wersji osadzonej w prompcie; sprzeczny zakaz `write_file`.
3. **Regresja wariantów**: po zmianach packera V6.4 nadal daje `aaea34e4…`, V6.5 `cb847599…`,
   V6.6 `b6686c53…`; build V6.6 deterministyczny (dwa buildy = jeden hash).

## Plan przebiegów — **zmieniony wobec V6.5: dwa pełne przebiegi, nie dwa mini**

**Powód zmiany (zapisany zanim cokolwiek uruchomiono):** slot L4x4 rozlicza **sesję kernela**, nie jej
długość. Mini (6 zadań, ~45 min) i pełny przebieg (30 zadań, ~2,8 h) kosztują więc **ten sam slot**.
Pełny przebieg zwraca 5× większą próbkę *oraz* zawiera te same 6 zadań, czyli daje wszystko, co dałby
mini, plus porównanie parami na 30 zadaniach. Mini ma sens tylko jako filtr wstępny dla kandydata,
o którym z góry wiemy, że jest zły — a V6.5 i V6.6 to dwie małe, celowane zmiany, więc filtr wstępny
niczego nie oszczędza.

**Jutro (2 sloty, oba przebiegi równolegle):**

1. **Pełny przebieg V6.5** — 30 zadań, seed `20261009`, outdir `v6-5-benchmark`, archiwum `cb847599…`.
2. **Pełny przebieg V6.6** — 30 zadań, seed `20261009`, outdir `v6-6-benchmark`, archiwum `b6686c53…`.

Oba porównywane parami z **V6.4** (10/30) i **V6.3** (10/30) na tym samym zbiorze 30 zadań.
Mini-screen pozostaje jako plan awaryjny, jeśli któryś slot wypadnie.

**Oczekiwania falsyfikowalne (zapisane przed przebiegami):**

- **R1 (V6.6, mechanizm B)**: liczba zadań, których **jedynym** zapisem jest plik poza drzewem repo,
  spada do **0** (baseline V6.4: 4 zadania). Mierzone ze śladów: zadanie bez edycji w repo
  i z zapisem absolutnym.
- **R2 (V6.6, wynik)**: liczba rozwiązań **≥ 11/30** (V6.4 i V6.3: 10/30) — czyli dźwignia przekłada
  się na rozwiązania, nie tylko na mniej pustych drzew.
- **R3 (V6.5, framing)**: liczba zadań z edycją w repo w terminie **call 4 ≥ 12/30**
  (V6.4: 1/30, V6.3: 1/30) — to był cel E7, dotąd nigdy nie osiągnięty.
- **R4 (obu)**: G1 = G3 = 0; G2 raportowane (V6.4: 3). Puste drzewa raportowane (V6.4: 11).
- **Falsyfikacja**: jeśli R1 i R2 zawiodą dla V6.6, to znaczy, że pułapka lokalizatora **nie była**
  przyczyną zer (usunięcie jej nic nie zmienia) i następna hipoteza musi dotyczyć czegoś innego —
  konkretnie mechanizmu A (sesje, które w ogóle nie próbują zapisu: `rich_3105`, `rich_3934`,
  `fastapi_14266`, `fastapi_14459` w V6.4). Jeśli R3 zawiedzie dla V6.5, framing edycji jest
  wyczerpany jako kierunek i zostają dźwignie architektoniczne/parametryczne (budżet wywołań,
  kolejność ról w prompcie, telemetria).
- **E5 obowiązuje**: żaden z tych przebiegów nie jest prognozą wyniku; decyduje pełny wynik na 30
  zadaniach i ostatecznie pomiar oficjalny.

## Reguła submissji (bez zmian, ale z jawnym zastrzeżeniem do rozstrzygnięcia przez użytkownika)

Warunek z `GATES_V6_4.md`: G1-G3 = 0 w obu przebiegach ∧ ≥ 9/30 ∧ wolny slot ∧ Twoja zgoda.
**Zastrzeżenie zapisane jawnie:** G2 = 0 nie zostało dotąd spełnione przez **żadną** wersję, także
przez V4 (`0,03`, G2 = 1). Jeśli żaden kandydat nie osiągnie G2 = 0, decyzja „wysyłamy mimo G2 > 0"
należy do Ciebie i musi być zapisana razem z powodem — mechanizm jawnego wyjątku jest już
zaimplementowany w `submit_kaggle_v64_once.py` (wymaga zapisu powodu w dokumentacji bramek,
inaczej odmawia wysłania).
