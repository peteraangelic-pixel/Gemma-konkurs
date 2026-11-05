"""Testy sond celowanych. Każdy test to pytanie: „czy ta odpowiedź to trafienie?”.

Najważniejsze są testy NEGATYWNE — sonda, która zgłasza wszystko, jest gorsza
niż brak sondy, bo kosztuje czas i wiarygodność u weryfikatora.
"""
import json

from nask.tools import probes
from nask.tools.probes import ProbeFinding


class R:
    def __init__(self, status=200, ctype="text/html", body="", headers=None, url=""):
        self.status, self.body, self.url = status, body.encode(), url
        self.headers = {"content-type": ctype, **(headers or {})}
        self.error = None
        self.text = body

    def __len__(self):          # dla wygody w asercjach
        return len(self.body)


class Http:
    def __init__(self, fn):
        self.fn = fn
        self.calls = []

    def get(self, url, headers=None, **kw):
        self.calls.append((url, dict(headers or {})))
        return self.fn(url, dict(headers or {}))


# --------------------------- S1: CORS ---------------------------
def test_cors_reflected_with_credentials_is_high():
    http = Http(lambda url, h: R(headers={"access-control-allow-origin": h.get("Origin", ""),
                                          "access-control-allow-credentials": "true"}))
    got = probes.probe_cors(http, "https://app.example.gov.pl")
    assert got and got[0].severity == "wysoki" and got[0].code == "S1"
    assert "14.1" in got[0].why


def test_cors_wildcard_without_creds_is_not_reported_as_hit():
    http = Http(lambda url, h: R(headers={"access-control-allow-origin": "*"}))
    got = probes.probe_cors(http, "https://www.gov.pl")
    assert all(f.severity == "niski" for f in got), [f.severity for f in got]
    assert "5.6" in got[0].why


def test_cors_no_headers_no_findings():
    http = Http(lambda url, h: R())
    assert probes.probe_cors(http, "https://nask.pl") == []


def test_cors_suffix_origin_trick_detected():
    """Naiwna walidacja „kończy się na nask.pl” przepuszcza nask.pl.evil.example."""
    http = Http(lambda url, h: R(headers={
        "access-control-allow-origin": h["Origin"],
        "access-control-allow-credentials": "true"}))
    got = probes.probe_cors(http, "https://nask.pl")
    origins = {f.raw.get("origin") for f in got}
    assert probes.SUFFIX_ORIGIN in origins


# --------------------- S2: middleware Next.js ---------------------
def test_middleware_bypass_when_status_changes():
    def fn(url, h):
        if probes.MIDDLEWARE_HEADER in h:
            return R(status=200, body="<html>panel admina</html>", url=url)
        return R(status=307, headers={"location": "/login"}, url=url)

    got = probes.probe_middleware_bypass(Http(fn), "https://oad.nask.pl")
    assert got and got[0].severity == "krytyczny"
    assert got[0].raw == {"plain": 307, "bypass": 200}


def test_middleware_no_false_positive_when_body_identical():
    same = "<html>login</html>"
    http = Http(lambda url, h: R(status=403, body=same, url=url))
    assert probes.probe_middleware_bypass(http, "https://nask.pl") == []


def test_middleware_skips_unprotected_paths():
    http = Http(lambda url, h: R(status=200, body="publiczna strona", url=url))
    assert probes.probe_middleware_bypass(http, "https://nask.pl") == []
    # brak drugiego żądania = nie marnujemy budżetu na ścieżki, które nie są chronione
    assert all(probes.MIDDLEWARE_HEADER not in h for _, h in http.calls)


# ------------------------ S3: /_next/data ------------------------
def test_next_data_with_page_props():
    payload = json.dumps({"pageProps": {"user": {"email": "a@b.c"}, "reports": [1, 2]}})

    def fn(url, h):
        if "/_next/data/" in url:
            return R(ctype="application/json", body=payload, url=url)
        return R(status=404)

    got = probes.probe_next_data(Http(fn), "https://zglos-dezinformacje.nask.pl",
                                 "abc123", ["/panel", "/dashboard"])
    assert got and "pageProps" in got[0].detail
    assert "user" in got[0].detail


def test_next_data_404_is_silent():
    http = Http(lambda url, h: R(status=404))
    assert probes.probe_next_data(http, "https://nask.pl", "abc", ["/x"]) == []


def test_next_data_without_build_id_does_nothing():
    http = Http(lambda url, h: R())
    assert probes.probe_next_data(http, "https://nask.pl", None, ["/x"]) == []
    assert http.calls == []


