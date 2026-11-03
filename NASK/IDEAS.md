# Pomysły na wygraną — policzone, nie rzucone

Zasada: każdy pomysł ma **co trzeba zrobić**, **ile to kosztuje godzin**, **ile płaci** i
**jakie jest ryzyko odrzucenia**. Kolejność = wartość oczekiwana na godzinę, nie kolejność „fajności”.

Stawki Tier 1 (NASK, CERT Polska, gov.pl, mSzyfr): 600 / 4 000 / **9 000** / **20 000 zł**.
Tier 2 (m.in. `dataannotation.pllum.org.pl`, `116sos.pl`, `science.nask.pl`): połowa.

---

## 0. Rachunek, który trzeba zrobić przed pierwszym żądaniem

Pula 100 000 zł na program, 12 domen (NASK). Nagrody lecą **w trakcie** miesiąca, ale
**duplikat = 0**. Wniosek: nie warto trzymać raportu „na później”, ale jeszcze mniej warto
wysłać zgadywanie — trzy odrzucone zgłoszenia pod rząd mogą **zablokować możliwość zgłaszania**.

Realistyczny wynik jednej osoby w 30 dni (2 h dziennie, bez doświadczenia bug-bountowego):

| scenariusz | co musi się udać | wynik | szansa |
|---|---|---|---|
| pesymistyczny | nic potwierdzonego | **0 zł** | ~35 % |
| bazowy | 1× średnia + 1× niska | **4 600 zł** | ~40 % |
| dobry | 1× wysoka (IDOR z realnym wpływem) | **9 000 zł** | ~20 % |
| bardzo dobry | krytyczna (RCE / pełne przejęcie konta) | **20 000 zł** | ~5 % |

To nie jest konkurs, w którym wygrywa się „mega narzędziem”. Wygrywa się **jedną złą linią kodu
w jednej funkcji**. Cała reszta planu istnieje po to, żeby tę linię zobaczyć w 200 godzinach, a nie
w 2000.

---

## 1. Ranking pomysłów (EV na godzinę)

### #1 — IDOR / złamana kontrola dostępu na `dataannotation.pllum.org.pl` (HIVE) · Tier 2
**Co:** załóż **dwa własne konta**. Wykonuj te same operacje na obu, eksportuj HAR z przeglądarki,
potem podmieniaj identyfikatory zasobów konta A w żądaniach wysyłanych z sesji B.
**Dlaczego pierwsze:** nie wymaga exploitów ani zgadywania — tylko porównania. Aplikacje
anotacyjne (zadania, fragmenty tekstu, przypisania) mają obiekty o numerowanych ID i role
(anotator / moderator / właściciel projektu). To klasyczne miejsce na BAC.
**Płaci:** 2 000 zł (średnia) → **4 500 zł** (wysoka), jeśli odczyt cudzych zadań;
**10 000 zł** (krytyczna Tier 2) przy masowym odczycie.
**Koszt:** 4–8 h. **Ryzyko:** średnie (obiekty mogą być GUID-ami — wtedy szukaj IDOR-a w innym
miejscu: eksport, załączniki, komentarze, „udostępnij linkiem”).
**Narzędzie:** `tools/nasktriage` — zrzut HAR z dwóch kont → tabela „ten sam endpoint, dwa konta,
różne odpowiedzi”. To dokładnie ten przypadek.

### #2 — walidacja uploadu na `zglos-dezinformacje.nask.pl` · Tier 1
**Co:** formularz zgłoszenia dezinformacji przyjmuje materiały dowodowe. Sprawdź: podwójne
rozszerzenie, SVG z `<script>`, HTML z meta-refresh, plik `.svg` serwowany z `Content-Type: image/svg+xml`
na tej samej domenie (→ **stored XSS w kontekście moderatora**).
**Dlaczego mocne:** treść wgrywa **niezaufany użytkownik**, a ogląda ją **moderator** — to nie jest
„przyjął .exe”, to realny wektor na sesję pracownika. W regulaminie poz. 7.3 płaci za obejście
walidacji z istotnym wpływem, a XSS jest w zakresie (poz. 8).
**Płaci:** 4 000 zł, **9 000 zł** jeśli prowadzi do przejęcia sesji moderatora.
**Koszt:** 2–4 h. **Ryzyko:** odrzucenie, jeśli plik jest serwowany z innej domeny (sandbox) —
wtedy sprawdź, czy sandbox jest w zakresie; jeśli nie, szukaj natychmiastowego renderowania
podglądu w panelu.

### #3 — SSRF w polu „źródło/link” · Tier 1
**Co:** aplikacje, które „pobiorą link” (zgłoszenia, OAD), często robią `fetch(url)` po stronie
serwera. Wskaż **własny** endpoint (np. webhook z `webhook.site` — tylko jako cel kontrolowany),
sprawdź, czy serwer wykonuje żądanie; potem sprawdź, czy potrafi trafić w `169.254.169.254`
lub w usługę wewnętrzną. **Wymagany odczyt**, nie sam DNS (blind SSRF jest wykluczony, §8).
**Płaci:** 4 000 zł, **9 000 zł** przy dostępie do usług wewnętrznych.
**Koszt:** 2–3 h. **Ryzyko:** wysokie (musi być odczyt).

### #4 — mass assignment na rejestracji / profilu · Tier 1/2
**Co:** przy rejestracji i edycji profilu dopisz pola, których UI nie pokazuje:
`role`, `is_admin`, `is_staff`, `approved`, `verified`, `email_verified`, `tier`, `credits`.
Sprawdzaj **odpowiedź**, nie tylko zachowanie — czasem pole jest zapisywane, ale nieużywane.
**Płaci:** 4 000–9 000 zł (eskalacja uprawnień).
**Koszt:** 1–2 h na aplikację. **Ryzyko:** niskie, ale często trafia w „nic”.

