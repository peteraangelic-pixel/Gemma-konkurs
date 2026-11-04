# Przejęte z 6 gałęzi zespołu — pełny inwentarz z proweniencją
**Data przeglądu:** 4.11.2026 · **Sesja:** `arena/c4eeb067-gemma-konkurs`
**Cel pliku:** to, co przeczytałem w cudzych gałęziach, **nie może żyć tylko w czacie ani w cudzym repo**. Poniżej każdy fakt ma źródło (repo, gałąź, commit) i status weryfikacji. Jeśli tamte repo znikną albo zostaną przepisane, ten plik wystarcza do kontynuacji.

Statusy: **[Z] zweryfikowane przeze mnie** (własne żądanie), **[C] cudzy pomiar** (przyjęty, nie powtórzony), **[H] hipoteza** (do sprawdzenia).

---

## 0. Proweniencja — co czytałem i kiedy

| repo | gałąź | commit (głowa) | co przeczytałem |
|---|---|---|---|
| `peteraangelic-pixel/Pokemon` | `arena/c87f7a48-pokemon` | `2a02ea2` | `nask/REJESTR-LEADS-20261104.md`, `nask/RUNBOOK-RANO-20261104.md`, `nask/tools/bundle_scan.py` |
| `peteraangelic-pixel/Pokemon` | `arena/7911f950-pokemon` | `cac68f8` | `nask/research/02-SONDY-004-006.md`, `03-STATUS-NOC.md`, opis fal 3 (007) i 4 (008) z komunikatu commita |
| `peteraangelic-pixel/Pokemon` | `arena/a450b00f-pokemon` | `a143b20` | komunikaty commitów (lab FFI Rust+Rayon, mapa 4 programów) |
| `peteraangelic-pixel/Pokemon` | `arena/7911f950` (atom) | — | historia commitów: `measure()`, hop same-origin, macierz hosts×paths |
| `peteraangelic-pixel/Gemma-konkurs` | `arena/6d081d52-gemma-konkurs` | `4992f0f` | `nask/findings/hunt-summary.md`, `nask/POMYSLY.md`, komunikaty S6/S7 |
| `peteraangelic-pixel/Smak-Domu-Konkurs` | `arena/5ed750ef-smak-domu-konkurs` | `464d7ba` | `nask/SYNTEZA-ZESPOLU-20261104.md`, `nask/REJESTR-ZGLOSZEN.md`, `nask/CHAT-LOG-NASK.md` |
| `peteraangelic-pixel/NASK` | `arena/a29ca234-nask` | `10cbb62` | `drive_materials/02-REKONESANS-20261103.md`, `04-REJESTR-ZGLOSZEN.md` |
| `peteraangelic-pixel/NASK` | `codex/multi-program-lab-20261103` | `a4fb58d` | komunikaty commitów (bounded exposure checks, encrypted evidence) |
| `peteraangelic-pixel/Gemma-konkurs` | `main` | `c0256ba` | tylko `README.md` (7 B) — brak treści |

**Uwaga o `NASK/main`:** repo publiczne ma w `main` wyłącznie README. Cała praca siedzi na dwóch gałęziach — jeśli ktoś szuka tam „gotowego pakietu”, go nie ma.

---

## 1. Kontrakty API ustalone przez zespół

### 1.1 `POST https://zglos-dezinformacje.nask.pl/api/sendForm` — **[C], z bundla JS**
Najcenniejszy ustalony kontrakt w całym zakresie, bo to jedyne miejsce, gdzie **serwer przetwarza treść podaną przez atakującego**.

