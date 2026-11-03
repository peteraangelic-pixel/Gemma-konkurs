"""Testy: wyłączenie programu Władysławowo + poświadczenia z sekretów.

Najważniejszy test w tym pliku to `test_credentials_never_reach_evidence` —
bo wyciek ciasteczka do dziennika dowodów to jedyny błąd w tym repo, który
mógłby zaszkodzić użytkownikowi, a nie tylko zepsuć wynik.
"""
import json
import os

import pytest

from nask.tools import credentials as cred
from nask.tools.fetch import GuardedFetcher, ScopeViolation
from nask.tools.scope import PROGRAMS, check_host


# --- Władysławowo: program wyłączony decyzją użytkownika -------------------

@pytest.mark.parametrize("host", [
    "eobieg.wladyslawowo.pl", "wladyslawowo.pl", "cciod.wladyslawowo.pl",
])
def test_disabled_program_refuses(host):
    d = check_host(host)
    assert not d.allowed
    assert d.tier == "DISABLED", "powinno być oznaczone jako wyłączone, nie 'poza scope'"
    assert "wyłączony" in d.reason


def test_disabled_program_still_documented():
    wl = next(p for p in PROGRAMS if p.slug == "wladyslawowo")
    assert wl.enabled is False
    assert wl.tier1 == ("eobieg.wladyslawowo.pl",), "dane scope zostają jako fakt z regulaminu"


def test_other_programs_still_enabled():
    for slug in ("nask", "cert", "gov", "mszyfr"):
        assert next(p for p in PROGRAMS if p.slug == slug).enabled is True
    assert check_host("mwdb.cert.pl").allowed


def test_triage_refuses_disabled_program():
    from nask.tools.triage import build
    with pytest.raises(ValueError):
        build("eobieg.wladyslawowo.pl", "09-idor-bac", days=1)


# --- Poświadczenia ---------------------------------------------------------

def test_env_key_names():
    # Nazwy sekretów GitHub: bez kropek i myślników, bo te znaki są w nazwach
    # sekretów niedozwolone (tylko litery, cyfry i _, nie może zaczynać się od cyfry).
    assert cred.env_key("mwdb.cert.pl") == "NASK_COOKIE_MWDBCERTPL"
    assert cred.env_key("zglos-dezinformacje.nask.pl", "token") == \
        "NASK_TOKEN_ZGLOSDEZINFORMACJENASKPL"


def test_no_secret_means_no_header(monkeypatch):
    monkeypatch.delenv("NASK_COOKIE_MWDBCERTPL", raising=False)
    assert cred.headers_for("mwdb.cert.pl") == {}


def test_cookie_from_env(monkeypatch):
    monkeypatch.setenv("NASK_COOKIE_MWDBCERTPL", "session=abc; csrf=xyz")
    assert cred.headers_for("mwdb.cert.pl") == {"Cookie": "session=abc; csrf=xyz"}


def test_token_header_overrides_cookie(monkeypatch):
    monkeypatch.setenv("NASK_COOKIE_MWDBCERTPL", "session=abc")
    monkeypatch.setenv("NASK_TOKEN_MWDBCERTPL", "Authorization: Bearer t0k3n")
    got = cred.headers_for("mwdb.cert.pl")
    assert got["Authorization"] == "Bearer t0k3n"


def test_host_outside_allowlist_gets_nothing(monkeypatch):
    # GITHUB_TOKEN ustawiony przypadkiem nie może wyciec do celu w scope.
    monkeypatch.setenv("NASK_COOKIE_EVILCOM", "session=abcd1234")
    assert cred.headers_for("evil.com") == {}
    assert cred.headers_for("mwdb.cert.pl") == {}


def test_audit_never_returns_values(monkeypatch):
    monkeypatch.setenv("NASK_COOKIE_MWDBCERTPL", "session=SECRETVALUE")
    rows = cred.audit()
    assert ("mwdbcertpl", "cookie", "ustawiony") in rows
    assert "SECRETVALUE" not in repr(rows)


def test_credentials_never_reach_evidence(tmp_path, monkeypatch):
    """Poświadczenie w nagłówku żądania NIE MOŻE trafić do evidence.jsonl."""
    monkeypatch.setenv("NASK_COOKIE_MWDBCERTPL", "session=SUPERSECRET")
    ev = tmp_path / "ev.jsonl"

    class FakeResp:
        status = 200
        headers = {"content-type": "text/html"}

        def read(self, n):
            return b"<html>ok</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResp())
    f = GuardedFetcher(max_requests=1, evidence_path=ev, use_credentials=True)
    f.get("https://mwdb.cert.pl/")

    raw = ev.read_text()
    assert "SUPERSECRET" not in raw
    row = json.loads(raw.strip())
    assert "cookie" not in row["headers"]
    assert row["status"] == 200


def test_credentials_off_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("NASK_COOKIE_MWDBCERTPL", "session=SUPERSECRET")
    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["cookie"] = req.get_header("Cookie")
        raise RuntimeError("stop")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    GuardedFetcher(max_requests=1, evidence_path=tmp_path / "e.jsonl").get(
        "https://mwdb.cert.pl/")
    assert seen["cookie"] is None


def test_plaintext_credential_detector(tmp_path):
    # Wartość sklejana w runtime, żeby TEN plik nie był "wyciekiem" dla własnego
    # detektora. Test ma sprawdzić plik w tmp, a nie siebie.
    fake = "session=" + "0123456789abcdef" * 2
    (tmp_path / "leak.py").write_text(f'COOKIE = "{fake}"\n')
    (tmp_path / "clean.py").write_text('COOKIE = os.environ["NASK_COOKIE_X"]\n')
    hits = cred.assert_no_plaintext_credentials(tmp_path)
    assert any("leak.py" in h for h in hits)
    assert not any("clean.py" in h for h in hits)


def test_repo_is_clean():
    from nask.tools.credentials import assert_no_plaintext_credentials
    assert assert_no_plaintext_credentials("nask") == []


def test_recon_targets_all_in_scope():
    from nask.recon import TARGETS
    from nask.tools.scope import check_host
    for url in TARGETS:
        host = url.split("/")[2]
        assert check_host(host).allowed, f"{url} nie jest w scope"


def test_recon_skips_disabled_program():
    from nask.tools.scope import check_host
    assert not check_host("eobieg.wladyslawowo.pl").allowed
