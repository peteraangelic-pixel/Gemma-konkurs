# Ocena pakietu 30.10 (druga sesja Arena) + mój kandydat v17-arena

Data: 30.10.2026 · gałąź `arena/6d081d52-gemma-konkurs` · wszystko **offline, read-only wobec
zdalnych gałęzi**. Żadnego biegu Kaggle, żadnej submisji, żadnego commita poza tą gałęzią.

Pytanie użytkownika: *czy warto* — dla trzech nowych rzeczy, które druga sesja Arena dołożyła do
`peteraangelic-pixel/Smak-Domu-Konkurs` (gałąź `arena/5ed750ef-…`): zipa
`arc-arena-handoff-30-10.zip` (commit `999f9194`, 13:40Z) oraz katalogów **v13.5-consensus**
(`63ede621`) i **v13.6-final** (`3bf4d3e0`).

**Odpowiedź w jednym zdaniu: tak, warto — ale nie za to, za co się chwali.** Wartością jest
dyscyplina i weryfikowalność (każda liczba i każdy patch odtwarzają się u mnie niezależnie),
a nie nowy wynik. Jedyny żywy nowy mechanizm daje mniej interwencji, nie więcej punktów.

---

## 1. Co dokładnie sprawdziłem (nie „przeczytałem”, tylko uruchomiłem)

| rzecz | jak sprawdzona | wynik |
|---|---|---|
| `arc-v16-package/tools/verify_v16.py` | uruchomiony lokalnie (stuby `requests`/`PIL`, Py 3.11) | 16 testów + 24 kontrole → **ALL LOCAL CHECKS PASSED** |
| trio gate, który druga sesja zostawiła **otwarty** | `verify_v16.py --bundle /tmp/r033 --tests` na czystym r033 (73 pliki, bez `.git`) | **ALL CHECKS PASSED** — ich zaległość jest domknięta, patch łańcuch aplikuje się na realne drzewo i kompiluje |
| 9 patchy v16-naj wyciągniętych z notebooka | `git apply` + `compileall` na r033 | 9/9 czysto, kompiluje |
| v13.6-final, odtwarzalność budownika | `build_v136_final.py --prev v13.5 --out …` | **bajt w bajt**: 40 komórek, 743 616 B, slug `petersharps/arc3-duck-v13-6-final` |
| v13.6-final, bramka własna | `verify_v13.py --bundle /tmp/r033 --tests` (9 patchy, 12+6+11 testów, self-pace, playbook) | **ALL CHECKS PASSED** |
| self-pace 22/14 — czy to prawda | własny audyt `/tmp/esc_audit.py` na 4 realnych `benchmark.json` (r085/r093/r110/r118), bez ich kodu | **22 nudge / 14 przedwczesnych na r085 — zgadza się co do sztuki** |
| playbook | sha256 gałęzi vs mój plik vs osadzony w notebooku | identyczne: 9 gier / 14 poziomów |

Czyli: **żadna liczba z ich README nie okazała się zmyślona.** Wcześniejsza podejrzliwość
(o „27/42”) niepotrzebna — ich tabela to 22/14 vs 42/26 i to się reprodukuje.

## 2. Mój niezależny audyt eskalacji (rdzeń sporu)

Ile razy reguła eskalacji wtrąca się do kontekstu i ile z tych wtrąceń jest **przedwczesnych**
(czyli gra była jeszcze w normie):

| benchmark (poziomy) | absolutne 20 | 20 + cap 2 (to, co leci w submisji z v13.4) | względne 1,2× (0008) | **self-pace (0009)** |
|---|---|---|---|---|
| r085 (32) | 67 / 26 | 42 / 26 | **8 / 0** | **22 / 14** |
| r093 (27) | 72 / 23 | 39 / 23 | **10 / 0** | **22 / 13** |
| r110 (4) | 8 / 4 | 5 / 4 | **3 / 0** | 5 / 4 |
| r118 (2) | 3 / 1 | 2 / 1 | **2 / 0** | 2 / 1 |

