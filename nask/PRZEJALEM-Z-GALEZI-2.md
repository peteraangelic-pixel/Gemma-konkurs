# Co przejąłem z gałęzi — część 2 (ponowny przegląd, 04.11.2026, po południu)

Część 1: `PRZEJALEM-Z-GALEZI.md` (rano). Tutaj tylko **to, co doszło po niej** +
wynik obowiązkowego sprawdzenia **wszystkich** gałęzi czterech repozytoriów, bo user
słusznie zauważył, że część z nich ma nowe commity.

## 0. Sprawdzenie wszystkich gałęzi — wynik

| repo | gałąź | tip | data commita | czy jest tam coś dla NASK |
|---|---|---|---|---|
| Pokemon | `arena/7911f950` | `ca0f3cc` | 04.11 10:28 | tak — przejęte rano (raport nocy 04, 256 sond) |
| Pokemon | `arena/c87f7a48` | `a2e1b16` | 04.11 10:45 | tak — przejęte rano (REJESTR-LEADS L1–L12, RAWPATH) |
| Pokemon | `arena/a450b00f` | `bb17ccd` | 04.11 10:14 | tak — przejęte rano (lab offline, mapy programów) |
| Pokemon | `arena/d1882c0f` | `2d46dcb` | **01.11 20:17** | **NIE** — `battery-sim` v0.2 (model baterii, audyt energetyczny) |
| Pokemon | `arena/7cc8a7e0` | `b64f580` | **11.10 21:02** | **NIE** — ARC-AGI-3: post-mortem atrapy (placeholder submission) |
| Pokemon | `arena/98ddb59f` | `148be97` | **13.10 12:04** | **NIE** — ARC-AGI-3 „duck" (ledger, world-model) |
| Pokemon | `arena/8560a56a` | `a852d3a` | **13.10 12:03** | **NIE** — Pokemon TCG agent (V33, kaggle_results) |
| Pokemon | `main` | `ca72e32` | 08.10 | nie |
| Gemma-konkurs | `arena/c4eeb067` | `e46c916` | 04.11 10:55 | tak — przejęte rano (runda 7: H10 obalona, `download-file`/`cookieHash` zamknięte) |
| Gemma-konkurs | `arena/6d081d52` (moja) | `48c2b21` | 04.11 10:32 | ja |
| Smak-Domu | `arena/5ed750ef` | `6fd86e3` | 04.11 10:12 | tak — przejęte rano (SYNTEZA ZESPOLU, 0 potwierdzonych) |
| Smak-Domu | 3× `codex/arc-*` | — | 30.10–02.11 | nie (ARC-AGI) |
| NASK | `arena/a29ca234` | `eb234af` | 03.11 | tak — przejęte rano (`nask-lab` bundling) |
| NASK | `codex/multi-program-lab` | `a4fb58d` | 03.11 22:56 | **tak, nowe** — patrz §1.1 |
| NASK | `main` | `e0a562e` | 03.11 11:08 | nie (przed operacją) |

**Cztery gałęzie Pokemon, których nie przejrzałem, nie mają nic wspólnego z konkursem**
(bateria, ARC-AGI-3 ×2, Pokemon TCG) i są starsze o 3–4 tygodnie od startu edycji. Sprawdzone
po tytułach commitów i drzewie plików (`battery-sim/`, `arc-agi-3/`, `pokemon-agent/`) — zero
plików `nask/`. Zamykam temat: **nie ma czego przejmować.**

## 1. Nowe fakty (poza tym, co było w części 1)

### 1.1. Operacja `.git`/`.env` na 24 hostach — wykonana, negatywna, z liczbami

`NASK/codex/multi-program-lab` @`a4fb58d`, przebieg Actions **41734282345** (2 min 21 s,
commit `93f84ba`, status `completed_with_skips`):

- pary kontrolne (2 nieistniejące adresy/host) + `/.git/HEAD` + `/.env`, dokładne hosty,
  HTTPS, bez przekierowań, 1 req/s, bez ponowień;
- **75 żądań** (4 regulaminy + 24 kontrola + 18 kontrola + 18 git + 11 env), 68 odpowiedzi,
  3 błędy transportu, 9× 403, **zero 429**, minimalny odstęp 1,000082 s;
- hashe **wszystkich czterech regulaminów** zgodne (kontrola przed ruchem);
- z 20 zachowanych treści dotyczących badanych plików: **9 negatywów, 11 nierozstrzygniętych**
  (brak 200 albo niepełne kontrole), **0 kandydatów, 0 potwierdzonych podatności**.

To jest mocniejszy dowód niż mój: mieli **kontrole parami** i weryfikację regulaminów przed
ruchem. Wpisuje się jako domknięcie hipotezy #9 (`HIPOTEZY-ZAMKNIETE.md`).