# -------------------------- S4: Drupal --------------------------
DRUPAL_OK = json.dumps({"data": [{"type": "user--user",
                                  "attributes": {"name": "jan", "mail": "jan@example.pl"}}]})


def test_drupal_jsonapi_exposing_user_mail_is_high():
    http = Http(lambda url, h: R(ctype="application/vnd.api+json", body=DRUPAL_OK, url=url))
    got = probes.probe_drupal_jsonapi(http, "https://dns.pl")
    assert got and got[0].severity == "wysoki"


def test_drupal_jsonapi_empty_data_is_not_a_finding():
    http = Http(lambda url, h: R(ctype="application/json", body='{"data": []}', url=url))
    assert probes.probe_drupal_jsonapi(http, "https://dns.pl") == []


def test_drupal_jsonapi_401_is_not_a_finding():
    http = Http(lambda url, h: R(status=401, ctype="application/json", body="{}"))
    assert probes.probe_drupal_jsonapi(http, "https://dns.pl") == []


# ------------------------ S5: WordPress ------------------------
WP_DRAFT = json.dumps([{"id": 7, "status": "draft",
                        "content": {"raw": "notatka wewnętrzna"}}])


def test_wordpress_raw_content_leak():
    http = Http(lambda url, h: R(ctype="application/json", body=WP_DRAFT, url=url))
    got = probes.probe_wordpress_private(http, "https://116sos.pl")
    assert got and got[0].severity == "wysoki" and "raw" in got[0].detail


def test_wordpress_public_list_alone_is_not_a_finding():
    """Publiczne posty (bez raw/status=draft) to nie wyciek."""
    public = json.dumps([{"id": 1, "status": "publish",
                          "content": {"rendered": "<p>hej</p>"}}])
    http = Http(lambda url, h: R(ctype="application/json", body=public, url=url))
    assert probes.probe_wordpress_private(http, "https://science.nask.pl") == []


# --------------------- S6: X-Original-URL ---------------------
def test_header_bypass_detected_only_when_body_differs():
    def fn(url, h):
        if h:
            return R(status=200, body="x" * 900, url=url)
        return R(status=403, body="forbidden", url=url)

    got = probes.probe_header_bypass(Http(fn), "https://www.gov.pl",
                                     paths=["/admin"])
    assert got and got[0].raw["header"] == "x-original-url"
    assert "9.3" in got[0].why


def test_header_bypass_ignores_small_identical_bodies():
    def fn(url, h):
        return R(status=200, body="ok", url=url)

    assert probes.probe_header_bypass(Http(fn), "https://www.gov.pl",
                                      paths=["/admin"]) == []


# --------------------------- run_all ---------------------------
def test_run_all_picks_probes_for_stack():
    calls = []

    def fn(url, h):
        calls.append(url)
        if "/jsonapi" in url:
            return R(ctype="application/json", body=DRUPAL_OK, url=url)
        if "/wp-json" in url:
            return R(ctype="application/json", body=WP_DRAFT, url=url)
        return R(status=404, url=url)

    drupal = probes.run_all(Http(fn), "https://dns.pl", {"tech": ["drupal"]})
    assert any(f.code == "S4" and f.host == "dns.pl" for f in drupal)
    wp = probes.run_all(Http(fn), "https://116sos.pl", {"tech": ["wordpress"]})
    assert any(f.code == "S5" for f in wp)


def test_findings_are_serialisable():
    f = ProbeFinding("S1", "h", "u", "wysoki", "t", "d", "why")
    assert json.loads(json.dumps(f.as_dict()))["code"] == "S1"


# ==========================================================================
# Testy regresyjne z PRAWDZIWEGO przebiegu nocnego (2026-11-03).
# Każdy z nich odtwarza fałszywe trafienie, które faktycznie wystąpiło.
# Bez nich poprawka byłaby wiarą, a nie dowodem.
# ==========================================================================
def test_regression_dns_pl_header_bypass_artifact():
    """`GET /admin` → 404, `GET /` z nagłówkiem → 200 (ta sama strona główna).

    Stara sonda porównywała te dwie odpowiedzi i „wykrywała obejście" 6 razy.
    Poprawiona porównuje `/` z nagłówkiem z `/` bez nagłówka — identyczne,
    więc wynik jest negatywny.
    """
    home = "h" * 51152
    not_found = "n" * 40921

    def fn(url, h):
        if url.endswith("/admin"):
            return R(status=404, body=not_found, url=url)
        return R(status=200, body=home, url=url)      # z nagłówkiem i bez: to samo

    assert probes.probe_header_bypass(Http(fn), "https://dns.pl", paths=["/admin"]) == []


