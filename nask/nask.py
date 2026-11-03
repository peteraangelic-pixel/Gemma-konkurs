#!/usr/bin/env python3
"""CLI projektu NASK bug bounty. Wszystko offline poza `get`.

  python3 nask/nask.py scope nask.pl
  python3 nask/nask.py scope --list
  python3 nask/nask.py plan nask/plan.json
  python3 nask/nask.py mine bundle.js --host app.komunikator.narodowy.gov.pl
  python3 nask/nask.py get https://www.gov.pl/ --dry-run     (domyślnie dry-run)
  python3 nask/nask.py get https://www.gov.pl/ --send        (naprawdę wysyła)

Świadoma decyzja: `get` domyślnie NIC nie wysyła. Wysyłka wymaga `--send`,
bo pomyłka w jednym argumencie nie może skończyć się żądaniem do złego hosta.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nask.tools import jsmine, triage  # noqa: E402
from nask.tools.fetch import GuardedFetcher, ScopeViolation  # noqa: E402
from nask.tools.scope import PROGRAMS, check_host, check_url  # noqa: E402


def cmd_scope(args) -> int:
    if args.list:
        for p in PROGRAMS:
            print(f"\n{p.name}  ({p.url})")
            print(f"  Tier 1: {', '.join(p.tier1)}")
            if p.tier2:
                print(f"  Tier 2: {', '.join(p.tier2)}")
            if p.exclude:
                print(f"  WYKLUCZONE: {', '.join(p.exclude)}")
            if p.notes:
                print(f"  uwaga: {p.notes}")
            pay = " | ".join(f"{k}: {v} zł" for k, v in p.payouts["T1"].items())
            print(f"  Tier 1 stawki: {pay}")
        return 0

    target = args.target
    if not target:
        print("podaj host lub URL", file=sys.stderr)
        return 2
    d = check_url(target) if "://" in target else check_host(target)
    mark = "✅ W SCOPE" if d.allowed else "⛔ ODMOWA"
    print(f"{mark}  {d.host}")
    print(f"   program: {d.program}   tier: {d.tier}")
    print(f"   powód:   {d.reason}")
    if d.allowed:
        prog = next(p for p in PROGRAMS if p.slug == d.program)
        print(f"   stawki:  {prog.payouts[d.tier]}")
    return 0 if d.allowed else 1


def cmd_plan(args) -> int:
    hyps = triage.load_plan(args.path)
    print(triage.table(hyps))
    if args.json:
        print(triage.to_json(hyps))
    return 0


def cmd_mine(args) -> int:
    text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    found = jsmine.rank(jsmine.mine(text, base_host=args.host or ""))
    if not found:
        print("brak kandydatów — plik nie zawiera endpointów/parametrów")
        return 0
    for f in found:
        print(f"[{f.kind:11s}] {f.value}\n              ↳ {f.hint}")
    print(f"\n{len(found)} kandydatów. To NIE są podatności — to lista do ręcznej weryfikacji.")
    return 0


def cmd_get(args) -> int:
    fetcher = GuardedFetcher(rps=args.rps, max_requests=1,
                             dry_run=not args.send, timeout=args.timeout)
    try:
        resp = fetcher.get(args.url)
    except ScopeViolation as exc:
        print(f"⛔ {exc}", file=sys.stderr)
        return 1
    if resp.error:
        print(f"dry-run: walidacja OK ({args.url} jest w scope), nic nie wysłano")
        return 0
    print(json.dumps({"status": resp.status, "sha256": resp.sha256,
                      "bytes": len(resp.body),
                      "headers": resp.headers}, indent=2, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scope", help="sprawdź, czy host jest w zakresie")
    s.add_argument("target", nargs="?")
    s.add_argument("--list", action="store_true", help="wypisz cały zakres")
    s.set_defaults(func=cmd_scope)

    p = sub.add_parser("plan", help="tabela EV hipotez")
    p.add_argument("path")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_plan)

    m = sub.add_parser("mine", help="wyciągnij endpointy z pliku JS/HTML")
    m.add_argument("file")
    m.add_argument("--host", default="")
    m.set_defaults(func=cmd_mine)

    g = sub.add_parser("get", help="jedno żądanie (domyślnie dry-run)")
    g.add_argument("url")
    g.add_argument("--send", action="store_true", help="naprawdę wyślij żądanie")
    g.add_argument("--rps", type=float, default=4.5)
    g.add_argument("--timeout", type=float, default=15.0)
    g.set_defaults(func=cmd_get)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
