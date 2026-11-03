"""Test end-to-end na PRAWDZIWYM HTTP, ale do serwera na 127.0.0.1.

Po co, skoro reszta testów używa podstawionych odpowiedzi: bo tam nie sprawdzam
ani `urllib`, ani logowania dowodów, ani dekodowania gzip. Ten test przechodzi
całą drogę — żądanie, nagłówki, zapis do JSONL — tylko cel jest lokalny.

Uwaga na scope: `GuardedFetcher` ODMÓWIŁBY 127.0.0.1 (i słusznie). Dlatego
podmieniamy wyłącznie `check()`. To jest jedyne miejsce w repo, gdzie kontrola
zakresu jest wyłączona, i jest to test, nie narzędzie.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nask.tools.crawl import Crawler
from nask.tools.fetch import GuardedFetcher
from nask.tools.scope import Decision

PAGES = {
    "/": b'<html><head><title>Test App</title></head><body><a href="/x">x</a></body></html>',
    "/api/server": b'{"server_version":"2.20.0","is_authenticated":false}',
    "/robots.txt": b"User-agent: *\nDisallow: /admin\n",
    "/admin": b"<html><title>403</title>Forbidden</html>",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):                                    # noqa: N802
        body = PAGES.get(self.path)
        if body is None:
            body = b"<html><title>404</title>nie ma</html>"
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            self.send_response(200 if self.path != "/admin" else 403)
            ctype = "application/json" if self.path == "/api/server" else "text/plain"
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):                           # cisza w testach
        pass


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


class LocalFetcher(GuardedFetcher):
    def check(self, url: str) -> Decision:               # test: tylko loopback
        assert "127.0.0.1" in url, f"test próbował wyjść w sieć: {url}"
        return Decision(allowed=True, host="127.0.0.1", program="test",
                        tier="T1", reason="loopback w teście")


def test_full_pipeline_over_real_http(server, tmp_path):
    ev = tmp_path / "evidence.jsonl"
    fetcher = LocalFetcher(rps=5.0, max_requests=50, evidence_path=ev)
    crawler = Crawler(fetcher)

    base = crawler.baseline(server)
    assert base.ok and base.status == 404

    hits = crawler.probe_paths(server, base,
                               paths=["api/server", "robots.txt", "admin"])
    urls = {h.url: h for h in hits}
    api_hit = urls[server + "/api/server"]
    assert api_hit.kind == "json" and "2.20.0" in api_hit.evidence
    assert urls[server + "/admin"].kind == "auth-wall"
    assert urls[server + "/robots.txt"].kind == "non-html"

    rows = [json.loads(line) for line in ev.read_text().splitlines()]
    assert len(rows) == 4
    assert all(r["sha256"] and r["status"] for r in rows)
    assert any(r["url"].endswith("/api/server") and r["status"] == 200 for r in rows)


def test_rate_limit_is_respected_in_practice(server, tmp_path):
    """5 żądań przy rps=5 i burst=1 nie może trwać krócej niż ~0,8 s."""
    import time
    fetcher = LocalFetcher(rps=5.0, max_requests=10, evidence_path=tmp_path / "e.jsonl")
    fetcher.bucket = type(fetcher.bucket)(rps=5.0, burst=1,
                                          state_path=tmp_path / "rl.json")
    t0 = time.time()
    for _ in range(5):
        fetcher.get(server + "/")
    assert time.time() - t0 >= 0.7