### #5 — obejście middleware Next.js (CVE-2025-29927) · wszystkie serwisy na Next.js
**Co:** jedno żądanie z nagłówkiem `x-middleware-subrequest: middleware:middleware:middleware:middleware:middleware`
na ścieżkę, która bez sesji daje 307/403. Jeśli odpowie 200 z treścią panelu — mamy krytyczną.
**Płaci:** do **20 000 zł**. **Koszt:** **5 minut**. **Ryzyko:** bardzo prawdopodobne, że załatane —
ale koszt sprawdzenia jest niższy niż koszt zastanawiania się.

### #6 — cache deception / cache poisoning na Azure Front Door · Tier 1
**Co:** `GET /konto/profil.css` (dopisana końcówka statyczna) przy zachowanym ciasteczku — jeśli
odpowiedź z danymi konta trafi do cache z `Cache-Control: public`, kolejny użytkownik ją dostanie.
**Płaci:** 9 000–20 000 zł. **Koszt:** 2 h. **Ryzyko:** średnie (często CDN nie cache'uje
odpowiedzi z `Set-Cookie`).

### #7 — HTTP request smuggling (CL.TE / TE.CL) · Tier 1
**Co:** tylko tam, gdzie przed aplikacją stoi własny proxy (Envoy/Azure). Wymaga precyzji
i **nie może** być testowane metodą „wyślij i patrz, czy coś padło” (to DoS = dyskwalifikacja).
Bardzo wysoka wartość (20 000 zł), bardzo niska szansa, wysoki koszt.
**Koszt:** 6–10 h. **Decyzja: dopiero po #1–#4.**

### #8 — takeover subdomeny z zakresu · tanie sprawdzenie
**Co:** dla 12 hostów sprawdź CNAME → czy cel wskazuje na usługę porzuconą (S3/Azure/Heroku).
„Znalazłem dangling CNAME” bez **działającego PoC przejęcia** jest wprost wykluczone (poz. 17).
**Koszt:** 30 min. **Płaci:** 4 000 zł.

### #9 — refleksje w wyszukiwarkach (XSS / HTML injection) · tanie
**Co:** `dns.pl` (whois), `science.nask.pl` (WordPress search), `dyzurnet.pl`.
Test: `<i>test</i>` w parametrze. Jeśli wraca nieescapowane — mamy HTML injection;
XSS dopiero gdy widać wykonanie JS.
**Koszt:** 20 min. **Płaci:** 600–4 000 zł.

---

## 2. Kolejność, jaką proponuję (i dlaczego nie inna)

```
dzień 1      #5 (5 min) → #9 (20 min) → #8 (30 min)  = wszystkie tanie testy z głowy
dzień 1-2    założenie 2 kont na HIVE + 1 na zglos-dezinformacje
dzień 2-6    #1 IDOR na HIVE  (największa szansa na 4 500-10 000 zł)
dzień 7-10   #2 upload + #3 SSRF na zglos-dezinformacje
dzień 11-14  #4 mass assignment na wszystkich 5 aplikacjach
dzień 15-30  #6, #7 i to, co wyniknie z obserwacji; drugi program (CERT Polska Tier 1)
```

**Bramka decyzyjna w dniu 7:** jeśli po 6 dniach nie mamy ani jednej *potwierdzonej* obserwacji
(różnicy, której nie da się wytłumaczyć zachowaniem aplikacji), zmieniamy aplikację, nie
„dokładamy narzędzi”. To jedyna reguła, która realnie chroni przed przepaleniem miesiąca.

---

## 3. Czego świadomie NIE robimy (i dlaczego to podnosi szansę)

| nie robimy | powód |
|---|---|
| masowego skanowania katalogów i fuzzingu | 204 żądania w rekonesansie dały **0** ekspozycji; SPA zwraca 200 na wszystko. Limit 5 req/s i tak nie pozwala na wolumen |
| testów obciążeniowych i „sprawdźmy, czy padnie” | **natychmiastowa dyskwalifikacja** (§8 poz. 10) |
| raportów z samym outputem skanera | odrzucane z definicji (§8 poz. 14) |
| zgłaszania „brak nagłówków CSP”, wersji, stack trace, user enumeration | wprost wykluczone (§8 poz. 2–3) |
| hostów spoza §5 (`*.snkom`, `zakupy`, `taskmanagement`, `panel.dns.pl`) | to nie „brak nagrody”, to problem prawny |
| trzymania raportu do 30.11 | nagrody lecą sukcesywnie, duplikat przegrywa |
| publikowania czegokolwiek o znaleziskach | wymóg poufności do czasu poprawki |

---

## 4. Gdzie realnie leży 20 000 zł

Nie w klasach z listy, tylko w **jednej funkcji napisanej w pośpiechu**: eksport do CSV z danymi
osobowymi, „udostępnij raport linkiem”, reset hasła przez token w URL, panel moderatora z IDOR-em,
endpoint `/api/internal/...` bez autoryzacji, „pobierz załącznik” serwujący po `id` bez sprawdzenia
właściciela. Każda z tych rzeczy jest **niewidoczna dla skanera** i **widoczna w 10 minut** dla
człowieka, który kliknął w aplikacji i patrzy na żądania w DevTools.

Dlatego moja rola to: przygotować listę kontrolną, analizować Twoje zrzuty HAR, pisać payloady
i raporty, i pilnować, żeby żadne zgłoszenie nie było odrzucalne. Twoja rola to: **klikać w aplikacji
i eksportować to, co widzisz**.
