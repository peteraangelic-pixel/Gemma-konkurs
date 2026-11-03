"""Triage: ile realnie płaci dana hipoteza — decyzja o kolejności pracy.

Pomysł jest prosty i dlatego użyteczny: skoro nagroda = f(krytyczność CVSS 4.0,
tier, program), a prawdopodobieństwo potwierdzenia zależy od klasy i dojrzałości
celu, to oczekiwana wartość `EV = nagroda × P(potwierdzenie) × P(brak duplikatu)`
pozwala porównać "kolejny tydzień na XSS" z "trzy dni na IDOR w MWDB".

Prawdopodobieństwa są ZAŁOŻENIAMI, nie pomiarami — dlatego są jawnym parametrem
i można je podmienić. Wartość tego modułu to nie "precyzja", a to, że kolejność
pracy przestaje być kwestią nastroju.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

# Klasy z regulaminu §8 → domyślna krytyczność, gdy nie znamy CVSS.
CLASS_SEVERITY = {
    "01-RCE": "krytyczny",
    "02-account-takeover": "krytyczny",
    "03-sensitive-data": "wysoki",
    "04-sqli": "krytyczny",
    "05-ssrf": "sredni",
    "06-ssti": "krytyczny",
    "07-file-upload": "wysoki",
    "08-xss": "sredni",
    "09-idor-bac": "wysoki",
    "10-privesc": "wysoki",
    "11-session": "niski",
    "12-api": "wysoki",
    "13-mass-assignment": "wysoki",
    "14-cors": "sredni",
    "15-path-traversal": "wysoki",
    "16-csrf": "sredni",
    "17-open-redirect": "niski",
    "18-cache-poisoning": "wysoki",
    "19-smuggling": "wysoki",
    "20-xxe": "wysoki",
}

# Klasy WYKLUCZONE z konkursu (§8) — zgłaszanie ich to strata czasu i wiarygodności.
EXCLUDED_CLASSES = {
    "self-xss", "tabnabbing", "content-injection-bez-js", "clickjacking-bez-akcji",
    "blind-ssrf-tylko-dns", "subdomain-takeover-bez-poc", "brak-naglowkow",
    "brak-captcha", "stary-certyfikat", "stack-trace", "user-enumeration",
    "otwarty-port", "literowki", "csrf-logout", "klucze-bez-naduzycia",
    "raport-z-automatu-bez-potwierdzenia", "dos", "testy-obciazeniowe",
}

# Realistyczne P(potwierdzenie) dla celu państwowego, pojedyncza osoba, 4 tygodnie.
DEFAULT_P_CONFIRM = {
    "01-RCE": 0.02,
    "02-account-takeover": 0.05,
    "03-sensitive-data": 0.10,
    "04-sqli": 0.03,
    "05-ssrf": 0.12,
    "06-ssti": 0.02,
    "07-file-upload": 0.10,
    "08-xss": 0.25,
    "09-idor-bac": 0.22,
    "10-privesc": 0.10,
    "11-session": 0.20,
    "12-api": 0.18,
    "13-mass-assignment": 0.15,
    "14-cors": 0.20,
    "15-path-traversal": 0.06,
    "16-csrf": 0.10,
    "17-open-redirect": 0.25,
    "18-cache-poisoning": 0.04,
    "19-smuggling": 0.05,
    "20-xxe": 0.05,
}

P_UNIQUE = 0.55   # państwowy bug bounty z pulą 100k i 30-dniową edycją: duplikaty będą


@dataclass
class Hypothesis:
    host: str
    cls: str                       # np. "09-idor-bac"
    program: str
    tier: str                      # T1 / T2
    payout: int                    # zł za potwierdzoną, unikalną lukę
    p_confirm: float
    days: float                    # szacowany nakład
    note: str = ""

    @property
    def ev(self) -> float:
        return self.payout * self.p_confirm * P_UNIQUE

    @property
    def ev_per_day(self) -> float:
        return self.ev / max(self.days, 0.1)


def build(host: str, cls: str, days: float, severity: str | None = None,
          p_confirm: float | None = None, note: str = "") -> Hypothesis:
    from .scope import check_host, PROGRAMS

    decision = check_host(host)
    if not decision.allowed:
        raise ValueError(f"{host} nie jest w scope: {decision.reason}")
    if cls in EXCLUDED_CLASSES:
        raise ValueError(f"klasa '{cls}' jest WYKLUCZONA z konkursu — nie tracimy na nią czasu")

    prog = next(p for p in PROGRAMS if p.slug == decision.program)
    sev = severity or CLASS_SEVERITY.get(cls, "sredni")
    return Hypothesis(
        host=host, cls=cls, program=decision.program, tier=decision.tier,
        payout=prog.payout(decision.tier, sev),
        p_confirm=p_confirm if p_confirm is not None else DEFAULT_P_CONFIRM.get(cls, 0.05),
        days=days, note=note,
    )


def rank(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    return sorted(hypotheses, key=lambda h: h.ev_per_day, reverse=True)


def table(hypotheses: list[Hypothesis]) -> str:
    rows = ["| host | klasa | tier | nagroda | P(traf) | dni | EV | EV/dzień |",
            "|---|---|---|---:|---:|---:|---:|---:|"]
    for h in rank(hypotheses):
        rows.append(f"| `{h.host}` | {h.cls} | {h.tier} | {h.payout:,} zł | "
                    f"{h.p_confirm:.0%} | {h.days:g} | {h.ev:,.0f} zł | "
                    f"{h.ev_per_day:,.0f} zł |".replace(",", " "))
    total = sum(h.ev for h in hypotheses)
    rows.append(f"\n**Suma EV przy realizacji wszystkich: {total:,.0f} zł** "
                f"(to nie prognoza zarobku — to sposób porównania kolejności)".replace(",", " "))
    return "\n".join(rows)


def load_plan(path: str | Path) -> list[Hypothesis]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for row in data["hypotheses"]:
        out.append(build(row["host"], row["cls"], row["days"],
                         row.get("severity"), row.get("p_confirm"), row.get("note", "")))
    return out


def to_json(hypotheses: list[Hypothesis]) -> str:
    return json.dumps([asdict(h) for h in rank(hypotheses)],
                      ensure_ascii=False, indent=2)