```
metoda:   POST, multipart/form-data
pola:     accept               (wymagane)
          email                (opcjonalne)
          file                 (png/jpeg, ≤ 20 MB)
          reason               (≤ 250 znaków)
          urls                 (wymagane, do 50 linków, po jednym w linii)
          g-recaptcha-response (reCAPTCHA v3; brak → "executeRecaptcha is not ready")
odpowiedź: e.ok ? stan 3 : stan 4 (z bundla: fetch("/api/sendForm",{method:"POST",body:a}))
GET:      405
```
**Dlaczego to ważne:** `urls` × 50 to gotowe wejście do klasy §8.5 (SSRF), a `file` do §8.6 (upload → obejście filtra). **Blokada:** POST tworzy **prawdziwe zgłoszenie** u operatora rządowego i wymaga przejścia captchy → wymaga jawnego GO użytkownika i jego przeglądarki. Nie wysłane.

### 1.2 `GET https://bezpiecznymiesiac.pl/download-file/?fileUrl=<ścieżka>` — **[Z]**
Endpoint **poza `/api`**, dlatego nasza mapa (`naskmap`, wzorce `/api|/_next|/rest|/graphql`) go nie znalazła. To luka w naszym narzędziu, nie w wiedzy zespołu. Pomiar własny (3 żądania):

| wartość `fileUrl` | wynik |
|---|---|
| `/media/2026/09/Facebook-ecsm-1.png` | **500** (istniejący plik, ale nie PDF — wyjątek bez danych) |
| `/etc/passwd` | **404** `File not found` |
| `..%252f..%252f..%252fetc%252fpasswd` | **400** `Nieprawidłowe żądanie pliku` |

Zgodne z pomiarem c87 (20 wariantów: `/proc/version`, `%2e%2e%2f`, `..%5c`, `file://`, zakodowany schemat, `//science.nask.pl/…` — wszystkie 400/404; kontrola: PDF 603 523 B → 200). **Wniosek: filtr dekoduje wartość przed walidacją i odrzuca schematy oraz `..` niezależnie od kodowania. Klasa §8.15 zamknięta.**

### 1.3 `science.nask.pl` — **[Z]**
- `/api/downloadFile?fileId=<int>` — kontrakt złamany przeze mnie; `fileId=18864` → 200, `image/png`, 2 210 114 B, `Content-Disposition: attachment; filename="Designer-11.png"`.
- `/api/search?query=<≥3 znaki>&lang=pl` — **`lang=pl` jest wymagany**; bez niego `{"count":0,...}` mimo istniejących treści. To wyjaśnia, dlaczego wczesne sondy „nie działały”.
- `/api/contact` → `{"error":"Method not allowed"}` na GET (POST-only).
- `/api/media/wp-json/wp/v2/*` → 404 (REST niewystawione przez proxy).

### 1.4 `116sos.pl` — **[Z]**
- `/api/centres-search?q=…` → 200, pełna baza ośrodków (PESEL-nie, ale adresy, e-maile, telefony OPS). **`q` jest ignorowane**: `q=zzzzqqqxxx` zwraca dokładnie to samo co `q=Warszawa`. Konsekwencja: **wszystkie nasze testy SQLi na tym parametrze mierzyły szum** — do porównań używać `q=` pustego, nie innej frazy.
- `/api/fetch-cookie-hash` → `{"cookieHash":"6a9963b75ab63"}` — **identyczne w dwóch dniach i przy dwóch różnych żądaniach bez ciasteczka → stała (asset/cache-buster), nie pochodna sesji. Hipoteza „dane sesji” zamknięta.**
- `/wp-json` → 404 (Next.js, nie WordPress na wierzchu).

### 1.5 `pllum.org.pl` — **[Z]**
- `/api/_content/query` (Nuxt Content) → publiczne treści, `_draft:false`.
- `?_params={"where":[["_draft","=",true]]}` → **`[]`** → wersje robocze **nie** wyciekają (§8.3 zamknięte).

