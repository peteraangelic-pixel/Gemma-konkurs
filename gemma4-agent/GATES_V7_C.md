# V7-c — ekran zegara 8 min na bazie V5 (pomiar, nie kandydat do wysyłki)

Stan: 2026-10-16 ~20:00 UTC. **Nic nie jest odpalone** — czeka na push
`gemma4-agent/kaggle_smoke/v7c-benchmark.trigger`.

## Po co ten ekran

Decyzja „podnieść zegar z 5,25 na 8 minut" jest warta najwięcej z pojedynczych dźwigni
(publicznie: konfiguracja 0,18 chodzi na 8 minutach; cap 6 min gubi ~45 % rozwiązań; bez capa 0,12
vs cap 4 min 0,08), ale jest **zakładem o limit 12 h**, a jego przekroczenie **zeruje całą submisję**
(host `743063`). Brakuje jednej liczby: **jak rośnie średni czas zadania, gdy podnieść cap**.

V7-c odpowiada na to pytanie przy minimalnej liczbie zmiennych: to **V5 z jedną zmienioną wartością**
(`max_time_minutes: 5.25 → 8.0`). `agent.yaml`, `configs/sampling.yaml` i `prompts/system.md` są
**bajt w bajt V5** — sprawdzone przy budowie archiwum.

| plik | V7-c |
| --- | --- |
| `agent.yaml` | identyczny z V5 (model, narzędzia, `submit_patch`) |
| `configs/sampling.yaml` | identyczny z V5 |
| `prompts/system.md` | identyczny z V5 (5 370 znaków, **bez** reguł pacingu z V6) |
| `eval_config.yaml` | **jedyna zmiana**: `max_time_minutes: 8.0`; `timeout_seconds: 150`, `max_tool_calls: 45`, `max_turns: 80` bez zmian |

Archiwum: `907b8648c6dcbb53b7f2fb3c5fa9a54d73af55278b66c04aeef70714ce19883e`, 5 091 B, 4 pliki.
Packer buduje je **tylko** z flagą `--clock-arm-minutes 8.0`, tylko z drzewa `submission-v7c`,
i drukuje banner „MEASUREMENT ARM ONLY"; ścieżka zgłoszeniowa V5 nadal odrzuca wszystko > 5,5 min.

## Arytmetyka, którą ten ekran rozstrzyga

    120 zadań × (średnia 3,9 min + ~0,5 min setup) = ~8,8 h     <- V5, jedyny przebieg ze wynikiem
    120 zadań × (cap 5,25 min + 0,5 min setup)     = 11,5 h     <- najgorszy przypadek, który V5 przeżył
    120 zadań × (cap 8,0  min + 0,5 min setup)     = 17,0 h     <- nie mieści się
    150 zadań × (średnia 4,3 min + 0,5 min setup)  = 12,0 h     <- konserwatywny próg

Czyli: **średnia ≤ 4,3 min = bezpiecznie nawet przy 150 zadaniach; ≤ 5,5 min = bezpiecznie tylko
przy ~120**. Wynik ekranu to jedna liczba (średnia) plus rozkład (ile sesji dobija do capa).

## Bramki (pre-registracja, przed uruchomieniem)

| # | miara | wartość odniesienia | decyzja |
| --- | --- | --- | --- |
| Z1 | **średni czas zadania** | V5: 233 s (cap 315 s); V6.4: 298 s (cap 315 s) | **≤ 258 s (4,3 min) → zegar 8 min jest bezpieczny i wchodzi jako dźwignia; 259–330 s → bezpieczny tylko przy ~120 zadaniach (wysyłka tylko po dodatkowym pomiarze); > 330 s → zegar zostaje na 5,25 min** |
| Z2 | suma wall-clock 30 zadań | V6.4: 8 954 s | ≤ 3,0 h → spójne z Z1 |
| Z3 | sesje dobijające do capa | V6.4: 12/30 na 30 wywołań | raportowane osobno; przy 8 min oczekujemy spadku |
| Z4 | puste drzewa | V5: 6/30 | raportowane osobno — jeśli podniesienie zegara *zmniejsza* puste drzewa, to jest dodatkowy argument za zegarem |
| Z5 | rozwiązane zadania | V5: 10/30 | **nie jest kryterium decyzji** — ekran nie jest forecastem (V4 11/30 → 0,03; V5 10/30 → 0,13) |