def test_regression_bezpiecznewybory_waf_nonce():
    """403 (374 B) vs 403 (377 B) — WAF wstawia własny identyfikator żądania.

    Stara sonda traktowała każdą różnicę treści jako trafienie i zgłosiła to
    sześć razy jako „wysokie". Teraz różnica musi być co najmniej dwukrotna.
    """
    def fn(url, h):
        size = 377 if probes.MIDDLEWARE_HEADER in h else 374
        return R(status=403, body="b" * size, url=url)

    assert probes.probe_middleware_bypass(Http(fn), "https://bezpiecznewybory.pl",
                                          paths=["/panel"]) == []


def test_regression_116sos_public_next_data():
    """`/_next/data/.../aktualnosci.json` serwuje publiczne artykuły.

    Stara sonda zgłaszała to osiem razy jako „dane chronionej strony", bo nie
    sprawdzała, że ta sama trasa zwraca 200 także jako HTML.
    """
    payload = json.dumps({"pageProps": {"title": "Aktualności", "news": []}})

    def fn(url, h):
        if "/_next/data/" in url:
            return R(ctype="application/json", body=payload, url=url)
        return R(status=200, body="<html>publiczna</html>", url=url)

    assert probes.probe_next_data(Http(fn), "https://116sos.pl", "abc",
                                  ["/aktualnosci"]) == []


def test_real_bypass_still_detected_after_fix():
    """Poprawka nie może zabić prawdziwego sygnału: 307 na login → 200 z nagłówkiem."""
    def fn(url, h):
        if probes.MIDDLEWARE_HEADER in h:
            return R(status=200, body="<html>panel</html>" * 50, url=url)
        return R(status=307, headers={"location": "/login"}, body="", url=url)

    got = probes.probe_middleware_bypass(Http(fn), "https://oad.nask.pl", paths=["/panel"])
    assert got and got[0].severity == "krytyczny"


# ------------------------ S7: autoryzacja API ------------------------
def test_api_authz_flags_open_user_endpoint():
    body = json.dumps({"id": 1, "email": "ktos@example.pl", "payout": {"iban": "PL00"}})
    http = Http(lambda url, h: R(ctype="application/json", body=body, url=url))
    got = probes.probe_api_authz(http, "https://hack.cert.pl",
                                 ["/users/${e.userId}/email", "/users/$userId/view"])
    assert got and got[0].severity == "krytyczny"
    assert "email" in got[0].raw["fields"]


def test_api_authz_401_is_negative_and_only_two_ids():
    http = Http(lambda url, h: R(status=401, ctype="application/json", body="{}", url=url))
    assert probes.probe_api_authz(http, "https://hack.cert.pl",
                                  ["/users/$userId/view"]) == []
    # Dwa identyfikatory × dwa prefiksy (`""` i `/api/v1`) = maksymalnie 4 żądania.
    # Żadna pętla po zakresie ID — to jest sedno ograniczenia.
    assert len(http.calls) <= 4, f"zbyt wiele żądań: {http.calls}"
    ids = {part for u, _ in http.calls for part in u.split("/") if part in {"1", "2"}}
    assert ids <= {"1", "2"}, f"odpytano inne identyfikatory: {ids}"


def test_api_authz_ignores_public_json_without_sensitive_fields():
    body = json.dumps({"id": 1, "login": "jan", "capabilities": []})
    http = Http(lambda url, h: R(ctype="application/json", body=body, url=url))
    assert probes.probe_api_authz(http, "https://hack.cert.pl",
                                  ["/users/$userId/view"]) == []


def test_api_authz_does_not_iterate_range():
    """Reguła: brak pętli po identyfikatorach. Dwa na szablon, koniec."""
    body = json.dumps({"email": "x@y.z"})
    http = Http(lambda url, h: R(ctype="application/json", body=body, url=url))
    probes.probe_api_authz(http, "https://hack.cert.pl",
                           ["/users/$userId/email", "/users/$id/view"])
    assert len(http.calls) <= 4, f"zbyt wiele żądań: {http.calls}"


