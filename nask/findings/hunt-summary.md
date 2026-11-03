# Nocne polowanie — wyniki

Wygenerowano: `2026-11-03T23:28:41+00:00`, żądań: **703**, hostów: **15**

> Trafienie sondy ≠ podatność. Każde wymaga ręcznego potwierdzenia w przeglądarce
> i sprawdzenia, czy nie wpada w wykluczenia §8. Kolumna „dlaczego nie wykluczone”
> jest tam po to, żeby tę weryfikację dało się zrobić w minutę.

## Trafienia wysokie/krytyczne: 0

_Brak. To też jest wynik: te sześć błędów sprawdzono i ich nie ma._

## Trafienia średnie/niskie (do wglądu, nie do zgłoszenia w tej formie)

- `S6` **sredni** `https://moje.cert.pl` — Nagłówek x-original-url zmienia odpowiedź tego samego adresu  
  `/panel` → 404. `GET /` bez nagłówka: 200, 31158 B. `GET /` z x-original-url: /panel → 403, 4542 B.
- `S6` **sredni** `https://moje.cert.pl` — Nagłówek x-original-url zmienia odpowiedź tego samego adresu  
  `/admin` → 403. `GET /` bez nagłówka: 200, 31158 B. `GET /` z x-original-url: /admin → 403, 4542 B.
- `S6` **sredni** `https://moje.cert.pl` — Nagłówek x-original-url zmienia odpowiedź tego samego adresu  
  `/dashboard` → 404. `GET /` bez nagłówka: 200, 31158 B. `GET /` z x-original-url: /dashboard → 403, 4542 B.
- `S6` **sredni** `https://moje.cert.pl` — Nagłówek x-original-url zmienia odpowiedź tego samego adresu  
  `/profil` → 404. `GET /` bez nagłówka: 200, 31158 B. `GET /` z x-original-url: /profil → 403, 4542 B.
- `S6` **sredni** `https://moje.cert.pl` — Nagłówek x-original-url zmienia odpowiedź tego samego adresu  
  `/konto` → 404. `GET /` bez nagłówka: 200, 31158 B. `GET /` z x-original-url: /konto → 403, 4542 B.
- `S6` **sredni** `https://moje.cert.pl` — Nagłówek x-original-url zmienia odpowiedź tego samego adresu  
  `/moje` → 404. `GET /` bez nagłówka: 200, 31158 B. `GET /` z x-original-url: /moje → 403, 4542 B.
- `S6` **sredni** `https://incydent.cert.pl` — Nagłówek x-forwarded-prefix zmienia odpowiedź tego samego adresu  
  `/konto` → 404. `GET /` bez nagłówka: 200, 2743 B. `GET /` z x-forwarded-prefix: /konto → 429, 5635 B.
- `S6` **sredni** `https://incydent.cert.pl` — Nagłówek x-original-url zmienia odpowiedź tego samego adresu  
  `/moje` → 404. `GET /` bez nagłówka: 200, 2743 B. `GET /` z x-original-url: /moje → 429, 5635 B.
- `S1` **niski** `https://incydent.cert.pl` — CORS: ACAO=* (bez credentials)  
  Origin: https://evil.example → ACAO: *.
- `S1` **niski** `https://incydent.cert.pl` — CORS: ACAO=* (bez credentials)  
  Origin: https://nask.pl.evil.example → ACAO: *.
- `S1` **niski** `https://www.gov.pl` — CORS: ACAO=* (bez credentials)  
  Origin: https://evil.example → ACAO: *.
- `S1` **niski** `https://www.gov.pl` — CORS: ACAO=* (bez credentials)  
  Origin: https://nask.pl.evil.example → ACAO: *.

## Powierzchnia per host

| host | tech | kandydaci | endpointy JS | trasy Next |
|---|---|---:|---:|---:|
| `https://dns.pl` | — | 7 | 0 | 0 |
| `https://dyzurnet.pl` | react | 5 | 0 | 0 |
| `https://zglos-dezinformacje.nask.pl` | react | 4 | 0 | 0 |
| `https://mwdb.cert.pl` | react | 3 | 0 | 0 |
| `https://moje.cert.pl` | — | 3 | 0 | 0 |
| `https://hack.cert.pl` | — | 2 | 21 | 0 |
| `https://oad.nask.pl` | react | 2 | 0 | 0 |
| `https://dataannotation.pllum.org.pl` | — | 2 | 0 | 0 |
| `https://n6portal.cert.pl` | react | 1 | 4 | 0 |
| `https://incydent.cert.pl` | — | 1 | 1 | 0 |
| `https://science.nask.pl` | react | 1 | 0 | 0 |
| `https://www.gov.pl` | — | 1 | 0 | 0 |
| `https://komunikator.narodowy.gov.pl` | — | 0 | 0 | 0 |
| `https://116sos.pl` | — | 0 | 0 | 0 |
| `https://bezpiecznewybory.pl` | — | 0 | 0 | 0 |
