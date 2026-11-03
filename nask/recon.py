#!/usr/bin/env python3
"""Pasywny rekonesans w GitHub Actions: ~14 żądań, 4,5 req/s, wszystko w scope.

To jest cała „praca sieciowa", którą warto robić zdalnie. Nie fuzzing, nie skan
portów — pobranie stron i bundli JS z hostów w scope, żeby potem **offline**
(czyli bez limitu i bez ryzyka) szukać w nich endpointów i pól.

Dlaczego nie 2000 żądań: przy 5 req/s to 7 minut, a WAF i tak odetnie. Wartość
jest w analizie treści, nie w liczbie żądań.

Użycie:
  python3 nask/recon.py                 # pełny przebieg (wysyła żądania)
  python3 nask/recon.py --dry-run       # tylko walidacja scope
  python3 nask/recon.py --hosts mwdb.cert.pl,www.gov.pl

Poświadczenia: jeżeli w środowisku są sekrety `NASK_COOKIE_*` / `NASK_TOKEN_*`,
`--auth` doda je do żądań (patrz tools/credentials.py). Bez `--auth` ruch jest
anonimowy, czyli taki jak zwykły odwiedzający.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nask.tools import jsmine  # noqa: E402
from nask.tools.credentials import audit  # noqa: E402
from nask.tools.fetch import GuardedFetcher, ScopeViolation  # noqa: E402
from nask.tools.scope import PROGRAMS, check_host  # noqa: E402

# Hosty aplikacyjne (te, które realnie mają powierzchnię). Strony statyczne
# pomijamy — na nich jedyne znaleziska to wykluczone błędy konfiguracji.
TARGETS = [
    "https://mwdb.cert.pl/",
    "https://n6portal.cert.pl/",
    "https://moje.cert.pl/",
    "https://incydent.cert.pl/",
    "https://dyzurnet.pl/",
    "https://dns.pl/",
    "https://oad.nask.pl/",
    "https://zglos-dezinformacje.nask.pl/",
    "https://dataannotation.pllum.org.pl/",
    "https://komunikator.narodowy.gov.pl/",
    "https://www.gov.pl/",
    "https://116sos.pl/",
    "https://science.nask.pl/",
    "https://hack.cert.pl/",
]

_SCRIPT_SRC = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)
_LINK_HREF = re.compile(r'<link[^>]+href=["\']([^"\']+\.js[^"\']*)["\']', re.I)


def _absolutize(base_url: str, ref: str) -> str | None:
    if ref.startswith("//"):
        return "https:" + ref
    if ref.startswith("http"):
        return ref
    if ref.startswith("/"):
        root = "/".join(base_url.split("/")[:3])
        return root + ref
    if ref.startswith("data:"):
        return None
    return base_url.rstrip("/") + "/" + ref


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--auth", action="store_true", help="dołącz poświadczenia z sekretów")
    ap.add_argument("--hosts", default="", help="lista URL-i po przecinku zamiast domyślnych")
    ap.add_argument("--out", default="nask/findings/recon.json")
    ap.add_argument("--max-bundles", type=int, default=6,
                    help="ile plików JS pobrać i zanalizować (każdy to 1 żądanie)")
    args = ap.parse_args(argv)

    targets = [t.strip() for t in args.hosts.split(",") if t.strip()] or TARGETS

    skipped = []
    keep = []
    for url in targets:
        d = check_host(url.split("/")[2])
        if not d.allowed:
            skipped.append({"url": url, "reason": d.reason})
        else:
            keep.append(url)

    print(f"cele w scope: {len(keep)}/{len(targets)}")
    for row in skipped:
        print(f"  POMINIĘTO {row['url']} — {row['reason']}")
    if args.auth:
        found = audit()
        print(f"sekrety w środowisku: {len(found)}")
        for host, kind, state in found:
            print(f"  {host:<32} {kind:<6} {state}")
    if not keep:
        print("brak celów w scope — kończę", file=sys.stderr)
        return 1

    fetcher = GuardedFetcher(max_requests=len(keep) + args.max_bundles + 2,
                             dry_run=args.dry_run, use_credentials=args.auth)

    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "dry_run": args.dry_run, "targets": [], "skipped": skipped,
              "bundles": [], "candidates": 0}

    for url in keep:
        try:
            resp = fetcher.get(url)
        except ScopeViolation as exc:
            report["targets"].append({"url": url, "error": str(exc)})
            continue
        row = {"url": url, "status": resp.status, "bytes": len(resp.body),
               "sha256": resp.sha256,
               "server": resp.headers.get("server", ""),
               "tech": sorted({f.value for f in jsmine.mine(
                   resp.text[:400_000], base_host=url.split("/")[2]) if f.kind == "tech"}),
               "bundles": []}
        if resp.body:
            for pattern in (_SCRIPT_SRC, _LINK_HREF):
                for ref in pattern.findall(resp.text[:400_000]):
                    absolute = _absolutize(url, ref)
                    if absolute and check_host(absolute.split("/")[2]).allowed:
                        if absolute not in row["bundles"]:
                            row["bundles"].append(absolute)
        report["targets"].append(row)

    # Analiza bundli: to jest właściwa praca tej roboty.
    for target in report["targets"]:
        for bundle in target.get("bundles", [])[:args.max_bundles]:
            try:
                resp = fetcher.get(bundle)
            except ScopeViolation:
                continue
            found = jsmine.rank(jsmine.mine(resp.text, base_host=target["url"].split("/")[2]))
            report["bundles"].append({
                "url": bundle, "status": resp.status, "bytes": len(resp.body),
                "sha256": resp.sha256,
                "top": [{"kind": f.kind, "value": f.value, "hint": f.hint} for f in found[:40]],
            })
            report["candidates"] += len(found)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nraport: {out}")
    print(f"cele: {len(report['targets'])}  bundle: {len(report['bundles'])}  "
          f"kandydaci: {report['candidates']}")
    print("UWAGA: 'kandydat' to nie podatność. To miejsce do ręcznego sprawdzenia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
