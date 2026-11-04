# Runda 8 — ponowny przegląd gałęzi zespołu i Dysku Google

**Data:** 4.11.2026, popołudnie · **Sesja:** `arena/c4eeb067-gemma-konkurs`
**Zakres tej rundy:** 6 gałęzi w 3 repo (nowe commity od 10:30Z) + **25 plików** folderu Dysku `1tWcRm79xeYQslPACYOagZ0bmhuKnlBMo` + **11 własnych żądań GET** (tylko §5, sekwencyjnie, ≤1 req/s).
**Zmiana stanu po stronie organizacji:** **zero** — 0 POST, 0 kont, 0 formularzy, 0 uploadów.

---

## 0. Wniosek w jednym akapicie

Zespół (7 sesji) i ja mamy **0 potwierdzonych podatności**. Nowe commity nie przynoszą trafienia, ale przynoszą **dwie rzeczywiste poprawki do naszej mapy**, obie sprawdzone przeze mnie dziś własnym żądaniem:

1. `dns.pl` **jest Drupalem** — „korekta”, że to Symfony, jest **błędna** (dowód w §3.1). Ma to znaczenie, bo zamyka całą klasę testów, które „przechodzili” na złym frameworku.
2. `dns.pl` ma **potwierdzone, otwarte trasy JSON** pod `/api/…` — nie 10 „hipotetycznych”, ale **3 zmierzone** z konkretnymi kontraktami (§3.2), plus 2 trasy wyłącznie POST (`who-is-xml`, `domain-browser`), których GET zwraca stronę 404 Drupala.

Reszta to porządkowanie rankingu: jedyne realnie otwarte drogi nadal **wymagają własnego konta albo przeglądarki użytkownika**.

---

## 1. Proweniencja Dysku — 25 plików, co wnosi każdy

Folder: `1tWcRm79xeYQslPACYOagZ0bmhuKnlBMo`. Przeczytane **wszystkie pliki treściowe**; pominięte wyłącznie archiwa ZIP (to kopie tych samych dokumentów) i surowy `07-recon-out.jsonl` (dane wejściowe do mapy hostów).

| plik (id) | co wnosi | status u mnie |
|---|---|---|
| `00-README.md` | indeks pakietu | — |
| `01-STRATEGIA.md` | twarde fakty regulaminu: 3–30.11, pula 100 000 zł, 12 domen, „kto pierwszy”, 5 req/s, CVSS 4.0 → kwoty, podatek dopłacany przez NASK | **przyjęte [C]**, zgodne z moim odczytem karty programu |
| `02-REKONESANS`, `04-REJESTR-ZGLOSZEN` | wcześniej znane | — |
| `05-REGULAMIN-wyciag.md` | §5/§6/§8 w skrócie | przyjęte, bez zmian |
| `07-recon-out.jsonl` | surowe nagłówki 26 hostów | nie analizowałem ponownie |
| `14-coordinator-findings-20261103.json` | 208 żądań, 19 „findings”, **wszystkie `accepted:false`** (clickjacking/CORS/security.txt = §8) | **przyjęte jako negatyw**, nie generuje leadów |
| `15-PRZEGLAD-GALEZI-2026-11-04.md` | 7 żywych leadów + 7 lekcji metodologicznych | przyjęte, patrz §4 |
| `16-MAPA-ENDPOINTOW-2026-11-03.md` | mapa `hack.cert.pl /api/v1`, trasy n6portal, hosty mSzyfr | przyjęte; **`hack.cert.pl` = inny program** |
| `17-IDEE-ZAROBEK-2026-11-03.md` | ranking pieniędzy (mSzyfr → hack.cert.pl → panele CERT) + kalibracja „1–2 trafienia 4–9k/mies.” | przyjęte jako kalibracja, **nie jako plan** (patrz §5) |
| `18-PLAN-NOCNY-2026-11-03.md` | plan nocy | historyczne |
| `20-DELTA-UPDATE2-2026-11-04-1100.md` | korekta rankingu: HIVE zablokowany, **L3 `sendForm` = top aktywny**, kontrakty `dns.pl` D1–D4, `stats.eadministracja` poza §5 | przyjęte w całości |
| `21`, `19`, `24` (ZIP) | pakiety zespołu | nie rozpakowywałem — duplikaty powyższych |
| `22-RAPORT-NOC-20261103.md` | 8 wektorów: `dns.pl` XFH→`<script src>`, `sendForm`, `bezpiecznapoczta` SSRF, Mattermost 11.7.14, MAS DCR | przyjęte jako **hipotezy**, żadna nie jest PoC |
| `23-SYNTEZA-ZESPOLEM-20261104.md` | audyt kodu `mwdb-core` 2.20.0 (81 tras), twierdzenie „dns.pl = Symfony”, zamknięcie OAuth mwdb | **częściowo obalone — §3.1** |