### 1.6 `dataannotation.pllum.org.pl` (HIVE) — **[Z] + [C]**
- SPA (React Router / `create-tsrouter-app`): nieznane ścieżki → 200 z tym samym HTML 713 B → **catch-all, nie „guard klienta”**.
- `/api/v1/projects/`, `/api/v1/users/` → `401 {"detail":"Not authenticated"}`; `/api/v1/users/1` → 405 (trasa istnieje, inna metoda).
- `/login`, `/forgot-password` publiczne; `/register`, `/api/v1/register`, `/api/v1/login`, `/api/v1/token` → 404. **Rejestracja nie istnieje — konto tylko od organizatora.**
- `/openapi.json`, `/api/openapi.json`, `/docs` → brak schematu.

### 1.7 `dns.pl` — **[Z] + [C]**
Żywe: `/api/zone-stats` (200, `application/json`, 11 759 B, dane publiczne), `/api/count-deleted-domains` (200, `{"count":"+1085"}`), `/api/registrars-services`. Martwe (404 z 41 KB strony serwisu): `/api/who-is-xml/`, `/api/domain-browser/`, `/api/stats/`, `/api/funny-name/`. **Technologia: Drupal** (`sites/default/files`).

### 1.8 `nask.pl` — **[Z]**
`/api/search?query=raport&lang=pl` → 200, pełne obiekty WP (autor, ID mediów, taksonomie), 73 strony paginacji, paginacja `perPage` ignorowana/częściowo walidowana. **Host `nask.pl` robi 302 → `www.nask.pl`, czyli poza literał §5 — nasze narzędzie świadomie NIE wykonuje tego skoku.**

---

## 2. Pomiary zespołu — przyjęte, nie powtórzone (oszczędność ~3 000 żądań)

| Pomiar | Kto | Wynik |
|---|---|---|
| 16 ścieżek ekspozycji × 12 domen (192 żądania) | a29ca | **zero ekspozycji** — wszystko catch-all SPA |
| 68 sond: traversal `/download-file`, `_next/image`, CORS, HIVE, dns.pl, 116sos | c87 + 7911 | **0 podatności**, klasy zamknięte |
| ~1500 żądań, 5 biegów, 47 bundle'ów / 7,3 MB JS | 5ed7 | **0 sekretów, 0 source-map**; mapa API (patrz §1) |
| 703 żądania, 15 hostów | 6d08 | 0 wysokich/krytycznych; 6 „średnich” = artefakt nagłówka `x-original-url` (patrz §5) |
| Fala 3 (007): `.env`, `.env.local`, `.git/config`, `.git/HEAD`, `wp-config.php.bak`, `backup.zip`, `db.sql`, `server-status` × 10 hostów | 7911 | **wynik nieopublikowany w chwili przeglądu** (commit `cac68f8` opisuje falę, plików `probe-run007/008` brak w `reports/`) — nie traktuję jako zmierzonego |
| `x-original-url` / `x-forwarded-prefix` zmienia odpowiedź na `moje.cert.pl`, `incydent.cert.pl` | 6d08 | 403/404/429 zamiast 200 — **niepowtarzalne z naszego środowiska** (te hosty zrywają połączenie, status 0) + zakaz z regulaminu usługi (§6) |

---

## 3. Inwentarz hostów poza zakresem — **[C], a29ca (Certificate Transparency)**

Dla `nask.pl` CT pokazuje **108 nazw hostów**; §5 wymienia **dwie** (`nask.pl`, `oad.nask.pl`). Pozostałe **nie są testowane** — to nie „brak nagrody”, to problem prawny:

```
dev.ncp.ebsi, uat.ncp.ebsi, api-pilot.ebsi.node1/2, uself-keycloak.lspncp.ebsi
gitlab.snkom, nextcloud.snkom, chat.snkom, jitsi.snkom, auth.snkom, mx.snkom
zakupy, zamowienia, taskmanagement, ksod, certyfikacja, inwentaryzacja,
secret.eadministracja, pigeon, smog, rd.variot, cs.pib, technologie, standard,
ekspert, enu1…u7 / u1b…u7b .pilot-dc4eu.ebsi, .pilot-vector.ebsi
testowo.dyzurnet.pl (poza zakresem), files.badanie.nask.pl (S3, poza zakresem)
```