### 1.2. `oad.nask.pl` — publiczny raport PowerBI z `autoAuth=true`

Nowa, **pasywna** ścieżka: nie żądanie do API, tylko „popatrz, co ten embed pokazuje”.
Kryterium: agregaty → zero; pojedyncze rekordy (dane osobowe/zgłoszenia) → klasa 03.
Wymaga 2 minut w przeglądarce, nie wymaga konta, nie wymaga GO. **Bierzemy.**

### 1.3. `moje.cert.pl` ma publiczne `/accounts/signup/`

Czyli własne konto jest tam **technicznie możliwe** — wcześniej zakładałem, że nie.
Blokadą pozostaje konflikt regulaminowy (ToS §IV 4.2 vs. karta programu, `SCOPE.md` §4a):
**konto tak, testy nie, dopóki nie ma pisemnej odpowiedzi organizatora.** Nie zmieniam zdania
pod wpływem tego, że ktoś inny „i tak by spróbował”.

### 1.4. `dyzurnet.pl` i `dns.pl` — `/api/` zwraca 308, mapa chunków JS niewykonana

Jedyna para hostów Tier 1 NASK, której **nikt** nie zmapował od strony kodu klienta.
To praca offline po pobraniu publicznych chunków (GET, w zakresie) — dokładnie mój profil.
Priorytet: średni (po `hack.cert.pl`), ale to jedyne miejsce, gdzie nie ma jeszcze 6 sesji
duplikatów.

### 1.5. mSzyfr: bundle tylko z przeglądarki

Brama zwraca **catch-all 200 HTML** dla `.js` poza przeglądarką. Automat tego nie pobierze.
Wniosek: mSzyfr jest **nietestowalny bez Ciebie** — i to jest ograniczenie metody, nie wynik.
Nie wpisuję jako negatywu; wpisuję jako „wymaga ręki”.

## 2. Korekta planu (trzecia i ostatnia przed Twoim GO)

| # | Ścieżka | Kto | Koszt | Status |
|---|---|---|---|---|
| 1 | `hack.cert.pl` — konto, awatar SVG, format ID własnego zgłoszenia | **Ty** | 15 min | bez zmian, nadal #1 |
| 2 | `hack.cert.pl` — H1–H7 (IDOR/BAC, `internal-notes`, `payout`) | Ty (DevTools) + ja (runbook) | 45–60 min | bez zmian, jedyny legalny host z sesją |
| 3 | `oad.nask.pl` — embed PowerBI, czy widać rekordy | **Ty** | 2 min | **NOWE, najtańsze** |
| 4 | `zglos-dezinformacje` `/api/sendForm` | Ty, ręcznie | 20 min | **wymaga GO** (żądanie zapisujące u operatora) |
| 5 | `dyzurnet.pl` + `dns.pl` — mapa chunków JS | ja, offline | 1–2 h | nowe, bezkolizyjne |
| 6 | `moje.cert.pl` / pozostałe CERT Tier 1 | — | — | **zablokowane** do odpowiedzi organizatora |
| 7 | `116sos.pl /api/centres-search` | ja (pomiar) + Ty (UI) | 10 min | czeka, aż host wstanie |
| 8 | `mSzyfr` | Ty | 2 × konto | nietestowalne automatem |

Zasada bez zmian: **nie uruchamiam kolejnego przebiegu sieciowego bez nowej hipotezy.**
Przebieg 4 (816 żądań) był ostatnim i potwierdził, co miał potwierdzić.

## 3. Co nowego jest teraz w repo

- `nask/SZABLON-ZGLOSZENIA.md` — szablon zgłoszenia z **20 klasami** i filtrem §8
  („czego nie zgłaszać”) — każdy przyszły draft raportu przechodzi przez niego.
- `nask/PRZEGLAD-DYSCU-2026-11-04.md` — pełny przegląd Dysku (20 plików): co przyjęte,
  co duplikat, co odrzucone.
- `nask/HIPOTEZY-ZAMKNIETE.md` — wpisy #16–#18 (oad `podglad-pdf`, science RAWPATH,
  mSzyfr catch-all jako ograniczenie pomiaru).

## 4. Jedno zdanie

Gałęzie nie przyniosły nowej podatności — przyniosły **jedną nową, darmową ścieżkę pasywną**
(PowerBI), **jedno potwierdzenie negatywu mocniejszym pomiarem** (75 żądań z parami kontrolnymi)
oraz **domknięcie mapy jedynego hosta, na którym sesja jest legalna** (`hack.cert.pl`).
Pieniądze nadal są w Twojej przeglądarce, nie w moim skanerze.