**Czego ten ekran nie powie:** czy wyższy zegar podnosi *wynik oficjalny*. To zmierzy dopiero
submisja — dlatego kolejność jest: najpierw bezpieczeństwo (Z1/Z2), potem wysyłka kandydata z zegarem.

## Uruchomienie

```
git push  # plik .github/workflows/gemma-kaggle-v7c-clock-screen.yml (rejestracja definicji)
git push  # plik gemma4-agent/kaggle_smoke/v7c-benchmark.trigger (odpala run)
```

Kolejność jest obowiązkowa: push, który **jednocześnie** zmienia plik workflow i dodaje nowy
plik-trigger, **nie odpala runu** — filtr `paths` ocenia zarejestrowana definicja. Sprawdzone
2026-10-16 (`2847461` bez runu, `6fc67dc` z runem natychmiast).

Koszt: 30 zadań × ~5–8 min ≈ **3,5–4,5 h** z tygodniowej kwoty 30 h (L4×4 liczy się ×2 → realnie
~7–9 h limitu). Workflow nie tworzy żadnej oficjalnej submisji.

## Uzbrojenie (wykonane) + awaria rejestracji workflow po stronie GitHuba

- Run: **`38957738585`**, sha `5834516`. Job `arm`, krok 3 „Wait for the weekly GPU quota reset /
  daily boundary" = `in_progress` o 19:50 UTC → ekran startuje o **2026-10-17 00:05 UTC** (po resecie
  kwoty o 00:00), a job `collect` (świeży budżet 6 h) dociąga wynik przez `tools/poll_kernel_until_done.py`.
- **Incydent GitHuba (2026-10-16, ~19:40 UTC):** GitHub **przestaje rejestrować nowe pliki workflow**
  w tym repo. Dowody: `gemma-kaggle-v67/v68/v69/v610/v611-benchmark.yml` oraz świeżo dodany
  `gemma-kaggle-v7c-clock-screen.yml` **nie występują** w `/actions/workflows` (43 pliki lokalnie,
  32 zarejestrowane), a **minimalny** workflow-sonda też się nie zarejestrował — czyli to nie treść
  pliku. Pliki istniejące nadal działają, **łącznie ze zmianami treści** (dowód: run `38956037802`
  odpalił się o 19:35 na pushu dotykającym wyłącznie `official-submit-v7b.trigger`, ścieżki obecnej
  tylko w zedytowanej definicji).
- **Obejście:** ekran V7-c jedzie na **istniejącym, zarejestrowanym** pliku
  `.github/workflows/gemma-kaggle-v64-benchmark.yml` (id `383191760`), zachowując jego ścieżkę
  triggera `gemma4-agent/kaggle_smoke/v64-benchmark.trigger` bez zmiany. Nazwa runu w Actions to
  „Gemma Kaggle V7-c clock screen", co jest *dowodem*, że GitHub użył nowej treści pliku.
  Ramię V6.4, które ten plik nosił, jest i tak przedawnione (zmierzone 10/30, a jego reguły to
  dokładnie ten rodzaj nieprzypisywalnej paczki, przed którą ostrzega wynik V6.12).
- Konsekwencja dla przyszłych prac: **dopóki nie rejestrują się nowe pliki, każdy nowy „launcher"
  musi wejść jako zmiana treści istniejącego zarejestrowanego pliku** (i to jest też powód, dla
  którego V6.10/V6.11 nigdy same nie odpaliły — ich workflowy są w tym gronie).
