"""Silnik rekonesansu: od jednego hosta do listy kandydatów do ręcznej weryfikacji.

Trzy zasady, które ten moduł wymusza, bo wynikają z regulaminu, nie z upodobań:

1. **Nie zgadujemy, czy trafiliśmy.** Każdy host dostaje najpierw *baseline* —
   żądanie do losowego, nieistniejącego adresu. Jeżeli `/api/admin` odpowiada
   dokładnie tak samo jak `/api/cokolwiek-losowego-123`, to nie jest znalezisko,
   a SPA zwracająca index.html na wszystko. To najczęstsze źródło fałszywych
   trafień w skanerach i główny powód, dla którego raporty ze skanerów są
   odrzucane (§8 poz. 14.1).
2. **Zero żądań zmieniających stan.** Wyłącznie GET. Ten moduł nie ma metody
   wysyłającej POST — nie da się nim przypadkiem niczego zmienić.
3. **Limit szybkości jest niżej, w `fetch.py`.** Tu nie ma własnego licznika,
   bo dwa liczniki w jednym procesie to jeden licznik za dużo.

Czego ten moduł NIE robi: nie orzeka „tu jest podatność”. Produkuje **kandydatów**
z dowodem (status, typ treści, długość, fragment), a decyzję podejmuje człowiek.
Tak wygląda różnica między skanerem a badaniniem.
"""
from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from . import jsmine

# Ścieżki, które warto sprawdzić na każdym hoście. Kolejność = kolejność żądań,
# więc najcenniejsze idą pierwsze (gdyby budżet się skończył).
STANDARD_PATHS = [
    "robots.txt",
    "sitemap.xml",
    ".well-known/security.txt",
    "api/server",
    "api/v1/",
    "api/docs",
    "swagger.json",
    "openapi.json",
    "api/openapi.json",
    "graphql",
    "wp-json/",
    "wp-json/wp/v2/users",
    "xmlrpc.php",
    "actuator/health",
    "server-status",
    "humans.txt",
    "manifest.json",
]

# Ścieżki, które prawie zawsze są tylko szumem informacyjnym (wykluczone z §8
# poz. 2). Sprawdzamy je WYŁĄCZNIE po to, by wiedzieć, że nie ma tam nic, co
# prowadzi do czegoś większego (np. `.env` z kluczem, który da się wykorzystać).
LEAK_PATHS = [
    ".git/config",
    ".env",
    "backup.zip",
    "config.json",
]

_CATCHALL_STATUS_OK = {200, 301, 302, 403, 404}


@dataclass
class Hit:
    """Jedno trafienie-kandydat. Nie „podatność”."""
    url: str
    kind: str            # json | redirect | non-html | status | leak | automation
    status: int
    note: str
    evidence: str = ""   # krótki, bezpieczny fragment (max 300 znaków)
    score: int = 0

    def as_dict(self) -> dict:
        return {"url": self.url, "kind": self.kind, "status": self.status,
                "note": self.note, "evidence": self.evidence, "score": self.score}


@dataclass
class Baseline:
    """Odpowiedź wzorcowa dla losowego, nieistniejącego adresu."""
    status: int = 0
    content_type: str = ""
    length: int = 0
    title: str = ""
    ok: bool = False

    def matches(self, status: int, content_type: str, length: int, title: str) -> bool:
        """Czy odpowiedź jest nierozróżnialna od catch-all?"""
        if not self.ok:
            return False
        if status != self.status:
            return False
        if (content_type or "") != self.content_type:
            return False
        if self.length and abs(length - self.length) > max(24, self.length * 0.02):
            return False
        if self.title and title and self.title != title:
            return False
        return True


def _title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else ""


def _snippet(text: str, limit: int = 300) -> str:
    """Fragment dowodu bez sekretów: tylko początek, bez ciasteczek i tokenów."""
    cleaned = re.sub(r"(?i)(set-cookie|authorization|bearer\s+\S+|token[\"']?\s*[:=]\s*[\"']?[\w.-]{8,})",
                     "[REDACTED]", text)
    return re.sub(r"\s+", " ", cleaned)[:limit]


