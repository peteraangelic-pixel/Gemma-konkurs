# ARC-AGI-3 — niezależny audyt v13.1 (30.10.2026)

## Zakres i werdykt

Audyt dotyczy tipa `peteraangelic-pixel/Pokemon@arena/a450b00f-pokemon`, commit `cbefdd4effbabe074547c1d38161bf06445ec20c` (`duck-v13-1`). Zewnętrzne repozytoria były czytane wyłącznie przez GitHub API; nie zmieniano Pokemon ani Smak. Nie uruchamiano Kaggle, submissionu, GPU ani benchmarku punktowanego.

**Wniosek:** v13.1 naprawia błąd logiczny v13 wynikający z `n_passes=1`: replay i dead-skip mają teraz kanał między powtarzanymi wpisami tego samego bazowego kodu gry. Dla wpisów obsłużonych sekwencyjnie zachowanie jest spójne i testowalne. Nie jest to jednak rozwiązanie odporne na możliwe nakładanie się wpisów tej samej gry przy `concurrency=10`: współdzielony store nie ma synchronizacji ani odświeżania, a aktualizacja licznika może zgubić inkrement. Nie ma wyniku score v13.1, który potwierdzałby korzyść w konkursie.

v13.1 jest osobnym katalogiem `arc-agi-3/duck-v13-1/`; poprzedni `duck-v13-mega/` pozostał na gałęzi. To istotne, bo instrukcja push w README nadal wskazuje stary katalog.

## Ustalenia bezpośrednio z kodu

- Notebook wykrywa `TRUE_SUBMISSION` przez `KAGGLE_IS_COMPETITION_RERUN`; w tej ścieżce ustawia `bm.n_passes = 1`. To potwierdza przesłankę poprzedniego audytu, że warunek oparty na `pass_index >= 4` był w competition rerun nieosiągalny.
- `base_key("ls20-9607627b") == "ls20"`. `_Store` zapisuje pod tym kluczem plik w `/kaggle/working/arc3_winpath`, z polami `passes_completed`, `best_levels` i `levels`. Sufiksy różnych wpisów mogą więc współdzielić stan w obrębie jednego procesu runu.
- `end_session()` zwiększa `passes_completed`; `dead_skip()` nie sprawdza `pass_index`, tylko wymaga `best_levels <= 0` oraz `passes_completed >= ARC3_DEAD_MIN_PASSES` (domyślnie 3). Przy trzech sekwencyjnych wpisach bez ukończonego poziomu czwarty wpis zostaje pominięty.
- Replay odtwarza zapisane akcje przez `_execute_action` i sprawdza hash planszy początkowej oraz hashe po akcjach. Inny stan początkowy nie powinien wykonać niewłaściwej ścieżki. Jest to dobry fail-safe, ale nie wielowariantowy cache.
- Cache ma tylko jeden wpis na bazowy kod gry i numer poziomu. Zapis ścieżki z innego wariantu tego samego kodu może zastąpić poprzednią; walidacja startowego hasha zablokuje replay na niepasującym wariancie, ale nie odzyska wcześniejszej ścieżki.
- `end_session()` jest wywoływane w `finally` i zwiększa licznik bez rozróżnienia, czy sesja zakończyła się normalnie, przez timeout, wyjątek lub błąd infrastruktury. Trzy zakończenia z zerowym postępem mogą więc zadziałać jak trzy „martwe” próby, choć przyczyna nie musi być w samej grze.

## Weryfikacja wykonana lokalnie

Wszystkie pobrane źródła, środowiska i artefakty testowe trafiły do `/tmp`; nie zmieniałem kodu, README ani kandydata w repo Gemma. Na tej gałęzi dodaję wyłącznie niniejszy raport.

1. Odtworzyłem archiwum r033 z `Smak-Domu-Konkurs` (`r033-recon-bundle`; 73 pliki, około 1,7 MB) w katalogu tymczasowym. `tools/verify_v13.py --bundle <r033> --tests` zakończył się `ALL CHECKS PASSED`:
   - notebook: 35 komórek, 20 komórek kodu kompiluje się;
   - wszystkie 6 patchy stosuje się do czystego drzewa `ARC3-Inference`;
   - spatchowane drzewo kompiluje się;
   - 12 testów plan-commit przechodzi;
   - testowy subprocess winpath przechodzi.
