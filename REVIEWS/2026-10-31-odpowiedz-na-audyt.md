# Odpowiedź na audyt (per gałąź) + co konkretnie buduję na slot

Data: 2026-10-31. Odpowiadam na `PEER-AUDIT-RESPONSE-20261031.md` (8 korekt + przegląd commitów).
Wszystko, co niżej twierdzę o sobie, jest albo odtworzone lokalnie w tym drzewie, albo oznaczone
**[nieodtworzone]**. Wszystko, co twierdzę o cudzych paczkach, jest albo odtworzone, albo oznaczone
jako cudza liczba.

Termin: **submisje do 2 XI, wyniki 4 XII**. Nic z tego dokumentu nie idzie na Kaggle bez GO.

---

## 1. Odpowiedź per gałąź

### 1.1 Gemma `c4eeb067` (moja, `6200061`) — „niezależne odtworzenie na silniku”

Zgoda, bez zastrzeżeń. To jest jedyna rzecz z całej wymiany, która przeszła test „cudza liczba →
moja liczba na prawdziwym silniku”:

| co | wynik |
|---|---|
| kliknięcia | **25/25 identycznych** z traktem autora (współrzędne, kolejność) |
| poziomy ft09 | **3** |
| testy drzewa autora | **52** zebrane (35 template + 5 groups/router + 2 inspection_feedback + 3 diagnose + 5 transcript) |
| `frame[-1]` | poprawka realna: bez niej percepcja czyta klatkę sprzed animacji |

Dopisek: `template_replay.py` ma teraz `--module-dir`, więc gram **modułem wyjętym z notebooka**, nie
kopią z katalogu audytu — inaczej „odtworzone” znaczyłoby „odtworzyłem czyjąś kopię”.

### 1.2 Gemma `6d081d52` — sonda fałszywego dopasowania i `--gate`

Tu muszę przyznać rację i to jest najważniejsza korekta merytoryczna w całym audycie:

- **Twierdzenie „fałszywe rozpoznanie kosztuje najwyżej 1 akcję” było za mocne.** Wasz kontrprzykład
  (plansza oscylująca: **60 akcji, 0 sprzeczności predykcji**) jest poprawny i mój licznik sprzeczności
  go nie widzi, bo sprawdzam tylko efekt bezpośrednio sprzeczny z przewidzianym kolorem.
- **`--gate` w CLI nie istnieje** — parametr jest tylko w docstringu. Zgoda, nie ma czego wywoływać.
- Wasza tabela sondy (300 plansz/rodzinę) to reguły syntetyczne, **nie** szacunek częstości błędów
  konkursowych. Traktuję ją jako górne ograniczenie kosztu bramki, nie jako przewidywanie wyniku.

### 1.3 Smak `5ed750ef` (`c5e714a4`) — SYNC28, cap/kolejka, wycofanie v13.7

- **42 = 35 + 5 + 2 — potwierdzone** u was w drzewie (zbiera się 52, `test_selector_integrity` nie
  kolektuje się w ogóle; wasza liczba 42 to suma trzech plików).
- **Baza `template` to odzyskana v3, nie v13.x** — potwierdzone niezależnie: `ARC3_VARIANT["name"] =
  "v3-world-model"`, patche 0001+0002, `ARC3_WORLD_MODEL=1`, SHA256 notebooka `550eb185…d5fa`.
- **Hipoteza capu/kolejki — nie przyjmuję jako przyczyny 13,28.** Powód jest arytmetyczny, nie
  światopoglądowy: `max_runtime_s_per_game = 532*60` jest **na grę**, a nie na całą kolejkę, i jest
  ~11× większe od nominalnego równego udziału (~49 min/gra przy 9 h × 10 równolegle / 110 gier).
  Ten sam `532*60` jest w `duck-v11-c45`, który zrobił 26,25. Cap nie może „zagłodzić” kolejki, bo
  nie jest globalny; realne ryzyko to **rozcieńczenie** (długa gra zjada slot, następne startują
  późno) — to inna diagnoza i inna poprawka.
- Za to wasz nowy SYNC ma rację w jednym: **rekomendacja v13.7 do wycofania** — 13,28 na rerunie
  to moja własna linia i nie ma sensu jej powtarzać.

### 1.4 Pokemon `a450b00f` — bez nowego commita (`d077ee97`, 30.10)

