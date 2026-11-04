"""Sondy celowane: sześć konkretnych błędów, nie „skaner".

Różnica wobec `crawl.py`: tam szukamy *powierzchni* (co w ogóle istnieje), tutaj
zadajemy **pytanie o konkretny błąd** i każde pytanie ma z góry ustaloną odpowiedź,
która znaczy „tak". Dzięki temu wynik da się obronić przed weryfikatorem: nie
„narzędzie coś pokazało", a „ta odpowiedź serwera znaczy dokładnie to".

Każda sonda ma pole `why` — dlaczego jej wynik NIE wpada w wykluczenia z §8.

## Historia, która jest ważniejsza niż sam kod

Pierwsza wersja tych sond przeszła 19 testów i wygenerowała w nocy **52 trafienia,
z których ~50 było fałszywych**. Przykład: `dns.pl` „odblokowany /admin" zwracał
51 121 B, a strona główna ma 51 152 B — sondy porównywały `/admin` z `/`, czyli
dwie różne strony, i „wykrywały różnicę" oczywiście zawsze.

Trzy poprawki wynikły wprost z tych danych i każda ma test regresyjny:
  • S2 liczy tylko realne odblokowanie (nie-2xx → 2xx), nie „inną treść",
  • S3 porównuje `/_next/data` **z tym samym adresem jako HTML**,
  • S6 porównuje **ten sam adres** z nagłówkiem i bez, nie `/` z `/admin`.

Wniosek na przyszłość: sonda bez grupy kontrolnej nie jest sondą, tylko generatorem
pracy. Testy jednostkowe tego nie wychwyciły, bo testowały logikę, a nie jej
odniesienie do rzeczywistości.

Sondy:
  S1  CORS odbija Origin obcej domeny i pozwala czytać dane      → §8 poz. 14.1
  S2  Obejście middleware Next.js nagłówkiem x-middleware-subrequest
                                                                 → §8 poz. 9.3 / 12.1
  S3  Trasy Next.js czytane bezpośrednio z /_next/data/…json     → §8 poz. 12.2
  S4  JSON:API Drupala otwarte bez uwierzytelnienia              → §8 poz. 12.2 / 03
  S5  WordPress: wersje robocze / kontekst edit bez logowania    → §8 poz. 03
  S6  Obejście kontroli dostępu nagłówkiem X-Original-URL        → §8 poz. 9.3
  S7  Endpoint `/users/{id}/…` z własnego JS zwraca dane bez sesji → §8 poz. 9.1/03

Czego świadomie NIE ma (i dlaczego):
  • user enumeration (/wp-json/wp/v2/users, /user/1?_format=json) — §8 poz. 2.2,
  • brak nagłówków, HSTS, wersje oprogramowania — §8 poz. 3,
  • znane CVE bez PoC — §8 poz. 3.10,
  • XML-RPC pingback — zbyt blisko „SSRF z dowodem tylko DNS" (§8 poz. 7).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

EVIL_ORIGIN = "https://evil.example"
SUFFIX_ORIGIN = "https://nask.pl.evil.example"   # test naiwnej walidacji „kończy się na nask.pl"

MIDDLEWARE_HEADER = "x-middleware-subrequest"
MIDDLEWARE_VALUE = ":".join(["middleware"] * 5)   # 5 > maxDepth(5) → middleware pominięty


@dataclass
class ProbeFinding:
    code: str
    host: str
    url: str
    severity: str        # niski | sredni | wysoki | krytyczny
    title: str
    detail: str
    why: str             # dlaczego to nie jest klasa wykluczona
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"code": self.code, "host": self.host, "url": self.url,
                "severity": self.severity, "title": self.title,
                "detail": self.detail, "why": self.why, "raw": self.raw}


def _hdr(r, name: str) -> str:
    return (r.headers.get(name) or "").strip()


def _short(body: str, n: int = 200) -> str:
    return re.sub(r"\s+", " ", body)[:n]


# --------------------------------------------------------------------------
# S1 — CORS
# --------------------------------------------------------------------------
def probe_cors(http, base: str) -> list[ProbeFinding]:
    """Czy obca domena może CZYTAĆ odpowiedź?

    Liczy się wyłącznie kombinacja: odbity Origin (albo `*`) **i** `credentials: true`,
    albo odbicie Originu przy odpowiedzi zawierającej dane. Sam `*` bez credentials
    to nie podatność (§8 poz. 5.6) — dlatego nie jest trafieniem, tylko obserwacją.
    """
    out: list[ProbeFinding] = []
    for origin in (EVIL_ORIGIN, SUFFIX_ORIGIN):
        r = http.get(base, headers={"Origin": origin})
        if r.error:
            continue
        acao = _hdr(r, "access-control-allow-origin")
        acac = _hdr(r, "access-control-allow-credentials").lower()
        exposes = _hdr(r, "access-control-expose-headers")
        if not acao:
            continue

        reflected = acao == origin
        wildcard = acao == "*"
        creds = acac == "true"

        if reflected and creds:
            out.append(ProbeFinding(
                "S1", "", base, "wysoki",
                "CORS odbija dowolny Origin i wysyła credentials:true",
                f"Żądanie z Origin: {origin} → ACAO: {acao}, ACAC: {acac}, "
                f"Expose: {exposes or 'brak'}. Status {r.status}.",
                "§8 poz. 14.1 — błędna konfiguracja CORS umożliwiająca odczyt danych; "
                "odbicie dowolnego Originu z credentials pozwala czytać odpowiedzi "
                "w kontekście zalogowanego użytkownika.", {"origin": origin}))
        elif reflected:
            out.append(ProbeFinding(
                "S1", "", base, "sredni",
                "CORS odbija dowolny Origin (bez credentials)",
                f"Żądanie z Origin: {origin} → ACAO: {acao}, ACAC: {acac or 'brak'}.",
                "§8 poz. 14.1 wymaga, by dało się CZYTAĆ dane — bez credentials "
                "znaczenie zależy od tego, czy endpoint zwraca dane bez sesji. "
                "Do ręcznej weryfikacji, nie do zgłoszenia w tej formie.", {"origin": origin}))
        elif wildcard and creds:
            out.append(ProbeFinding(
                "S1", "", base, "sredni",
                "CORS: ACAO=* razem z credentials:true",
                f"Origin: {origin} → ACAO: {acao}, ACAC: {acac}.",
                "Przeglądarki odrzucą `*` z credentials, więc to zwykle tylko błąd "
                "konfiguracji — chyba że inny endpoint odbija Origin. Sprawdzić resztę.",
                {"origin": origin}))
        elif wildcard:
            out.append(ProbeFinding(
                "S1", "", base, "niski",
                "CORS: ACAO=* (bez credentials)",
                f"Origin: {origin} → ACAO: {acao}.",
                "§8 poz. 5.6 — samo `*` bez możliwości kradzieży danych jest wykluczone. "
                "Zapisane, żeby nie sprawdzać drugi raz.", {"origin": origin}))
    return out


# --------------------------------------------------------------------------
# S2 — obejście middleware Next.js (CVE-2025-29927)
# --------------------------------------------------------------------------
PROTECTED_CANDIDATES = ["/panel", "/admin", "/dashboard", "/profil", "/konto", "/moje"]


def probe_middleware_bypass(http, base: str,
                            paths: list[str] | None = None) -> list[ProbeFinding]:
    """Porównuje odpowiedź z nagłówkiem i bez niego.

    Trafienie musi spełnić JEDEN z warunków:
      a) bez nagłówka trasa jest zablokowana (nie-2xx), a z nagłówkiem jest 2xx
         — realne obejście autoryzacji (krytyczny);
      b) oba są zablokowane, ale treść różni się co najmniej dwukrotnie
         długością — sygnał do ręcznego sprawdzenia (średni).

    Dlaczego nie „każda różnica treści": pierwsza wersja tak robiła i zgłosiła
    `bezpiecznewybory.pl` sześć razy, bo 403 z WAF-a ma 374 B, a bez nagłówka
    377 B — WAF wstawia identyfikator żądania. Bez progu ilościowego to szum.
    """
    out: list[ProbeFinding] = []
    for path in (paths or PROTECTED_CANDIDATES):
        url = base.rstrip("/") + path
        plain = http.get(url)
        if plain.error:
            continue
        blocked = plain.status in (401, 403) or (
            plain.status in (301, 302, 307, 308)
            and any(k in _hdr(plain, "location").lower() for k in ("login", "signin", "auth")))
        if not blocked:
            continue
        bypass = http.get(url, headers={MIDDLEWARE_HEADER: MIDDLEWARE_VALUE})
        if bypass.error:
            continue

        unlocked = bypass.status // 100 == 2 and plain.status // 100 != 2
        ratio = (len(bypass.body) / len(plain.body)) if plain.body else 0
        big_change = ratio >= 2 or ratio <= 0.5

        if unlocked:
            out.append(ProbeFinding(
                "S2", "", url, "krytyczny",
                "Nagłówek x-middleware-subrequest odblokowuje chronioną trasę",
                f"Bez nagłówka: {plain.status} (Location: {_hdr(plain, 'location') or '-'}). "
                f"Z nagłówkiem: {bypass.status}, {len(bypass.body)} B.",
                "§8 poz. 9.3/12.1 — obejście autoryzacji w warstwie aplikacji. "
                "Nagłówek jest publicznie znany (CVE-2025-29927), ale wymagane jest "
                "PoC na tej instancji — i to jest to PoC. Trzeba jeszcze ustalić, "
                "CO ujawnia odblokowana trasa (samo 200 to za mało).",
                {"plain": plain.status, "bypass": bypass.status}))
        elif big_change:
            out.append(ProbeFinding(
                "S2", "", url, "sredni",
                "Nagłówek x-middleware-subrequest zmienia treść (bez odblokowania)",
                f"Bez nagłówka: {plain.status}, {len(plain.body)} B. "
                f"Z nagłówkiem: {bypass.status}, {len(bypass.body)} B.",
                "Różnica ilościowa bez zmiany statusu. Najczęściej WAF albo inny "
                "wariant strony błędu — do ręcznego sprawdzenia, nie do zgłoszenia.",
                {"plain": plain.status, "bypass": bypass.status}))
    return out


# --------------------------------------------------------------------------
# S3 — trasy Next.js przez /_next/data
# --------------------------------------------------------------------------
def probe_next_data(http, base: str, build_id: str | None,
                    routes: list[str]) -> list[ProbeFinding]:
    """`/_next/data/<buildId><trasa>.json` a **ten sam adres jako HTML**.

    Trafieniem jest wyłącznie sytuacja, w której strona HTML wymaga logowania,
    a JSON wydaje dane bez sesji. Publiczna strona z publicznymi danymi to nie
    podatność — pierwsza wersja tego nie sprawdzała i zgłosiła osiem razy
    `116sos.pl`, gdzie `/_next/data` serwuje zwykłe artykuły i tagi.
    """
    out: list[ProbeFinding] = []
    if not build_id:
        return out
    for route in routes[:12]:
        html_probe = http.get(base.rstrip("/") + route)
        if html_probe.error or html_probe.status // 100 == 2:
            continue                      # treść i tak publiczna — nie ma czego zgłaszać
        path = f"/_next/data/{build_id}{route.rstrip('/')}.json"
        r = http.get(base.rstrip("/") + path)
        if r.error or r.status != 200 or "json" not in _hdr(r, "content-type"):
            continue
        try:
            payload = json.loads(r.text)
        except ValueError:
            continue
        if not isinstance(payload, dict) or "pageProps" not in payload:
            continue
        keys = sorted(payload.get("pageProps", {}).keys())[:10]
        preview = json.dumps(payload.get("pageProps", {}), ensure_ascii=False)[:180]
        out.append(ProbeFinding(
            "S3", "", r.url, "wysoki",
            "Dane chronionej strony Next.js czytane bez sesji przez /_next/data",
            f"HTML `{route}` → {html_probe.status} (wymaga logowania), "
            f"a JSON → 200 ({len(r.body)} B); pageProps: {', '.join(keys) or 'puste'}; "
            f"podgląd: {preview}",
            "§8 poz. 12.2 / 9.3 — dane niepubliczne przez nieudokumentowany endpoint, "
            "z pominięciem sprawdzenia w warstwie HTML. To realne ryzyko tylko wtedy, "
            "gdy pageProps nie są publiczne — trzeba przeczytać podgląd.",
            {"route": route, "html_status": html_probe.status}))
    return out


# --------------------------------------------------------------------------
# S4 — JSON:API Drupala
# --------------------------------------------------------------------------
JSONAPI_PATHS = ["/jsonapi", "/jsonapi/user/user", "/jsonapi/node/page",
                 "/jsonapi/node/article"]


def probe_drupal_jsonapi(http, base: str) -> list[ProbeFinding]:
    out: list[ProbeFinding] = []
    for path in JSONAPI_PATHS:
        r = http.get(base.rstrip("/") + path)
        if r.error or r.status != 200 or "json" not in _hdr(r, "content-type"):
            continue
        try:
            doc = json.loads(r.text)
        except ValueError:
            continue
        data = doc.get("data")
        if not isinstance(data, list) or not data:
            continue
        first = data[0]
        attrs = sorted((first.get("attributes") or {}).keys())[:8]
        out.append(ProbeFinding(
            "S4", "", r.url, "wysoki" if any(
                a in attrs for a in ("mail", "pass", "name", "field_")) else "sredni",
            "JSON:API zwraca rekordy bez uwierzytelnienia",
            f"{len(data)} rekord(ów), typ: {first.get('type')}, atrybuty: {', '.join(attrs)}",
            "§8 poz. 12.2 / 03 — dostęp do danych przez API bez autoryzacji. "
            "Krytyczność rośnie, jeśli w atrybutach są dane osobowe.",
            {"count": len(data), "attributes": attrs}))
    return out


# --------------------------------------------------------------------------
# S5 — WordPress: kontekst edit / wersje robocze
# --------------------------------------------------------------------------
WP_PATHS = ["/wp-json/wp/v2/posts?context=edit&per_page=1",
            "/wp-json/wp/v2/pages?context=edit&per_page=1",
            "/wp-json/wp/v2/media?per_page=1&context=edit",
            "/wp-json/wp/v2/posts?status=draft&per_page=1"]


def probe_wordpress_private(http, base: str) -> list[ProbeFinding]:
    """Wyłącznie próby czytania treści NIEpublicznych. Lista użytkowników jest
    pominięta celowo: §8 poz. 2.2 (user enumeration)."""
    out: list[ProbeFinding] = []
    for path in WP_PATHS:
        r = http.get(base.rstrip("/") + path)
        if r.error or r.status != 200 or "json" not in _hdr(r, "content-type"):
            continue
        try:
            doc = json.loads(r.text)
        except ValueError:
            continue
        if not isinstance(doc, list) or not doc:
            continue
        item = doc[0]
        # `context=edit` bez logowania powinien zwrócić 401. 200 z `content.raw`
        # albo `status=draft` = realny wyciek treści roboczej.
        raw_present = isinstance(item.get("content"), dict) and "raw" in item["content"]
        if not (raw_present or item.get("status") == "draft"):
            continue
        proof = "content.raw" if raw_present else "status=draft"
        out.append(ProbeFinding(
            "S5", "", r.url, "wysoki",
            "WordPress REST zwraca treści w kontekście edit bez logowania",
            f"200 JSON, id={item.get('id')}, status={item.get('status')}, "
            f"dowód: {proof}, pola: {', '.join(sorted(item)[:8])}",
            "§8 poz. 03.2 — dostęp do niepublicznych treści. Nie jest to user "
            "enumeration (§8 poz. 2.2) — to odczyt treści roboczych.",
            {"id": item.get("id")}))
    return out


# --------------------------------------------------------------------------
# S6 — nagłówki omijające kontrolę dostępu na proxy
# --------------------------------------------------------------------------
BYPASS_HEADERS = ["x-original-url", "x-rewrite-url", "x-forwarded-prefix"]


def probe_header_bypass(http, base: str, paths: list[str] | None = None) -> list[ProbeFinding]:
    """Gdy ścieżka daje 403/404, sprawdza, czy nagłówek proxy ją odblokuje.

    Kluczowe: porównujemy **ten sam adres** z nagłówkiem i bez niego, a nie
    „ścieżkę" z „stroną główną". Pierwsza wersja robiła to drugie i wygenerowała
    36 fałszywych trafień: `GET /admin` → 404 vs `GET /` + nagłówek → 200 to
    przecież zawsze będzie różnica, bo to dwie różne strony.

    Sygnałem jest wyłącznie to, że **ta sama** odpowiedź na `/` zmienia się pod
    wpływem nagłówka — czyli serwer go respektuje. To jeszcze nie podatność,
    ale to jedyne miejsce, gdzie warto patrzeć dalej.
    """
    out: list[ProbeFinding] = []
    control = http.get(base)
    if control.error:
        return out
    for path in (paths or PROTECTED_CANDIDATES):
        path_resp = http.get(base.rstrip("/") + path)
        if path_resp.error or path_resp.status // 100 == 2:
            continue                      # ścieżka i tak działa — nie ma czego obchodzić
        for header in BYPASS_HEADERS:
            r = http.get(base, headers={header: path})
            if r.error:
                continue
            same_status = r.status == control.status
            delta = abs(len(r.body) - len(control.body))
            if same_status and delta <= max(64, len(control.body) * 0.02):
                continue                  # nagłówek zignorowany — wynik negatywny
            out.append(ProbeFinding(
                "S6", "", base, "sredni",
                f"Nagłówek {header} zmienia odpowiedź tego samego adresu",
                f"`{path}` → {path_resp.status}. `GET /` bez nagłówka: {control.status}, "
                f"{len(control.body)} B. `GET /` z {header}: {path} → {r.status}, "
                f"{len(r.body)} B.",
                "§8 poz. 9.3 — sygnał obejścia autoryzacji w warstwie proxy. "
                "Sam wpływ nagłówka to jeszcze nie podatność: trzeba pokazać, że "
                "zwrócona treść odpowiada zasobowi, do którego nie ma dostępu.",
                {"header": header, "path_status": path_resp.status,
                 "control": control.status, "test": r.status}))
            break
    return out


# --------------------------------------------------------------------------
def run_all(http, base: str, ctx: dict) -> list[ProbeFinding]:
    """Uruchamia sondy, które mają sens dla wykrytego stacku."""
    tech = {t.lower() for t in ctx.get("tech", [])}
    findings: list[ProbeFinding] = []
    findings += probe_cors(http, base)
    findings += probe_middleware_bypass(http, base)
    findings += probe_header_bypass(http, base)
    if "next.js" in tech or ctx.get("build_id"):
        findings += probe_next_data(http, base, ctx.get("build_id"),
                                    ctx.get("routes", []))
    if "drupal" in tech:
        findings += probe_drupal_jsonapi(http, base)
    if "wordpress" in tech:
        findings += probe_wordpress_private(http, base)
    if ctx.get("mwdb"):
        findings += probe_server_version(http, base)
    endpoints = ctx.get("endpoints") or []
    if any(ID_PARAM_RE.search(e) for e in endpoints):
        findings += probe_api_authz(http, base, endpoints)
    for f in findings:
        f.host = re.sub(r"^https?://", "", base).split("/")[0]
    return findings


# --------------------------------------------------------------------------
# S7 — autoryzacja na endpointach API znanych z własnego JS aplikacji
# --------------------------------------------------------------------------
# Endpointy w stylu `/users/{id}` pochodzą z bundla, który aplikacja sama wysyła
# przeglądarce — nie zgadujemy ścieżek, tylko sprawdzamy te, które naprawdę istnieją.
#
# BARDZO WAŻNE OGRANICZENIE: podmieniamy identyfikator na 1 i 2 — bez iteracji po
# zakresie. Celem jest ustalenie, czy odpowiedź to 401/403 (poprawnie) czy 200
# z danymi (podatność). Jeśli odpowiedź zawiera dane, kończymy natychmiast
# i raportujemy sam fakt, nie treść. Regulamin §6 pkt 1 mówi o kontach; etyka jest
# tu prostsza niż regulamin — minimum konieczne do dowodu.
ID_SAFE_VALUES = ["1", "2"]
ID_PARAM_RE = re.compile(r"\$\{?[\w.]*(?:userId|id|Id|ID)[\w.]*\}?|\$(?:userId|id)")
SENSITIVE_FIELDS = ("email", "payout", "bank", "iban", "account_number", "phone",
                    "pesel", "address", "full_name", "token", "password_hash")
API_PREFIXES = ("", "/api/v1")


def probe_api_authz(http, base: str, endpoints: list[str],
                    max_endpoints: int = 6) -> list[ProbeFinding]:
    """Czy endpoint z identyfikatorem użytkownika sprawdza uprawnienia?

    Sprawdzamy dwa prefiksy, bo ścieżka z bundla bywa trasą frontendu
    (`/users/1/view`), a nie API. Dla hack.cert.pl realne API to `/api/v1/...`.
    Drugi prefiks to zgadywanie, ale kosztuje jedno żądanie na szablon.
    """
    out: list[ProbeFinding] = []
    templates = [e for e in endpoints if ID_PARAM_RE.search(e)][:max_endpoints]
    for tpl in templates:
        for value in ID_SAFE_VALUES:
            done = False
            for prefix in API_PREFIXES:
                path = prefix + ID_PARAM_RE.sub(value, tpl)
                if not path.startswith("/"):
                    continue
                hit = _judge_user_endpoint(http, base.rstrip("/") + path, path, value)
                if hit:
                    out.append(hit)
                    done = True
                    break
            if done:
                break
    return out


def _judge_user_endpoint(http, url: str, path: str, value: str) -> ProbeFinding | None:
    r = http.get(url, headers={"Accept": "application/json"})
    if r.error or r.status // 100 != 2:
        return None
    if "json" not in _hdr(r, "content-type") and "{" not in r.text[:200]:
        return None
    hits = [f for f in SENSITIVE_FIELDS if f'"{f}"' in r.text[:4000]]
    if not hits:
        return None
    return ProbeFinding(
        "S7", "", url, "krytyczny",
        "Endpoint użytkownika zwraca dane bez sesji",
        f"`{path}` → {r.status}, {len(r.body)} B. Pola wrażliwe w treści: "
        f"{', '.join(hits[:6])}. Zażądano WYŁĄCZNIE identyfikatora {value}; "
        f"nie pobierano dalszych rekordów.",
        "§8 poz. 9.1/9.2 i 03 — IDOR / brak kontroli dostępu prowadzący do odczytu "
        "cudzych danych. Wymaga potwierdzenia w przeglądarce dwoma własnymi kontami "
        "przed zgłoszeniem.",
        {"path": path, "fields": hits[:6], "value": value})


# --------------------------------------------------------------------------
# S8 — wersja aplikacji znanej z otwartych źródeł
# --------------------------------------------------------------------------
# Po co: żeby wiedzieć, czy POPRAWKA, którą widziałem w publicznym repo, jest już
# wdrożona. To odwrotność typowego „wykrywania wersji" (wykluczonego w §8 poz. 2.1)
# — tu wersja nie jest znaleziskiem, a narzędziem decyzyjnym: jeśli produkcja stoi
# na wersji sprzed poprawki XSS w atrybutach Rich (mwdb-core #1272/#1274, wydane
# w 2.20.0), warto sprawdzać dalej; jeśli nie — temat jest zamknięty i nie tracimy
# na niego nocy.
MWDB_FIX_VERSION = (2, 20, 0)


def probe_server_version(http, base: str) -> list[ProbeFinding]:
    r = http.get(base.rstrip("/") + "/api/server", headers={"Accept": "application/json"})
    if r.error or r.status != 200 or "json" not in _hdr(r, "content-type"):
        return []
    try:
        doc = json.loads(r.text)
    except ValueError:
        return []
    version = doc.get("server_version")
    if not version:
        return []
    nums = re.findall(r"\d+", str(version))[:3]
    older = len(nums) == 3 and tuple(int(n) for n in nums) < MWDB_FIX_VERSION
    return [ProbeFinding(
        "S8", "", r.url, "niski",
        f"Wersja aplikacji: {version}",
        f"`/api/server` → {version}"
        + ("; poprawka 2.20.0 (sanityzacja linków w atrybutach Rich, #1272/#1274) "
           "NIE jest wdrożona — warto sprawdzić XSS."
           if older else
           "; poprawka 2.20.0 jest wdrożona, temat XSS w Rich zamknięty."),
        "To nie jest znalezisko i nie idzie do zgłoszenia (§8 poz. 2.1). To informacja "
        "decyzyjna: mówi, czy warto sprawdzać błąd znany z publicznego repo.",
        {"version": version, "older_than_fix": older})]
