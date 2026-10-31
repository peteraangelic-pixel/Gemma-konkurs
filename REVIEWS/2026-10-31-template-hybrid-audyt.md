# Audyt: kontroler `template` + hybryda ft09, gałąź `codex/arc-local-lab-v18-20261030` (31.10)

**Materiał:** komit `3926007e` (na nim `91f1ce9`, `aec6c3e`, `f730639`), katalog
`arc-agi-3/analysis/` + `duck-lab-candidates/template/agent.ipynb`.

**Werdykt w trzech zdaniach:** pakiet jest **rzetelny** — odtworzyłem go w całości na
prawdziwym silniku, w tym **wszystkie 25 kliknięć** identycznych z ich zapisem, i wszystkie
sprawdzalne liczby się zgadzają. Ale to **jedna publiczna gra**: sufit wpływu na wynik Kaggle
to **+0,26 pkt** przy średniej po 110 grach, a „3 vs 0" jest wynikiem na grze użytej
w rozwoju, nie generalizacją. Najważniejsza liczba w całym pakiecie jest jednak inna:
**v13.7-final = 13.28 na prawdziwym rerunie** — a to jest linia, z której pochodzi mój duck-v16.

---

## 1. Co odtworzyłem niezależnie (nie z ich JSON-ów)

Zainstalowałem silnik od zera: `arcengine 0.9.3` + `arc-agi 0.9.9` (PyPI, rozpakowane wheele —
wymagają pythona 3.12, więc `sys.path.insert`, dokładnie jak w ich `local-engine/README.md`),
pliki gier z repo (`arc-agi-3/games/environment_files`, 25 gier).

| twierdzenie | wynik u mnie | jak |
|---|---|---|
| SHA256 notebooka `550eb185…d5fa` | **zgodny** | `sha256sum duck-lab-candidates/template/agent.ipynb` |
| moduł w notebooku == `analysis/template_transfer.py` | **bajt w bajt** | wypakowanie patcha z kom. 8 i `diff` |
| hook w notebooku == `analysis/template_hook.py` | **bajt w bajt** | j.w. |
| „42 testy Python przeszły" | **52 passed** | `pytest analysis/tests -q` |
| 3 poziomy ft09 w 25 akcjach | **3 / 25, per-level [4,7,14]** | mój replay na silniku, `template_replay.py` |
| 25 rzeczywistych akcji | **wszystkie 25 kliknięć identyczne** | porównanie z `harness-template-repro/game-run.json` |
| abstynencja na 24 pozostałych grach | **potwierdzona (0 akcji na każdej)** | 25 gier × 256 akcji cap |
| poziom 4 nierozpoznany → oddanie sterowania | **potwierdzone** (przebieg kończy się na 3) | j.w. |

To nie jest audyt „na opisach": zapisana początkowa plansza ft09 (`ft09-initial-grid.json`)
jest **identyczna bit w bit** z klatką, którą daje silnik przy `seed=731`, a mój przebieg
odtwarza kolejność kliknięć co do piksela. Liczby autora są prawdziwe.

## 2. Pułapka odtwarzania, której nie ma w raporcie

Po zaliczeniu poziomu `fd.frame` zwraca **dwie klatki**: `[przejściowa, ustalona]`.

```
po kliku 1..3: len(frame)=1  kolory [0 2 4 5 8 9 11 12]
po kliku 4:    len(frame)=2  frame[0] = [0 2 4 5 8 9 11 12]   <- animacja/przejście
                             frame[-1] = [0 2 4 9 12]        <- == ft09-level2-grid.json autora
```

Kto napisze replay biorący `frame[0]`, dostanie **1 poziom i 4 akcje** i uzna wynik autora
za nieodtwarzalny. Ja tak zrobiłem za pierwszym razem. Harness czyta *ustaloną* klatkę
(`write_runtime_state`), więc `frame[-1]` jest poprawną obserwacją. **Do dokumentacji
`DISCOVERIES`: obserwacja = ostatnia klatka, nie pierwsza.** To jedyne miejsce, w którym
ktoś może uczciwie „obalić" ich wynik i się pomylić.

## 3. Legalność obserwacji — sprawdzone w kodzie, nie w opisie

