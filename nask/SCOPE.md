# Zakres konkursu — zweryfikowany u źródła (2026-11-03)

Wszystko poniżej **odczytane ze stron edycji 11/2026 na hack.cert.pl**, nie z pamięci
i nie z artykułu prasowego. Ten plik jest jedynym źródłem prawdy o scope w tym repo;
narzędzia biorą dane z `tools/scope.py`, który jest z nim zgodny 1:1.

**Edycja:** 03.11.2026 – 30.11.2026. **Pula edycji NASK: 100 000 zł** (nie 1 mln —
milion to pula całego, wieloletniego programu bug bounty NASK).

## 1. Pięć programów, pięć różnych zakresów

| program | Tier 1 | Tier 2 | wykluczone |
|---|---|---|---|
| **NASK** | `nask.pl`, `dyzurnet.pl`, `dns.pl`, `oad.nask.pl`, `zglos-dezinformacje.nask.pl` | `bezpiecznymiesiac.pl`, `secure.edu.pl`, `bezpiecznewybory.pl`, `116sos.pl`, `pllum.org.pl`, `science.nask.pl`, `dataannotation.pllum.org.pl` | — |
| **CERT Polska** | `cert.pl`, `m.cert.pl`, `incydent.cert.pl`, `moje.cert.pl`, `n6portal.cert.pl`, `mwdb.cert.pl`, `hack.cert.pl` | `*.cert.pl`, `ctf.hack.cert.pl` | `*.hack.cert.pl`, `*.lab.cert.pl` |
| **Portal Gov.pl** | `www.gov.pl` | — | wszystko inne (w tym samo `gov.pl`) |
| **mSzyfr** | `*.komunikator.narodowy.gov.pl` | — | — |
| **Gmina Władysławowo** | `eobieg.wladyslawowo.pl` | `wladyslawowo.pl`, `cciod.wladyslawowo.pl` | `bip.wladyslawowo.pl` (usunięte z zakresu) |

Źródła:
- <https://hack.cert.pl/programs/nask-pib/nask/editions/1>
- <https://hack.cert.pl/programs/cert-polska/bug-bounty-cert-polska/editions/1>
- <https://hack.cert.pl/programs/centralny-osrodek-informatyki/portal-gov-pl/editions/1>
- <https://hack.cert.pl/programs/mszyfr/mszyfr/editions/1>
- <https://hack.cert.pl/programs/cciod-wladyslawowo/bug-bounty-gmina-wladyslawowo/editions/1>

## 2. Nagrody (kwoty brutto wskazane w tabelach; NASK dopłaca podatek ryczałtowy)

| program | Tier | niska | średnia | wysoka | krytyczna |
|---|---|---:|---:|---:|---:|
| NASK, CERT Polska, Gov.pl | T1 | 600 zł | 4 000 zł | 9 000 zł | **20 000 zł** |
| NASK, CERT Polska, Gov.pl | T2 | 300 zł | 2 000 zł | 4 500 zł | **10 000 zł** |
| mSzyfr | — | 600 zł | 4 000 zł | 9 000 zł | **20 000 zł** |
| Władysławowo | T1 | 200 zł | 1 000 zł | 2 000 zł | 4 000 zł |
| Władysławowo | T2 | 100 zł | 500 zł | 1 000 zł | 2 000 zł |

Krytyczność liczona **CVSS 4.0**. Wysokość zależy od krytyczności, trudności eksploatacji
i wpływu na usługi państwa.

## 3. Zasady, które zmieniają sposób pracy

1. **Maksymalna szybkość narzędzi automatycznych: 5 req/s.** Naruszenie → odrzucenie
   zgłoszenia (§6). Dlatego limiter jest w tym repo domyślnie 4,5 req/s i **odmawia
   startu** przy wyższej wartości.
2. **Tylko własne konta** (poza domenowymi) albo konta testowe. Platforma **nie daje**
   kont testowych — trzeba rejestrować własne.
3. **Bez DoS i testów obciążeniowych** — wszystkie formy zabronione.
4. **Rozpatrywanie sukcesywne**, zwycięzcy ogłaszani **w trakcie** miesiąca → nie czekamy
   z raportem do końca.
5. **Duplikat** rozstrzyga data i godzina pierwszego poprawnego zgłoszenia (§7 pkt 8).
6. **Ta sama przyczyna źródłowa** w kilku serwisach = **jedna** podatność (§7 pkt 9).
7. Zgłoszenia wyłącznie przez formularz na hack.cert.pl; dyskrecja do wdrożenia poprawki.

## 4. Czego NIE zgłaszać (skrót z §8)

Stack trace, wersje, IP, listingi katalogów, user enumeration, brak nagłówków, HSTS,
brak captchy, flagi cookies, SPF/DKIM/DMARC bez spoofingu, wygasłe certyfikaty, otwarte
porty bez znaczenia, znane CVE bez działającego PoC, self-XSS, tabnabbing, content
injection bez JS, clickjacking bez krytycznej akcji, blind SSRF z dowodem tylko DNS,
subdomain takeover bez PoC, klucze API bez możliwości nadużycia, phishing/social
engineering, „potencjalne” scenariusze bez PoC, **raporty z automatów bez ręcznego
potwierdzenia**, literówki i layout.

> Regulamin karze „znalazłem 50 błędów konfiguracji”, a nagradza **jeden działający
> łańcuch ataku**.

## 5. Trzy pułapki, które kosztują nagrodę

1. `gov.pl` **nie jest** w scope — tylko `www.gov.pl`.
2. `hack.cert.pl` jest w scope, ale jego subdomeny **nie** (poza `ctf.hack.cert.pl`).
   Sam `hack.cert.pl` — tak.
3. `bip.wladyslawowo.pl` **usunięte** z zakresu. Stare poradniki wciąż je podają.
