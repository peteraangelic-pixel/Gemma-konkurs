# Noc 03/04.11.2026 — co sprawdzono i co z tego wyszło

Ten plik jest zapisem uczciwym, nie marketingowym. Jeśli rano szukasz „co znaleźliśmy”,
odpowiedź brzmi: **nic pewnego**. Poniżej dokładnie dlaczego tak uważam i co to zmienia
w planie — bo fałszywe trafienie jest gorsze niż brak trafienia (kosztuje czas i wiarygodność).

## 1. Przebieg pierwszy: 706 żądań, 15 hostów, 52 „trafienia” — z czego ~50 fałszywych

| sonda | zgłoszone | prawdziwe | dlaczego fałszywe |
|---|---:|---:|---|
| S6 (X-Original-URL) | 36 | **0** | porównywała `/admin` (404) z `/` + nagłówek (200 = strona główna) |
| S2 (middleware Next.js) | 6 | **0** | WAF: 403 z treścią 374 B vs 377 B (identyfikator żądania w blokadzie) |
| S3 (/_next/data) | 8 | **0** | publiczne artykuły `116sos.pl` czytane przez JSON — dane i tak publiczne |
| S1 (CORS) | 4 | **0** | `ACAO: *` bez credentials — wprost wykluczone (§8 poz. 5.6) |

Dowód, że S6 kłamała: dla `dns.pl` „odblokowany /admin” zwracał **51 121 B**, a strona
główna ma **51 152 B**. To była po prostu strona główna, nie panel.

**Wniosek techniczny:** sonda bez grupy kontrolnej nie jest sondą, tylko generatorem pracy.
Testy jednostkowe tego nie wychwyciły, bo sprawdzały logikę, a nie jej odniesienie do
rzeczywistości. Poprawka: każda sonda porównuje **ten sam adres** z bodźcem i bez
(wcześniej porównywała dwa różne adresy), a różnice treści muszą przekraczać próg
ilościowy. Do repo doszły cztery testy regresyjne odtwarzające dokładnie te przypadki.

## 2. Co realnie wiemy o celach (dane, nie opinie)

| host | tech | co zaobserwowano | wartość dla nas |
|---|---|---|---|
| `hack.cert.pl` | SPA (Vite) | w bundlu trasy `/users/{id}/view`, `/users/{id}/email`, `/users/{id}/role`, `/users/me/profile/payout`, `/auth/session/activity` | **największa** — to sama platforma, Tier 1, i widać, że ma dane wypłat |
| `mwdb.cert.pl` | React + Flask | `/api/server` publiczny (wersja), `/api/docs` → 401 | wysoka — mamy kod tego serwera |
| `dns.pl` | Drupal | 404 o rozmiarze 40 921 B, sitemap, whois | średnia — JSON:API sprawdzone, brak |
| `116sos.pl` | Next.js | buildId `8CjJwbyxpVqpWnorny23T`, 20+ tras, `/api/fetch-cookie-hash` | średnia — dane o zdrowiu, Tier 2 |
| `science.nask.pl` | Next.js + WP | trasy doktoranckie, `/api` | niska |
| `zglos-dezinformacje.nask.pl` | Next.js | robots.txt, sitemap.xml, 403 na `/.env` i `/.git/config` (czyli WAF, nie wyciek) | średnia |
| `moje.cert.pl` | Django | `/jsi18n/`, `/static/CACHE/`, Cloudflare | średnia — panel użytkownika |
| `dataannotation.pllum.org.pl` | SPA 713 B | manifest, robots | średnia (wymaga konta) |
| `bezpiecznewybory.pl` | — | WAF 403 na wszystko | pomijamy |

## 3. Co z tego wynika dla kolejności pracy

1. **`hack.cert.pl` awansuje na pierwszy cel** — nie `mwdb`. Powód jest konkretny: bundel
   ujawnia trasy z identyfikatorami użytkownika i sekcję **payout** (dane wypłat).
   Jeśli którakolwiek z nich nie sprawdza uprawnień, to jest klasa 03/09 przy stawce
   Tier 1 = 9 000–20 000 zł. Do tego to platforma, na której wszyscy składają zgłoszenia,
   więc konkurencja patrzy na programy, nie na nią.
