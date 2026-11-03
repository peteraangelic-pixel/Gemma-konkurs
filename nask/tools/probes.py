"""Sondy celowane: sześć konkretnych błędów, nie „skaner".

Różnica wobec `crawl.py`: tam szukamy *powierzchni* (co w ogóle istnieje), tutaj
zadajemy **pytanie o konkretny błąd** i każde pytanie ma z góry ustaloną odpowiedź,
która znaczy „tak". Dzięki temu wynik da się obronić przed weryfikatorem: nie
„narzędzie coś pokazało", a „ta odpowiedź serwera znaczy dokładnie to".

Każda sonda ma pole `why` — dlaczego jej wynik NIE wpada w wykluczenia z §8.
Jeżeliby wpadł, sondy nie ma w tym pliku. To jest jedyny powód, dla którego
lista jest krótka: 6 sond, z których każda ma szansę na nagrodę, jest warta
więcej niż 60, które trzeba potem odsiać.

Sondy:
  S1  CORS odbija Origin obcej domeny i pozwala czytać dane      → §8 poz. 14.1
  S2  Obejście middleware Next.js nagłówkiem x-middleware-subrequest
                                                                 → §8 poz. 9.3 / 12.1
  S3  Trasy Next.js czytane bezpośrednio z /_next/data/…json     → §8 poz. 12.2
  S4  JSON:API Drupala otwarte bez uwierzytelnienia              → §8 poz. 12.2 / 03
  S5  WordPress: wersje robocze / kontekst edit bez logowania    → §8 poz. 03
  S6  Obejście kontroli dostępu nagłówkiem X-Original-URL        → §8 poz. 9.3

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
    to nie podatność (§8 poz. 5.6) — dlatego go nie zgłaszamy jako trafienia,
    tylko jako obserwację.
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

    Sens ma tylko wtedy, gdy BEZ nagłówka ścieżka jest zablokowana
    (307/308 na login, 401, 403), a Z nagłówkiem serwer zwraca coś innego.
    Jeżeli obie odpowiedzi są takie same — nic nie ma, i to jest wynik negatywny,
    który też raportujemy (żeby nie sprawdzać drugi raz).
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
        changed = bypass.status != plain.status
        same_body = bypass.body == plain.body
        if changed or not same_body:
            sev = "krytyczny" if bypass.status == 200 else "wysoki"
            out.append(ProbeFinding(
                "S2", "", url, sev,
                "Nagłówek x-middleware-subrequest zmienia odpowiedź chronionej trasy",
                f"Bez nagłówka: {plain.status} (Location: {_hdr(plain, 'location') or '-'}). "
                f"Z nagłówkiem: {bypass.status}, {len(bypass.body)} B, "
                f"treść {'inna' if not same_body else 'ta sama'}.",
                "§8 poz. 9.3/12.1 — obejście autoryzacji w warstwie aplikacji. "
                "Nagłówek jest publicznie znany (CVE-2025-29927), ale wymagane jest "
                "PoC na tej instancji — i to jest to PoC. Trzeba jeszcze ustalić, "
                "CO ujawnia odblokowana trasa (samo 200 to za mało).",
                {"plain": plain.status, "bypass": bypass.status}))
    return out


# --------------------------------------------------------------------------
# S3 — trasy Next.js przez /_next/data
# --------------------------------------------------------------------------
def probe_next_data(http, base: str, build_id: str | None,
                    routes: list[str]) -> list[ProbeFinding]:
    """`/_next/data/<buildId><trasa>.json` omija HTML-owe sprawdzenia w przeglądarce.

    Trafieniem jest dopiero odpowiedź JSON z danymi, która normalnie wymaga
    zalogowania (sprawdzenie po stronie serwera należy do użytkownika).
    """
    out: list[ProbeFinding] = []
    if not build_id:
        return out
    for route in routes[:12]:
        path = f"/_next/data/{build_id}{route.rstrip('/')}.json"
        r = http.get(base.rstrip("/") + path)
        if r.error or r.status != 200:
            continue
        ctype = _hdr(r, "content-type")
        if "json" not in ctype:
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
            "S3", "", r.url, "sredni",
            "Dane strony Next.js czytane bezpośrednio z /_next/data",
            f"200 JSON ({len(r.body)} B), pageProps: {', '.join(keys) or 'puste'}; "
            f"podgląd: {preview}",
            "§8 poz. 12.2 — dostęp do danych przez nieudokumentowany endpoint. "
            "Znaleziskiem staje się dopiero wtedy, gdy pageProps zawiera dane "
            "niepubliczne; gołe `{}` to nie podatność.",
            {"route": route}))
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
        # `context=edit` bez logowania powinien zwrócić 401. 200 z polami
        # `content.raw`/`status` = realny wyciek treści roboczej.
        suspicious = ("content" in item and isinstance(item["content"], dict)
                      and "raw" in item["content"]) or item.get("status") == "draft"
        if not suspicious:
            continue
        proof = ("content.raw" if isinstance(item.get("content"), dict)
                 and "raw" in item.get("content", {}) else "status=draft")
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

    To klasyczna pomyłka w konfiguracji Azure Front Door / Envoy — a takie
    właśnie warstwy stoją przed celami w tym konkursie.
    """
    out: list[ProbeFinding] = []
    for path in (paths or PROTECTED_CANDIDATES):
        url = base.rstrip("/") + path
        plain = http.get(url)
        if plain.error or plain.status not in (401, 403, 404):
            continue
        for header in BYPASS_HEADERS:
            r = http.get(base.rstrip("/") + "/", headers={header: path})
            if r.error:
                continue
            if r.status == 200 and r.body and r.body != plain.body and len(r.body) > 500:
                out.append(ProbeFinding(
                    "S6", "", url, "wysoki",
                    f"Nagłówek {header} zmienia treść odpowiedzi",
                    f"{path} → {plain.status}; żądanie na / z {header}: {path} → "
                    f"{r.status}, {len(r.body)} B (inna treść)",
                    "§8 poz. 9.3 — obejście autoryzacji w warstwie aplikacji. "
                    "Wymaga ręcznego potwierdzenia, że treść odpowiada chronionej "
                    "zasobowi, a nie losowej stronie.",
                    {"header": header, "plain": plain.status}))
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
    for f in findings:
        f.host = re.sub(r"^https?://", "", base).split("/")[0]
    return findings