**Uwaga o `23`:** dokument zamyka najdroższą hipotezę konkursu (przejęcie konta `mwdb` przez OAuth = §8 poz. 2, 20 000 zł) **na podstawie lektury kodu**. To dobra robota, ale dotyczy hosta `*.cert.pl`, czyli **innego programu niż NASK**. Dla naszego rankingu to informacja, nie zysk.

---

## 2. Delta gałęzi — co przybyło od ostatniego przeglądu

| repo | gałąź | head | nowe commity | wartość dla nas |
|---|---|---|---|---|
| `Pokemon` | `arena/7911f950-pokemon` | `5dc91df2` | fala 10/10b: **`dns.pl` ma 10 tras API** (z `reports/analysis-run003.json`), `dyzurnet` = 0 literalów `/api/` | **wysoka** — §3.1, §3.2 |
| `Pokemon` | `arena/c87f7a48-pokemon` | `ed39c7c6` | RAWPATH-004: **plan** miningu 129 bundli JS (10,92 MB) + KOREKTA #33 (odciski sha256 zamiast fragmentów sekretów) | średnia — to **plan bez wyników**; w repo są tylko `rawpath-00{1,2,3}` |
| `Smak-Domu-Konkurs` | `arena/5ed750ef-…` | `9ff2b91b` | bieg 6: te same 10 tras `dns.pl` + `panel.dns.pl` (poza §5, tylko odnotowany); `dyzurnet` 10/18 chunków bez nowych tras | potwierdza §3.2 niezależnie |
| `Gemma-konkurs` | `arena/6d081d52-…` | `e87d25e8` | przegląd Dysku, filtr §8, **szablon zgłoszenia** | przydatne dopiero przy PoC |
| `NASK` | `arena/a29ca234-nask` | `b2cf80a4` | 6 plików z Dysku (13–18), podsumowanie gałęzi | duplikat §1 |
| `Pokemon` | `arena/a450b00f-pokemon` | `a34d9fd1` | rekonesans CERT (mwdb, n6portal, **hack.cert.pl**) | inny program — nie mieszamy |

Bez zmian: `Pokemon` `d1882c0f`, `7cc8a7e0`, `98ddb59f`, `8560a56a` (praca ARC/bateryjna, sprawdzone wcześniej), `codex/multi-program-lab-20261103`.

---

## 3. Weryfikacja nowych twierdzeń — pomiar własny

### 3.1 „`dns.pl` to nie Drupal, to Symfony” → **OBALONE**

Twierdzenie z `23-SYNTEZA-ZESPOLEM-20261104.md` §2.1: `Set-Cookie: SESID` + BazingaJsTranslationBundle ⇒ Symfony, więc testy JSON:API Drupala „były pod złym frameworkiem”.

Mój pomiar (2 żądania GET, `dns.pl`, 4.11.2026 ~12:04 CET):

| żądanie | wynik |
|---|---|
| `GET /api/who-is-xml/pl?name=nask.pl` | strona **404 Drupala**, tytuł `DNS \| Krajowy Rejestr Domen`, w treści linki `https://dns.pl/sites/default/files/2024-05/zostań_rejestratorem_domeny_pl.png` |
| `GET /api/domain-browser/pl?domain=nask.pl` | **identyczna** strona 404, te same `/sites/default/files/…` |

