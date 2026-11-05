# Runbook: `hack.cert.pl` — 45 minut w Twojej przeglądarce

Jedyny host w konkursie, gdzie **sesja jest legalna, darmowa i nie ma konfliktu regulaminowego**
(karta programu pozwala na własne konto; to portal, który sam rozdaje konta).

Cel: sprawdzić 7 hipotez IDOR/BAC. Każda ma **warunek odrzucenia** — jeśli odpowiedź jest 403/404,
hipoteza jest zamknięta i nie wracamy. Jeśli jest 200 z cudzymi danymi — **stop, jedno żądanie
potwierdzające, zrzut ekranu, koniec**. Nie zbieramy danych.

Zasady, których nie łamiemy: własne konto, własne zasoby, `id±1` **od własnego** ID,
max ~1 żądanie/s, zero zmian w cudzych zasobach (żadnych `PATCH` na cudzym), dyskrecja.

---

## 0. Przygotowanie (5 minut, jednorazowo)

1. Rejestracja: <https://hack.cert.pl> — zwykłe konto, Twój e-mail.
2. Uzupełnij profil (imię/nazwisko może być prawdziwe — to Twój profil, nie dane testowe).
3. Otwórz DevTools → **Network** → zaznacz „Preserve log”.
4. Zaloguj się i przejdź do **swoich zgłoszeń**. Zrób jedno zgłoszenie **w wersji roboczej
   (draft, niewysłane)** — potrzebuję jego ID.
5. Zapisz dwie rzeczy (wklej mi w czacie, bez hasła i bez tokenu):
   - **format ID zgłoszenia** (liczba, np. `1421`, czy UUID, np. `7f3c…`),
   - **format ID użytkownika** (z `/users/<id>/view` na własnym profilu).

To rozstrzyga wszystko dalej: jeśli ID jest **liczbowe**, `id±1` jest sensownym testem.
Jeśli **UUID**, enumeracja to szum i H1–H3 testujemy tylko wtedy, gdy ID pojawi się
w cudzym kontekście publicznym (np. ranking, publiczny profil).

---

## 1. H1 — cudze zgłoszenie przez widok programu (5 minut)

W konsoli DevTools (zakładka **Console**), na `https://hack.cert.pl`:

```js
// 1. własne zgłoszenie — kontrola
await fetch('/api/v1/me/reports/' + OWN_REPORT_ID, {credentials:'include'})
  .then(r => r.status + ' ' + r.headers.get('content-type'))
```

```js
// 2. ten sam zasób w widoku PROGRAMU (staff) — czy odda coś uczestnikowi?
await fetch('/api/v1/reports/' + OWN_REPORT_ID, {credentials:'include'})
  .then(r => r.status)
```

Kryteria:

| wynik | znaczenie | co dalej |
|---|---|---|
| `200` na `me/reports`, `403/404` na `reports/{id}` | rozdzielenie widoków działa | **H1 zamknięte** |
| `200` na obu | uczestnik widzi widok staffa | sprawdź §1a (jedno żądanie na `id±1`) |
| `401` na obu | brak sesji/cookie | powtórz po zalogowaniu |

### 1a. Tylko jeśli `200` na `reports/{id}`

**Jedno** żądanie na sąsiedni identyfikator — i tylko jeśli ID jest liczbowe:

```js
await fetch('/api/v1/reports/' + (OWN_REPORT_ID - 1), {credentials:'include'})
  .then(r => r.status + ' ' + (r.headers.get('content-type')||''))
```

- `403/404` → **zamknięte**, nie sprawdzaj `-2`, `-3`. To nie „trzeba więcej prób”,
  a „kontrola właściciela działa”.
- `200` + JSON → **trafienie**. Zrób zrzut ekranu (bez danych osobowych!), zapisz status
  i to, że w odpowiedzi są cudze dane. **Nie czytaj dalej, nie kopiuj treści.**

## 2. H2 — cudzy załącznik (3 minuty, tylko po `200` z §1a)

