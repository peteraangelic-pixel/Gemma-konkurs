# Przebiegi 5–8 (05.11.2026): co sprawdzono i co z tego wynika

Cztery przebiegi na Actions, **1 921 żądań łącznie**, 18 hostów w scope. Cel: zamknąć resztę
powierzchni anonimowej i sprawdzić dwie nowe klasy, których nikt w zespole nie testował
(trucizna cache współdzielonego, dane osobowe w publicznym JSON-ie).

**Potwierdzone podatności: 0.** Ale trzy narzędzia powstały i dwa fałszywe alarmy zostały
zabite własnymi rękami, zamiast trafić do raportu.

| przebieg | żądania | hosty | chunki | trafienia | werdykt |
|---|---:|---:|---:|---|---|
| 5 (`42037025885`) | 880 | 17 | 0 | 21 | 2× S3 `wysoki` → **fałszywy alarm**, poprawiony w kodzie |
| 6 (`42037073612`) | 880 | 17 | 0 | 21 | parametry nie dotarły z flagi (naprawione) |
| 7 (`42042393940`) | 982 | 18 | 47 | 21 | S3 czyste, S10 = 2 negatywy, S11 nie ruszyło |
| 8 (`42046017424`) | 59 | 1 | 0 | 0 | `hack.cert.pl` public API → 404 |

---

## 1. Fałszywy alarm, który byłby wstydem — S3 (`/_next/data`)

Przebieg 5 zgłosił **dwa trafienia `wysoki`** na `116sos.pl`:

```
HTML /index → 404   („wymaga logowania”)      JSON /_next/data/…/index.json → 200, 8256 B
pageProps: chips, articles, consultantQuotes, searchRanges, …
```

Wyglądało jak wyciek. Nie było: `/index` **nie jest chronioną stroną — nie istnieje**, a JSON
serwuje publiczne treści strony głównej (chipsy pomocy, cytaty konsultantów, zakresy wyszukiwania).
Błąd był w warunku sondy: „HTML nie jest 2xx” uznawałem za odmowę dostępu, a 404 to brak strony.

**Poprawka:** chronione = wyłącznie `401`/`403` albo przekierowanie na ścieżkę z
`login`/`signin`/`zaloguj`/`auth`/`sso`/`oidc`. Trasy `/x` i `/x/` deduplikowane
(przebieg 5 zgłosił tę samą trasę dwa razy). 5 nowych testów regresyjnych, w tym jeden
stary **poprawiony**, bo jego stanem wejściowym było 404 — czyli utrwalał błąd.

To trzecia runda tej samej lekcji: *sonda bez prawdziwej grupy kontrolnej produkuje pracę*.
Pierwsza dała 52 fałszywe trafienia, druga 2. Teraz mamy 133 testy i każdy fałszywy alarm
zostawia po sobie test.

## 2. Nowa klasa: trucizna cache współdzielonego (S10)

Punkt wyjścia — cudzy pomiar (`Gemma-konkurs/c4eeb067`): `dns.pl` odbija `X-Forwarded-Host`
do `<script src="https://ATTAKER/…">`, ale nie ma cache'u współdzielonego, więc wektor jest
martwy. W ich raporcie były jednak dwie rzeczy, których nikt nie wykorzystał:

* `pllum.org.pl` i `bezpiecznymiesiac.pl` mają **`Cache-Control: public, max-age=3600`** —
  czyli *mogą* cache'ować współdzielnie, więc trucizna miałaby gdzie osiąść;
* testowano tam **wyłącznie `X-Forwarded-Host`**.

Sprawdziłem **8 nagłówków × para kontrolna** na 6 hostach (`X-Forwarded-Host`,
`-Proto`, `-Scheme`, `-Port`, `-Prefix`, `X-Host`, `X-Original-URL`, `Accept-Language`).

**Wynik: `pllum.org.pl` i `bezpiecznymiesiac.pl` nie odbijają ANI JEDNEGO z ośmiu.**
Jedynym hostem z odbiciem jest `dns.pl` (`X-Forwarded-Host`, `X-Forwarded-Prefix`) i tam
propagacji nie ma — odpowiedź bez nagłówka jest czysta, `Cache-Control` zawiera `private`.
**Temat zamknięty, z dowodem, nie z opinii.**

## 3. Nowa klasa: dane osobowe w publicznym JSON-ie (S11)