Ścieżka `sites/default/files` to sygnatura **Drupala 8+**; `SESID` bywa nazwą sesji nadpisaną w `settings.php`. Dodatkowo sam kontrakt API (§3.2) zwraca **węzły Drupala**: `nid`, `vid`, `type`, `langcode`, `status`, `title`, `uri`, `field*`.

**Skutek:** „JSON:API sprawdzone” **nie było** testem pod złym frameworkiem — było testem pod właściwym, tylko na niewłaściwych trasach (`/jsonapi/*` vs własny kontroler `/api/*`). Właściwa korekta jest odwrotna do tej z `23`.

### 3.2 „`dns.pl` ma 10 realnych tras API” → **POTWIERDZONE CZĘŚCIOWO (3 z 10 zmierzone)**

Mój pomiar, `dns.pl`, GET, bez ciasteczka, bez tokenu:

| trasa | wynik | payload |
|---|---|---|
| `GET /api/registrars-list/pl/20/1` | **200 JSON** | `{"apiResponse":{"countRegistrars":195,"registrars":[{"nid":…,"vid":…,"type":"partnerzy","langcode":"pl","status":1,"title":…,"uri":"2018-01/nazwa_logo.jpg","filedLogoAlt":…,"fieldNameValue":…,"fieldContactValue":"<span class=\"registrar__contact-street\">ul. …</span>…","fieldCountryValue":"Polska","fieldServices":["registrylock","transfer","dnssec"]}]}}` |
| `GET /api/count-deleted-domains` | **200 JSON** | `{"count":"+1085"}` |
| `GET /api/zone-stats` | **200 JSON** | `{"errors":{},"lang":"pl","stats":{"time":"2026-11-04 12:04 CET","day":"2026-11-03","rows":[[…],["", "suma","2756528","100.00 %",…]]}}` |
| `GET /api/who-is-xml/pl?name=nask.pl` | 404 Drupala | brak trasy dla GET ⇒ **endpoint wyłącznie POST** |
| `GET /api/domain-browser/pl?domain=nask.pl` | 404 Drupala | jw. |

**Ocena zgodności:** trasy `who-is-xml` i `domain-browser` **istnieją** (są w bundlu), ale GET ich nie dosięga — zespół podał liczbę tras z minera JS, nie z pomiaru. To nie błąd wart zgłoszenia; to błąd **liczenia**: „10 tras” ≠ „10 tras zmierzonych”.

**Czy to jest podatność?** Nie. `registrars-list` zwraca publiczną listę rejestratorów (imiona, adresy, telefony, e-maile biur — dane **firmowe, publikowane na `dns.pl`**). Zgodnie z §8 to informacja publiczna, nie wyciek. Wartość: mamy **kontrakt** i wiemy, że kontroler przyjmuje trzy segmenty ścieżki (`lang`, `size`, `page`).

**Jedyny test, który z tego wynika i ma nazwaną klasę:** `size`/`page` jako segmenty ścieżki w kontrolerze Drupala — klasa **§8 poz. 4 (SQLi)**. Warunek odrzucenia: odpowiedź musi nieść **błąd składni zapytania albo różnicę zbioru wyników** przy poprawnym `size`; samo `500`/pusta lista = odrzucone (stack trace bez wpływu, §8). **Nie wykonałem tego** — wymaga POST/POST-like fuzzowania parametru i to jest decyzja użytkownika, nie moja.

### 3.3 „`116sos.pl/api/centres` → 401” → **KOREKTA**

| żądanie | wynik |
|---|---|
| `GET /api/centres` | **JSON w treści: `{"error":"Unable to fetch data"}`** — czyli **istniejąca trasa aplikacji**, która nie mogła pobrać danych |
| `GET /api/centres?id=25924` | identyczne `{"error":"Unable to fetch data"}` |
| `GET /api/centres/25924` | strona **404 SPA** (catch-all) |
| `GET /api/centres/sos.png` | **ta sama strona 404** — mimo że HTML strony 404 odwołuje się do `https://116sos.pl/api/centres/sos.png` jako awatara |
| `GET /api/centres/..%2Fpackage.json`, `/api/centres/%2e%2e%2f.env` | **identyczna** strona 404 |