# ------------------------ S8: wersja aplikacji ------------------------
def test_server_version_older_than_fix_points_at_xss():
    body = json.dumps({"server_version": "2.19.3", "is_authenticated": False})
    http = Http(lambda url, h: R(ctype="application/json", body=body, url=url))
    got = probes.probe_server_version(http, "https://mwdb.cert.pl")
    assert got and got[0].raw["older_than_fix"] is True
    assert "NIE jest wdrożona" in got[0].detail


def test_server_version_after_fix_closes_topic():
    body = json.dumps({"server_version": "2.20.0"})
    http = Http(lambda url, h: R(ctype="application/json", body=body, url=url))
    got = probes.probe_server_version(http, "https://mwdb.cert.pl")
    assert got and got[0].raw["older_than_fix"] is False
    assert "zamknięty" in got[0].detail


def test_server_version_absent_is_silent():
    http = Http(lambda url, h: R(status=404, body="nope", url=url))
    assert probes.probe_server_version(http, "https://nask.pl") == []


# ==========================================================================
# Regresje z przebiegu 3 (2026-11-04) — sonda S6 myliła utwardzenie z obejściem.
# ==========================================================================
def test_regression_moje_cert_pl_header_causes_403():
    """`x-original-url` na moje.cert.pl → 403 (Cloudflare), nie obejście.

    Przebieg 3 zgłosił to 6 razy jako „średnie". 200 → 403 to SPADEK dostępu.
    """
    home = "h" * 31158

    def fn(url, h):
        if h:
            return R(status=403, body="b" * 4542, url=url)
        if url.endswith("/"):
            return R(status=200, body=home, url=url)
        return R(status=404, body="n" * 1000, url=url)

    got = probes.probe_header_bypass(Http(fn), "https://moje.cert.pl", paths=["/panel"])
    assert got and all(f.severity == "niski" for f in got), [f.severity for f in got]
    assert "spadł" in got[0].detail


def test_regression_incydent_rate_limit_is_not_bypass():
    """`x-forwarded-prefix` na incydent.cert.pl → 429. Rate-limit to nie obejście."""
    def fn(url, h):
        if h:
            return R(status=429, body="r" * 5635, url=url)
        if url.endswith("/"):
            return R(status=200, body="h" * 2743, url=url)
        return R(status=404, body="n" * 100, url=url)

    got = probes.probe_header_bypass(Http(fn), "https://incydent.cert.pl", paths=["/moje"])
    assert got and got[0].severity == "niski"


def test_header_real_bypass_is_still_high():
    """Prawdziwe obejście: kontrolnie 403 na `/`, z nagłówkiem 200 innej treści."""
    def fn(url, h):
        if h:
            return R(status=200, body="<html>panel administratora</html>", url=url)
        return R(status=403, body="forbidden", url=url)

    got = probes.probe_header_bypass(Http(fn), "https://www.gov.pl", paths=["/admin"])
    assert got and got[0].severity == "wysoki"


# ------------------------ S9: Wagtail / Django ------------------------
WAGTAIL_DOCS = json.dumps({
    "meta": {"total_count": 3},
    "items": [
        {"id": 11, "title": "Umowa ramowa 2025 (wersja robocza)",
         "download_url": "/documents/11/umowa.pdf", "meta": {"draft": True}},
        {"id": 12, "title": "Regulamin", "download_url": "/documents/12/reg.pdf",
         "meta": {"draft": False}},
    ],
})


def test_wagtail_documents_leak_is_high():
    http = Http(lambda url, h: R(ctype="application/json", body=WAGTAIL_DOCS, url=url))
    got = probes.probe_wagtail(http, "https://moje.cert.pl")
    docs = [f for f in got if "documents" in f.url]
    assert docs and docs[0].severity == "wysoki"
    assert docs[0].raw["looks_private"] is True
    assert "Umowa ramowa" in docs[0].detail


def test_wagtail_empty_items_is_negative():
    body = json.dumps({"meta": {"total_count": 0}, "items": []})
    http = Http(lambda url, h: R(ctype="application/json", body=body, url=url))
    assert probes.probe_wagtail(http, "https://nask.pl") == []


def test_wagtail_404_is_negative():
    http = Http(lambda url, h: R(status=404, body="nope", url=url))
    assert probes.probe_wagtail(http, "https://science.nask.pl") == []


def test_wagtail_html_response_is_ignored():
    """Strona HTML na /api/v2/pages/ to nie API, tylko catch-all — nie zgłaszamy."""
    http = Http(lambda url, h: R(ctype="text/html", body="<html>index</html>", url=url))
    assert probes.probe_wagtail(http, "https://nask.pl") == []