Pierwsza sonda, która pyta odwrotnie niż cała reszta: nie „czy wejdę bez sesji w miejsce
chronione”, a „czy miejsce publiczne oddaje dane, które publiczne być nie powinny”.

Reguły przeciw fałszywym trafieniom: tylko `application/json`, e-maile z domeny serwisu
wykluczone (adresy instytucji są publiczne), próg **≥ 3 różne adresy z obcych domen**,
wartości **maskowane** w dowodzie (`o***@gmail.com`), plus IBAN/PESEL/JWT.

**Wynik: brak.** Publiczne trasy `hack.cert.pl` (`/api/v1/public/institutions`,
`/programs`, `/reports`, `/institutions/nask`) zwracają **404 + powłokę SPA (1 966 B)** —
publiczne API w tej postaci nie istnieje. To domyka trzecią drogę do portalu bez konta
(po S7 w przebiegu 4 i mapie z bundla).

## 4. `ctf.hack.cert.pl` — w scope, ale nie istnieje

CERT Tier 2 wymienia go imiennie. Root zwraca **404, 207 B**, brak vhosta, brak treści,
sześć sond S6 — wszystkie negatywy. Host w scope nie znaczy host z usługą; nie ma tam czego
testować do czasu, gdy ruszy CTF.

## 5. Co dały chunki JS (mimo że nie dały ścieżek API)

`index.js` `hack.cert.pl` to mapa **92 plików**; pobrałem 20 priorytetowych (payout, users,
view, ranking, reports, members). Klient skleja ścieżki szablonem (`${e}/api/v1/users/${t}`),
więc **prefiks `/api` nie występuje w chunkach** i moje wyciąganie ścieżek zwróciło zero —
to zapisane w kodzie jako ograniczenie, nie jako „nic nie ma”.

Ale chunki oddały coś innego i użytecznego: **pola, które serwer może przyjąć od klienta** —
`role`, `email`, `status`, `message_id`, `id`. To dokładnie lista mass-assignment do testu
z sesją (H5 w runbooku). `dataannotation.pllum.org.pl`: 233 chunki, w pobranych 20 pola
`id`, `status`, `role`, `token` — też pod mass assignment, ale bez konta nie do sprawdzenia.

## 6. Stan po ośmiu przebiegach

| | wartość |
|---|---|
| żądań własnych (wszystkie przebiegi) | ~2 700 |
| żądań zespołu (7 sesji) | ~3 000+ |
| potwierdzonych podatności | **0** |
| zgłoszeń wysłanych | **0** |
| nowych sond w tej serii | S10 (cache), S11 (PII), chunkowanie |
| testów offline | **133**, wszystkie zielone |

Wniosek, którego nie da się obejść: **anonimowa powierzchnia 18 hostów jest utwardzona na
każdej klasie mierzalnej bez sesji.** Nie dlatego, że „nie ma luk” — dlatego, że wszystko,
co płaci (IDOR, mass assignment, przejęcie konta, upload→RCE, SSRF z odczytem), wymaga
zalogowania, a logowanie wymaga Ciebie.

## 7. Trzy drogi do pieniędzy — wszystkie zaczynają się w Twojej przeglądarce

1. **`hack.cert.pl`** — `RUNBOOK-HACKCERT.md`, 45 minut, 7 hipotez z warunkami odrzucenia.
   Konto darmowe, ToS nie zakazuje, mapa `/api/v1` kompletna. **To jest droga nr 1.**
2. **`zglos-dezinformacje /api/sendForm`** — upload + SSRF z pola `urls`, 20 minut, ale to
   **żądanie zapisujące** u operatora rządowego → **wymaga Twojego GO**. reCAPTCHA v3 i tak
   wymaga przeglądarki.
3. **mSzyfr** — 2 własne konta, testy odseparowania rozmów. Bundle tylko z DevTools
   (brama daje catch-all 200 na `.js`), więc i tak potrzebna Twoja przeglądarka.

Co ja robię w tym czasie bez Ciebie: **nie uruchamiam kolejnego przebiegu po 18 hostach.**
Przebieg 7 (982 żądania, 8 nagłówków × 6 hostów, 47 chunków) był wyczerpaniem tematu.
Kolejny skan bez nowej hipotezy to większa liczba, nie większa wiedza.