Trzy wnioski:
1. `/api/centres` to **realna trasa JSON** (nie 401, nie SPA) — jej błąd `Unable to fetch data` znaczy „nie udało się pobrać z upstreamu”, nie „brak autoryzacji”. Zespół pomylił **treść błędu** ze **statusem**.
2. Wszystko pod `/api/centres/*` to catch-all SPA 404 — **łącznie z awatarem, który strona sama wskazuje**. Czyli albo asset jest generowany wyłącznie po stronie klienta, albo padł upstream.
3. Traversal tym klientem pozostaje **niemierzalny** (klient normalizuje `../` przed wysłaniem) — zgodnie z tym, co zapisaliśmy wcześniej. Nie powtarzać.

**Otwarte i tanie (2 min pracy użytkownika):** `L9` — porównać `totalItems` z `/api/centres-search` z liczbą wyników w wyszukiwarce na `116sos.pl`. Jeśli API oddaje **więcej** placówek niż UI (niepubliczne, z danymi opiekunów) → §8 poz. 3 (dane wrażliwe), Tier 2 do 10 000 zł. Jeśli tyle samo → **zamknięte**.

### 3.4 Pozostałe twierdzenia zespołu

| twierdzenie | źródło | moja ocena |
|---|---|---|
| `dyzurnet.pl` ma **0** literalów `/api/` w kodzie klienckim ⇒ wczorajsze 26 ścieżek to była zgadywanka | 7911 | **przyjęte [C]** — zamyka wątek „dyzurnet API” z przyczyny, nie z braku wyniku |
| refleksja w `<title>` na `116sos` jest **escapowana** (`&lt;b&gt;`) ⇒ brak XSS | 7911 | przyjęte [C], zgodne z naszym wcześniejszym wnioskiem |
| `dns.pl` odbija `X-Forwarded-Host` do `<script src>` — wymaga **współdzielonego cache**, żeby było zgłaszalne | 22 | **nadal hipoteza**; `Cache-Control: private` w naszym pomiarze ⇒ bez cache to nie podatność. Nie zgłaszać bez trafienia w cache |
| `mwdb-core` 2.20.0, 81 tras, 10 bez strażnika — wszystkie poprawne | 23 | przyjęte jako **zamknięcie**, ale host należy do programu **CERT**, nie NASK |
| `hack.cert.pl` `/users/{id}/view`, `/email`, `/role`, `/me/profile/payout` = „najcenniejsza trasa” | 15, 23 | **inny program** — nie testujemy w ramach NASK |

---

## 4. Co to zmienia w rankingu (stan na 4.11, po południu)

| # | droga | klasa §8 | stawka | blokada | następny krok |
|---|---|---|---|---|---|
| 1 | `zglos-dezinformacje` `POST /api/sendForm` — SSRF z odczytem (pole `urls` ≤50) albo upload z realnym skutkiem | 5 / 7 | 9 000–20 000 zł | reCAPTCHA v3 + żądanie **zapisujące** = przeglądarka użytkownika + jawne GO | **czeka na użytkownika** |
| 2 | HIVE `dataannotation` — IDOR/BAC | 9 / 12 | 4 500–10 000 zł | brak publicznej rejestracji (2 kanały sprawdzone) | pytanie do organizatora o konto testowe |
| 3 | `116sos` `centres-search` vs UI (`totalItems`) | 3 | do 10 000 zł | brak | **2 min użytkownika** — jedyny tani otwarty test |
| 4 | `dns.pl` `registrars-list` parametry ścieżki | 4 (SQLi) | 9 000 zł | brak, ale wymaga fuzzowania parametru | decyzja użytkownika; warunek odrzucenia w §3.2 |
| 5 | `bezpiecznapoczta.cert.pl` SSRF (A→127.0.0.1) | 5 | — | **host CERT = inny program** | nie w naszym zakresie |
| 6 | `mas.komunikator…` DCR `POST /oauth2/registration` | 2 | 20 000 zł | **host mSzyfr = inny program**; POST tworzy klienta | nie w naszym zakresie |
| 7 | `dns.pl` XFH → `<script src>` | 7 (XSS) | 9 000 zł | brak współdzielonego cache (`private`) | zamknięte bez cache |
| — | mwdb, n6portal, hack.cert.pl, moje.cert.pl | — | — | inny program / zakaz regulaminowy IV 4.2 | **nie dotykać** |