Wniosek, który trzeba powiedzieć wprost, bo w pakiecie jest tylko zasugerowany:

* Na **replayu** reguła względna (8/0) jest wyraźnie lepsza od self-pace (22/14).
* W **submisji** reguła względna jest **bezwładna** — `taaf/game.py` podaje
  `base_actions_per_level = None`, więc 0008 zjeżdża do 20 + cap 2 (42/26). To potwierdziłem
  w kodzie silnika (linie 252, 295, 448), nie z ich notatek.
* Self-pace jest jedyną eskalacją, która w biegu, który się liczy, faktycznie różni się od „20”:
  22 zamiast 42 wtrąceń i 14 zamiast 26 przedwczesnych na r085.

**Ale**: mniej wtrąceń to oszczędność tokenów i mniejsze ryzyko rozbicia działającego planu.
To **nie jest** wzrost wyniku. Z mojej dekompozycji warstw wyniki ciągnie ukończenie poziomów,
a eskalacja dotyka efektywności/warstwy planowania. Rozsądne oczekiwanie: kilka procent
trafień, nie punkty. Ktokolwiek twierdzi, że 22/14 „daje” 30+, ten zgaduje.

## 3. Czy warto brać ich paczkę: co tak, co nie

**Warto (3 rzeczy):**

1. **v13.6-final jako baza.** To najmocniejsza znana mi kombinacja: self-pace (jedyna żywa
   eskalacja) + instrument `a/call` naprawiony z martwego `< 1,5` na bezwarunkowy druk
   (baza r019 = 4,357, cele 5,7/7,6) + sondy coverage/baseline. Wszystko z kill-switchami,
   playbook 14/14 bajt w bajt, budownik odtwarzalny.
2. **Ich testy jako bramka.** `verify_v13.py`/`verify_v16.py` wyciągają patche **z notebooka**,
   a nie z katalogu `patches/` — czyli sprawdzają to, co naprawdę pojedzie. Ta jedna decyzja
   łapie całą klasę błędów, których nie łapie testowanie plików obok.
3. **Dyscyplina pomiarowa.** Wszystkie trzy liczby z ich tabeli odtworzyłem bez ich kodu.

**Nie warto / trzeba poprawić:**

1. **`petersharps/arc3-duck-v13-6-final`** — nowy slug. Kaggle przyjmuje metadane i **nadpisuje**
   istniejący kernel o tym id; przy trzech numerach w historii jest realne ryzyko, że „nowy
   bieg” wyląduje jako wersja starego kernela. Numer kernela i numer notebooka muszą iść
   osobnymi torami; to jest ostrzeżenie z ich własnego dokumentu porównawczego i ja je podbijam.
2. **Dormant ≠ neutralny.** W ich pakiecie v16-naj nowy patch 0009 (dyn-cap w
   `arc3_level_budget.py`) jest **uśpiony**: przy `ARC3_LEVEL_TOKEN_CAP=0` wyrażenie
   `dyn_enabled = _env_bool("ARC3_DYN_CAP", True) and static_cap > 0` daje `False`, więc
   zachowanie jest bajt-równe v13.4. To dobra decyzja (jednoenvowe uzbrojenie), ale trzeba to
   czytać jako „zmiana na później”, nie „zmiana w tym biegu”.
3. **„24×” na batching/hint** z ich porównania: to nie jest pomiar, to arytmetyka na założeniu
   (`a/call ≥ 6,0`, 253 akcje/grę = 50 pkt). Bramkę warto mieć w logu, ale nie wolno jej
   przenosić do oczekiwanego wyniku.
4. **Nie robić „v18” z warstwy action-efficiency** — tu zgadzam się z ich README: bug
   unhashable-action w `ConvergedGuard` jest realny, a warstwa na pierwszym kontakcie ma
   **0 trafień cache** (99 na replayu), czyli jest bezużyteczna dokładnie tam, gdzie miała
   pomagać. Wchodzić później, jako patch frame-hash win-path, nie jako nowa wersja.

## 4. Mój kandydat: `duck-v17-arena`

