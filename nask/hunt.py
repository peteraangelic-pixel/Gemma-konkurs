#!/usr/bin/env python3
"""Nocne polowanie: rekonesans + sondy celowane po hostach w scope.

Uruchamiane w GitHub Actions (sandbox agenta nie ma wyjścia do tych hostów).
Wynik: `nask/findings/hunt.json` — trafienia z uzasadnieniem i **wyniki negatywne**,
żeby rano nie sprawdzać drugi raz tego samego.

  python3 nask/hunt.py --out nask/findings --budget 900
  python3 nask/hunt.py --hosts https://dns.pl --budget 120

Zasady wbudowane w kod, nie w dobre chęci:
  • wyłącznie GET (ten plik nie potrafi wysłać POST),
  • 4,5 req/s (TokenBucket odmawia startu powyżej 5),
  • każdy host przechodzi przez scope.py (nieznany = pominięty z komunikatem),
  • Władysławowo pominięte (decyzja użytkownika, nie zapomnienie).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nask.tools import probes  # noqa: E402
from nask.tools.crawl import LEAK_PATHS, STANDARD_PATHS, Crawler, summarise  # noqa: E402
from nask.tools.fetch import GuardedFetcher, ScopeViolation  # noqa: E402
from nask.tools.scope import check_url  # noqa: E402

TARGETS = [
    "https://hack.cert.pl",
    "https://dns.pl",
    "https://mwdb.cert.pl",
    "https://n6portal.cert.pl",
    "https://komunikator.narodowy.gov.pl",
    "https://zglos-dezinformacje.nask.pl",
    "https://oad.nask.pl",
    "https://moje.cert.pl",
    "https://incydent.cert.pl",
    "https://dyzurnet.pl",
    "https://116sos.pl",
    "https://science.nask.pl",
    "https://www.gov.pl",
    "https://dataannotation.pllum.org.pl",
    "https://bezpiecznewybory.pl",
]

SKIP_PROGRAMS = {"wladyslawowo"}          # decyzja użytkownika: szkoda czasu
SEVERITY_ORDER = {"krytyczny": 0, "wysoki": 1, "sredni": 2, "niski": 3}


def build_id_of(html: str) -> str | None:
    m = re.search(r'"buildId"\s*:\s*"([\w-]+)"', html)
    return m.group(1) if m else None


def plan_targets(explicit: list[str] | None) -> list[tuple[str, str, str]]:
    chosen = []
    for url in (explicit or TARGETS):
        if "://" not in url:
            url = "https://" + url
        url = url.rstrip("/")
        d = check_url(url)
        if not d.allowed:
            print(f"POMINIĘTY (poza zakresem): {url} → {d.reason}", file=sys.stderr)
            continue
        if d.program in SKIP_PROGRAMS:
            print(f"POMINIĘTY (program wyłączony): {url}", file=sys.stderr)
            continue
        chosen.append((url, d.program, d.tier))
    return chosen


def run(out: Path, budget: int, explicit: list[str] | None, rps: float) -> int:
    out.mkdir(parents=True, exist_ok=True)
    fetcher = GuardedFetcher(rps=rps, max_requests=budget,
                             evidence_path=out / "evidence.jsonl")
    crawler = Crawler(fetcher)
    targets = plan_targets(explicit)
    if not targets:
        print("brak celów w zakresie", file=sys.stderr)
        return 1

    hits_all, probes_all, hosts = [], [], []
    for url, program, tier in targets:
        if fetcher.budget.left <= 10:
            print(f"budżet wyczerpany przed {url}", file=sys.stderr)
            break
        print(f"\n=== {url} [{program}/{tier}] budżet={fetcher.budget.left}", flush=True)
        try:
            base = crawler.baseline(url)
            root = fetcher.get(url)
            html = root.text if not root.error else ""
            tech = {t for t in re.findall(r"next\.js|drupal|wordpress|react", html.lower())}

            hits = crawler.probe_paths(url, base)
            hits += crawler.probe_paths(url, base, paths=LEAK_PATHS)
            js_findings, js_tech = crawler.analyse_bundles(html, url)
            tech |= set(js_tech)

            bid = build_id_of(html)
            routes: list[str] = []
            if bid or tech & {"next.js"}:
                routes = crawler.next_routes(html, url)
                endpoints = [f.value for f in js_findings if f.kind == "endpoint"]
                hits += crawler.verify_endpoints(url, base, endpoints)

            found = probes.run_all(
                fetcher, url,
                {"tech": sorted(tech), "build_id": bid, "routes": routes})

            row = summarise(url, hits)
            row.update({"program": program, "tier": tier,
                        "root_status": root.status,
                        "baseline": {"status": base.status, "ctype": base.content_type,
                                     "len": base.length},
                        "tech": sorted(tech), "build_id": bid,
                        "next_routes": routes[:30],
                        "js_endpoints": sorted({f.value for f in js_findings
                                                if f.kind == "endpoint"})[:60],
                        "probes": [p.as_dict() for p in found]})
            hosts.append(row)
            hits_all.extend(hits)
            probes_all.extend(found)
            print(f"    kandydaci: {len(hits)}, sondy: {len(found)}, "
                  f"budżet: {fetcher.budget.left}", flush=True)
            for p in found:
                print(f"    !! {p.code} [{p.severity}] {p.title} → {p.url}", flush=True)
        except ScopeViolation as exc:
            print(f"    ODMOWA: {exc}", file=sys.stderr)

    probes_all.sort(key=lambda p: SEVERITY_ORDER.get(p.severity, 9))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requests_used": budget - fetcher.budget.left,
        "hosts_scanned": len(hosts),
        "probe_findings": [p.as_dict() for p in probes_all],
        "hosts": hosts,
    }
    (out / "hunt.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    (out / "hunt-summary.md").write_text(render(payload, hits_all), encoding="utf-8")
    print(f"\n{payload['requests_used']} żądań, {len(probes_all)} trafień sond")
    return 0


def render(payload: dict, hits: list) -> str:
    L = ["# Nocne polowanie — wyniki", "",
         f"Wygenerowano: `{payload['generated_at']}`, żądań: **{payload['requests_used']}**, "
         f"hostów: **{payload['hosts_scanned']}**", "",
         "> Trafienie sondy ≠ podatność. Każde wymaga ręcznego potwierdzenia w przeglądarce",
         "> i sprawdzenia, czy nie wpada w wykluczenia §8. Kolumna „dlaczego nie wykluczone”",
         "> jest tam po to, żeby tę weryfikację dało się zrobić w minutę.", ""]

    findings = payload["probe_findings"]
    real = [f for f in findings if f["severity"] in ("krytyczny", "wysoki")]
    L.append(f"## Trafienia wysokie/krytyczne: {len(real)}")
    L.append("")
    if not real:
        L.append("_Brak. To też jest wynik: te sześć błędów sprawdzono i ich nie ma._")
    for f in real:
        L.append(f"### `{f['code']}` [{f['severity']}] {f['title']}")
        L.append(f"- host: `{f['host']}`")
        L.append(f"- URL: `{f['url']}`")
        L.append(f"- dowód: {f['detail']}")
        L.append(f"- dlaczego nie wykluczone: {f['why']}")
        L.append(f"- surowe: `{json.dumps(f['raw'], ensure_ascii=False)}`")
        L.append("")
    L.append("")
    L.append("## Trafienia średnie/niskie (do wglądu, nie do zgłoszenia w tej formie)")
    L.append("")
    for f in findings:
        if f["severity"] in ("krytyczny", "wysoki"):
            continue
        L.append(f"- `{f['code']}` **{f['severity']}** `{f['url']}` — {f['title']}  ")
        L.append(f"  {f['detail'][:180]}")
    L.append("")
    L.append("## Powierzchnia per host")
    L.append("")
    L.append("| host | tech | kandydaci | endpointy JS | trasy Next |")
    L.append("|---|---|---:|---:|---:|")
    for h in sorted(payload["hosts"], key=lambda x: -x["hits"]):
        L.append(f"| `{h['host']}` | {', '.join(h['tech']) or '—'} | {h['hits']} | "
                 f"{len(h['js_endpoints'])} | {len(h['next_routes'])} |")
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="nask/findings")
    ap.add_argument("--budget", type=int, default=900)
    ap.add_argument("--hosts", nargs="*", default=None)
    ap.add_argument("--rps", type=float, default=4.5)
    args = ap.parse_args(argv)
    return run(Path(args.out), args.budget, args.hosts, args.rps)


if __name__ == "__main__":
    sys.exit(main())
