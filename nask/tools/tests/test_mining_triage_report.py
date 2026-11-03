"""Testy ekstraktora JS, triage'u EV, generatora raportu i guarded fetch."""
import json

import pytest

from nask.tools.fetch import GuardedFetcher, ScopeViolation
from nask.tools.jsmine import mine, rank
from nask.tools.report import Report
from nask.tools.triage import EXCLUDED_CLASSES, build, rank as rank_h, table, to_json

BUNDLE = r"""
window.__NEXT_DATA__ = {apiBase:"https://app.example.gov.pl/api/v1"};
fetch("/api/v1/messages/" + id).then(...)
const q = "/api/users?userId=42&role=admin";
xhr.open("GET", "https://files.example.gov.pl/upload/abc");
const cfg = {token:"abcdef1234567890", internal:"10.42.0.7"};
payload = {"userId": 5, "role": "admin", "is_verified": true}
//# sourceMappingURL=main.abc123.js.map
"""


def test_extracts_endpoints_and_fields():
    got = mine(BUNDLE, base_host="app.example.gov.pl")
    kinds = {f.kind for f in got}
    assert "endpoint" in kinds and "hot_field" in kinds
    values = {f.value for f in got}
    assert "/api/v1/messages/" in values
    assert "userId" in values and "role" in values
    assert any(f.kind == "internal_ip" for f in got)
    assert any(f.kind == "tech" and f.value == "next.js" for f in got)


def test_deduplicates():
    got = mine('"/api/x" "/api/x" "/api/x"', base_host="a.gov.pl")
    assert sum(1 for f in got if f.value == "/api/x") == 1


def test_rank_puts_high_value_first():
    got = rank(mine(BUNDLE, base_host="app.example.gov.pl"))
    assert got[0].kind in ("hot_field", "endpoint")


def test_foreign_domain_flagged_as_url():
    got = mine('"https://cdn.other.com/lib.js"', base_host="app.example.gov.pl")
    assert any(f.kind == "url" and "other.com" in f.value for f in got)


def test_payout_follows_program_table():
    h = build("mwdb.cert.pl", "04-sqli", days=3)
    assert h.tier == "T1" and h.payout == 20000
    w = build("wladyslawowo.pl", "04-sqli", days=3)
    assert w.tier == "T2" and w.payout == 2000


def test_out_of_scope_rejected():
    with pytest.raises(ValueError):
        build("bip.wladyslawowo.pl", "09-idor-bac", days=1)
    with pytest.raises(ValueError):
        build("gov.pl", "09-idor-bac", days=1)


def test_excluded_class_rejected():
    with pytest.raises(ValueError):
        build("nask.pl", "subdomain-takeover-bez-poc", days=1)
    assert "dos" in EXCLUDED_CLASSES


def test_ev_per_day_ordering():
    slow = build("www.gov.pl", "09-idor-bac", days=20, p_confirm=0.2)
    fast = build("wladyslawowo.pl", "09-idor-bac", days=1, p_confirm=0.2)
    assert rank_h([slow, fast])[0] is fast
    assert fast.ev < slow.ev


def test_serialisation_and_table():
    h = [build("dns.pl", "12-api", days=2), build("cert.pl", "08-xss", days=1)]
    assert json.loads(to_json(h))[0]["host"] in {"dns.pl", "cert.pl"}
    txt = table(h)
    assert "host" in txt and "EV" in txt


def _report(tmp_path, **over):
    ev = tmp_path / "ev.jsonl"
    ev.write_text('{"url":"https://mwdb.cert.pl/api/object/1","status":200}\n')
    base = dict(
        title="IDOR w API obiektów", host="mwdb.cert.pl", program="cert", tier="T1",
        cls="09-idor-bac", cvss="8.1", summary="Skrót.",
        impact="Odczyt obiektów innego użytkownika — dane próbek złośliwego oprogramowania.",
        steps="1. Utwórz konto A i B.\n2. Zaloguj się jako B, pobierz /api/object/<id_A>.\n"
              "3. Serwer zwraca obiekt A mimo braku uprawnień.\n4. Powtórz dla 3 identyfikatorów.",
        evidence_path=str(ev), fix="Dodaj sprawdzenie właściciela w widoku obiektu.",
    )
    base.update(over)
    return Report(**base)


def test_complete_report_renders(tmp_path):
    out = _report(tmp_path).render()
    assert "SHA-256 dowodów" in out and "mwdb.cert.pl" in out
    assert "- [ ]" in out


def test_refuses_without_evidence_file(tmp_path):
    r = _report(tmp_path, evidence_path=str(tmp_path / "brak.jsonl"))
    with pytest.raises(ValueError) as exc:
        r.render()
    assert "nie istnieje" in str(exc.value)


def test_refuses_short_steps_and_impact(tmp_path):
    r = _report(tmp_path, steps="1. zrób", impact="dużo")
    gaps = r.missing()
    assert any("steps" in g for g in gaps) and any("impact" in g for g in gaps)


def test_scope_violation_blocks_request(tmp_path):
    f = GuardedFetcher(max_requests=1, evidence_path=tmp_path / "ev.jsonl")
    with pytest.raises(ScopeViolation):
        f.get("https://example.com/")
    with pytest.raises(ScopeViolation):
        f.get("https://gov.pl/")


def test_dry_run_sends_nothing_but_validates(tmp_path):
    f = GuardedFetcher(max_requests=1, evidence_path=tmp_path / "ev.jsonl", dry_run=True)
    resp = f.get("https://www.gov.pl/")
    assert resp.error and "dry-run" in resp.error
    assert not (tmp_path / "ev.jsonl").exists()
    assert f.budget.left == 1