2. **`mwdb.cert.pl`: sprawdzić wersję, zanim cokolwiek innego.** Poprawka XSS w atrybutach
   Rich (#1272/#1274, wersja 2.20.0) jest w publicznym repo. Jeśli produkcja stoi niżej,
   to mamy **stored XSS w obiekcie udostępnianym grupie** — czyli nie self-XSS, a klasa 08
   z realnym wpływem na innych użytkowników. Sonda `S8` odpowiada na to jednym żądaniem.
3. **IDOR w `mwdb` schodzi na dalszy plan** — przegląd kodu (`PRZEGLAD-KODU-MWDB.md`)
   pokazał jedną wspólną, poprawną ścieżkę `access_object → Object.access`.
4. **`dataannotation` i `komunikator` bez konta = brak weryfikacji.** To jedyne dwa cele,
   gdzie bez zalogowania nie da się rozstrzygnąć niczego — potrzebny jest Twój własny
   profil (nie hasło: sesja w przeglądarce).

## 4. Czego świadomie NIE zrobiłem

- **nie zbierałem danych innych użytkowników** — sonda S7 odpytuje najwyżej identyfikatory
  `1` i `2`, bez iteracji; jeśli odpowiedź zawiera dane, kończy i raportuje fakt, nie treść,
- **nie testowałem obciążeniowo** niczego, żadnych logowań siłowych, żadnych POST-ów
  zmieniających stan (narzędzie w ogóle nie potrafi wysłać POST),
- **nie zgłosiłem niczego** — nie mam potwierdzenia, a zgłoszenie bez PoC psuje reputację
  na całą edycję (§8 poz. 14).

## 5. Stan na rano

- 100 testów offline zielonych, w tym 4 regresyjne z fałszywych trafień nocy.
- Przebieg 2 i 3 w Actions: naprawa fałszywych trafień + sonda S7 (autoryzacja API)
  + S8 (wersja aplikacji). Wyniki w `nask/findings/hunt.json`.
- **Następny krok należy do Ciebie:** rejestracja konta na `mwdb.cert.pl` i `hack.cert.pl`,
  jedno zdjęcie profilowe do testu uploadu awatara (`/users/me/profile/account/avatar`)
  i jedna próba: czy awatar przyjmuje SVG z `<script>`. To 15 minut, a rozstrzyga
  największy otwarty wątek.


---

# DOPISEK po przeglądzie gałęzi i przebiegu 4 (2026-11-04)

## Rozstrzygnięcie: `mwdb.cert.pl` stoi na **2.20.0**

Sonda S8 w przebiegu 4 odpowiedziała na pytanie, które planowałem zadać dopiero po
Twojej rejestracji konta:

```
GET https://mwdb.cert.pl/api/server  ->  "server_version": "2.20.0"
```

Poprawka XSS w atrybutach Rich (#1272/#1274) weszła **właśnie w 2.20.0**, więc jest
wdrożona. **Cały wątek zamknięty** — nie trzeba konta, nie trzeba testu w przeglądarce.
To jedna z trzech dróg wykreślona przez jedno żądanie.

## Przebieg 4 (816 żądań, 16 hostów): 13 trafień, **wszystkie „niskie"**

Po poprawce S6 (rozróżnia spadek i wzrost dostępu) wynik jest czysty: same wyniki
negatywne zapisane po to, żeby nie sprawdzać ich drugi raz — `x-original-url` dający
403 na `moje.cert.pl` i 429 na `incydent.cert.pl` to utwardzenie, a `ACAO: *` bez
credentials jest wprost wykluczone.

Zero trafień z S7 na `hack.cert.pl` **bez sesji** — API wymaga tokenu, co jest
zachowaniem poprawnym, ale zamyka wariant anonimowy. **Wariant z sesją pozostaje
najlepszą otwartą drogą.**

## Zostały dwie drogi (były trzy)

| # | droga | blokada | stawka |
|---|---|---|---|
| 1 | `hack.cert.pl` — `/users/{id}/view`, `/email`, `/role`, `/me/profile/payout`, awatar SVG | konto + dwie sesje w przeglądarce | 9 000–20 000 zł |
| 2 | `zglos-dezinformacje` — upload (SVG z JS → stored XSS w panelu moderatora) | reCAPTCHA v3 = tylko przeglądarka | 4 000–9 000 zł |

Obie wymagają Ciebie, nie narzędzia. Szczegóły i kryteria „tak/nie": `DO-ZROBIENIA-RANO.md`.

---

# Dopisek 3 (05.11) — cztery przebiegi, dwie nowe klasy, zero podatności

Szczegóły: [`WYNIKI-PRZEBIEGOW-5-8.md`](WYNIKI-PRZEBIEGOW-5-8.md).

- **Przebiegi 5–8: 1 921 żądań, 18 hostów, 0 potwierdzonych podatności.**
- **Zabity własny fałszywy alarm:** S3 zgłosiła 2× `wysoki` na `116sos.pl`, bo `404`
  liczyło się jako „strona wymaga logowania”. Poprawione w kodzie + 5 testów regresyjnych,
  w tym jeden stary **poprawiony**, bo utrwalał błąd.
- **Nowa sonda S10 (trucizna cache):** 8 nagłówków × para kontrolna. `pllum` i
  `bezpiecznymiesiac` (jedyne z `public, max-age=3600`) **nie odbijają żadnego**;
  `dns.pl` odbija, ale bez propagacji. Temat zamknięty z dowodem.
- **Nowa sonda S11 (dane osobowe w publicznym JSON):** publiczne trasy `hack.cert.pl`
  → 404 + powłoka SPA. Trzecia droga do portalu bez konta, domknięta.
- **`ctf.hack.cert.pl`:** w scope, ale 404 / brak vhosta — nie ma czego testować.
- **Chunki JS:** 47 pobranych; ścieżek API nie oddają (klient skleja prefiks szablonem),
  ale oddają **pola przyjmowane od klienta**: `role`, `email`, `status`, `message_id` —
  to lista do mass assignment z sesją.
- **133 testy offline**, wszystkie zielone.

**Następny krok nie jest mój:** [`RUNBOOK-HACKCERT.md`](RUNBOOK-HACKCERT.md) — 45 minut,
7 hipotez, tabela statusów do odesłania. To jedyny host, gdzie sesja jest darmowa i legalna.