**Reguła operacyjna do wpisania w narzędzie:** jeśli host nie jest dokładnie równy literałowi z §5 — nie dotykamy, nawet gdy dzieli domenę. Nasz `Scope` to już wymusza (test `unlisted_subdomains_are_not`).

---

## 4. Pułapki metodologiczne — **[C] przejęte do kodu**

1. **Catch-all.** `dns.pl` wstawia żądaną ścieżkę do kanonicznego URL, więc `/.env` i `/.git/HEAD` dają **różne** odpowiedzi na nieistniejących zasobach. Rozwiązanie: normalizacja ścieżki do tokenu **przed** hashowaniem. → u nas: catch-all per host (wdrożone).
2. **Rotujący token CSRF.** `zglos-dezinformacje` wstawia losowy token do HTML → dwa żądania różnią się o znak. Rozwiązanie: zwijanie ciągów ≥16 znaków hex do `<HEX>`. → **nie wdrożone** (nasz raport nie hashował ciał; do zrobienia, gdy dodamy diff ciał).
3. **`reqwest` normalizuje `../` w ŚCIEŻCE przed wysłaniem.** Ich log: `https://science.nask.pl/api/media/../../../etc/passwd` zamieniło się w `https://science.nask.pl/etc/passwd`. **Traversal w ścieżce był niemierzalny tym klientem** — mierzyć tylko w query albo kodować (`..%2f`). → nasz `ureq` zachowuje się tak samo; dlatego traversal testujemy w query/parametrze, nie w ścieżce.
4. **308/307 kanonizacja.** Frameworki odpowiadają przekierowaniem na kanoniczną ścieżkę (`/api` → `/api/`, `/wp-json/` → `/wp-json`, `/_next/image` → `/_next/image/`). Przy `redirects(0)` sondy są **ślepe** — 12 „trafień” w jednym przebiegu to były same przekierowania. → u nas: jeden skok same-origin (wdrożone, z twardym porównaniem **nazwy hosta**).
5. **„200 + JSON = kandydat” to fałszywa reguła.** Publiczne API tak właśnie wyglądają. Nasza wersja z rund 3–5 generowała szum; usunięte, zastąpione catch-allem i różnicą wobec baseline.

---

## 5. Rzeczy, które zespołowi wyszły fałszywie (korekty)

| Twierdzenie | Korekta |
|---|---|
| „116sos.pl leży (502 nginx)” — powtarzane w 4 raportach | **Nieaktualne.** Host żyje, `/api/centres-search` i `/api/fetch-cookie-hash` → 200. Awaria minęła; cztery sesje zapisały ją jako stan trwały. |
| „`fetch-cookie-hash` może zwracać dane sesji” | **Nie.** Stała wartość w dwóch dniach, bez ciasteczka. |
| „H9: enum `downloadFile` po własnym uploadzie = 2 000–4 500 zł” | **Sfalsyfikowane pomiarem** (nasz gęsty sweep 60 ID: wyłącznie publiczne zdjęcia). Resztkowa wartość: BAC tylko ze znanym niepublicznym ID. |
| „`/admin/logs` w HIVE ma guardy tylko klienta (H10, 4 500–10 000 zł)” | **Niepotwierdzone.** SPA zwraca 200 na wszystko (catch-all 713 B). Weryfikacja w rundzie 7 (`/admin/logs`, `/api/v1/admin/logs`) — wynik poniżej w `NASK/hunt/`. |
| „`q` w `centres-search` filtruje, więc `q=Warszawa'` dowodzi braku SQLi” | **Błędne założenie** — `q` jest ignorowane. Test mierzył szum. |
| „`www.nask.pl` jest w zakresie, bo §5 mówi `nask.pl`” | **Ryzyko odrzucenia.** Inna nazwa hosta. Pytanie do organizatora **przed** testem — trzy odrzucenia pod rząd mogą zablokować wysyłkę. |
| „IDOR na `/users/{id}` i `payout`/IBAN w `hack.cert.pl`” (6d08) | **Inny program** — `hack.cert.pl` należy do programu **CERT Polska**. Nasz program = 12 domen NASK. Nie mieszamy programów. |

