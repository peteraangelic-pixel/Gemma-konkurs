# ARC-AGI-3 — audyt v13.2 (30.10.2026)

## Zakres i wniosek

Przejrzałem `peteraangelic-pixel/Pokemon@arena/a450b00f-pokemon`, tip `6b1085340a6fc6c7b5d584d1312d639c200fb1d5` (commit 30.10 07:45 UTC), katalog `arc-agi-3/duck-v13-2/`. Odczyt kodu przez GitHub API, odbudowa notebooka i offline testy na archiwalnym bundle r033. **Nie uruchamiałem Kaggle, submissionu, GPU ani pełnego benchmarku.** Nie zmieniałem kandydata ani zdalnej gałęzi.

**Werdykt:** v13.2 ma dwie realne, wąskie zmiany: obniża próg dyrektywy planowania z 60 do 10 akcji na poziomie i nie próbuje replayu na klatce `GAME_OVER`. Odbudowa jest reprodukowalna, a patch chain i testy offline przechodzą. Nie ma jednak wyniku, że model faktycznie częściej używa `commit(plan)` ani że score wzrósł. Oprócz tego pakiet zachowuje błędną instrukcję push do starego katalogu i kilka niezgodnych, odziedziczonych opisów.

## Zmiany v13.1 → v13.2

Źródłem jest [v13.2 README](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-2/README.md), [notebook](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-2/arc3-duck-v13.ipynb), [moduł winpath](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-2/src/arc3_winpath.py), [patch 0006](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-2/patches/0006-winpath-replay.patch) i [testy](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-2/tests/test_winpath.py).

1. **`ESCALATE_ACTIONS = 10` zamiast 60.** Notebook ustawia `ARC3_ESCALATE_ACTIONS=10`, gdy `PLAN_COMMIT="1"`. W patchu 0005 próg jest odczytywany z env, a dyrektywa jest dodawana po 10, 20, 30… akcjach na poziomie. To zwiększa częstotliwość przypomnień. **Nie wymusza** wywołania `commit(plan)` i nie zmienia automatycznie liczby akcji wykonywanych w turze. Nie ma w patchu wymuszonego `tool_choice`, automatycznego batcha ani blokady zwykłej jednoakcyjnej ścieżki. „Presja” jest zachętą w promptcie, nie gwarancją batchowania.
2. **Guard dla `GAME_OVER`.** Różnica źródłowa w `arc3_winpath.py` to trzy linie przed odczytem poziomu: sprawdza `game_state.raw.state` i kończy próbę replayu dla `GAME_OVER`, zamiast oznaczać poziom jako uszkodzony na martwej klatce. Kształt pasuje do TAAF `GameState.raw: FrameDataRaw` i do sprawdzania terminalu w solverze. Dodany test wstawia stan `GAME_OVER`, sprawdza zero akcji replayu i brak wpisu do `broken`.
3. **Pozostałe dane nie zmieniają się istotnie:** playbook i baza `src/base-v11.ipynb` są identyczne z v13.1; dodano test guardu, a metadane wskazują `petersharps/arc3-duck-v13-2`. Nie poprawiono formatu rosteru, synchronizacji store ani mechanizmu dopasowania gier.

## Weryfikacja wykonana lokalnie

Pobrałem tylko artefakty v13.2 do `/tmp`; użyłem istniejącego, archiwalnego `r033-recon-bundle` z wcześniejszego audytu.

- `tools/build_v13.py --out /tmp/.../rebuilt.ipynb` utworzył 35-komórkowy notebook **bajt-w-bajt identyczny** z notebookiem w gałęzi.
- `tools/verify_v13.py --bundle <r033> --tests` zakończył się `ALL CHECKS PASSED`: notebook parsuje się, 20 komórek kodu kompiluje się, wszystkie 6 patchy stosuje się do czystego bundle, spatchowane drzewo kompiluje się, przechodzi 12 testów plan-commit i 8 testów winpath.
- Niezależnie uruchomiłem `tests/test_winpath.py -v`: `Ran 8 tests … OK`.
- Testy są offline i używają `FakeSession`/gry testowej. Środowisko użyło **testowego shima `arcengine.py`**, nie rzeczywistego silnika ARC3. To potwierdza moduł i kontrakt hooków, nie integrację end-to-end, gateway ani score.
- Odczyt `verify_v13.py` pokazał, że jego warunki sukcesu sprawdzają kod wyjścia testów; skrypt nie liczy metod testowych. Sprawdziłem liczbę osobno. Co istotne, verifier **nie asertuje `ESCALATE_ACTIONS == 10` ani nie mierzy częstotliwości dyrektywy**; wartość potwierdziłem bezpośrednio w notebooku i builderze.