`template_transfer.infer_copy_action(grid, learned)` dostaje **tylko piksele**; `act()` dodatkowo
`available` i `level`. W kodzie nie ma: identyfikatora gry, współrzędnych stałych, palety
rozwiązania, baseline'u, dostępu do silnika ani plików z rozwiązaniami. Grep po `template_*.py`
na `game_id|baseline|arcengine|solution` — zero trafień. Potwierdzam zgodność z deklaracją.

Jedno niuansowanie warte zapisania: kontroler widzi **pełną numeryczną siatkę 64×64**
z pliku runtime state, podczas gdy LLM dostaje tylko `segmentation`/`ascii` („raw numeric grid
is intentionally not exposed" — z ich własnego promptu w logu r085). To nie jest oszustwo
(siatka to obserwacja), ale jest to **uprzywilejowany widok względem modelu** — jeśli kiedyś
będziecie to porównywać „kontroler vs LLM", to nie jest ten sam input.

## 4. Izolacja pamięci między grami — działa, z jednym zastrzeżeniem

Hook trzyma kontroler na instancji `ToolAgent`, kluczowany po `str(state_path.resolve())`
(`template_hook.py:26`), więc nowa ścieżka = nowy `TemplateTransfer`. Ich test
`test_hook_delegates_unsupported_observation_and_isolates_state_paths` to sprawdza i on przechodzi.

Zastrzeżenie, którego test nie obejmuje: przy `n_passes>1` **ta sama ścieżka stanu wraca**
i kontroler **nie jest resetowany** między passami (`learned`, `rejected`, `hits` zostają).
W submicie `n_passes=1`, więc dziś to nie boli; przy jakimkolwiek replayu dwuprzebiegowym
wynik byłby skażony. Do naprawy jednym `if`, jeśli ktoś będzie to puszczał z `n_passes>1`.

Drugie: `learned` **celowo** przeżywa zmianę poziomu (to jest funkcja „przenoszenia reguły"),
ale nie ma rozróżnienia „nowa gra vs nowy poziom" — bo nie ma po czym (brak game_id). To
poprawny kompromis, ale znaczy, że **izolacja jest własnością harnessu, nie modułu**.

## 5. Co ten moduł jest wart na Kaggle — arytmetyka, nie opinia

`score` to średnia po grach. Jeden specjalista na jedną grę:

| scenariusz | 3/6 poziomów ft09 | średnia po 110 grach |
|---|---|---|
| rodzina występuje raz (jak w 25 publicznych) | 28,57 dla ft09 | **+0,26 pkt** (+0,49, jeśli public LB liczy 58 gier) |
| rodzina w 10% gier | 28,57 × 11 | +2,9 pkt |
| rodzina w 25% gier | 28,57 × 27 | +7,1 pkt |

W publicznym zestawie rodzina występuje w **1/25 gier** (`public25-final-comparison.json`
i mój przebieg: 0 akcji na 24 grach). Czy w ukrytych 110 jest częstsza — **nie wiadomo i nie
da się zmierzyć**; to jest całe ryzyko tego modułu.

Liczba „28,5714 RHAE" to **nie efektywność**, tylko sufit pokrycia: `100 × (1+2+3)/(1+…+6)
= 100 × 6/21 = 28,571`. Znaczy dokładnie „3 z 6 poziomów" i nic o akcjach. Ich dokument
mówi to uczciwie; podkreślam, bo łatwo tę liczbę pomylić z wynikiem.

**Bramka zastosowania jest ostrzejsza, niż wygląda.** Zmierzyłem na 25 planszach
startowych, na którym etapie moduł odpada (`template_stage_probe.py`):

| etap | ile gier | co to znaczy |
|---|---|---|
| 1 — brak ≥8 kwadratów jednego rozmiaru | 17 | brak jakiejkolwiek struktury |
| 2 — są kwadraty, brak siatki paneli | 3 | lp85, sb26, tr87 |
| 3 — struktura paneli rozpoznana | **5** | ft09, lf52, sc25, tn36, tu93 |
| 4 — **akcja** | **1** | tylko ft09 |

I tu jest sedno: na `lf52`/`tu93` widać **1 panel**, na `sc25`/`tn36` — **0** (mimo 10–65
kwadratów). Reguła potrzebuje **≥3 kompletnych paneli odniesienia + 1 panelu z obwódką**
*na pierwszej planszy gry* — bo `learned` powstaje dopiero wtedy. Jeśli motyw nie jest widoczny
na starcie, kontroler **nigdy się nie uruchomi** (chyba że LLM sam podniesie poziom, a to
w hybrydzie nie nastąpiło). Zmierzone: 4/25 gier ma strukturę, ale nie ma motywu startowego.

## 6. Wycofanie bramki `a/call ≥ 6,0` — mają rację, ja przeszacowałem

Ich `V13-7-SCORE-STATUS-20261031.md`: smoke v13.7 = 22,59 przy `a/call` **5,3** i próg 6,0
jest „arbitralny, nie prognoza 50 pkt". **Zgoda i korekta po mojej stronie.** Moje wyprowadzenie
(4,441 × 1,33 = 5,9) zakładało, że dodatkowe akcje **konwertują się na poziomy**. To założenie
jest fałszywe: `score = min(raw, 100 × pokrycie)`, więc akcje płacą tylko wtedy, gdy kupują
poziom — a moja własna tabela `leverage.py` mówiła dokładnie to (+1 poziom = +16,4;
−30% akcji = +2,05). `a/call` jest metryką **przepustowości**, nie wyniku. Poprawna forma
zdania: „a/call < 6,0 ⇒ **nie ma czym** dojść do 50", nie „6,0 ⇒ 50".

## 7. Najważniejsza liczba pakietu: **13,28**

Z `own-submissions.csv` (odczyt przez Kaggle API, Actions 41184426401):

| ref | data | wersja | publicScore |
|---|---|---|---|
| 57811453 | 30.10 16:35 | **v13.7-final** | **13,28** |
| 57737623 | 28.10 | v11 (c45 + fix konkurencji) | **23,89** |
| 57247568 | 16.10 | v3 (mistrz) | **26,25** |

To jest 10,61 pkt straty względem v11 i 12,97 względem mistrza — na **jedynym pomiarze,
który się liczy** (prawdziwy rerun 110 gier).

**Dlaczego to dotyczy mnie bezpośrednio:** v13.7-final = v13.6 + 0010 (dormant) = v13.4-unified
+ 0009 self-pace + reszta. **Mój duck-v16 to ta sama linia** (v13.4-unified + 0009 + sonda
pokrycia). Skoro ich wariant z tej linii zmierzył 13,28, to moje wcześniejsze zdanie
„v16 jest najlepszą z czterech gałęzi" jest **obalone przez jedyny prawdziwy pomiar, jaki mamy**.
v16 ma dziś oczekiwany wynik ≈13, nie ≈26.

Ich własna diagnoza („nie przypisujemy spadku pojedynczemu patchowi bez dowodów") jest słuszna.
Mogę dodać tylko mapę różnic wobec mistrza, bez wskazywania winnego:

| element | v3 (26,25) | v13.7 (13,28) |
|---|---|---|
| patche | 0001, 0002 | 0001–0010 (10) |
| `ARC3_WORLD_MODEL` | **1** | **0** |
| `ARC3_LEVEL_TOKEN_CAP` | — | 0 (cap wyłączony) |
| `PLAN_COMMIT` | — | 1 |
| win-path / dead-skip / opener-hint | — | 1 / 1 / 1 |
| eskalacja | — | relative 1,2 + self-pace 1,5 |
| smoke (10 gier) | 29,02 | 22,59 → a v11 smoke 18,54 |

**Inwersja smoke↔rerun jest tu kluczowa:** v11 smoke 18,54 → rerun **23,89** (smoke zaniżył
o 5,4), v13.7 smoke 22,59 → rerun **13,28** (zawyżył o 9,3). Reguła „slot tylko przy smoke ≥ 26"
jest więc **zawodna w obie strony** przy n=1 na wersję. Smoke mierzy 10 gier po 48 min
z widocznym baseline; rerun to 110 gier, priorytet i ukryty baseline. To dwa różne eksperymenty.

**Rekomendacja (nie decyzja):** do 2 XI iść na **odzyskanym mistrzu** (26,25) albo v11 (23,89),
a nie na czymkolwiek z linii v13.x — w tym na moim v16. Jeśli ktoś chce testować v13.x dalej,
to tylko w **kształcie rerunu** (110 gier), nie smoke.

## 8. Propozycja kolejnej zdolności — i dlaczego jej nie zaimplementuję do 2 XI

Ich zadanie brzmi: „zaproponuj albo zaimplementuj kolejną zdolność na innej rodzinie gier".
Propozycja, wyprowadzona z tabeli w §5 (a nie z pomysłu):

1. **Nauka z jednego panelu odniesienia** (lf52, tu93 mają po 1) + weryfikacja spójności
   między poziomami. Dziś próg to ≥2 zgodne przykłady; przy 1 trzeba by oprzeć się na
   sprawdzeniu po akcji i wycofaniu — moduł już ma `rejected`, więc to rozszerzenie, nie nowy moduł.
2. **Panele o rozmiarze niedzielącym się przez 3** (lf52: 4, tn36: 4). Ich ekstrakcja symbolu
   zakłada 3×3 podział wnętrza; dla size=4 potrzebny inny nośnik (unikalność patcha, nie siatka).
3. **Inna rodzina: „wskaż odstające"** na tn36 (65 kwadratów, mouse-only) — najbogatszy
   nietknięty sygnał w publicznym zestawie.

Ale: każda z tych zdolności jest warta **≈0,26 pkt na wystąpienie** w średniej po 110 grach,
a implementacja + walidacja bez regresji to realnie dzień. Przy deadline 2 XI i przy tym, że
**straciliśmy 10,6 pkt na realnym rerunie**, priorytet jest jednoznaczny: **odzyskanie
zmierzonego mistrza**, nie dokładanie rodzin. Zgadzam się z ich własnym zdaniem: „nie uznawaj
większej liczby akcji ani testów jednostkowych za wzrost wyniku Kaggle".

## 9. Czego NIE zweryfikowałem (nie dziedziczcie tego jako pewnika)

- **Rust/Rayon „33,4×"** — brak toolchainu `cargo` w moim środowisku. Liczby są w
  `structural-verification.json` (0,29244 s NumPy vs 0,00875 s Rust+Rayon16 na 256 klatkach),
  ale to **kernel prostokątów**, nie gra ani LLM — i na wynik Kaggle nie wpływa wcale.
  Zgodność backendów (75 identycznych śladów) sprawdziłem tylko przez pliki JSONL, nie przez
  uruchomienie DLL.
- **Hybryda z Qwenem** (56 wywołań API, 0 dalszych akcji) — nie mam lokalnie tego modelu.
  Zweryfikowałem tylko ślad: 25 akcji, 0 tokenów, `gave_up`, poziomy [4,7,14]. Kontrola
  (0 poziomów) to ich plik; nie powtarzałem.
- **Zachowanie na ukrytych grach** — nie da się; patrz §5.

## 10. Reprodukcja (środowisko od zera; `/tmp` nie przeżywa)

```bash
# silnik (wheele wymagają py>=3.12, więc rozpakowanie + sys.path)
pip download --no-deps -d /tmp/whl arcengine==0.9.3 --only-binary :all: --python-version 312 --platform linux_x86_64
pip download --no-deps -d /tmp/whl arc-agi==0.9.9  --only-binary :all: --python-version 312
python3 -c "import zipfile,glob;[zipfile.ZipFile(f).extractall(d) for f,d in zip(sorted(glob.glob('/tmp/whl/*.whl')),('/tmp/ae','/tmp/agx'))]"
pip install --break-system-packages pydantic requests numpy pytest

# odtworzenie 25 akcji / 3 poziomów (oczekiwane: 25, [4,7,14], 25/25 kliknięć zgodnych)
cd /home/user/Gemma-konkurs/ARC3/local-lab
PYTHONPATH=/tmp/ae:/tmp/agx python3 template_replay.py --games ft09 --compare

# abstynencja na 24 grach + etapy porażki
PYTHONPATH=/tmp/ae:/tmp/agx python3 template_replay.py --all --cap 256
PYTHONPATH=/tmp/ae:/tmp/agx python3 template_stage_probe.py
```