class Crawler:
    """Rekonesans jednego hosta. `http` to obiekt z metodą `get(url)` → Response."""

    def __init__(self, http, max_bundles: int = 6, max_js_bytes: int = 800_000):
        self.http = http
        self._sources: dict[str, int] = {}   # bundle → ile findingów wniósł
        self.max_bundles = max_bundles
        self.max_js_bytes = max_js_bytes

    # -- 1. baseline ----------------------------------------------------
    def baseline(self, base: str) -> Baseline:
        probe = base.rstrip("/") + "/" + _random_path()
        r = self.http.get(probe)
        ctype = r.headers.get("content-type", "")
        text = r.text if "html" in ctype else ""
        # Bez udanej odpowiedzi nie ma baseline — a wtedy `matches()` zawsze
        # zwraca False, czyli każda odpowiedź wygląda na "inną". To celowo
        # fail-open w stronę SZUMU, nie w stronę fałszywego spokoju: lepiej
        # pokazać człowiekowi za dużo, niż przemilczeć trafienie.
        ok = bool(r.status) and not r.error
        return Baseline(status=r.status, content_type=ctype.split(";")[0].strip().lower(),
                        length=len(r.body), title=_title(text), ok=ok)

    # -- 2. ścieżki standardowe ----------------------------------------
    def probe_paths(self, base: str, base_catch: Baseline,
                    paths: list[str] | None = None) -> list[Hit]:
        hits: list[Hit] = []
        for path in (paths or STANDARD_PATHS):
            url = urljoin(base.rstrip("/") + "/", path)
            r = self.http.get(url)
            hit = self._judge(url, r, base_catch, path)
            if hit:
                hits.append(hit)
        return hits

    def _judge(self, url: str, r, base_catch: Baseline, path: str) -> Hit | None:
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
        text = r.text
        title = _title(text) if "html" in ctype else ""

        if r.error:
            return None
        if r.status in (404, 410):
            return None
        if base_catch.matches(r.status, ctype, len(r.body), title):
            return None                      # catch-all: nie ma o czym mówić

        if "json" in ctype:
            score = 70
            if r.status == 200:
                score += 20
            if any(k in url for k in ("/api", "/graphql", "/swagger", "/openapi")):
                score += 10
            return Hit(url, "json", r.status,
                       f"JSON bez HTML-owego catch-all ({len(r.body)} B)",
                       _snippet(text), score)

        if r.status in (301, 302, 303, 307, 308):
            loc = r.headers.get("location", "")
            # przekierowanie na logowanie = normalne; na inny host = sprawdzić
            if loc and urlparse(loc).netloc and urlparse(loc).netloc != urlparse(url).netloc:
                return Hit(url, "redirect", r.status, f"przekierowanie poza host: {loc}", loc, 45)
            return Hit(url, "redirect", r.status, f"przekierowanie → {loc[:80]}", loc, 20)

        if r.status in (401, 403):
            return Hit(url, "auth-wall", r.status,
                       "istnieje i wymaga uwierzytelnienia (nie catch-all)", _snippet(text), 50)

        if r.status == 200 and "html" not in ctype:
            return Hit(url, "non-html", r.status,
                       f"200, ale nie HTML ({ctype or 'brak typu'}, {len(r.body)} B)",
                       _snippet(text, 200), 60)

        if r.status == 200 and r.body:
            return Hit(url, "status", r.status, "200 inny niż catch-all (SPA/route)", "", 15)
        return None

    # -- 3. Next.js: manifest tras -------------------------------------
    def next_routes(self, html: str, base: str) -> list[str]:
        """Next.js publikuje `_buildManifest.js` — listę tras aplikacji za darmo."""
        m = re.search(r'"buildId"\s*:\s*"([\w-]+)"', html)
        build_id = m.group(1) if m else None
        routes: list[str] = []
        candidates = []
        if build_id:
            candidates.append(f"/_next/static/{build_id}/_buildManifest.js")
        for c in re.findall(r'src="(/_next/[^"]+?\.js)"', html)[:4]:
            candidates.append(c.replace("/_next/static/", "/_next/static/", 1))
        for path in candidates:
            r = self.http.get(urljoin(base, path))
            if r.status == 200 and r.body:
                found = re.findall(r'"/([a-z0-9\-_/\[\]]{2,60})"', r.text)
                for f in found:
                    if not f.startswith("_next"):
                        routes.append("/" + f)
        # dedup zachowując kolejność
        seen, out = set(), []
        for r_ in routes:
            if r_ not in seen:
                seen.add(r_)
                out.append(r_)
        return out[:80]

    # -- 4. bundle JS → endpointy --------------------------------------
    def analyse_bundles(self, html: str, base: str) -> tuple[list, dict]:
        """Pobiera bundlе JS i wyciąga z nich powierzchnię ataku."""
        host = urlparse(base).netloc
        srcs = re.findall(r'src="([^"]+\.js[^"]*)"', html)
        srcs = [s for s in srcs if "/_next/" in s or "/static/" in s or "assets" in s]
        findings, techs = [], {}
        for src in srcs[: self.max_bundles]:
            url = urljoin(base, src)
            r = self.http.get(url)
            if r.error or not r.body or len(r.body) > self.max_js_bytes:
                continue
            found = jsmine.rank(jsmine.mine(r.text, base_host=host))
            # Finding jest niemutowalny (frozen) — zamiast dopisywać źródło
            # do obiektu, doklejamy je przy eksporcie. Mniej wygodne,
            # ale nie da się przez przypadek zmienić wyniku analizy.
            findings.extend(found)
            for f in found:
                if f.kind == "tech":
                    techs[f.value] = techs.get(f.value, 0) + 1
            self._sources[src] = len(findings)
        return findings, techs

    # -- 5. weryfikacja endpointów odkrytych w JS ----------------------
    def verify_endpoints(self, base: str, base_catch: Baseline,
                         endpoints: list[str], limit: int = 40) -> list[Hit]:
        """GET na endpointach odkrytych w kodzie. Tylko odczyt, bez parametrów akcji."""
        hits: list[Hit] = []
        seen = set()
        host = urlparse(base).netloc
        for ep in endpoints[:limit]:
            if ep in seen or not ep.startswith("/"):
                continue
            seen.add(ep)
            url = urljoin(base, ep)
            if urlparse(url).netloc != host:
                continue                      # nie wychodzimy poza host
            r = self.http.get(url)
            hit = self._judge(url, r, base_catch, ep)
            if hit and hit.kind == "json":
                hit.score += 15               # JSON z kodu aplikacji = mocniejszy sygnał
            if hit and hit.score >= 50:
                hits.append(hit)
        return hits


def _random_path() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(18))


def summarise(host: str, hits: list[Hit]) -> dict:
    return {
        "host": host,
        "hits": len(hits),
        "top": [h.as_dict() for h in sorted(hits, key=lambda h: -h.score)[:15]],
    }