# ---------------- S10 (recon): chunki leniwie ładowane ----------------
# Po co te testy: pierwsza wersja składała URL jako `…js.js`, bo doklejałem
# rozszerzenie do dopasowania, które już je zawierało. Test na dokładny URL
# łapie to od razu, a przebieg sieciowy już nie — on by po prostu dostał 404
# i „nie znalazł nic", co wygląda identycznie jak „nic nie ma".

def _chunks():
    from nask.tools import chunks
    return chunks


def test_chunk_extraction_builds_exact_url():
    c = _chunks()
    hint = 'm.f=["assets/payout-KEUQA3LX.js","assets/users-B4gUxef1.js"]'
    got = c.extract_chunks(hint, "https://hack.cert.pl")
    assert got == ["https://hack.cert.pl/assets/payout-KEUQA3LX.js",
                   "https://hack.cert.pl/assets/users-B4gUxef1.js"], got


def test_chunk_extraction_dedupes_and_caps_by_caller():
    c = _chunks()
    hint = '"assets/a-12345678.js" "assets/a-12345678.js" "assets/b-87654321.js"'
    assert c.extract_chunks(hint, "https://x.example") == [
        "https://x.example/assets/a-12345678.js",
        "https://x.example/assets/b-87654321.js"]


def test_chunk_extraction_ignores_other_hosts():
    """/assets/… z obcej domeny nie może wejść: to już nie jest nasz zakres."""
    c = _chunks()
    assert c.extract_chunks('"https://cdn.evil.example/assets/x-12345678.js"',
                            "https://hack.cert.pl") == []


def test_api_paths_catch_template_concatenation():
    c = _chunks()
    src = 'const u=`${e}/api/v1/users/${t}/role`;fetch(`/api/v1/reports/${a}/internal-notes`)'
    got = c.api_paths(src)
    assert "/api/v1/users/${t}/role" in got, got
    assert any(p.startswith("/api/v1/reports/") for p in got), got


def test_mine_chunks_collects_and_marks_skipped():
    c = _chunks()
    idx = 'm.f=["assets/payout-AAAABBBB.js","assets/big-CCCCDDDD.js"]'
    js = 'fetch("/api/v1/payout/export?editionId=1&userId=2")'

    class HR:
        def __init__(self, body=b"", err=None):
            self.body, self.error, self.text = body, err, body.decode() if body else ""

    class H:
        def __init__(self, big):
            self.big = big

        def get(self, url):
            return HR(body=b"x" * (2_000_000 if self.big else 1)) if not self.big else HR(b"x" * 2_000_000)

    # normalny chunk: dostaje kod, reszta duża → skipped=too_big
    class H2:
        def get(self, url):
            if "payout" in url:
                return HR(body=js.encode())
            return HR(body=b"y" * 1_000_000)

    got = c.mine_chunks(H2(), "https://hack.cert.pl", idx)
    # Jeden plik realnie przeczytany, drugi za duży — i to MUSI być w wyniku,
    # bo brak wpisu nie może znaczyć „sprawdzone i czyste”.
    assert got["chunks_total"] == 2 and got["chunks_fetched"] == 1
    assert [s["why"] for s in got["skipped"]] == ["too_big"], got["skipped"]
    assert "/api/v1/payout/export" in got["api_paths"], got["api_paths"]
    assert "editionId" in got["params"] and "userId" in got["params"]


def test_mine_chunks_prioritises_interesting_names():
    """"Przy 24 żądaniach lepiej przeczytać payout niż animacje."""
    c = _chunks()
    idx = ('m.f=["assets/animations-AAAA1111.js","assets/payout-BBBB2222.js"]')
    order = []

    class H:
        def get(self, url):
            order.append(url)
            class R:
                body, error, text = b"x", None, "x"
            return R()

    c.mine_chunks(H(), "https://hack.cert.pl", idx, max_chunks=1,
                  interesting=("payout",))
    assert order and "payout" in order[0]


def test_mine_chunks_never_exceeds_max_chunks():
    c = _chunks()
    idx = " ".join(f'"assets/c{i}-1234567{i}.js"' for i in range(9))
    calls = []

    class H:
        def get(self, url):
            calls.append(url)
            class R:
                body, error, text = b"x", None, "x"
            return R()

    c.mine_chunks(H(), "https://hack.cert.pl", idx, max_chunks=3)
    assert len(calls) == 3, calls
