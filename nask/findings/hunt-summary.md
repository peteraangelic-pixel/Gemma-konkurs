# Nocne polowanie — wyniki

Wygenerowano: `2026-11-05T13:47:59+00:00`, żądań: **880**, hostów: **17**

> Trafienie sondy ≠ podatność. Każde wymaga ręcznego potwierdzenia w przeglądarce
> i sprawdzenia, czy nie wpada w wykluczenia §8. Kolumna „dlaczego nie wykluczone”
> jest tam po to, żeby tę weryfikację dało się zrobić w minutę.

## Trafienia wysokie/krytyczne: 2

### `S3` [wysoki] Dane chronionej strony Next.js czytane bez sesji przez /_next/data
- host: `116sos.pl`
- URL: `https://116sos.pl/_next/data/irh57X00spepTJQOOO68A/index.json`
- dowód: HTML `/index` → 404 (wymaga logowania), a JSON → 200 (8256 B); pageProps: appPageUrl, articles, chips, consultantQuotes, content, ogDescription, ogImageId, ogTitle, searchRanges, seodescription; podgląd: {"chips": [{"chipContent": "Wsparcie dla osób dorosłych", "tooltipContent": "Wspieramy osoby szukające pomocy dla siebie lub kogoś bliskiego.", "order": 1}, {"chipContent": "24/7",
- dlaczego nie wykluczone: §8 poz. 12.2 / 9.3 — dane niepubliczne przez nieudokumentowany endpoint, z pominięciem sprawdzenia w warstwie HTML. To realne ryzyko tylko wtedy, gdy pageProps nie są publiczne — trzeba przeczytać podgląd.
- surowe: `{"route": "/index", "html_status": 404}`

### `S3` [wysoki] Dane chronionej strony Next.js czytane bez sesji przez /_next/data
- host: `116sos.pl`
- URL: `https://116sos.pl/_next/data/irh57X00spepTJQOOO68A/index.json`
- dowód: HTML `/index/` → 404 (wymaga logowania), a JSON → 200 (8256 B); pageProps: appPageUrl, articles, chips, consultantQuotes, content, ogDescription, ogImageId, ogTitle, searchRanges, seodescription; podgląd: {"chips": [{"chipContent": "Wsparcie dla osób dorosłych", "tooltipContent": "Wspieramy osoby szukające pomocy dla siebie lub kogoś bliskiego.", "order": 1}, {"chipContent": "24/7",
- dlaczego nie wykluczone: §8 poz. 12.2 / 9.3 — dane niepubliczne przez nieudokumentowany endpoint, z pominięciem sprawdzenia w warstwie HTML. To realne ryzyko tylko wtedy, gdy pageProps nie są publiczne — trzeba przeczytać podgląd.
- surowe: `{"route": "/index/", "html_status": 404}`


## Trafienia średnie/niskie (do wglądu, nie do zgłoszenia w tej formie)

- `S8` **niski** `https://mwdb.cert.pl/api/server` — Wersja aplikacji: 2.20.0  
  `/api/server` → 2.20.0; poprawka 2.20.0 jest wdrożona, temat XSS w Rich zamknięty.
- `S6` **niski** `https://moje.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/panel` → 404. `GET /` bez nagłówka: 200, 31217 B. `GET /` z x-original-url: /panel → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://moje.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/admin` → 403. `GET /` bez nagłówka: 200, 31217 B. `GET /` z x-original-url: /admin → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://moje.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/dashboard` → 404. `GET /` bez nagłówka: 200, 31217 B. `GET /` z x-original-url: /dashboard → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://moje.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/profil` → 404. `GET /` bez nagłówka: 200, 31217 B. `GET /` z x-original-url: /profil → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://moje.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/konto` → 404. `GET /` bez nagłówka: 200, 31217 B. `GET /` z x-original-url: /konto → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://moje.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/moje` → 404. `GET /` bez nagłówka: 200, 31217 B. `GET /` z x-original-url: /moje → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S1` **niski** `https://incydent.cert.pl` — CORS: ACAO=* (bez credentials)  
  Origin: https://evil.example → ACAO: *.
- `S1` **niski** `https://incydent.cert.pl` — CORS: ACAO=* (bez credentials)  
  Origin: https://nask.pl.evil.example → ACAO: *.
- `S6` **niski** `https://incydent.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/konto` → 404. `GET /` bez nagłówka: 200, 2743 B. `GET /` z x-original-url: /konto → 429, 5635 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://incydent.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/moje` → 404. `GET /` bez nagłówka: 200, 2743 B. `GET /` z x-original-url: /moje → 429, 5635 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S1` **niski** `https://www.gov.pl` — CORS: ACAO=* (bez credentials)  
  Origin: https://evil.example → ACAO: *.
- `S1` **niski** `https://www.gov.pl` — CORS: ACAO=* (bez credentials)  
  Origin: https://nask.pl.evil.example → ACAO: *.
- `S6` **niski** `https://ctf.hack.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/panel` → 404. `GET /` bez nagłówka: 200, 5853 B. `GET /` z x-original-url: /panel → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://ctf.hack.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/admin` → 404. `GET /` bez nagłówka: 200, 5853 B. `GET /` z x-original-url: /admin → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://ctf.hack.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/dashboard` → 404. `GET /` bez nagłówka: 200, 5853 B. `GET /` z x-original-url: /dashboard → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://ctf.hack.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/profil` → 404. `GET /` bez nagłówka: 200, 5853 B. `GET /` z x-original-url: /profil → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://ctf.hack.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/konto` → 404. `GET /` bez nagłówka: 200, 5853 B. `GET /` z x-original-url: /konto → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.
- `S6` **niski** `https://ctf.hack.cert.pl` — Nagłówek x-original-url jest blokowany przez serwer (bez obejścia)  
  `/moje` → 404. `GET /` bez nagłówka: 200, 5853 B. `GET /` z x-original-url: /moje → 403, 4542 B — dostęp **spadł**, czyli WAF/proxy odrzuca żądanie z tym nagłówkiem.

## Powierzchnia per host

| host | tech | kandydaci | endpointy JS | trasy Next |
|---|---|---:|---:|---:|
| `https://dns.pl` | — | 7 | 0 | 0 |
| `https://dyzurnet.pl` | react | 5 | 0 | 0 |
| `https://zglos-dezinformacje.nask.pl` | react | 4 | 0 | 0 |
| `https://mwdb.cert.pl` | react | 3 | 0 | 0 |
| `https://moje.cert.pl` | — | 3 | 0 | 0 |
| `https://116sos.pl` | next.js, react | 3 | 3 | 12 |
| `https://hack.cert.pl` | — | 2 | 21 | 0 |
| `https://nask.pl` | next.js, react | 2 | 0 | 4 |
| `https://oad.nask.pl` | react | 2 | 0 | 0 |
| `https://dataannotation.pllum.org.pl` | — | 2 | 0 | 0 |
| `https://ctf.hack.cert.pl` | — | 2 | 0 | 0 |
| `https://n6portal.cert.pl` | react | 1 | 4 | 0 |
| `https://incydent.cert.pl` | — | 1 | 1 | 0 |
| `https://science.nask.pl` | next.js, react | 1 | 3 | 30 |
| `https://www.gov.pl` | — | 1 | 0 | 0 |
| `https://komunikator.narodowy.gov.pl` | — | 0 | 0 | 0 |
| `https://bezpiecznewybory.pl` | — | 0 | 0 | 0 |
