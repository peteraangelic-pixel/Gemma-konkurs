"""Wydobywanie leniwie ładowanych chunków JS — offline, na już pobranym kodzie.

## Po co to jest (konkret, nie ogólnik)

Paczka z Dysku (`19-nask-noc-…`, `recon/evidence-20261103/`) zawiera **7 bundli**
`hack.cert.pl`. W `index-B5IFYBO_.js` jest mapa zależności (`__vite__mapDeps`) z **92
plikami** `assets/*.js`. Mapa mówi tylko *jak nazywają się pliki* — a prawdziwe wywołania
API (ścieżki, parametry zapytań, nagłówki, pola formularzy) siedzą w chunkach
funkcjonalnych: `payout-*.js`, `users-*.js`, `view-*.js`, `ranking-*.js`,
`ReportsTable-*.js`, `ProgramMembersField-*.js`, `integrations-*.js`.

Bez nich mapa endpointów jest **listą nazw bez parametrów**, a bez parametrów nie da się
ani napisać runbooka dla człowieka, ani odróżnić „publiczne z definicji” od „wycieka”.

## Reguły wbudowane w kod

* **Tylko ten sam host.** Chunk z innej domeny (CDN, analytics) jest pomijany — nie
  rozszerzamy powierzchni poza zakres programu przez przypadek.
* **Tylko `assets/` z mapy zależności**, nie zgadywanie nazw plików.
* **Budżet żądań jest jawny.** `max_chunks` liczone w żądaniach; przy wyczerpaniu
  zwracamy to, co już mamy, plus `skipped`.
* **Pominięte chunki są zapisane z powodem** (`too_big`, `error`, `budget`) — brak
  wpisu nie może znaczyć „sprawdzone i czyste”.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from . import jsmine

# `assets/name-HASH.js` — dokładnie tak wygląda mapa zależności Vite.
_CHUNK_RE = re.compile(r"assets/([A-Za-z0-9_\-]+-[A-Za-z0-9_\-]{8,})\.js")

# Ścieżki API sklejane z prefiksem w kodzie (`${e}/api/v1/users/${t}`), więc nie łapią
# ich cudzysłowy jak w jsmine._PATH_RE. Dlatego drugi, luźniejszy wzorzec.
_API_PATH_RE = re.compile(r"/(?:api)/(?:v\d+/)?[A-Za-z0-9_\-]+"
                          r"(?:/[A-Za-z0-9_\-${}.:]{1,40}){0,6}")

# Nazwy parametrów zapytań typowe dla tej aplikacji — zbierane razem z endpointem,
# bo „endpoint” bez parametru nic nie mówi o IDOR-ze.
_QUERY_RE = re.compile(r"[?&]([A-Za-z_][A-Za-z0-9_]{1,30})=")

MAX_JS_BYTES = 900_000          # chunk funkcjonalny ~10–40 kB; 900 kB to już wyjątek


@dataclass
class ChunkResult:
    url: str
    size: int
    endpoints: list[str] = field(default_factory=list)
    params: list[str] = field(default_factory=list)
    hot_fields: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    skipped: str = ""


def extract_chunks(index_text: str, base_url: str) -> list[str]:
    """Lista bezwzględnych URL-i chunków z mapy zależności, bez duplikatów.

    `base_url` to adres aplikacji (np. `https://hack.cert.pl`), z którego zbudowany
    jest `assets/…`. Kolejność zachowana jak w mapie (Vite układa je wg trasy).
    """
    host = urlparse(base_url).netloc
    out, seen = [], set()
    for m in _CHUNK_RE.finditer(index_text):
        # Dopasowanie poprzedzone pełnym adresem obcej domeny (CDN) nie jest
        # naszym plikiem — urljoin zrobiłby z niego adres naszego hosta i tak
        # powstałby fałszywy wpis „chunk pobrany/404”.
        pre = index_text[max(0, m.start() - 60):m.start()]
        abs_host = re.findall(r"https?://([A-Za-z0-9.\-]+)/[^\s\"']*$", pre)
        if abs_host and abs_host[-1] != host:
            continue
        url = urljoin(base_url.rstrip("/") + "/", m.group(0))
        if urlparse(url).netloc != host:       # obca domena = nie dotykamy
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def api_paths(text: str) -> list[str]:
    """Ścieżki `/api/...`, także te sklejane szablonem (`${base}/api/v1/…`)."""
    out, seen = [], set()
    for m in _API_PATH_RE.finditer(text):
        p = m.group(0).rstrip(".,;:'\"`") 
        p = re.sub(r"/$", "", p)
        if len(p) < 6 or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def mine_chunks(http, base_url: str, index_text: str, max_chunks: int = 24,
                interesting: tuple[str, ...] = ()) -> dict:
    """Pobiera chunki i zwraca skonsolidowaną powierzchnię API.

    `interesting` — fragmenty nazw plików, które mają priorytet (np. `payout`, `users`,
    `view`). Puste = bierzemy w kolejności z mapy. Ten parametr istnieje, bo przy
    ograniczonym budżecie lepiej przeczytać 24 pliki o autoryzacji niż 24 o animacjach.
    """
    chunks = extract_chunks(index_text, base_url)
    if interesting:
        low = [c.lower() for c in chunks]
        first = [c for c, l in zip(chunks, low)
                 if any(k in l for k in interesting)]
        rest = [c for c in chunks if c not in first]
        chunks = first + rest

    results: list[ChunkResult] = []
    endpoints: list[str] = []
    params: list[str] = []
    hot: list[str] = []
    secrets: list[str] = []

    for url in chunks[:max_chunks]:
        try:
            r = http.get(url)
        except Exception as exc:                    # noqa: BLE001 — powód do raportu
            results.append(ChunkResult(url, 0, skipped=f"error: {type(exc).__name__}"))
            continue
        if getattr(r, "error", None):
            results.append(ChunkResult(url, 0, skipped="error"))
            continue
        body = getattr(r, "body", b"") or b""
        if len(body) > MAX_JS_BYTES:
            results.append(ChunkResult(url, len(body), skipped="too_big"))
            continue
        text = getattr(r, "text", "") or ""
        found = jsmine.mine(text, base_host=urlparse(base_url).netloc)
        eps = [f.value for f in found if f.kind == "endpoint"]
        eps += api_paths(text)
        pm = [f.value for f in found if f.kind == "param"]
        pm += [m.group(1) for m in _QUERY_RE.finditer(text)]
        hf = [f.value for f in found if f.kind == "hot_field"]
        sc = [f.value for f in found if f.kind == "secret"]

        results.append(ChunkResult(url, len(body),
                                   endpoints=_uniq(eps), params=_uniq(pm),
                                   hot_fields=_uniq(hf), secrets=_uniq(sc)))
        endpoints += eps
        params += pm
        hot += hf
        secrets += sc

    return {
        "chunks_total": len(chunks),
        "chunks_fetched": sum(1 for r in results if not r.skipped),
        "skipped": [{"url": r.url, "size": r.size, "why": r.skipped}
                    for r in results if r.skipped],
        "endpoints": _uniq(endpoints),
        "api_paths": _uniq(p for r in results for p in r.endpoints if p.startswith("/api")),
        "params": _uniq(params),
        "hot_fields": _uniq(hot),
        "secrets": _uniq(secrets),
        "per_chunk": [{"url": r.url, "size": r.size,
                       "endpoints": len(r.endpoints), "params": len(r.params)}
                      for r in results],
    }


def _uniq(seq) -> list[str]:
    out, seen = [], set()
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