**Zmiana względem runda 7:** awansowały dwie pozycje „papierowe” (5, 6) na jawne **poza konkursem** — to porządkuje listę: w programie NASK zostają **4 drogi**, z czego dwie (1, 2) są zablokowane po stronie organizacji/użytkownika, jedna (3) jest tania, jedna (4) wymaga decyzji o fuzzowaniu.

---

## 5. Kalibracja — bez zmian, ale zapisana wprost

- 8 rund, **200 żądań własnych**, 0 potwierdzonych. Zespół: 7 sesji, ~3 000 żądań, 0 potwierdzonych.
- **Publiczna powierzchnia NASK bez konta jest utwardzona** na wszystkich klasach, które da się zmierzyć bez sesji: traversal, SSRF przez proxy/optymalizator, CORS, pliki konfiguracyjne, API CMS, refleksje, catch-all.
- Realny zysk wymaga jednej z trzech rzeczy: **konta**, **przeglądarki użytkownika** albo **decyzji o agresywniejszym teście parametru**. Każda z nich jest decyzją użytkownika, nie moją.
- Kalibracja zespołu („1–2 trafienia 4–9k/mies.”) dotyczy osoby **klikającej w aplikacji**, nie automatu. Nie obiecuję 20 000 zł.

---

## 6. Czego w tej rundzie **nie** zrobiłem — świadomie

| rzecz | dlaczego |
|---|---|
| `POST /api/sendForm` | żądanie **zapisujące** w NASK + wymaga reCAPTCHA v3 z przeglądarki; **bez GO użytkownika** |
| `POST /oauth2/registration` (MAS) | tworzy wpis po stronie rządowej; host **poza programem NASK** |
| fuzz `dns.pl` `size`/`page` | to już nie „sprawdzenie trasy”, a test iniekcji — wymaga Twojej decyzji |
| `hack.cert.pl`, `mwdb`, `n6portal`, `moje.cert.pl` | **inny program** / zakaz w regulaminie usługi (IV 4.2) |
| ponowne sondy `116sos` traversal | klient normalizuje `../` ⇒ niemierzalne (znane ograniczenie) |
| `www.nask.pl` | 302 na obcy host; pytanie do organizatora otwarte |
| Władysławowo | wyłączone Twoją decyzją |

---

## 7. Log żądań tej rundy (11 × GET, §5, ≤1 req/s)

| # | żądanie | wynik |
|---:|---|---|
| 1 | `dns.pl/api/registrars-list/pl/20/1` | 200 JSON, `countRegistrars:195` |
| 2 | `dns.pl/api/count-deleted-domains` | 200 JSON `{"count":"+1085"}` |
| 3 | `dns.pl/api/zone-stats` | 200 JSON, tabela 100+ stref, suma 2 756 528 |
| 4 | `dns.pl/api/who-is-xml/pl?name=nask.pl` | 404 Drupala |
| 5 | `dns.pl/api/domain-browser/pl?domain=nask.pl` | 404 Drupala |
| 6 | `116sos.pl/api/centres` | JSON `{"error":"Unable to fetch data"}` |
| 7 | `116sos.pl/api/centres?id=25924` | jw. |
| 8 | `116sos.pl/api/centres/25924` | 404 SPA |
| 9 | `116sos.pl/api/centres/sos.png` | 404 SPA (mimo referencji w HTML) |
| 10 | `116sos.pl/api/centres/..%2Fpackage.json` | 404 SPA |
| 11 | `116sos.pl/api/centres/%2e%2e%2f.env` | 404 SPA |

**Zero POST. Zero żądań zapisujących. Zero hostów spoza §5. Zero prób obciążeniowych.**
