# Runda 7 — weryfikacja twierdzeń zespołu (2026-11-04)
**Raport źródłowy:** `NASK/hunt/report-20261104T1050Z.{md,json}` · 24 żądania, ≤2 req/s, GET-only
**Zestaw sond:** `NASK/tools/naskhunt/checks.json` (archiwum: `checks-round6.json`)
**Werdykt zbiorczy: 0 podatności. Jeden cudzy lead obalony, dwie hipotezy domknięte.**

---

## 1. OBALONE: „`/admin/logs` w HIVE ma guardy tylko klienta” (H10, 4 500–10 000 zł)

| sonda | wynik |
|---|---|
| `GET dataannotation.pllum.org.pl/admin/logs` | **200, 713 B, `text/html`** |
| catch-all hostu (losowa ścieżka) | **200, 713 B** — identyczne |
| `GET /api/v1/admin/logs` | **404, `{"detail":"Not Found"}`** |
| `GET /api/v1/users/` | **401, `{"detail":"Not authenticated"}`** |

**Interpretacja:** 713 B to powłoka SPA (`create-tsrouter-app`) — ta sama, którą host zwraca na **dowolną** nieistniejącą ścieżkę. To nie „guard po stronie klienta”, tylko catch-all. API pod `/api/v1/admin/logs` nie istnieje (404), a API, które istnieje, ma autoryzację po stronie serwera (401).
**Wniosek:** H10 w wersji „guardy tylko klienta” jest artefaktem pomiaru. Nie ma tu nic do zgłoszenia i nie ma na czym budować budżetu. **Zamknięte pomiarem, nie opinią.**

## 2. DOMKNIĘTE: `bezpiecznymiesiac.pl/download-file/?fileUrl=` (nowy punkt na mapie)

| `fileUrl` | wynik |
|---|---|
| `/media/2026/09/Facebook-ecsm-1.png` (kontrola) | **200**, `image/png`, 540 927 B, `attachment` |
| `%2Fmedia%2F2026%2F09%2FFacebook-ecsm-1.png` (kodowane ukośniki) | **200**, identyczne 540 927 B |
| `/MEDIA/2026/09/Facebook-ecsm-1.png` (wielkie litery) | **200**, identyczne 540 927 B |
| `media/2026/09/Facebook-ecsm-1.png` (bez wiodącego ukośnika) | **200**, identyczne 540 927 B |
| `/media/./2026/09/Facebook-ecsm-1.png` (segment `.`) | **400** `Nieprawidłowe żądanie pliku` |
| `/media/2026/09/` (katalog) | **400** |

**Interpretacja:** walidacja normalizuje prefiks (wielkość liter i wiodący ukośnik nie mają znaczenia), ale **każdy segment `.`/`..` jest odrzucany** — także zakodowany (wcześniejsze 20 wariantów c87). Wszystkie 200 zwracają **ten sam plik** z katalogu mediów, więc „elastyczny prefiks” nie poszerza dostępu. Klasa §8.15 pozostaje zamknięta.

## 3. DOMKNIĘTE: `116sos.pl`

| sonda | wynik | wniosek |
|---|---|---|
| `/api/fetch-cookie-hash` × 2 w jednym przebiegu | 200, 30 B, identyczne | wartość stała, nie pochodna sesji |
| `/api/fetch-cookie-hash` + `X-Forwarded-Host: arena-probe.example` | 200, 30 B, identyczne | brak wpływu nagłówka hosta (brak wektora cache poisoning na tym endpoincie) |
| `/api/centres-search?q=zzzzqqqxxx` | 200, 13 306 B | **`q` ignorowane** — zwraca całą bazę; potwierdza, że wcześniejsze „testy SQLi” na `q` mierzyły szum |
| `/api/centres-search?q=a&id=1` | 200, 13 306 B | parametr `id` ignorowany; brak endpointu szczegółowego tą drogą |

Hipoteza „`cookieHash` = dane sesji” (punkt 2 rankingu z raportu nocnego) — **usunięta z rankingu.**

## 4. DOMKNIĘTE: `pllum.org.pl` Nuxt Content

`/api/_content/query?_params={"where":[["_draft","=",true]]}` → **200, 2 B = `[]`**. Wersje robocze nie są wystawione. §8.3 (dane niepubliczne) — brak sygnału.

## 5. POTWIERDZONE POMIAREM: granice zakresu

| sonda | wynik |
|---|---|
| `nask.pl` `/` i `/api/search?query=raport&lang=pl` | **302, 0 B** — i **bez skoku** (`hop=0`) |

Narzędzie **odmówiło** podążenia za przekierowaniem, bo `Location` wskazuje `www.nask.pl`, czyli **inną nazwę hosta niż literał w §5**. To zachowanie jest celowe: lepiej stracić pomiar, niż przekroczyć zakres i narazić zgłoszenia na odrzucenie.

## 6. POTWIERDZONE: `dyzurnet.pl` nie ma API

`GET /api` → **404** + 38 981 B HTML (catch-all App Routera). Zgodne z pomiarem 5ed7.

---

## Co to zmienia w planie

- Z rankingu leadów **wypada** H10 (4 500–10 000 zł) i `cookieHash`.
- **Zostaje jedno** miejsce z potencjałem na kwotę wyższą niż 600–4 000 zł: `POST /api/sendForm` (klasa §8.5/§8.6) — wymaga zgody użytkownika, bo tworzy prawdziwe zgłoszenie u operatora rządowego.
- **Zostaje jedno pytanie do organizatora**, które odblokowuje trzy ścieżki naraz: zakres `www.nask.pl`, zakaz z regulaminu `moje.cert.pl`, konto testowe w HIVE.