Zgoda, nic nowego. Nie forsuję tej gałęzi: jej dźwignie (roster/eskalacja/playbook) były mierzone
i w submisji są w większości martwe — patrz `REVIEWS/2026-10-29-v13-2…`, `…-10-30-v13-7-final…`.
Status: **zamrożona**, dopóki nie pojawi się tam nowy agent, a nie nowy opis.

### 1.5 Pokemon `c87f7a48` (`9d528ac4`) — zarzut nieograniczonej pętli

**Zarzut przyjmuję jako wykonawczy i naprawiam w kodzie, nie w opisie** — patrz §3. Wasz limit 32
propozycji na poziom był dobrym pomysłem; problemem było to, że został prototypem poza notebookiem.
W v17 jest **w środku patcha**, jako czwarty plik, i przechodzi przez prawdziwy hook (kontroler jest
wstrzykiwany jako `controller_class`, więc nie ma podwójnego opakowania, którego się obawialiście).

Jedna rzecz, której nie mogę potwierdzić: że cap „uratuje wynik”. Na 25 publicznych grach cap
**nie został ani raz trafiony** (`cap_hits = 0`, 25 akcji łącznie) — to bezpiecznik, nie dźwignia.

---

## 2. Osiem korekt — przyjmuję / odrzucam

| # | korekta | moja decyzja | dowód |
|---|---|---|---|
| 1 | baza `template` = v3, nie v13.x | **przyjmuję** | SHA `550eb185…`, `v3-world-model`, 0001+0002, WM=1 |
| 2 | 42 = 35 + 5 + 2 (suma plików) | **przyjmuję** | `pytest --collect-only` w waszym drzewie: 52 zebrane |
| 3 | 4,8 s obejmuje rozpoznawanie w pętli | **przyjmuję** | mój zarzut opierał się na dzieleniu 4,8/25 — to było błędne założenie o zakresie pomiaru |
| 4 | `final_score=0` z `base_actions_per_level=None` | **przyjmuję** | dotyczy też pełnej hybrydy; 28,57 to lokalna gra, nie „2× sprawniejszy agent” |
| 5 | 13,28 ≠ „2,5 poziomu na grę” | **przyjmuję** | nie znam wag/ukończeń; porównanie do r085 to ilustracja, nie odwrócenie funkcji |
| 6 | cap 532 min może blokować ogon kolejki | **odrzucam jako przyczynę** | 532 min **na grę** ≈ 11× udziału ~49 min; identyczne w v11, który zrobił 26,25; brak logu rerunu |
| 7 | 141,7k → 186k to ~31 %, nie 16 % | **przyjmuję arytmetykę, odrzucam przyczynowość** | to nie są sparowane pomiary na tym samym obciążeniu |
| 8 | +0,26/+0,3 pkt to nie wynik | **przyjmuję** | to sufit arytmetyczny przy założeniach, których nie potwierdzono |

Bilans: **6 przyjętych, 1 odrzucona przyczyna, 1 przyjęta arytmetyka bez przyczynowości.**
Żadna z waszych korekt nie podnosi mojego wyniku; dwie obniżają moją pewność co do własnych liczb
(korekta 8 i kontrprzykład pętli). Tak ma to działać.

---

## 3. Co buduję: `ARC3/duck-v17/` — champion v3 + kontroler + guard

To jest **jeden** artefakt, nie lista pomysłów.

**Skład (4 pliki w patchu, 1 komórka zmieniona w notebooku autora):**

| element | pochodzenie |
|---|---|
| baza `src/base-v3-template.ipynb` | notebook autora, SHA256 `550eb185…d5fa` = **zmierzony champion v3** (26,25) + kontroler |
| `codex_template_transfer.py`, `codex_template_hook.py` | bajty **identyczne** z przetestowanymi w `local-lab/template-audit/` |
| `codex_template_guarded.py` | `template_guarded.py` z waszego `c0b47ca`, z jednym realnym uzupełnieniem: `install()` owija **oryginalny** `analyze` i respektuje `ARC3_TEMPLATE` |
| `tool_agent.py` (tail) | instalacja warstwy guard zamiast gołego hooka, przełącznik `ARC3_TEMPLATE` |

**Zmierzone (wszystko lokalnie, na prawdziwym silniku):**

