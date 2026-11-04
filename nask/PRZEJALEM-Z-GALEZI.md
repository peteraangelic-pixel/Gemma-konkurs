# Co przejąłem z równoległych gałęzi (przegląd 04.11)

Przegląd wszystkich wskazanych gałęzi: `Pokemon/arena/7911f950`, `Pokemon/arena/a450b00f`,
`Pokemon/arena/c87f7a48`, `Gemma-konkurs/arena/c4eeb067`, `NASK/codex/multi-program-lab`,
`Smak-Domu-Konkurs/arena/5ed750ef`. Poniżej **tylko to, co zmienia moją pracę** —
z podziałem na: fakty, których nie miałem; rzeczy, które potwierdzają moje wnioski;
i błędy, których dzięki nim uniknąłem.

## Łączny bilans wszystkich gałęzi — i to jest najważniejsza liczba

| gałąź | żądania | potwierdzone podatności |
|---|---:|---:|
| `Pokemon/7911f950` (Rust surface + 3 przebiegi) | 479 + 68 = ~550 | **0** |
| `Gemma-konkurs/c4eeb067` (naskhunt, 6 rund) | 165 | **0** |
| `NASK/codex` (night, `.git/HEAD` + `.env` na 24 hostach) | 75 | **0** |
| moja gałąź (3 przebiegi) | ~2 100 | **0** |
| **razem** | **~2 900 żądań** | **0** |

To jest najbardziej kosztowna informacja z całego przeglądu i trzeba ją powiedzieć wprost:
**cztery niezależne podejścia, 2 900 żądań, zero.** Publiczna powierzchnia NASK jest
utwardzona na wszystko, co da się sprawdzić bez konta. Dalsze skanowanie tej samej
powierzchni to strata nocy — niezależnie od tego, jak dobre będzie narzędzie.

## 1. Fakty, których nie miałem