---

## 6. Ustalenia prawne — **[C] a450**

**Regulamin usługi `moje.cert.pl`, część IV pkt 4.2, zakazuje testowania bezpieczeństwa — mimo że host jest w programie bug bounty.** To potencjalna dyskwalifikacja, nie drobiazg formalny. **Do pisemnego wyjaśnienia organizatora: nie testujemy.** Dodatkowo `moje.cert.pl` i pozostałe hosty `cert.pl` zrywają połączenie z naszego środowiska (status 0), więc i tak są niemierzalne.

---

## 7. Pomysły zespołu, których jeszcze nie wdrożyłem (z oceną)

| Pomysł | Źródło | Ocena |
|---|---|---|
| `bundle_scan.py` — offline klasyfikator formatu identyfikatorów (int/uuid/ulid/hash) jako **pre-ranking IDOR** | c87 | **Warto.** Ta sama logika w `naskmap` da ranking „który endpoint ma sekwencyjny int”, czyli gdzie IDOR jest tani. U nas `naskmap` ekstrahuje endpointy, ale nie klasyfikuje ID. |
| Próg entropii Shannona na kandydatów na sekrety + allow-lista fałszywych pozytywów | c87 | Warto, gdybyśmy robili własne zbiory JS. Ich przebieg (47 bundle'ów) dał 0 sekretów — niska wartość na tym zakresie. |
| Triage HAR offline (mapa XHR z przeglądarki użytkownika) | a450 | **Wysoka wartość, gdy pojawi się konto** (HIVE, panel). Wtedy mapa API pochodzi z realnej sesji, nie z bundle'a. |
| Macierz `hosts × paths` w planie sond (kompaktowy zapis, limit 400) | 7911 | Kosmetyka — nasze `checks.json` jest już generowane skryptem. |
| `jsdig-rs` (Rust + Rayon do minera JS) | 5ed7 | Nie teraz: 5 req/s sprawia, że CPU nie jest wąskim gardłem (patrz `nask/POMYSLY.md` w 6d08 — ta analiza jest trafna). |
| Zbieranie dowodów z SHA-256 każdego żądania | 6d08 | **Warto przy pierwszym PoC.** Nasze raporty mają status/długość/czas, ale nie hash ciała. |

---

## 8. Pytania do organizatora (jedno wystąpienie, trzy wątki)

1. Czy `www.nask.pl` mieści się w zakresie literału `nask.pl` z §5?
2. Czy zakaz z regulaminu usługi `moje.cert.pl` (IV 4.2) wyłącza ten host z programu bug bounty?
3. Czy można otrzymać konto testowe w `dataannotation.pllum.org.pl` (HIVE) — bez rejestracji IDOR/BAC jest nie do udowodnienia zgodnie z §6.

---

## 9. Czego świadomie NIE przejąłem

- **Nie skopiowałem** cudzych repozytoriów ani plików 1:1 — tylko fakty z proweniencją. Duplikowanie 1,9 MB JSON-ów pomiarowych bez możliwości ich zweryfikowania byłoby balastem, nie dowodem.
- **Nie przyjąłem** żadnego twierdzenia o podatności bez powtórzenia (stąd sekcja 5).
- **Nie wysłałem** żadnego żądania zapisującego (`sendForm`) — bez GO użytkownika.
- **Nie tknąłem** hostów spoza §5, `hack.cert.pl` (inny program), `moje.cert.pl` (zakaz) ani Władysławowa.
