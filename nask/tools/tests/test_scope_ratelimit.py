"""Testy scope + limitera. Uruchom: python -m pytest nask/tools/tests -q"""
import time

import pytest

from nask.tools.ratelimit import Budget, RateConfigError, TokenBucket
from nask.tools.scope import PROGRAMS, check_host, check_url, payout_for

IN = [
    ("nask.pl", "nask", "T1"),
    ("oad.nask.pl", "nask", "T1"),
    ("dataannotation.pllum.org.pl", "nask", "T2"),
    ("mwdb.cert.pl", "cert", "T1"),
    ("hack.cert.pl", "cert", "T1"),
    ("ctf.hack.cert.pl", "cert", "T2"),
    ("anything.cert.pl", "cert", "T2"),
    ("www.gov.pl", "gov", "T1"),
    ("app.komunikator.narodowy.gov.pl", "mszyfr", "T1"),
    ("eobieg.wladyslawowo.pl", "wladyslawowo", "T1"),
    ("wladyslawowo.pl", "wladyslawowo", "T2"),
]

OUT = [
    "gov.pl",                      # w scope jest TYLKO www.gov.pl
    "api.gov.pl",
    "nask.pl.evil.com",            # klasyczny suffix-trick
    "evilnask.pl",
    "bip.wladyslawowo.pl",         # jawnie wykluczone
    "lab.cert.pl",                 # jawnie wykluczone
    "moje.hack.cert.pl",           # subdomeny hack.cert.pl wykluczone
    "komunikator.narodowy.gov.pl.evil.pl",
    "example.com",
    "",
    "10.0.0.1",
    "http://nask.pl@evil.com",     # userinfo trick
]


@pytest.mark.parametrize("host,program,tier", IN)
def test_in_scope(host, program, tier):
    d = check_host(host)
    assert d.allowed, f"{host} powinno być w scope: {d.reason}"
    assert (d.program, d.tier) == (program, tier)


@pytest.mark.parametrize("host", OUT)
def test_out_of_scope(host):
    assert not check_host(host).allowed, f"{host} NIE powinno być w scope"


def test_normalization():
    assert check_host("WWW.GOV.PL.").allowed
    assert check_host("Www.Gov.Pl").program == "gov"
    assert not check_host("WWW.GOV.PL.EVIL.COM").allowed


def test_url_checks():
    assert check_url("https://www.gov.pl/web/cyfryzacja").allowed
    assert not check_url("ftp://www.gov.pl/").allowed
    assert not check_url("https://user:pass@www.gov.pl/").allowed
    assert not check_url("https://evil.com/?x=www.gov.pl").allowed


def test_payout_by_program():
    assert payout_for("mwdb.cert.pl", "krytyczny") == 20000
    assert payout_for("anything.cert.pl", "krytyczny") == 10000   # Tier 2
    assert payout_for("eobieg.wladyslawowo.pl", "krytyczny") == 4000
    assert payout_for("example.com", "krytyczny") == 0


def test_every_program_has_source_url():
    for p in PROGRAMS:
        assert p.url.startswith("https://hack.cert.pl/programs/")


def test_refuses_rate_above_regulation(tmp_path):
    with pytest.raises(RateConfigError):
        TokenBucket(rps=5.1, state_path=tmp_path / "s.json")
    with pytest.raises(RateConfigError):
        TokenBucket(rps=50, state_path=tmp_path / "s.json")


def test_allows_limit_and_below(tmp_path):
    TokenBucket(rps=5.0, state_path=tmp_path / "a.json")
    TokenBucket(rps=4.5, state_path=tmp_path / "b.json")


def test_bucket_actually_throttles(tmp_path):
    b = TokenBucket(rps=5.0, burst=1, state_path=tmp_path / "s.json")
    start = time.time()
    for _ in range(3):
        b.acquire()
    elapsed = time.time() - start
    assert elapsed >= 0.30, f"3 żądania przy 5 req/s i burst=1 trwały {elapsed:.2f}s"


def test_state_shared_between_instances(tmp_path):
    p = tmp_path / "shared.json"
    a = TokenBucket(rps=5.0, burst=1, state_path=p)
    b = TokenBucket(rps=5.0, burst=1, state_path=p)
    a.acquire()
    start = time.time()
    b.acquire()          # musi czekać: token zużyty przez a
    assert time.time() - start >= 0.15


def test_budget_hard_stops():
    bud = Budget(2)
    bud.spend()
    bud.spend()
    with pytest.raises(RuntimeError):
        bud.spend()
    assert bud.left == 0
