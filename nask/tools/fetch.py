"""Jedno żądanie HTTP, które nie może wyjść poza scope i nie może przekroczyć 5 req/s.

Wszystko, co w tym projekcie dotyka sieci, przechodzi przez `get()`. Dzięki temu
limit szybkości i kontrola zakresu są w jednym miejscu, a nie "w każdym narzędziu
osobno, może ktoś pamiętał".

Każde żądanie zapisuje dowód do dziennika JSONL: czas, pełny URL, status, nagłówki,
sha256 treści. Bez tego nie da się napisać PoC (regulamin §8 poz. 14.1).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from .credentials import headers_for
from .ratelimit import Budget, TokenBucket
from .scope import Decision, check_url

DEFAULT_UA = ("nask-bugbounty-research/1.0 (responsible disclosure; "
              "kontakt: podaj-swoj-email@example.com)")


@dataclass
class Response:
    url: str
    status: int
    headers: dict
    body: bytes
    elapsed_s: float
    sha256: str
    error: str | None = None

    @property
    def text(self) -> str:
        data = self.body
        if self.headers.get("content-encoding", "").lower() == "gzip":
            try:
                data = gzip.decompress(data)
            except OSError:
                pass
        return data.decode("utf-8", errors="replace")


class ScopeViolation(RuntimeError):
    pass


class GuardedFetcher:
    def __init__(self, rps: float = 4.5, max_requests: int = 60,
                 evidence_path: str | Path = "nask/findings/evidence.jsonl",
                 user_agent: str = DEFAULT_UA, timeout: float = 15.0,
                 dry_run: bool = False, use_credentials: bool = False):
        self.bucket = TokenBucket(rps)
        self.budget = Budget(max_requests)
        self.evidence_path = Path(evidence_path)
        self.user_agent = user_agent
        self.timeout = timeout
        self.dry_run = dry_run
        # Domyślnie NIE dokładamy poświadczeń. Włącza się je jawnie, bo
        # uwierzytelniony ruch to zupełnie inna kategoria testów (§6 pkt 1)
        # i nie może się włączyć przez przypadek.
        self.use_credentials = use_credentials

    def check(self, url: str) -> Decision:
        return check_url(url)

    def get(self, url: str, headers: dict | None = None,
            method: str = "GET", data: bytes | None = None) -> Response:
        decision = self.check(url)
        if not decision.allowed:
            raise ScopeViolation(f"ODMOWA: {url} → {decision.reason}")
        if method not in ("GET", "HEAD", "POST"):
            raise ScopeViolation(f"metoda {method} nieobsługiwana w tym narzędziu")
        if self.dry_run:
            return Response(url, 0, {}, b"", 0.0, "", error="dry-run: nie wysłano")

        self.budget.spend()
        self.bucket.acquire()

        req = urllib.request.Request(url, method=method, data=data)
        req.add_header("User-Agent", self.user_agent)
        req.add_header("Accept", "*/*")
        # Poświadczenia ZAWSZE przed nagłówkami wywołującego, żeby jawne
        # nagłówki w teście mogły je nadpisać, a nie odwrotnie.
        if self.use_credentials:
            for k, v in headers_for(decision.host).items():
                req.add_header(k, v)
        for k, v in (headers or {}).items():
            req.add_header(k, v)

        started = time.time()
        status, hdrs, body, err = 0, {}, b"", None
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                body = resp.read(2_000_000)
        except urllib.error.HTTPError as exc:          # 4xx/5xx też jest dowodem
            status = exc.code
            hdrs = {k.lower(): v for k, v in (exc.headers or {}).items()}
            body = exc.read(2_000_000) if hasattr(exc, "read") else b""
        except Exception as exc:                        # noqa: BLE001 — zapisujemy powód
            err = f"{type(exc).__name__}: {exc}"

        elapsed = time.time() - started
        digest = hashlib.sha256(body).hexdigest()
        resp = Response(url, status, hdrs, body, elapsed, digest, err)
        self._record(decision, method, resp)
        return resp

    def _record(self, decision: Decision, method: str, resp: Response) -> None:
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "method": method,
            "url": resp.url,
            "program": decision.program,
            "tier": decision.tier,
            "status": resp.status,
            "elapsed_s": round(resp.elapsed_s, 3),
            "sha256": resp.sha256,
            "bytes": len(resp.body),
            "headers": {k: v for k, v in resp.headers.items()
                        if k in ("content-type", "server", "location", "content-length",
                                 "x-powered-by", "set-cookie", "allow", "x-azure-ref")},
            "error": resp.error,
        }
        with open(self.evidence_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