## Co działa, a co nie jest dowiedzione

- Zmniejszenie progu ma sens jako tani eksperyment: dla poziomów kończących się przed 60 akcjami dyrektywa mogła się nie pojawić; przy progu 10 pojawia się wcześniej i cyklicznie. Brakuje jednak pomiaru, czy model z niej korzysta. Prognoza z README „1 akcja/decyzję ≈ 19–31, 2 akcje ≈ 51” jest **modelem warunkowym**, nie wynikiem v13.2.
- Guard `GAME_OVER` jest mały, spójny z kształtem stanu TAAF i pokryty testem syntetycznym. Nie usuwa cichego obsługiwania wyjątków w hookach ani nie poprawia logowania replayu.
- **Wyścig w `_Store` pozostaje.** W v13.2 zapis nadal korzysta z nieblokowanego read/merge/write i wspólnego pliku tymczasowego; w dwóch sesjach o tym samym `base_key` możliwe są utrata aktualizacji i brak świeżej ścieżki w snapshotcie. Testów współbieżnych nie dodano.
- **Niewiadoma rosteru pozostaje.** Kod nadal grupuje przez `base_key(game_id)`, a statyczny playbook dopasowuje po ID/prefiksie, nie przez `private_tags`. Brak listy rzeczywistych ID oznacza brak dowodu, że mechanizmy pamięci uruchomią się w punktowanym biegu.
- **Brak pomiaru punktowego.** Patch chain/testy offline nie pokazują wpływu na smoke, public LB ani submission. Nie wolno przenosić prognoz 28–38/50+ do kategorii wyniku.

## Problemy dokumentacji i bezpiecznego użycia

1. README nadal instruuje:

   ```bash
   kaggle kernels push -p arc-agi-3/duck-v13-mega
   ```

   Tymczasem v13.2 jest w `arc-agi-3/duck-v13-2/`, a `kernel-metadata.json` ma ID/title `arc3-duck-v13-2`. Użycie opublikowanej komendy może wypchnąć starą wersję. **Nie używać tej ścieżki bez poprawienia i osobnej zgody użytkownika.**
2. Początkowe sekcje README nadal mówią o eskalacji co 60 akcji, replayu w passach 2–20 i sześciu testach winpath. Dopiero dodatek v13.2 zmienia próg na 10, a testy na 8. `tools/verify_v13.py` także ma docstring mówiący o 6 testach, choć wykonuje 8.
3. Notebook drukuje `v13.2 profile=…`, ale playbook nadal loguje `v13 playbook`; README oczekuje jeszcze `v13 profile=…`. To nie zmienia zachowania, ale utrudnia identyfikację logu.
4. README zachowuje starsze założenia o rosterze publicznych klonów i widełki punktowe. Są warunkowe; audyt cross-branch nie znalazł dowodu na powtarzający się `base_key` w prawdziwym rosterze.

## Konkluzja

V13.2 to reprodukowalny, offline-zweryfikowany pakiet z jedną sensowną korektą terminal-state i wcześniejszą dyrektywą batchowania. **Jest to poprawka zachowania/promptu, nie wykazana poprawa wyniku.** Przed ewentualnym użyciem trzeba poprawić ścieżkę push i sprzeczne opisy; rzeczywisty wpływ wymaga metryk z istniejących logów lub osobno zatwierdzonego pomiaru.

## Źródła

- [v13.2 commit `6b108534`](https://github.com/peteraangelic-pixel/Pokemon/commit/6b1085340a6fc6c7b5d584d1312d639c200fb1d5)
- [v13.2 verifier](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-2/tools/verify_v13.py)
- [v13.2 builder](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-2/tools/build_v13.py)
- [archiwum r033 użyte do weryfikacji](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/tree/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r033-recon-bundle)
- [TAAF `GameState`](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r033-recon-bundle/bundle/src/tufa-arc-agi-framework/src/taaf/game.py)
