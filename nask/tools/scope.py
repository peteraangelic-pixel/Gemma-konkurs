"""Zakres (scope) programów hack.cert.pl — dane wpisane ze stron edycji 11/2026.

ŹRÓDŁA (odczytane 2026-11-03, nie z pamięci):
  https://hack.cert.pl/programs/nask-pib/nask/editions/1
  https://hack.cert.pl/programs/cert-polska/bug-bounty-cert-polska/editions/1
  https://hack.cert.pl/programs/centralny-osrodek-informatyki/portal-gov-pl/editions/1
  https://hack.cert.pl/programs/mszyfr/mszyfr/editions/1
  https://hack.cert.pl/programs/cciod-wladyslawowo/bug-bounty-gmina-wladyslawowo/editions/1

Ten plik jest JEDYNYM źródłem prawdy o scope w tym repo. Jeśli platforma zmieni
zakres, poprawiamy tutaj — a nie w skryptach, które mają wtedy odmówić startu.

Zasada: nieznany host = ODMOWA. Domyślne zachowanie musi być bezpieczne, bo
literówka w nazwie domeny to nie "brak nagrody", a problem prawny. Program
w scope platformy, ale wyłączony w warsztacie (`enabled=False`) = też ODMOWA:
narzędzie ma odmówić, a nie "może jednak spróbuje".
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlsplit

MAX_RPS = 5.0          # regulamin §6 pkt 2 — twardy limit platformy
SAFE_RPS = 4.5         # nasz zapas, żeby nie trafić w sufit

PAYOUTS_PL = {
    "T1": {"niski": 600, "sredni": 4000, "wysoki": 9000, "krytyczny": 20000},
    "T2": {"niski": 300, "sredni": 2000, "wysoki": 4500, "krytyczny": 10000},
}
PAYOUTS_WLADYSLAWOWO = {
    "T1": {"niski": 200, "sredni": 1000, "wysoki": 2000, "krytyczny": 4000},
    "T2": {"niski": 100, "sredni": 500, "wysoki": 1000, "krytyczny": 2000},
}


@dataclass(frozen=True)
class Program:
    slug: str
    name: str
    url: str
    tier1: tuple[str, ...]
    tier2: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    payouts: dict = field(default_factory=lambda: PAYOUTS_PL)
    notes: str = ""
    # Program istnieje na platformie, ale my go NIE testujemy. Decyzja użytkownika,
    # nie moja: nie usuwam danych ze scope (są faktami z regulaminu), tylko zamykam
    # drogę do wysłania tam żądania. `check_host` odmawia, więc żadne narzędzie
    # w tym repo nie dotknie wyłączonego programu przez pomyłkę.
    enabled: bool = True

    def tier_of(self, host: str) -> str | None:
        """Kolejność ma znaczenie — dokładnie tak, jak w regulaminie.

        1. Wpis WPROST (bez gwiazdki) wygrywa ze wszystkim. Dlatego
           `hack.cert.pl` jest w T1 i `ctf.hack.cert.pl` w T2, mimo że
           wykluczenie `*.hack.cert.pl` obejmuje ich sąsiedztwo.
        2. Dopiero potem wykluczenia — łapią to, co nie zostało wpisane wprost.
        3. Na końcu wpisy z gwiazdką (subdomeny).

        Bez tej kolejności `*.hack.cert.pl` blokowało sam `hack.cert.pl`
        i `ctf.hack.cert.pl` — czyli platformę, na której składamy zgłoszenia.
        """
        for rule, tier in (*((r, "T1") for r in self.tier1),
                           *((r, "T2") for r in self.tier2)):
            if not rule.startswith("*.") and host == rule:
                return tier
        for rule in self.exclude:
            if _matches(rule, host):
                return "EXCLUDED"
        for rule in self.tier1:
            if rule.startswith("*.") and _matches(rule, host):
                return "T1"
        for rule in self.tier2:
            if rule.startswith("*.") and _matches(rule, host):
                return "T2"
        return None

    def payout(self, tier: str, severity: str) -> int:
        return self.payouts.get(tier, {}).get(severity, 0)


PROGRAMS: tuple[Program, ...] = (
    Program(
        slug="nask",
        name="NASK - PIB",
        url="https://hack.cert.pl/programs/nask-pib/nask/editions/1",
        tier1=("nask.pl", "dyzurnet.pl", "dns.pl", "oad.nask.pl",
               "zglos-dezinformacje.nask.pl"),
        tier2=("bezpiecznymiesiac.pl", "secure.edu.pl", "bezpiecznewybory.pl",
               "116sos.pl", "pllum.org.pl", "science.nask.pl",
               "dataannotation.pllum.org.pl"),
        notes="Tylko systemy dostępne bezpośrednio z internetu, bez VPN i kont domenowych.",
    ),
    Program(
        slug="cert",
        name="CERT Polska",
        url="https://hack.cert.pl/programs/cert-polska/bug-bounty-cert-polska/editions/1",
        tier1=("cert.pl", "m.cert.pl", "incydent.cert.pl", "moje.cert.pl",
               "n6portal.cert.pl", "mwdb.cert.pl", "hack.cert.pl"),
        tier2=("*.cert.pl", "ctf.hack.cert.pl"),
        exclude=("*.hack.cert.pl", "*.lab.cert.pl"),
        notes="hack.cert.pl jest w scope, jego subdomeny NIE — poza ctf.hack.cert.pl.",
    ),
    Program(
        slug="gov",
        name="Portal Gov.pl (COI)",
        url="https://hack.cert.pl/programs/centralny-osrodek-informatyki/portal-gov-pl/editions/1",
        tier1=("www.gov.pl",),
        notes="W scope jest WYŁĄCZNIE www.gov.pl — nie gov.pl i nie inne subdomeny.",
    ),
    Program(
        slug="mszyfr",
        name="mSzyfr",
        url="https://hack.cert.pl/programs/mszyfr/mszyfr/editions/1",
        tier1=("*.komunikator.narodowy.gov.pl", "komunikator.narodowy.gov.pl"),
        notes="Apex dopisany świadomie: strona podaje '\\*.komunikator...', a brak "
              "apexu w scope byłby niespójny. Przy pierwszym raporcie zapytać "
              "organizatora, jeśli luka jest na samym apexie.",
    ),
    Program(
        slug="wladyslawowo",
        name="Gmina Władysławowo (CCIOD)",
        url="https://hack.cert.pl/programs/cciod-wladyslawowo/bug-bounty-gmina-wladyslawowo/editions/1",
        tier1=("eobieg.wladyslawowo.pl",),
        tier2=("wladyslawowo.pl", "cciod.wladyslawowo.pl"),
        exclude=("bip.wladyslawowo.pl",),
        payouts=PAYOUTS_WLADYSLAWOWO,
        notes="WYŁĄCZONY z warsztatu 2026-11-03 (decyzja użytkownika: szkoda czasu). "
              "Maksymalna nagroda 4 000 zł przy tej samej pracy co 20 000 zł w Tier 1 — "
              "to nie zły wybór celu, tylko zła arytmetyka. Dane scope zostają, bo są "
              "faktem z regulaminu, ale check_host odmawia żądań.",
        enabled=False,
    ),
)


def _matches(rule: str, host: str) -> bool:
    """Dopasowanie reguły scope do hosta. Reguły: 'a.b.c' lub '*.b.c'.

    Gwiazdka obejmuje też domenę bazową. Asymetria jest celowa i zawsze
    w stronę bezpieczną: przy WYKLUCZENIU lepiej odrzucić o jeden host za dużo
    (`*.lab.cert.pl` obejmuje więc i `lab.cert.pl`) niż o jeden za mało.
    Przy WPISIE do scope nadmiarowość nie szkodzi, bo wprost wymienione hosty
    i tak wygrywają z gwiazdką (patrz `tier_of`), a `hack.cert.pl` jest
    w Tier 1 osobno.
    """
    if rule.startswith("*."):
        suffix = rule[2:]
        return host == suffix or host.endswith("." + suffix)
    return host == rule


def normalize_host(host: str) -> str:
    host = (host or "").strip().lower().rstrip(".")
    if "@" in host:                      # userinfo w URL — odrzucamy
        raise ValueError("host zawiera '@' — to nie jest nazwa hosta")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]                # IPv6 w nawiasach
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


@dataclass
class Decision:
    allowed: bool
    host: str
    program: str | None
    tier: str | None
    reason: str

    def __bool__(self) -> bool:
        return self.allowed


def check_host(host: str) -> Decision:
    """Czy host jest w scope? Zwraca decyzję z uzasadnieniem (audytowalną)."""
    try:
        h = normalize_host(host)
    except ValueError as exc:
        return Decision(False, host, None, None, f"odrzucono: {exc}")

    if not h:
        return Decision(False, host, None, None, "pusty host")
    if is_ip_literal(h):
        return Decision(False, h, None, None,
                        "adres IP — scope jest zdefiniowany nazwami domen, nie IP")
    if "/" in h or " " in h:
        return Decision(False, h, None, None, "host zawiera '/' lub spację")

    for prog in PROGRAMS:
        tier = prog.tier_of(h)
        if tier == "EXCLUDED":
            return Decision(False, h, prog.slug, "EXCLUDED",
                            f"jawnie wykluczone w programie '{prog.slug}'")
        if tier:
            if not prog.enabled:
                return Decision(False, h, prog.slug, "DISABLED",
                                f"program '{prog.slug}' jest w scope platformy, ale "
                                f"wyłączony z naszego warsztatu (decyzja użytkownika)")
            return Decision(True, h, prog.slug, tier,
                            f"program '{prog.slug}', {tier}")

    known = {p.slug for p in PROGRAMS}
    return Decision(False, h, None, None,
                    f"host nie występuje w scope żadnego programu ({', '.join(sorted(known))})")


def check_url(url: str) -> Decision:
    """Walidacja pełnego URL-a (schemat + host + brak sztuczek)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return Decision(False, parts.netloc, None, None,
                        f"schemat '{parts.scheme}' nieobsługiwany (tylko http/https)")
    if parts.username or parts.password:
        return Decision(False, parts.hostname or "", None, None,
                        "URL zawiera dane logowania — odrzucono")
    return check_host(parts.hostname or "")


def all_in_scope_hosts() -> list[tuple[str, str, str]]:
    """Lista (host, program, tier) do dokumentacji i testów."""
    out = []
    for p in PROGRAMS:
        if not p.enabled:
            continue
        for rule in p.tier1:
            out.append((rule, p.slug, "T1"))
        for rule in p.tier2:
            out.append((rule, p.slug, "T2"))
    return out


def payout_for(host: str, severity: str) -> int:
    """Ile realnie płaci ten program za tę krytyczność (0 gdy poza scope)."""
    d = check_host(host)
    if not d.allowed:
        return 0
    prog = next(p for p in PROGRAMS if p.slug == d.program)
    return prog.payout(d.tier, severity)