### 1.1. `zglos-dezinformacje.nask.pl` zwraca **500** na każdą nieznaną ścieżkę
Nie 404 — stronę błędu Azure („ERROR 258337316"). Konsekwencja: **kod odpowiedzi nic
tu nie znaczy**, a mapa tej aplikacji musi być robiona inaczej niż statusami. Mój
przebieg pokazał tam tylko `robots.txt`, `sitemap.xml` i 403 na `/.env` — teraz wiem,
że to nie „mało powierzchni", a „źle mierzona powierzchnia".

### 1.2. Formularz zgłoszenia: dokładny kontrakt z bundle'a
`POST /api/sendForm`, `multipart/form-data`, pola: `accept` (wymagane), `email`,
`file` (klient przepuszcza `image/png`, `image/jpeg`, ≤ 20 MB), `reason` (≤ 250 znaków),
`urls` (**do 50 linków**), `g-recaptcha-response` (**reCAPTCHA v3, wymagana**).
**Konsekwencja:** tego formularza nie da się przetestować automatem — captcha jest
wykonywana w przeglądarce i brak tokenu kończy żądanie **przed** wysłaniem. Narzędzie
może przygotować payload, nie może go wysłać. To ostatecznie zamyka automatyczną drogę
do hipotezy SSRF w polu `urls`.

### 1.3. `hack.cert.pl` — mapa z bundla, której nie miałem
Trasy: `/users/{id}/view`, `/users/{id}/role`, `/users/{id}/email`, `/users/me/profile/payout`,
`/auth/session/activity`. To **najbardziej obiecujący cel w całym konkursie** (Tier 1,
sama platforma, widać dane wypłat) — i to jest zgodne z moim wnioskiem z przebiegu 2.
Różnica: tamta gałąź nie zdążyła tego sprawdzić. Ja mam już sondę S7 (2 identyfikatory,
bez iteracji).

### 1.4. HIVE (`dataannotation.pllum.org.pl`) = FastAPI, **rejestracja nie istnieje**
`/api/v1/projects/` i `/api/v1/users/` → **401 `Not authenticated`**; `/api/v1/users/1` → **405**
(trasa istnieje, ale nie dla GET). `/register` i `/api/v1/register` → 404.
**Konsekwencja, która zmienia plan:** mój plan zakładał „zarejestruj własne konto w HIVE".
**Tego nie da się zrobić bez zaproszenia.** Kontrola dostępu działa na poziomie routera,
więc IDOR wymaga konta, a konta nie ma jak zdobyć. HIVE wypada z planu do czasu, gdy
ktoś z NASK da konto testowe — a regulamin mówi wprost, że **nie dają**.

### 1.5. `science.nask.pl /api/downloadFile?fileId=<liczba>` — kontrakt potwierdzony, luka nie
`fileId=18864` → 200, `image/png`, 2 210 114 B, `Content-Disposition: attachment`.
Walidacja twarda: `-1`, `18864abc`, `fileId[]` → 400. Gęsty sweep 60 ID w okolicach
realnych → wszystkie trafienia to **publiczne zdjęcia z aktualności**, dostępne też przez
`/api/media/`. **Endpoint to nadmiarowość, nie luka** — bez ID pliku niepublicznego nie ma
zgłoszenia, a tego ID nie da się odgadnąć. Zamykam.

### 1.6. `moje.cert.pl` — publiczna mapa API + **konflikt regulaminów**
Nieoficjalna kolekcja `github.com/Ysiakowy/moje.cert.pl-API` (2025, 15 operacji: 9 GET,
2 POST, 1 PATCH, 1 PUT, 2 DELETE) grupuje je wokół użytkownika, **organizacji i domen**.
To dokładnie mapa pod IDOR/BAC na przypisaniu ról w organizacji.

**Ale:** regulamin samego `moje.cert.pl` (część IV pkt 4.2) zakazuje „działań mających na
celu testowanie możliwości przełamania lub ominięcia zabezpieczeń", podczas gdy program
bug bounty na ten host pozwala na testy z własnych kont. **Dokumenty sobie przeczą.**
→ **Nie testować `moje.cert.pl` uwierzytelnionym aż do pisemnego wyjaśnienia organizatora.**
Ryzyko: utrata nagrody za znalezisko z powołaniem na regulamin usługi. To jest jedyna
rzecz w tym przeglądzie, którą trzeba załatwić **przed** pracą, nie po.

### 1.7. `nask.pl /api/search` — WP CMS listujący treści
`?lang=pl` zwraca pełne obiekty WordPressa (autor, ID mediów, taksonomie), paginacja
73 stron. Refleksji parametru w HTML brak → brak XSS. **Uwaga formalna:** §5 wymienia
literał `nask.pl`; `www.nask.pl` to inna nazwa hosta. Przed jakimkolwiek zgłoszeniem
z tego hosta — potwierdzić interpretację z organizatorem.

### 1.8. WAF ucina payloady
`' OR 1=1`, `pg_sleep`, `../` w ścieżce → status 0 / reset połączenia. **Testy iniekcji
przez GET są tu praktycznie nieskuteczne.** Zostają żądania z ciałem i nagłówkami —
czyli znowu część zalogowana/forms.

## 2. Co potwierdza moje wnioski (i podnosi ich wagę)

- **Catch-all musi być odejmowany** — niezależnie doszły do tego trzy gałęzie (HIVE 200
  na wszystko, `zglos` 500 na wszystko). Moje `crawl.py` ma to od początku; ich raporty
  pokazują, ile kosztuje brak tej reguły (100 % fałszywych trafień).
- **Reguła „200 + JSON = kandydat" generuje szum** — jedna gałąź musiała ją usunąć
  w trakcie. U mnie to samo zjawisko w S6 (poprawione dziś po raz drugi).
- **Limit 5 req/s nie jest wąskim gardłem**; wąskim gardłem jest decyzja, co wysłać.
  Wszystkie gałęzie doszły do tego samego, każda własną drogą.
- **WAF blokuje ruch z runnerów GitHub Actions do rodziny `cert.pl`** (`hack.cert.pl`,
  `cert.pl`, `moje.cert.pl`, `incydent.cert.pl`, `mwdb.cert.pl`). U mnie `mwdb` i
  `hack.cert.pl` **odpowiedziały** w przebiegu 2, więc blokada jest co najmniej
  niestabilna — ale to argument, żeby najcenniejsze cele sprawdzać **z Twojej sieci**,
  nie z Actions.

## 3. Błędu, którego uniknąłem — i to jest konkret

Gałąź `7911f950` odkryła, że **nie mogła zmierzyć path traversal**, bo ich klient HTTP
(Rust/reqwest) normalizował `..` **przed wysłaniem**: żądanie na `/api/media/../../etc/passwd`
docierało jako `/etc/passwd`. Zmierzyłem to u siebie na lokalnym serwerze:

```
/api/media/../../etc/passwd            -> serwer zobaczyl: /api/media/../../etc/passwd
/api/media/..%2f..%2fetc/passwd        -> serwer zobaczyl: /api/media/..%2f..%2fetc/passwd
/a/./b//c                              -> serwer zobaczyl: /a/./b//c
```

**Mój klient (`urllib`) nie normalizuje** — `..` dociera dosłownie. To znaczy, że
ograniczenie z tamtej gałęzi mnie nie dotyczy i **nie powinienem kopiować ich wniosku
„traversal niemierzalny"**. Ale kopiuję coś cenniejszego: **nawyk weryfikowania, czy test
w ogóle dotarł tam, gdzie myślę.** To jest klasa błędu, która unieważnia całą noc pracy
i nie widać jej w wynikach — widać ją tylko wtedy, gdy się sprawdzi.

## 4. Co z tego wynika dla planu (korekta)

**Zamykam** (dowody w `HIPOTEZY-ZAMKNIETE.md`): path traversal w `download-file`
(20 wariantów), SSRF przez `_next/image` (7 hostów), CORS (8 endpointów + moje),
middleware bypass Next.js (4 hosty + moje), IDOR na `downloadFile`, XSS w `nask.pl/api/search`,
IDOR w HIVE bez konta, `.git/HEAD` + `.env` na 24 hostach.

**Zostają trzy realne drogi — wszystkie wymagają Ciebie, nie narzędzia:**

| # | droga | dlaczego warto | co blokuje |
|---|---|---|---|
| 1 | `hack.cert.pl` — `/users/{id}/view`, `/email`, `/role`, `/me/profile/payout` | Tier 1, sama platforma, widać dane wypłat; konkurencja patrzy na *programy*, nie na platformę | konto + 2 sesje w przeglądarce |
| 2 | `zglos-dezinformacje` — upload w formularzu (SVG z JS → stored XSS w panelu moderatora) | treść od niezaufanego użytkownika ogląda pracownik; klasa 7.3 + 8 | reCAPTCHA v3 = tylko przeglądarka |
| 3 | `mwdb.cert.pl` — XSS w atrybutach Rich, **jeśli wersja < 2.20.0** | mamy kod i znamy wektor; jedno żądanie rozstrzyga | `curl /api/server` |

**Wypada:** HIVE (brak rejestracji), `moje.cert.pl` (konflikt regulaminów do wyjaśnienia),
Władysławowo (decyzja użytkownika), wszystko bezstanowe (2 900 żądań, zero).

## 5. Jedno zdanie podsumowania

Równoważne gałęzie nie znalazły podatności, ale **zaoszczędziły mi dwie noce** — bo każda
z nich zamknęła inną klasę z dowodem, a ja nie muszę tych dróg przechodzić ponownie.
Najcenniejsze z całego przeglądu są dwie rzeczy: **kontrakt formularza `sendForm`
z reCAPTCHA v3** (który ostatecznie wycina automat z tej drogi) i **konflikt regulaminów
`moje.cert.pl`** (który trzeba wyjaśnić, zanim ktokolwiek tam kliknie w imieniu uczestnika).
