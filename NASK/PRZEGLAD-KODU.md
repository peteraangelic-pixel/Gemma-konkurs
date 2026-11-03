# Przegląd istniejącego kodu i kolejność napraw

Cel: nie pisać szóstego narzędzia, tylko doprowadzić do stanu używalności to, co już jest,
i nie duplikować tego, co działa.

## 1. Co jest zepsute w narzędziach z gałęzi `arena/a29ca234-nask` (repo NASK)

Z przeglądu z 2026-11-03 (`nask-codex/research/arena-review-2026-11-03.md`) i z mojego
czytania kodu — uporządkowane według tego, co **blokuje realną pracę**, nie według kosmetyki:

| # | problem | skutek | naprawa |
|---|---|---|---|
| 1 | `probe`/`ffuzz` nie kompilują się (`timeout_connect` nie istnieje w `ureq` 2.x) | narzędzia nie istnieją w praktyce | usunąć wywołanie lub użyć `ureq::AgentBuilder::timeout_connect` |
| 2 | **brak wspólnego limitera tempa** (równoległość = liczba wątków, nie żądań/s) | ryzyko przekroczenia 5 req/s = naruszenie regulaminu | użyć `nasktriage::rate::TokenBucket` — jest wspólny, testowany, odmawia startu > 5/s |
| 3 | **brak wymuszenia zakresu** (komentarz zamiast kontroli) | żądanie do hosta spoza §5 to problem prawny | `nasktriage::scope::Scope::check_url` przed każdym żądaniem **i** po każdym przekierowaniu |
| 4 | brak TLS w `ureq` (`default-features = false`) | narzędzie nie połączy się z HTTPS | włączyć feature `tls` i sprawdzić na lokalnej usłudze |
| 5 | CI zielone przy zepsutym kodzie (`clippy \|\| true`, brak `cargo test`) | fałszywe poczucie poprawności | osobne kroki `clippy` i `test`, bez `\|\| true` (tak działa `nask-triage-ci.yml`) |
| 6 | `build-native.sh` kopiuje `.so` do złego katalogu; `native` poza `members` workspace | FFI nie da się zbudować | dodać do `members` + poprawić ścieżkę |
| 7 | przykłady w `ffuzz` używają `gov.pl` / `mszyfr.gov.pl` | nieprawidłowe hosty (w zakresie są `www.gov.pl` i `*.komunikator.narodowy.gov.pl`) | poprawić przykłady, inaczej ktoś je skopiuje |

## 2. Czego świadomie **nie** naprawiam

- **Nie robię z tego skanera podatności.** Limit 5 req/s sprawia, że wolumen jest bezużyteczny,
  a regulamin odrzuca output skanera bez ręcznego PoC (§8 poz. 14).
- **Nie dokładam kolejek, proxy-rotatorów, „fuzzerów”.** To narzędzia do łamania limitów,
  czyli do złamania regulaminu.
- **Nie obiecuję 100–200× przyspieszenia.** Działa ono tam, gdzie jest CPU-bound praca
  (analiza setek plików JS, haszowanie i klastrowanie tysięcy odpowiedzi) — i tam Rayon jest
  włączony (`analyze.rs`: `par_iter` po wpisach HAR). Nie działa tam, gdzie czeka się na sieć.

## 3. Co nowego jest w `tools/nasktriage` (i czego nie ma w innych)

| element | po co | stan |
|---|---|---|
| `scope.rs` — dokładna lista hostów, normalizacja, odrzucenie subdomen i sufiksów | §5 regulaminu jako **kod**, nie komentarz | ✅ testy |
| `rate.rs` — wspólny token bucket z wstrzykiwanym zegarem, twardy sufit 5/s | §6 pkt 2 | ✅ testy deterministyczne |
| `har.rs` — czytanie zrzutów, wzorce ścieżek (`/api/tasks/101` → `/api/tasks/{id}`), kształt JSON | materiał z przeglądarki bez ręcznego czytania | ✅ testy |
| `analyze.rs` — różnica między dwoma własnymi kontami: asymetria uprawnień, kandydat na IDOR, token w URL, dostęp bez logowania, cache | **to jest realna robota**, nie skanowanie | ✅ 12 testów |
| brak modułu sieciowego | narzędzie nie może „przypadkiem” wysłać żądania | ✅ celowo |

## 4. Kolejność prac (jeśli mamy wracać do kodu)

1. **Teraz:** używać `nasktriage` na zrzutach HAR (offline, zero ryzyka).
2. Po pierwszym potwierdzonym znalezisku: naprawić #1–#3 w narzędziach z repo NASK,
   ale tylko jeśli okaże się, że potrzebny jest ruch aktywny (na razie nie był).
3. FFI/Python: dopiero gdy pomiar pokaże wąskie gardło w analizie offline — nie wcześniej.

## 5. Weryfikacja

```bash
cd NASK/tools/nasktriage
cargo test --all-targets      # 12 testów
cargo clippy --all-targets    # 0 ostrzeżeń
cargo run --release -- scope --scope scope.example.json
```

To samo leci w GitHub Actions (`.github/workflows/nask-triage-ci.yml`) przy każdym pushu
zmieniającym ten katalog. **Wynik CI jest dowodem, nie deklaracją** — logi kompilatora lądują
w `ci/`, bo z tego sandboxa nie da się pobrać logów przebiegu.
