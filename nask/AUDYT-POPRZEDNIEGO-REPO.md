# Audyt repo `peteraangelic-pixel/NASK` (gałąź `arena/a29ca234-nask`) — moje własne sprawdzenie

Data: 2026-11-03. Sprawdziłem **kod i workflow**, nie opisy. Poniżej co się potwierdziło,
co jest nieprawdą i co z tym zrobić.

## 1. Co jest w repo

- `main`: 1 plik (`README.md`, 7 B) — puste.
- `arena/a29ca234-nask`: 25 plików, `rust/{subenum,ffuzz,probe,takeover,native}`,
  `python/{jsminer,gen_report,ffi_native}`, `templates/{report,poc-example,scope}`,
  `STRATEGIA.md`, 2 workflow. Tip `ed96a2f`.

## 2. Potwierdzone defekty (sprawdzone w źródłach)

### 2.1. Trzy z czterech crate'ów nie skompilują się

`rust/Cargo.toml` deklaruje `ureq = { version = "2.11", default-features = false }`.
W kodzie `probe`, `ffuzz` i `takeover` wywołanie wygląda tak:

```rust
ureq::get(&target).timeout_connect(timeout).call()
```

W ureq 2.x `timeout_connect` jest metodą **`AgentBuilder`**, nie `Request`. `ureq::get()`
zwraca `Request`, więc to się nie skompiluje (`E0599`). Potwierdzone w trzech plikach:
`probe/src/main.rs:65`, `takeover/src/main.rs:63`, `ffuzz/src/main.rs:119,122,125`.

**Drugi, cichszy problem w tym samym miejscu:** `default-features = false` wyłącza TLS.
Nawet po naprawie `timeout_connect` każde żądanie do `https://` skończy się błędem runtime,
bo w binarce nie ma obsługi TLS. Poprawnie: `features = ["tls"]` (albo `rustls`).

### 2.2. CI nie sprawdza, czy kod się buduje

`.github/workflows/ci.yml` zawiera dziś tylko:

```yaml
- run: cargo fmt          (continue-on-error: true)
- run: cargo clippy --all-targets || true
```

**Zero `cargo build`, zero testów.** Zielona plakietka w tym repo nie znaczy nic.
To dokładnie ten rodzaj „zielonego CI”, który ukrył defekt 2.1.

### 2.3. Brak jakiegokolwiek limitera szybkości

```
grep -rniE "rate|limit|rps|sleep|throttle|semaphore" rust/   → 0 trafień
```

Regulamin §6 pkt 2: **maksymalnie 5 req/s**; naruszenie → odrzucenie zgłoszenia.
`ffuzz` puszcza tyle żądań, ile rdzeni (Ryzen 9 5950X = 32 wątki) — setki req/s.
To jedyny defekt w tym repo, który może **unieważnić wszystkie nagrody naraz**, nawet
jeśli luka zostanie znaleziona.

### 2.4. `scan.yml` wskazuje nieistniejący słownik

Domyślna wartość `wordlist` to `rust/wordlists/small.txt`. **Tego pliku nie ma w repo.**
Workflow przechodzi dalej tylko dzięki fallbackowi z 10 wbudowanymi subdomenami — czyli
„skan” sprawdza 10 nazw i nic nie wnosi.

### 2.5. Błędy faktograficzne w dokumentacji

| gdzie | jest | jest naprawdę |
|---|---|---|
| `README.md` | „pula 1 mln PLN” | **100 000 zł** to pula tej edycji; milion to pula całego programu |
| `templates/scope.md` | jedna wspólna lista dla 5 programów | 5 osobnych zakresów i 5 osobnych regulaminów — `gov.pl` ≠ `www.gov.pl` |
| `STRATEGIA.md` | „subdomain takeover — najlepszy stosunek wysiłku do nagrody” | §8 poz. 11.2: takeover **bez działającego PoC** jest wykluczony |
| `templates/scope.md` | brak wykluczeń | `*.hack.cert.pl`, `*.lab.cert.pl`, `bip.wladyslawowo.pl` są wyłączone |

## 3. Co w tym repo jest dobre i zostaje

1. **`templates/report.md`** — porządny szablon zgłoszenia z listą klas z §8.
2. **`templates/poc-example.md`** — wzorzec PoC z krokami i sekcją „wpływ po ludzku”.
3. **`python/gen_report.py`** — generator raportu z CLI, 116 linii, bez zależności.
4. **`rust/subenum`** — jedyny działający crate; pomysł (Rayon + DNS) jest sensowny.
5. **`python/jsminer.py`** — ekstrakcja endpointów z JS; uzupełnia moje `jsmine.py`
   (moje działa na plikach lokalnych, ich pobiera po URL).

## 4. Decyzja: co dalej z tym repo

Nie przenoszę tu cudzego kodu 1:1. Zamiast tego:

- **narzędzia** biorę z mojego `nask/tools/` — mają limiter (odmowa startu > 5 req/s),
  kontrolę zakresu (46 testów, w tym pułapki `gov.pl`, `*.hack.cert.pl`, `bip.…`) i dziennik
  dowodów z SHA-256;
- **szablony raportu** z ich repo są dobre — mój `tools/report.py` wymusza to samo,
  tylko twardo: nie wygeneruje raportu bez dowodów i kroków odtworzenia;
- **CI** naprawiam tak, żeby **czerwony build faktycznie blokował** (patrz
  `nask/github-workflow-ci.yml` — do wklejenia w repo NASK).

## 5. Wniosek jednym zdaniem

Repo ma trafną intuicję (jedna klasa podatności, PoC, własne konta), ale jest w stanie
nieukończonym: **3 z 4 crate'ów się nie kompilują, CI przestało cokolwiek sprawdzać,
a narzędzia nie mają limitera 5 req/s** — czyli jedynej rzeczy, która może przekreślić
udane zgłoszenie. Najlepsze, co można zrobić: zostawić szablony, a narzędzia wziąć stąd.