2. Środowisko ma Python 3.11, a `arcengine==0.9.3` z PyPI wymaga Pythona >=3.12. Do winpath testów użyłem zatem tymczasowego, minimalnego shima `GameAction`/`ActionInput`. Testy same używają `FakeSession` i toy game, więc wynik nie jest testem na prawdziwym ARC3 engine ani gatewayu. `requests`, Pillow i pydantic były zainstalowane wyłącznie w tymczasowym venv.
3. `tests/test_winpath.py` zawiera **7** metod testowych; bezpośredni przebieg dał `Ran 7 tests ... OK`. Weryfikator opisuje je jako „8 winpath tests pass”, ale sprawdza wyłącznie kod wyjścia procesu, nie liczbę testów. README w innych miejscach deklaruje 6/6. Poprawny odczyt aktualnego pliku testów to 7.
4. `tools/build_v13.py` odtworzył committed notebook bajt-w-bajt. `src/arc3_winpath.py` jest bajtowo zgodny z plikiem dodawanym przez patch, a patch w notebooku zgadza się ze standalone `0006-winpath-replay.patch`. `playbook.json` jest identyczny jak w v13; SHA-256 obu kopii: `0474dda43f9faa78c288fd3119c8b64d8a07e969ebd2cf21c6095d3ec804d8d1`.
5. Dodatkowa symulacja lokalna z kodem store: wpisy 1–3 zwróciły `dead_skip=False`, wpis 4 `True`, licznik po czterech zakończeniach wyniósł 4. Drugi test wykazał wyścig: dwa `_Store` wczytane przed zapisem, każdy inkrementuje lokalnie 0→1; po obu zapisach plik zawiera 1, choć ukończyły się dwie sesje.

## Najważniejsze ryzyko: równoległość

`_Store` wczytuje plik raz przy `begin_session()`. `maybe_replay()` i `dead_skip()` korzystają z tego snapshotu i nie odświeżają go z dysku. Sesja klona uruchomiona przed zapisaniem rozwiązania przez inny klon nie zobaczy nowej ścieżki w trakcie własnego działania.

`save()` wykonuje read/merge/write bez locka, inkrementuje licznik lokalnie, a potem scala go przez `max(disk, local)`. Dwa sesyjne snapshoty o tej samej wartości mogą zgubić inkrement; wszystkie instancje używają też tego samego pliku tymczasowego `<base>.tmp`. Ponieważ notebook ustawia `bm.solver.concurrency = 10`, nakładanie się sesji tej samej gry jest możliwe przy nierównych czasach ich trwania, nawet jeśli lista wpisów jest round-robin. Nie twierdzę, że występuje w każdym runie; kod nie gwarantuje serializacji.

Skutek praktyczny: memory/replay może pomagać sesjom, które rozpoczną się po zapisie poprzedniego klona, a dead-skip może działać po trzech zapisanych bezpostępowych sesjach. Nie jest zagwarantowane, że każdy klon zobaczy pamięć ani że licznik osiągnie próg w obecności współbieżnych sesji.

## Roster i poziom dowodów

Recenzja Smak v13.1 twierdzi, że roster ma 110 wpisów — round-robin klonów 25 gier, około 4,4 wpisu na grę. Oryginalny notebook Tufy pobiera listę z `arcade.available_environments` i ustawia `bm.n_passes=1`, ale sam sprawdzony kod notebooka nie zawiera statycznej listy 110 ID. Zapisane w Smak `r085` i `r108` `roster_probe.jsonl`, które sprawdziłem, to każdy 10 startów i 10 końców, 10 unikalnych kodów bazowych i `pass_index=0` — smoke, nie pełny roster. Dlatego w tym audycie liczba/układ 110 jest oznaczony jako twierdzenie recenzji, nie niezależnie odtworzony pomiar pełnego competition rosteru.