Ścieżka: `/api/v1/reports/{id}/attachments/{aid}/download`, gdzie `aid` bierze się
z JSON-a cudzego zgłoszenia z §1a (pierwsze `id` na liście).

To samo kryterium: `403/404` = zamknięte; pobranie pliku = trafienie klasy 03
(cudze prywatne treści), stawka wysoka.

## 3. H3 — notatki wewnętrzne CERT (2 minuty, ta sama bramka)

```
GET /api/v1/reports/{id}/internal-notes
```

To najwyższa waga w portalu (wewnętrzne notatki analityków). `403/404` = dobrze.
Nie próbuj `nid` z §1a — wystarczy sam fakt, że lista notatek wyszła.

## 4. H4 — logika nagród na WŁASNYM zgłoszeniu (5 minut)

Tylko własne dane:

```js
await fetch('/api/v1/me/reports/' + OWN_REPORT_ID + '/reward-offers/latest', {credentials:'include'})
  .then(r => r.status)
```

- Brak oferty (bo zgłoszenie jest draftem) → **hipoteza niemierzalna teraz**, pomiń.
- Jest oferta → sprawdź, czy `accept` przyjmuje się dwukrotnie (drugi `accept` powinien dać
  409/400, nie 200). Podwójne przyjęcie = błąd logiki stanów (niska/średnia klasa).

## 5. H5 — eskalacja pionowa na własnym koncie (5 minut)

```js
// czy serwer przyjmuje zmianę roli na MOIM koncie?
await fetch('/api/v1/users/' + OWN_USER_ID + '/role', {
  method:'PATCH', credentials:'include',
  headers:{'content-type':'application/json'},
  body: JSON.stringify({role:'ADMIN'})
}).then(r => r.status)
```

- `403/405/400` → **zamknięte** (dobrze).
- `200` → sprawdź `GET /api/v1/auth/me` i zobacz, czy rola naprawdę się zmieniła.
  Jeśli tak: **to jest trafienie** (mass assignment / eskalacja), ale **natychmiast
  zgłoś mi to i nie rób z tym nic więcej** — nie wchodź w panel staffa.

To samo dla `member-program` (`memberships/{mid}/role`) — tylko własne członkostwo.

## 6. H6 — historia zdarzeń cudzego zgłoszenia (2 minuty)

`GET /api/v1/reports/{id}/events` — ten sam schemat co H1. Wystarczy status.

## 7. H7 — `creation-eligibility` i `rejected-reports` (2 minuty)

```
GET /api/v1/me/reports/creation-eligibility
GET /api/v1/me/reports/rejected-reports
```

Szukamy nie tego, czy działają (działają), a tego, czy w odpowiedzi są **dane innych osób**
(np. powód odrzucenia z cudzym e-mailem, limit „innego użytkownika”). `200` z pustą listą =
zamknięte.

---

## Co mi odesłać (i czego nie wysyłać)

Odeślij **tabelkę statusów** — wystarczy:

```
H1 me/reports/{id}: 200      H1 reports/{id}: 403
H1a reports/{id-1}: 403
H2 załącznik: 404
H3 internal-notes: 403
H5 users/{me}/role PATCH: 403
format report id: liczba / UUID
```

**Nie wysyłaj:** haseł, ciasteczek, tokenów, treści cudzych danych, zrzutów z danymi osobowymi.
Jeśli `status ≠ 403/404` — napisz tylko „jest 200, w odpowiedzi widać cudze pole X”.

## Co się dzieje po Twojej tabelce

- **Wszystko 403/404** → portal zamknięty, wracamy do `zglos-deinformacje` (upload/SSRF,
  wymaga Twojego GO) i do mSzyfr (2 konta).
- **Cokolwiek 200 z cudzymi danymi** → przygotowuję zgłoszenie w ciągu godziny, ze
  szablonem `SZABLON-ZGLOSZENIA.md`, Ty wysyłasz przez formularz pod swoim kontem.
  Pierwszeństwo ma ten, kto zgłosi pierwszy — dlatego liczy się tempo, nie liczba prób.
