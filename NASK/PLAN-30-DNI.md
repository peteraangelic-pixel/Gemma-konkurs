# Plan 30 dni — 3–30.11.2026

Budżet: **2 h dziennie** (60 h) + 8 h w weekendy (≈ **100 h** łącznie). Plan jest ułożony tak,
żeby przy 40 h też coś dał (dni 1–2 i 2–6 są najważniejsze).

## §0. Cztery zasady, których złamanie kosztuje wszystko

| zasada | konsekwencja złamania |
|---|---|
| **Tylko hosty z §5 programu** (lista 12 domen, bez wildcardu) | test poza zakresem = problem prawny, nie „brak nagrody” |
| **≤ 5 żądań/s** narzędziami automatycznymi | naruszenie regulaminu; testy obciążeniowe = **dyskwalifikacja** |
| **Tylko własne konta**, dane syntetyczne | przetwarzanie danych osób trzecich jest zakazane |
| **PoC + odtwarzalność** w każdym zgłoszeniu | zgłoszenie odrzucone; 3 pod rząd mogą zablokować zgłaszanie |

Dodatkowo: **poufność** do czasu poprawki i **własna tożsamość** przy rejestracji (Login.gov.pl).

## §1. Podział pracy (to jest najważniejsze zdanie w całym planie)

| ja (agent) | Ty (człowiek) |
|---|---|
| lista kontrolna testów, payloady, analiza zrzutów HAR, klastrowanie odpowiedzi, pisanie raportów, weryfikacja „czy to na pewno w zakresie” | logowanie, klikanie, rejestracja **własnych** kont, eksport HAR, wysyłka zgłoszenia |
| offline: analiza JS bundle'i, ekstrakcja endpointów, szukanie tokenów | decyzja „to wygląda źle” w przeglądarce |
| pilnowanie, żeby raport nie był odrzucalny (wyłączenia §8) | tempo: 1 aplikacja naraz |

Nie mogę się zalogować. **Bez Twoich zrzutów HAR jestem ślepy** — to nie jest uprzejmość, to
ograniczenie techniczne.

## §2. Jak zbierać materiał (5 minut, powtarzalne)

1. Otwórz DevTools → Network → zaznacz **Preserve log** + **Disable cache**.
2. Zaloguj się **kontem A**, przejdź wszystkie funkcje aplikacji (kliknij wszystko po kolei).
3. Prawy klik → **Save all as HAR with content** → `private/har/{app}-A-{data}.har`.
4. Wyloguj, zaloguj **kontem B**, powtórz to samo → `…-B-…har`.
5. Uruchom: `nasktriage scan private/har/hive-A.har private/har/hive-B.har --account A:sessionid=… --account B:sessionid=…`
6. Dostajesz tabelę: **ten sam endpoint, dwa konta, różne odpowiedzi** — to jest lista hipotez.

`private/` jest w `.gitignore`. **Nigdy nie commituj HAR-ów** (zawierają Twoje tokeny sesji).

## §3. Kalendarz

### Dzień 1 (3.11) — fundamenty, 2 h
- [ ] konto na hack.cert.pl, akceptacja regulaminu platformy **i** programu NASK
- [ ] przeczytanie §5 (zakres) i §8 (wyłączenia) w PDF — **nie skrótu**
- [ ] tanie testy „z głowy”: CVE-2025-29927 na 5 serwisach Next.js (5 min), refleksja XSS
      w wyszukiwarkach (20 min), dangling CNAME na 12 hostach (30 min)
- [ ] rejestracja własnych kont: HIVE (`dataannotation.pllum.org.pl`), `zglos-dezinformacje.nask.pl`

### Dni 2–6 — IDOR na HIVE (10 h)
- [ ] mapa funkcji: co tworzy obiekt, jaki ma identyfikator, jaka jest rola
- [ ] zrzuty HAR z dwóch kont po **identycznej** ścieżce klików
- [ ] `nasktriage scan` → lista endpointów z asymetrią
- [ ] ręczne potwierdzenie każdej hipotezy (podmiana ID z sesji B na zasób A)
- [ ] **pierwsze zgłoszenie w ciągu 48 h od potwierdzenia**

**Bramka #1 (koniec dnia 6):** mamy co najmniej jedną potwierdzoną różnicę? Jeśli **nie** →
przechodzimy do `zglos-dezinformacje` (upload/SSRF), nie dokładamy narzędzi.

### Dni 7–10 — upload + SSRF na `zglos-dezinformacje` (8 h)
- [ ] ścieżka zgłoszenia z załącznikiem; gdzie plik ląduje, jak jest serwowany, jaki `Content-Type`
- [ ] SVG/HTML z aktywną treścią; podwójne rozszerzenie; ZIP
- [ ] pole linku → czy serwer pobiera? (cel: własny webhook, potem test na `169.254.169.254`)

### Dni 11–14 — mass assignment i kontrola ról (8 h)
- [ ] rejestracja/profil: dopisane pola (`role`, `approved`, `email_verified`…)
- [ ] endpointy `/api/*` bez sprawdzania roli (porównanie UI vs API)

### Dni 15–22 — drugi program: CERT Polska Tier 1 (16 h)
- [ ] `hack.cert.pl` — **nowa platforma, w scope**, aplikacja z kontami, zgłoszeniami i płatnościami
- [ ] ten sam cykl: mapa → dwa konta → HAR → diff
- [ ] uwaga na niejednoznaczność `ctf.hack.cert.pl` (karta vs PDF) — **nie testować**, dopóki
      organizator nie potwierdzi

### Dni 23–30 — to, co zostało + dyscyplina raportów (16 h)
- [ ] cache deception / smuggling tylko tam, gdzie jest przesłanka (Envoy/Azure przed aplikacją)
- [ ] porządkowanie zgłoszeń: status, odpowiedź komisji, poprawki
- [ ] **nie** wysyłać niczego „na wszelki wypadek” — 3 odrzucone pod rząd blokują zgłaszanie

## §4. Bramki decyzyjne (twarde)

| kiedy | warunek | decyzja |
|---|---|---|
| koniec dnia 2 | 0 potwierdzonych obserwacji | zmiana aplikacji (nie: więcej narzędzi) |
| koniec dnia 6 | brak IDOR-a na HIVE | przejście na `zglos-dezinformacje` |
| dzień 14 | 0 zgłoszeń wysłanych | przegląd: czy hipotezy są falsyfikowalne? |
| dzień 21 | 0 potwierdzonych zgłoszeń | zmiana programu na CERT Polska / gov.pl |
| każdy dzień | znalezisko „ciekawe, ale bez wpływu” | **nie wysyłać** — to generuje odrzucenia |

## §5. Definicja „gotowe do wysłania”

Zgłoszenie idzie dopiero, gdy mam wszystkie sześć:

1. dokładny URL + metoda + pełne żądanie (nagłówki, bez Twoich tokenów w treści raportu),
2. dwa konta / dwie role i **dowód, że dane nie są Twoje** (syntetyczne),
3. krok po kroku odtwarzalne, zrzut ekranu + treść odpowiedzi,
4. **wpływ** jednym zdaniem („odczyt cudzych zgłoszeń”, „przejęcie sesji moderatora”),
5. sprawdzenie, że klasa **nie jest** w wyłączeniach §8,
6. propozycja poprawki (jedno zdanie) — podnosi szansę na wyższą kwalifikację.

Szablon: `../drive_materials/10-ZALACZNIK-report-szablon.md` (z repo NASK) — używać, nie wymyślać
nowego za każdym razem.
