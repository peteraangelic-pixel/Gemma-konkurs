# Przegląd Dysku Google — folder zespołu (04.11.2026)

Folder: <https://drive.google.com/drive/folders/1tWcRm79xeYQslPACYOagZ0bmhuKnlBMo>
Stan odczytu: 20 pozycji, wszystkie odczytane (18 md/json/kod + 2 archiwa zip).
Właściciel zapisu: sesje „codex" (NASK) — pliki 00–14 z 03.11, 15–19 z 04.11 rano (10:51 UTC).

Cel tego dokumentu: **co z Dysku przyjmuję, co już mam, a czego nie ruszam.**
Numeracja plików jest ich własna (00–19), nie moja.

---

## 1. Inwentarz — co leży na Dysku i co z tego biorę

| # | Plik | Co zawiera | Decyzja |
|---|---|---|---|
| 00 | `00-README.md` | spis paczki | pomijam (meta) |
| 01 | `01-STRATEGIA.md` | strategia 5 programów, mapa 26 hostów | **duplikat** — mam to samo w `SCOPE.md`; jedna rzecz nowa: tabela stawek per program (patrz §2.1) |
| 02 | `02-REKONESANS-20261103.md` | rekonesans hostów z 03.11 (pasywny) | duplikat mojego `hunt` przebieg 1–2 |
| 03 | `03-PLAN-DZIALANIA.md` | plan | duplikat `PLAN.md` |
| 04 | `04-REJESTR-ZGLOSZEN.md` | rejestr zgłoszeń — **pusty** | potwierdza: nikt nic nie wysłał |
| 05 | `05-REGULAMIN-wyciag.md` | wyciąg z regulaminu (zakres, §8) | **przyjmuję jako źródło klasy** → `SZABLON-ZGLOSZENIA.md` |
| 06 | `06-LOG-REKONESANSU.md` | log pobrań | duplikat |
| 07 | `07-recon-out-20261103.jsonl` | surowe obserwacje | duplikat mojego `evidence.jsonl` |
| 08 | `08-nask-bugbounty-komplet.zip` (53 kB) | paczka narzędzi/notatek | pomijam — to ich kit, mam własny |
| 09 | `09-PRZEGLAD-REPO-NASK-20261103.md` | audyt repo NASK | duplikat `AUDYT-POPRZEDNIEGO-REPO.md` |
| 10 | `10-ZALACZNIK-report-szablon.md` | **szablon zgłoszenia** | **przyjmuję** → `SZABLON-ZGLOSZENIA.md` (§4) |
| 11 | `11-ZALACZNIK-poc-example.md` | przykład PoC | **przyjmuję** jako wzorzec (kroki + surowy request) |
| 12 | `12-ZALACZNIK-gen_report.py` | generator raportu | pomijam — mam `probes.py`; format biorę z 10/11 |
| 13 | `13-STRATEGIA-5-PROGRAMOW.md` | pomiar 208 żądań / 26 hostów → 0 zgłoszeń, 19 odrzuconych przez §8 | **przyjmuję jako potwierdzenie kalibracji** (§2.4) |
| 14 | `14-coordinator-findings-20261103.json` | ich findings (wszystkie odrzucone) | pomijam — 0 nowych klas |
| 15 | `15-PRZEGLAD-GALEZI-2026-11-04.md` | ich przegląd 6 gałęzi + synteza nocy | **przyjmuję** — zbieżne z moim `PRZEJALEM-Z-GALEZI.md` |
| 16 | `16-MAPA-ENDPOINTOW-2026-11-03.md` | **pełna mapa `/api/v1` hack.cert.pl**, mapa n6portal (OIDC/MFA/api_key), moje.cert.pl, mSzyfr | **przyjmuję — najcenniejszy plik** (§2.2, §2.3) |
| 17 | `17-IDEE-ZAROBEK-2026-11-03.md` | rank pieniędzy + kalibracja + lista „czego nie robić” | **przyjmuję** zgodne z moim planem |
| 18 | `18-PLAN-NOCNY-2026-11-03.md` | plan nocy + update rano | duplikat `PLAN.md` |
| 19 | `19-nask-noc-20261104-komplet.zip` (3,2 MB) | archiwum: te same md + `recon/evidence-20261103/` (46 bundli JS, 3,9 MB), `rust/endminer`, binarka | **sprawdzone: zero treści poza md 01–18** — nie wciągam 3 MB do repo |