Nawet przy poprawnym mnożniku 4,4 replay wymaga, by klony miały ten sam stan startowy. Hash zabezpiecza przed błędnym odtworzeniem, lecz jeden slot ścieżki na `(base_key, level)` nie przechowuje kilku różnych wariantów startu.

## Dokumentacja i prognozy

- README v13.1 nadal podaje `kaggle kernels push -p arc-agi-3/duck-v13-mega`, choć `kernel-metadata.json` ma ID/title `petersharps/arc3-duck-v13-1` / `arc3-duck-v13-1`. Ponieważ stary katalog v13 pozostał na gałęzi, użycie polecenia z README może wypchnąć starą wersję.
- README oraz docstring modułu nadal zawierają opis replayu w passach 2–20 i stare opisy dead-skip; późniejsza sekcja korekt przyznaje, że `n_passes=1`. Należy usunąć sprzeczne, nieaktualne fragmenty.
- `ANALIZA-23.md` skorygowała punkt o pamięci/passach, ale punkt 2 nadal przedstawia hipotezę o wysłanym v12-plan. Nie traktować jej jako ustalenia; wcześniejszy zapis r116 identyfikuje submission `#57737623` jako v11 z `PLAN_COMMIT=0`.
- README podaje oczekiwanie 28–38 i warunkowy scenariusz 45–55. To prognozy, nie wynik testu ani publiczny LB. Dokumentacja v13.1 mówi, że nic nie wysłano; w tym audycie nie wykonano żadnego Kaggle runu ani submissionu.
- „GO” w niezależnej recenzji Smak jest opinią o kodzie/kandydacie, nie score’em i nie zgodą użytkownika na wysyłkę.

## Zalecenia przed przyszłym użyciem

1. Synchronizować zapis store per bazowa gra (np. Linux `flock` na pliku lock), w sekcji krytycznej ponownie wczytać najnowszy stan, inkrementować licznik względem dysku i używać unikalnego pliku tymczasowego. Nie opierać licznika na `max(local, disk)`.
2. Albo serializować sesje tego samego `base_key`, albo odświeżać wspólny store przed decyzją replay/dead-skip; dodać test dwóch równoległych klonów oraz test zakończenia przez wyjątek/timeout.
3. Rozważyć kluczowanie ścieżek przez `(base_key, level, init_hash)` i jawnie zdefiniować, czy dead-skip ma działać dla całego kodu gry, czy dla danego wariantu startowego.
4. Poprawić push path, log line (`v13.1`), stary opis passów oraz liczby testów w README/verifierze. Nie pushować na podstawie aktualnej instrukcji README.
5. Utrzymać osobno: lokalne testy/patch-chain, smoke score, public LB i wynik competition submission. Prognoza 28–38 nie zastępuje pomiaru; nie obiecywać 50+.

## Źródła

- [v13.1 notebook](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-1/arc3-duck-v13.ipynb)
- [v13.1 moduł winpath](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-1/src/arc3_winpath.py)
- [patch 0006](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-1/patches/0006-winpath-replay.patch)
- [testy winpath](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-1/tests/test_winpath.py)
- [verifier](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-1/tools/verify_v13.py)
- [README v13.1](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-1/README.md)
- [metadata](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-1/kernel-metadata.json)
- [niezależna recenzja Smak v13.1](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/duck-v13-1/OCENA-ARENA-V13-1.md)
- [archiwum r033 i manifest](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r033-recon-bundle/SUMMARY.md)
- [Tufa notebook z pobieraniem listy środowisk](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r022-pull-original/tufa-labs-duck-harness-june-30-milestone-winner.ipynb)
- [roster smoke r108](https://github.com/peteraangelic-pixel/Smak-Domu-Konkurs/blob/arena%2F5ed750ef-smak-domu-konkurs/arc-agi-3/kaggle/ops/results/r108-kernel_output_pick/output-pick/roster_probe.jsonl)
- [ANALIZA-23](https://github.com/peteraangelic-pixel/Pokemon/blob/arena%2Fa450b00f-pokemon/arc-agi-3/duck-v13-1/ANALIZA-23.md)

Ten commit obejmuje wyłącznie niniejszy raport; nie obejmuje kodu kandydata ani pozostałych wcześniej istniejących lokalnych artefaktów.