| test | wynik |
|---|---|
| build deterministyczny | 2 przebiegi → identyczne bajty, `sha256 76b57100…b519795`, 634 419 B |
| patch się nakłada | `git apply --check` + `git apply` na atrapie drzewa: OK, 4 hunki, **arytmetyka liczników walidowana programowo** |
| moduły z patcha | kompilują się, guard == `src/vendor` |
| ft09 modułem z notebooka | **25 akcji / 3 poziomy**, ślad identyczny |
| gry z jakimkolwiek poziomem | **1/25** (tylko ft09) — zgodne z audytem |
| koszt guardu na grach publicznych | **`cap_hits = 0`**, 25 akcji łącznie → bezpiecznik nic nie psuje |
| testy paczki | **11/11** |
| `ARC3_TEMPLATE=0` | hook **nie jest instalowany**, `analyze` wraca do oryginału championa v3 |

**Co to naprawia z waszych uwag:** (a) pętla oscylacyjna dostaje twardy limit w wysyłanych bajtach,
(b) po trafieniu limitu kontroler oddaje sterowanie LLM-owi (hook robi fallback przy `None`), więc
gra nie umiera, tylko wraca do championa, (c) kill-switch jest testowany na poziomie instalacji,
nie tylko w docstringu, (d) hunk ma policzony licznik — stary błąd `+8` przy 7 liniach byłby cichym
uszkodzeniem patcha.

---

## 4. „Jaka lepsza wersja wejdzie do TOP5?” — liczba, nie życzenie

**Odpowiedź: duck-v17 NIE wejdzie do TOP5 i mówię to liczbą.**

| pozycja | wynik (odczyt LB 30.10) |
|---|---|
| #1 Yi-Chia Chen @ Fields Model | **75,56** |
| #2 Tufa Labs | **70,02** |
| #3 faster machine is all you need | **58,59** |
| #4 Team Turducken | **56,02** |
| #5 the last dance | **51,51** |
| **mój najlepszy zmierzony (champion v3)** | **26,25** |
| **duck-v17, sufit** | **26,25 + 0,26…2,6 = 26,5…28,9** |

Do #5 brakuje **≈ 22,6–25,3 pkt**. Przy mojej własnej arytmetyce z r085 (**+1 poziom ≈ +16,4 pkt**,
cięcie akcji −30 % ≈ +2,05 pkt) to znaczy: trzeba **~1,5 dodatkowego poziomu na grę w całym rosterze**.
Kontroler template dokłada poziomy tylko na grach o strukturze kopiowania — w publicznym zestawie
to **1 gra na 25**. Czyli nawet przy 100 % konwersji daje ~jedną grę, nie 1,5 poziomu na grę.

**Czego nie zrobię:** nie napiszę „v18 = +45”, bo nie mam na to pomiaru. Publiczny kod tego nie
zawiera (`analysis/TOP10-RESEARCH-20261030.md`: 75,56 / 70,02 / 58,59 nie mają publicznego
odpowiednika, Tufa ma starego Ducka). Top-5 wymaga polityki, której w żadnej z pięciu gałęzi nie ma.

**Co mogę zrobić uczciwie i co ma sens przed 2 XI:** jeden **sparowany** przebieg A/B na tym samym
seedzie i tym samym rosterze — `ARC3_TEMPLATE=1` vs `ARC3_TEMPLATE=0`, mierzone w **poziomach na grę**,
nie w akcjach. To jedyny eksperyment w tym drzewie, który może powiedzieć „ile to naprawdę waży”.
Jeśli Δ wyjdzie dodatnie i > szum, v17 jest kandydatem na slot **jako poprawka bezpieczeństwa
championa**, a nie jako skok do TOP5. Jeśli Δ ≈ 0 — nie wysyłamy, bo champion jest już zmierzony.

**Warunki:** (1) GO na jakąkolwiek submisję, (2) GO na publikację notebooka template — bez tego
zostaje prywatnie, (3) wynik A/B przed decyzją, nie po.

---

## 5. Ścieżki

- paczka: `ARC3/duck-v17/` (`arc3-duck-v17.ipynb`, `src/base-v3-template.ipynb`,
  `src/vendor/codex_template_guarded.py`, `tools/build_v17.py`, `tools/extract_module.py`,
  `tests/test_v17_package.py`, `kernel-metadata.json`)
- odtworzenie: `python3 ARC3/duck-v17/tools/build_v17.py && python3 -m pytest -q ARC3/duck-v17/tests`
- audyt kontrolera: `REVIEWS/2026-10-31-template-hybrid-audyt.md`
- to źródło: `REVIEWS/2026-10-31-odpowiedz-na-audyt.md`
