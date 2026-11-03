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