**Netto: 4 rzeczy do przyjęcia (05, 10/11, 16, 17), 1 potwierdzenie (13), reszta duplikat.**
Archiwum 19 nie zawiera niczego, czego nie ma w plikach 01–18 — sprawdzone przez rozpakowanie
(82 plików: md + `evidence-20261103/*.js` + źródła `endminer`).

---

## 2. Co z Dysku jest realnie nowe

### 2.1. Tabela stawek per program — pierwsze pełne zestawienie

| program | pula | Tier 1 | Tier 2 | uwaga |
|---|---:|---|---|---|
| NASK | 100 000 zł | 600/4 000/9 000/**20 000** | 300/2 000/4 500/10 000 | największa pula |
| CERT Polska | b.d. | 600/4 000/9 000/**20 000** | 300/2 000/4 500/10 000 | `*.cert.pl` = wildcard |
| Portal Gov.pl | b.d. | 600/4 000/9 000/**20 000** | — | **tylko `www.gov.pl`** |
| mSzyfr | b.d. | 600/4 000/9 000/**20 000** | — | `*.komunikator.narodowy.gov.pl` |
| Władysławowo | b.d. | 100/1 000/2 500/4 000 | 100/600/1 500/2 500 | **odrzucone przez usera** (stawki 5× niższe) |

Konsekwencja dla mnie: **`ctf.hack.cert.pl` jest Tier 2** (300–10 000), a `hack.cert.pl` — Tier 1.
Nie mieszamy tych dwóch w jednym zgłoszeniu.

### 2.2. `hack.cert.pl` — `/api/v1` z bundla SPA, z rozdzieleniem widoku programu i uczestnika

Najważniejsze, czego nie miałem w tej postaci:

- `reports/{id}` = **widok programu (staff)**, `me/reports/{id}` = **widok uczestnika** — to
  rozdzielenie jest wskazówką, gdzie szukać BAC: te same dane, dwa różne prefiksy.
- `/api/v1/users/{uid}{,/role,/email}` — zmiana roli i maila **na dowolnym uid**.
- `/api/v1/users/me/profile/payout` — dane wypłat (klasa „dane wrażliwe”, jeśli IDOR).
- `/api/v1/institutions/{slug}/programs/{prog}/editions/{num}/payout-export` — eksport wypłat
  (CSV z danymi osobowymi = największa pojedyncza wartość w portalu).
- `/api/v1/me/reports/{id}/reward-offers/{rid}/accept` — automat stanów nagród.
- `/api/v1/reports/{id}/internal-notes{,/{nid},/authors/{uid}/avatar}` — notatki wewnętrzne CERT.

To pokrywa się z moją sondą S7 (bez sesji: 0 trafień) — **wariant z sesją pozostaje jedynym
żywym testem na tym hoście.**

### 2.3. Dwie nowe, tanie ścieżki pasywne (nie wymagają konta)

1. **`oad.nask.pl` — publiczny embed PowerBI z `autoAuth=true`.**
   Ryzyko: raport osadzony z auto-uwierzytelnieniem pokazuje rekordy, nie agregaty.
   Test: otworzyć embed w przeglądarce i **przeczytać, co widać**. Zero żądań ofensywnych,
   zero narzędzi. Kryterium odrzucenia: raport pokazuje wyłącznie agregaty → zamykamy.
   Klasa, gdyby pokazywał rekordy: 03 (dane wrażliwe).
2. **`moje.cert.pl` ma publiczne `/accounts/signup/`.**
   Czyli **konto własne jest możliwe** — a to była jedna z blokad w planie. Blokadą pozostaje
   konflikt regulaminowy (§4a `SCOPE.md`): regulamin usługi zakazuje testowania bezpieczeństwa
   pomimo programu bug bounty na tym hoście. **Bez pisemnego wyjaśnienia organizatora nie
   zakładam tam konta i nie testuję niczego.**

### 2.4. Potwierdzenie kalibracji z ich pomiaru

`13-STRATEGIA-5-PROGRAMOW.md`: 26 hostów, 208 żądań, **0 do zgłoszenia, 19 odrzuconych przez §8**
(braki nagłówków, brak `security.txt`). Moje 816 żądań w przebiegu 4 dało 13 trafień, wszystkie
`niski`, żadne niekwalifikowalne. Trzy niezależne pomiary, ta sama odpowiedź: **anonimowa
powierzchnia tych programów nie płaci.** To nie opinia — to trzy pomiary.

### 2.5. Nowe negatywy, które zamykają tematy

- **`oad.nask.pl/podglad-pdf?url=`** — martwe: serwer waliduje **prefiks `/media/`**, wartość
  spoza prefiksu → 500 bez danych, `169.254.169.254` i `https://example.com/x.pdf` → 500.
  Brak pobierania po stronie serwera. (→ `HIPOTEZY-ZAMKNIETE.md` #16)
- **`science.nask.pl` — path traversal mierzony surowym gniazdem (nie klientem HTTP)** — 7/7
  identycznych statusów/rozmiarów/sha256, `%2e` normalizowane przez nginx, `%252e%252e` → 404.
  Powtarzalny negatyw, nie „nie udało się zmierzyć”. (→ #17)
- **`/api/v1/register` w HIVE nie istnieje** (`/register` → 404) — konto tylko od organizatora.
- **`dns.pl` = Drupal**, JSON:API wyłączone; z 5 tras z bundla **żyją 2** (`zone-stats`,
  `registrars-services`), obie publiczne.
- **`mSzyfr`**: brama zwraca catch-all 200 HTML dla `.js` poza przeglądarką → bundle
  niedostępny curl-em. Pomiary bez konta **niemożliwe** (nie negatyw, ograniczenie metody).
- **`116sos.pl`** leżał od ~23:00 (502 na wszystko) — awaria, nie wynik. Po powrocie
  do sprawdzenia: `/api/fetch-cookie-hash` (stała `6a9963b75ab63` — zamknięte jako enum),
  `/api/centres-search` (28 kluczy, **nadal otwarte**: porównać `totalItems` z publicznym UI).

---

## 3. Czego z Dysku świadomie NIE biorę

1. **Ich kitu narzędziowego** (08, 12, 14) — mój `probes.py` jest węższy, ale ma 110 testów
   regresyjnych i kontrakt „sonda bez grupy kontrolnej nie istnieje”. Ich 19 odrzuconych
   findings to dokładnie ten problem, którego u siebie nie mam.
2. **Ich pętli nocnej / harmonogramu** — oni sami ją wyłączyli (`night-operation`: „nie działa
   nocna pętla powtórzeń ani monitor gałęzi”). Moje Actions zostają jednoetapowe.
3. **Zasady „wysyłaj formularz, żeby zobaczyć”** — ich `nastepny-etap` wprost odrzuca
   automatyczne wysyłanie zgłoszeń bez zgody usera. Zgadzam się: `sendForm` = żądanie
   ZAPISUJĄCE u operatora rządowego, **wymaga Twojego GO i ręki**.

---

## 4. Wnioski — trzy zadania, żadne nie jest skanem

1. **Ty, 2 minuty, przeglądarka:** otwórz embed PowerBI z `oad.nask.pl` i powiedz, czy widać
   pojedyncze rekordy, czy tylko agregaty. To jedyna nowa **pasywna** ścieżka z Dysku.
2. **Ja, offline:** wpisać 20 klas z §8 + tabelę „nie płaci” do `SZABLON-ZGLOSZENIA.md`, żeby
   każdy przyszły drafts raportu przechodził przez ten sam filtr (bez tego piszemy raporty za 0 zł).
3. **Ty, decyzja:** czy piszemy do organizatora o (a) `moje.cert.pl` (konflikt ToS) i
   (b) literał `nask.pl` vs `www.nask.pl`. Bez odpowiedzi (a) nie ruszamy CERT Tier 1 poza
   `hack.cert.pl` i `mwdb` (zamknięte).

Nic z Dysku nie zmienia wniosku, do którego doszły wszystkie sesje: **bez sesji nie ma
pieniędzy**. Zmienia jedno: mamy teraz kompletną mapę jedynego hosta, na którym sesja jest
legalna i darmowa (`hack.cert.pl`).