Zbudowany, zweryfikowany offline, **nie uruchamiany, nie wysłany**.

**v17-arena = v13.6-final (40 komórek) + dokładnie jedna zmienna: patch 0010
`ARC3_PRIORITY_DPRIME=1` (D′).**

Dlaczego ta baza, a nie mój wcześniejszy `v16-arena`: `v16-arena` stoi na v13.4, którego
eskalacja względna jest w submisji martwa (patrz §2). Baza z martwym mechanizmem to gorszy
punkt startu niż baza z jedynym żywym. D′ jest ortogonalny wobec self-pace — inny plik
(`priority_scheduler.py`), inne pytanie (która gra dostaje następny slot, nie kiedy nudge),
więc kompozycja jest naprawdę jednozmiennościowa.

Stan techniczny:

* 43 komórki, 764 759 B; budownik **powtarzalny bajt w bajt**.
* `tools/verify_v17.py --bundle /tmp/r033 --tests` → **47/47 kontroli, ALL CHECKS PASSED**:
  wszystkie 10 patchy wyciągniętych z notebooka aplikuje się czysto na realne r033, drzewo się
  kompiluje, przechodzi 12 plan-commit + 5 względnej eskalacji + 21 D′ + 11 win-path,
  self-pace odtwarza **22/14 z drzewa po patchach**, a przy nieustawionym
  `ARC3_PRIORITY_DPRIME` `select_priority()` zwraca **dokładnie** `priority_value()` na 24
  kombinacjach snapshotów i argumentów.
* Kill-switch: `"ARC3_PRIORITY_DPRIME": "0"` = dokładnie v13.6-final. Każda inna warstwa ma
  swój własny (self-pace, względna, cap/poziom, opener-hint, winpath, dead-skip, plan-commit,
  cap tokenów).
* Nowa obserwowalność (0 kosztu GPU): sonda D′ **przed** `bm.run` (czy przełącznik jest żywy
  i czy OFF == fabryka) i miernik D′ **po** biegu (`dprime_metering.jsonl`: tokeny/akcje na
  ukończony poziom, `a/call`, wynik), z jawnym ostrzeżeniem, gdy **żaden** run nie ukończył
  poziomu — wtedy D′ pracuje na referencji 30k i jego wkład jest efektem ubocznym, nie pomiarem.
* Uczciwa oczekiwana wartość D′: 4 publiczne drawy 31,54 / 30,74 / 29,05 / 24,77 (średnia ≈29,0)
  wobec porównywalnej linii ≈25,77 (SD ≈3,93). **n=4, SD ~4 — to nie dowód.** Dlatego D′ jest
  jednym przełącznikiem, a nie przepisaniem.

Katalog: `arc3_local_candidate/v17-arena/` (`README.md`, `tools/build_v17.py`,
`tools/verify_v17.py`, `src/priority_scheduler_v17.py` — zrzut drzewa po patchach do replayu).

## 5. Rekomendacja

1. **Slot 30.10**: `v13.6-final`. Zmiana jest mała, ale prawdziwa, w pełni odwracalna i jako
   jedyna działa w biegu, który się liczy.
2. **Slot kolejny**: `v17-arena` **tylko jako kontrolowany eksperyment z D′**, po jednym biegu
   na wariant, na tym samym seedzie/puli. Bez tego nie ma jak odróżnić D′ od szumu (SD ≈4).
3. **Nie** łączyć D′ z uzbrojeniem dyn-cap w jednym biegu — dwa przełączniki naraz to znowu
   zgadywanie, którego mechanizmu nie da się przypisać.
4. **Nie** obiecywać 50+ z żadnej z tych warstw. Zmierzone bazowo: `#57752672` 1,18,
   `#57737623` 23,89, `#57247568` 26,25. Droga do 50+ wymaga zmiany klasy zachowania (batching
   i pokrycie), a nie kolejnego progu eskalacji.

Nic z tego nie zostało uruchomione w Kaggle, wysłane ani scommitowane poza tą gałęzią.
