# Szablon zgłoszenia + filtr „czy to w ogóle płaci"

Dwa narzędzia w jednym pliku:

1. **Filtr przed pisaniem** — 30 sekund, żeby nie pisać raportu za 0 zł.
2. **Szablon zgłoszenia** — wypełniany dopiero, gdy filtr przepuścił.

Źródło klas i wyłączeń: wyciąg z regulaminu edycji 03–30.11.2026 (`hack.cert.pl`), w tym
wyciąg z Dysku `05-REGULAMIN-wyciag.md` i `10-ZALACZNIK-report-szablon.md`.
**Numeracja poz. §8 pochodzi z odczytu innych sesji — przed wysłaniem sprawdź numer
w aktualnym regulaminie.** Klasy i zasady są pewne, numeracja nie.

---

## Część A — filtr przed pisaniem (obowiązkowy)

### A1. Cztery pytania, na które musi być „tak”

| # | Pytanie | Jeśli „nie” |
|---|---|---|
| 1 | Czy mam **odtwarzalny PoC** — kroki, które powtórzy ktoś inny? | nie piszemy, wracamy do pomiaru |
| 2 | Czy **wpływ** jest nazwany (cudze dane / przejęcie konta / wykonanie kodu / zmiana stanu)? | nie piszemy |
| 3 | Czy to **nie jest** żadna pozycja z listy A2? | nie piszemy — §8 |
| 4 | Czy testowałem **własne** konta i **własne** dane, w zakresie z §5? | zgłoszenie może zostać odrzucone, a ja łamię zasady |

### A2. Czego NIE zgłaszamy (nie płaci — §8)

| co widać bez logowania | dlaczego nie płaci |
|---|---|
| brak `X-Frame-Options`, brak CSP / `frame-ancestors`, flagi cookies, HSTS, captcha | pozycje 3.1–3.4 — konfiguracja, nie podatność |
| stack trace, wersje oprogramowania, listing katalogów, user enumeration | 2.1–2.2 |
| nieaktualne biblioteki i znane CVE **bez własnego PoC** | 3.9–3.10 |
| otwarty port bez wykazanego wpływu | 3.8 |
| blind SSRF z samym DNS (bez odczytu) | 7 |
| open redirect bez łańcucha (OAuth, kradzież tokenu) | 8 |
| brak rate limitingu **bez scenariusza przejęcia konta** | 10.3 |
| klucz API bez możliwości nadużycia | 12.1 |
| `ACAO: *` **bez** credentials / bez odbicia `Origin` | 5.6 |
| metadane w publicznym API (autor, ID mediów w CMS) | 2.3 |
| **raport ze skanera bez ręcznego potwierdzenia** | 14.4 |
| DoS, load testing, spam, brak rate-limitu jako taki | dyskwalifikacja |
| self-XSS, clickjacking, „goły” open redirect, porównywarka wersji | wykluczone |

### A3. Co PŁACI (kolejność wg wartości)

IDOR/BAC na cudzych zasobach • mass assignment (rola, właściciel, uprawnienia) • przejęcie
konta • SSRF **z odczytem** • upload → RCE / stored XSS w panelu obsługi • SQLi • eksport
danych osobowych • logika stanów (np. podwójne `accept` nagrody).

### A4. Zasady testu (bez wyjątków)

- max **5 req/s**, u mnie realnie 1–1,5;
- **tylko własne konta**, własne dane, własne zasoby; `id±5` **od własnego** ID, nigdy sweep;
- **jedno żądanie potwierdzające + powtórka** — wystarczy; dalej to już zrzut danych;
- zero DoS, zero load testów, zero spamu, zero SE;
- dane osobowe osób trzecich → **stop natychmiast**, nie zapisuję, zgłaszam fakt dostępu;
- dyskrecja do wdrożenia poprawki; publikacja dopiero po zgodzie programu;
- zgłoszenie **tylko** przez formularz `hack.cert.pl`, pod własnym kontem.

---

## Część B — szablon zgłoszenia

### 1. Program
`NASK (nask-pib)` / `CERT Polska (cert-polska)` / `Portal Gov.pl` / `mSzyfr` / ~~Władysławowo~~
(wybór jednego; **`hack.cert.pl` = CERT Polska Tier 1, `ctf.hack.cert.pl` = CERT Tier 2**)

### 2. Tytuł
`<klasa> w <endpoint> umożliwia <wpływ> w <host>`
Przykład: `IDOR w GET /api/v1/reports/{id} umożliwia odczyt cudzych zgłoszeń w hack.cert.pl`

### 3. Opis
Co jest źle, gdzie, i co to daje. Dwa–cztery zdania. Bez historii dochodzenia.

### 4. Klasa (z tabeli konkursu)
01 RCE · 02 przejęcie konta · 03 dane wrażliwe · 04 SQLi · 05 SSRF · 06 SSTI · 07 file upload ·
08 XSS · 09 autoryzacja/IDOR · 10 eskalacja uprawnień · 11 sesja/uwierzytelnianie · 12 API ·
13 mass assignment · 14 CORS · 15 path traversal/LFI/RFI · 16 CSRF · 17 open redirect ·
18 cache poisoning · 19 request smuggling · 20 XXE

### 5. Krytyczność (szacunek)
- niski 600–4 000 zł · średni 4 000–9 000 · wysoki 9 000–20 000 · krytyczny 20 000
(Tier 2 = połowa stawek)

### 6. PoC krok po kroku (obowiązkowe)
```
1. Wejdź na https://<host>/
2. Załóż dwa własne konta testowe: A i B
3. Jako A utwórz <zasób>, zapisz ID (np. <id>)
4. Jako B wyślij: GET /api/.../<id>
5. Odpowiedź zawiera <dane A> — B nie powinien ich widzieć
```

### 7. Surowe żądania
```http
GET /api/.../<id> HTTP/1.1
Host: <host>
Authorization: Bearer <token_konta_B>
Cookie: session=<sesja_B>
```
**Tokeny i ciasteczka w zgłoszeniu: tylko własne, testowe, i tak wygaszone po teście.**

### 8. Wpływ
Jakie dane, ile, czyje; czy da się zmienić stan; czy prowadzi dalej (łańcuch).
Liczba, nie przymiotnik: „odczyt 1 rekordu zawierającego imię, e-mail, numer sprawy”.

### 9. Sugestia naprawy
Jedno–dwa zdania, konkretnie (sprawdzenie właściciela zasobu w endpointcie, whitelist pól,
walidacja typu pliku po stronie serwera).

### 10. Oświadczenie
Testy wyłącznie w zakresie programu · brak DoS · dyskrecja do poprawki · PoC prawdziwe
i odtwarzalne · brak danych osób trzecich.

### Czego NIE dołączam
Danych osobowych innych użytkowników · poświadczeń kont pracowników · zrzutów bazowych ·
materiałów naruszających poufność · skanów z narzędzi bez ręcznego potwierdzenia.

---

## Część C — rejestr (wypełniany po wysłaniu)

| data | program | host | klasa | tytuł | status | nagroda |
|---|---|---|---|---|---|---|
| — | — | — | — | **nic nie wysłano** | — | — |

Pierwszeństwo ma **pierwsze** zgłoszenie tej samej luki. Dlatego: potwierdzenie → draft →
wysyłka **tego samego dnia**.
