# V7-b — V5 + jedno zdanie (pierwsza submisja „jedna dźwignia" po 0,08)

Stan: 2026-10-16 ~20:00 UTC. Uzbrojone na **2026-10-17 00:05 UTC** (02:05 czasu Warszawskiego).

## Skąd ta paczka

V6.12 dał **0,08** przy V5 **0,13** — a różnił się od V5 w pięciu miejscach naraz, więc wyniku nie da
się przypisać żadnej dźwigni (`ANALYSIS_2026-10-16_V6_12_RESULT.md`). Wracamy do jedynej bazy
z dodatnim wynikiem oficjalnym i ruszamy dokładnie **jeden** czynnik.

## Delta wobec V5 (wykonalna definicja, nie deklaracja)

| plik | V7-b |
| --- | --- |
| `agent.yaml` | **bajt w bajt V5** (`42f5f5a8a688`) — `submit_patch` zarejestrowane, ta sama nazwa, ten sam model |
| `eval_config.yaml` | **bajt w bajt V5** (`de6b3f1182d2`) — 150 s / 45 / 80 / **5,25 min** |
| `configs/sampling.yaml` | **bajt w bajt V5** (`66479019de1e`) |
| `prompts/system.md` | V5 (5 370 znaków) + **jedno dopisane zdanie** (484 znaki) = 5 855 znaków |

Dopisane zdanie (`tools/check_v7b_delta.py` trzyma jego treść jako stałą):

> **Put the edit on disk before you verify**: in the last screen every session that scored zero died
> with an empty tree - five ran out of clock (298-325 s of the 315 s cap) and one spent 227 s inside a
> single command - so once you have read the definition you intend to change, making that change is
> the very next call you make, and keep every command you run bounded (`timeout 45`): an edit that has
> not been written yet cannot be graded, and an empty tree is the only guaranteed zero.

**Czego w nim celowo NIE ma** (to jest różnica wobec V6.12): żadnego „pierwsza edycja do wywołania 4",
żadnego „finish as soon as your edit is on disk", żadnych deadline'ów po numerze wywołania. V6.12
odziedziczył po V6.4–V6.10 twarde deadline'y i to one są podejrzane o zamianę weryfikacji na wczesne
zatrzymanie sesji. Bramka odrzuca te frazy, jeśli ktokolwiek je dopisze.

## Uzasadnienie z pomiarów (nie z intuicji)

- V5-owy ekran: **6/30 pustych patchy = 6 gwarantowanych zer**; wszystkie 6 miały `exit=-1`.
- Mechanizm: **5 z 6 zginęło na zegarze** (298–325 s przy capie 315 s), jedno zadanie spaliło **227 s
  w jednym poleceniu** przy 7 wywołaniach (nieograniczony `pytest`), 2 uderzyły w limit 45 wywołań.
- Wniosek z dokumentacji harnessu: oceniany jest **diff drzewa**, nie wywołanie `submit_patch()`;
  jedynym gwarantowanym zerem jest drzewo bez edycji. Skoro sesje giną, *zanim* cokolwiek napiszą,
  to kolejność „najpierw edycja, potem weryfikacja" jest dźwignią, a nie stylem.
- Wszystkie 10 rozwiązanych patchy V5 było < 1 900 znaków, a patche > 2 000 znaków przegrały 0/6 —
  czyli V5-owa reguła „minimalna edycja" działa; brakowało kolejności wykonania.

## Weryfikacja przed wysyłką

| kontrola | wynik |
| --- | --- |
| packer V5 (`build_submission_v5.py --source-dir gemma4-agent/submission-v7b`) | PASS — zamknięty zbiór 4 plików, `agent.yaml` w korzeniu, model `gemma-4-31b-it-qat-w4a16-ct`, tylko narzędzia harnessu, budżet ≤ 5,5 min, thinking + summaries |
| bramka delty (`tools/check_v7b_delta.py`) | PASS — 3 pliki bajt w bajt V5, prompt = V5 + dokładnie jedno zdanie |
| mutacje bramki (`--mutate`) | **6/6 kontroli się zapala** (IDENT ×2, PREFIX, SENTENCE, FORBIDDEN, NAME) |
| archiwum | `e35f20ab1361450d1877010188620d130117e657492a7b48d2c49d681086886e`, 5 002 B, 4 pliki, CRC OK |
| strażnicy wysyłki (pin SHA, duplikat komunikatu, slot dzienny, okno 24 h) | bez zmian — te same, przetestowane 7/7 |

## Pre-registracja odczytu wyniku

Ten sam pakiet publicznie dawał 0,13/0,15/0,17/0,15, więc **pojedynczy przebieg przy ±0,02 niczego
nie rozstrzyga**. Czytamy tak:

| wynik V7-b | odczyt | co dalej |
| --- | --- | --- |
| **≥ 0,16** | dźwignia „edycja przed weryfikacją" konwertuje | zostaje w bazie; następna dźwignia: ewoluowany lokalizator |
| **0,11–0,15** | nieodróżnialne od V5 | zdanie zostaje (nie szkodzi), przechodzimy do lokalizatora; pustych drzew pilnujemy na ekranie |
| **≤ 0,09** | samo zdanie szkodzi (bardzo mało prawdopodobne) | cofamy zdanie i wracamy do czystego V5 |

**Uczciwa granica:** V7-b **nie** jest poprawką na skalę 0,13 → 0,20. To tania informacja o jednej
dźwigni, na darmowym slocie, bez zużycia kwoty GPU. Skok do okolic 0,20+ wiążemy z adapterami LoRA
(jedyna droga, którą czołówka faktycznie idzie), a nie z kolejnymi zdaniami w prompcie.

## Odtworzenie

```
python3 gemma4-agent/tools/check_v7b_delta.py --mutate
python3 gemma4-agent/build_submission_v5.py --source-dir gemma4-agent/submission-v7b --output gemma4-agent/submission-v7b.zip
# oczekiwany SHA-256: e35f20ab1361450d1877010188620d130117e657492a7b48d2c49d681086886e
```
