# Przegląd kodu `mwdb-core` — co wynika dla planu

Data: 2026-11-03. Źródło: <https://github.com/CERT-Polska/mwdb-core>,
commit `50d8b15` (2026-10-30), 172 pliki `.py`, ~8,8 tys. linii w `mwdb/resources`.
Metoda: własne narzędzie `nask/tools/authz_scan.py` (offline, zero żądań) + ręczne
czytanie miejsc oznaczonych jako podejrzane.

**To jest przegląd, nie audyt.** Nie znalazłem podatności. Znalazłem coś innego i
równie przydatnego: **wiedzę, gdzie tej podatności nie ma**, czyli gdzie nie tracić dni.

## 1. Wynik skanera

```
OPEN=9  PARTIAL=2  GUARDED≈120
```

Dwie metody **PARTIAL** są w `oauth.py`: `OpenIDBindAccountResource.POST`
i `OpenIDLogoutResource.GET` — obie wymagają zalogowania i biorą `provider_name`
z ścieżki, a skaner nie widzi w nich sprawdzenia dostępu do obiektu. To nie jest
podatność: to dwie funkcje do ręcznego przeczytania w pierwszej kolejności.

Dziewięć endpointów „OPEN" to **wszystkie legalnie publiczne**: `LoginResource`,
`RegisterResource`, `ChangePasswordResource` (token z maila), przepływ OAuth
(`OpenID*`), `PingResource`, `ServerInfoResource`, `UserPendingResource`
(ten ma `@requires_capabilities(manage_users)`, czyli capability).

**Żadnego endpointu, który pobiera obiekt po identyfikatorze z żądania, mając
uwierzytelnienie, ale bez sprawdzenia właściciela** (poza dwiema metodami OAuth
wymienionymi wyżej). To nie przypadek: kontrolę trzyma jedna funkcja `access_object()`
w `mwdb/resources/__init__.py`, która woła `Object.access()` w `mwdb/model/object.py`:

```python
obj = cls.get(identifier).first()
if obj is None: return None
if obj.has_explicit_access(requestor): return obj       # jawny dostęp lub access_all_objects
if requestor.has_rights(Capabilities.share_queried_objects): ...  # dostęp "queried"
return None                                             # brak dostępu
```

Trzy konsekwencje, wszystkie ważne dla planu:

1. **Klasyczny IDOR po identyfikatorze jest tu mało prawdopodobny.** Ten kod ma
   jedną, wspólną ścieżkę autoryzacji i jest ona poprawna. Dzień spędzony na
   „podmienianiu ID w URL-u" na `mwdb.cert.pl` to dzień stracony.
2. **Prawdziwe ryzyko jest w konfiguracji wdrożenia, nie w kodzie.** Kluczowe są
   capabilities: `access_all_objects`, `share_queried_objects`, `sharing_with_all`,
   `manage_users`. Jeśli w produkcji jakiś zespół dostał `access_all_objects`,
   to nie jest błąd aplikacji — i nie jest to podatność, którą wolno nam testować
   (wymaga cudzych uprawnień, §8 poz. 1).
3. **Zostaje warstwa logiki, nie warstwa dostępu.** Miejsca warte czytania dalej:
   `share.py` (semantyka `give_access`, grupy), `oauth.py` (865 linii, publiczne
   endpointy, przepływy z `state` i konfiguracją providera — największa powierzchnia
   w całym repo), `remotes.py` (626 linii, kilka endpointów biorących identyfikator),
   `api_key.py` (zakres tokenu).

## 2. Korekta mojego wcześniejszego planu — i dlaczego to jest ważne

W `plan.json` miałem hipotezę „IDOR w `mwdb.cert.pl`, 22 % szans, 4 dni". Po
przeczytaniu kodu **obniżam ją do 10 %** i przenoszę na dalsze miejsce. Powód
jest konkretny, nie intuicyjny: wspólna ścieżka `access_object → Object.access`
jest poprawna, więc szansa, że trafię IDOR, spada.

Co rośnie w zamian:

| obszar | dlaczego | jak sprawdzić |
|---|---|---|
| `oauth.py` (publiczne przepływy) | największa powierzchnia, złożona logika `state`/`redirect_uri`, błędy tu są częste | dwa własne konta, ręcznie w przeglądarce |
| `share.py` + grupy | semantyka `give_access` i `sharing_with_all` bywa subtelna | własne konto, własne obiekty, obserwacja, kto widzi co |
| `remotes.py` | kilka endpointów biorących identyfikator, mniej uczęszczana ścieżka | tylko odczyt, własne konto |
| konfiguracja wdrożenia | capabilities nadane zespołom | **nie testujemy** — cudze uprawnienia, §8 poz. 1 |

## 3. Czego to nie zmienia

`mwdb.cert.pl` **nadal jest najlepszym celem** — ale z innego powodu, niż myślałem:
nie „bo znajdę IDOR", a „bo mam kod i mogę czytać bez limitu 5 req/s". Ta przewaga
jest realna; zmienił się tylko kierunek, w którym warto ją wykorzystać.

## 4. Uczciwe oczekiwania po tym przeglądzie

Przed: „IDOR w mwdb to moja najlepsza szansa". Po: „mwdb to najlepsze miejsce do
czytania kodu, ale szansa na trafienie w miesiąc jest niższa, niż zakładałem".
Nie owijam: **to obniża sumę EV planu**, a nie podnosi. Wolę to napisać teraz niż
po trzech tygodniach.

## 5. Jak to powtórzyć na `n6portal`

```bash
git clone --depth 1 https://github.com/CERT-Polska/n6portal
python3 -m nask.tools.authz_scan <ścieżka>/src --only-suspect
```

Skaner jest ogólny (szuka `access_object`/`.access(`/`has_rights`/`requires_*`
w dekoratorach i ciele), więc działa też na innych projektach Flask/Django — pod
warunkiem, że trzymają kontrolę w tych samych wzorcach. Na `n6portal` wynik trzeba
przeczytać ostrożniej: inny framework, inne konwencje.
