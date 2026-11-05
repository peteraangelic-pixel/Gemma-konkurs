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
from urllib.parse import urljoin
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nask.tools import chunks, probes  # noqa: E402
from nask.tools.crawl import LEAK_PATHS, STANDARD_PATHS, Crawler, summarise  # noqa: E402
from nask.tools.fetch import GuardedFetcher, ScopeViolation  # noqa: E402
from nask.tools.scope import check_url  # noqa: E402

TARGETS = [
    "https://hack.cert.pl",
    "https://dns.pl",
    "https://nask.pl",
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
    "https://ctf.hack.cert.pl",      # CERT T2, wyjątek z regulaminu — nigdy nie testowany
    "https://pllum.org.pl",          # NASK T2; `public, max-age=3600` = cache współdzielony
]

# Publiczne trasy API `hack.cert.pl` znane z bundla SPA (mapa z Dysku, sekcja
# `/api/v1/public/...`). Sonda S11 nie mogła ich wziąć z chunków, bo klient
# skleja ścieżki szablonem (`${e}/api/v1/...`) i sam prefiks w chunkach nie
# występuje. Cztery żądania; 404 jest równie dobrym wynikiem jak 200.
HACKCERT_PUBLIC = [
    "/api/v1/public/institutions",
    "/api/v1/public/programs",
    "/api/v1/public/reports",
    "/api/v1/public/institutions/nask",
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


def run(out: Path, budget: int, explicit: list[str] | None, rps: float,
        timeout: float = 10.0, chunks_n: int = 0) -> int:
    out.mkdir(parents=True, exist_ok=True)
    fetcher = GuardedFetcher(rps=rps, max_requests=budget,
                             evidence_path=out / "evidence.jsonl", timeout=timeout)
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
            low = html.lower()
            tech = {t for t in re.findall(r"next\.js|drupal|wordpress|react", low)}
            # Django/Wagtail: `csrfmiddlewaretoken`, `__admin_media_prefix__`,
            # `wagtail` w treści. Wtedy warto sprawdzić /api/v2/.
            cms_api = any(k in low for k in ("csrfmiddlewaretoken", "__admin_media_prefix__",
                                             "wagtail", "django"))

            hits = crawler.probe_paths(url, base)
            hits += crawler.probe_paths(url, base, paths=LEAK_PATHS)
            js_findings, js_tech = crawler.analyse_bundles(html, url)
            tech |= set(js_tech)

            # Chunki leniwie ładowane: index.js wymienia 92 pliki, ale prawdziwe
            # wywołania API (ścieżki + parametry) są w chunkach funkcjonalnych.
            chunk_info: dict = {}
            endpoints_c: list[str] = []
            if chunks_n and html:
                srcs = re.findall(r'src="([^"]+\.js[^"]*)"', html)
                index_src = next((x for x in srcs if "index-" in x), srcs[0] if srcs else "")
                if index_src:
                    idx = fetcher.get(urljoin(url + "/", index_src.lstrip("/")))
                    if not idx.error and idx.body:
                        chunk_info = chunks.mine_chunks(
                            fetcher, url, idx.text, max_chunks=chunks_n,
                            interesting=("payout", "users", "view", "ranking", "report",
                                         "account", "integrations", "create", "edit",
                                         "details", "members", "reward"))
                        endpoints_c = chunk_info.get("endpoints") or []

            bid = build_id_of(html)
            routes: list[str] = []
            if bid or tech & {"next.js"}:
                routes = crawler.next_routes(html, url)
                hits += crawler.verify_endpoints(
                    url, base, [f.value for f in js_findings if f.kind == "endpoint"])

            endpoints = [f.value for f in js_findings if f.kind == "endpoint"]
            endpoints += endpoints_c
            found = probes.run_all(
                fetcher, url,
                {"tech": sorted(tech), "build_id": bid, "routes": routes,
                 "endpoints": endpoints,
                 # mwdb ma publiczny kod i publiczny /api/server — wersja mówi,
                 # czy poprawka XSS z 2.20.0 jest wdrożona.
                 "mwdb": "mwdb" in url,
                 # S10 (trucizna cache) tylko tam, gdzie ma to sens: hosty z
                 # deklarowanym cache współdzielonym + dns.pl (tam odbicie XFH
                 # już zmierzono, u nas jest para kontrolna).
                 # S11: publiczne trasy API (z bundli/chunków) — czy oddają dane
                 # osobowe. Tylko `/public/` i trasy listujące, żeby nie chodzić
                 # po całym API bez powodu.
                 "pii_paths": (HACKCERT_PUBLIC if "hack.cert.pl" in url and
                               "ctf." not in url else [])
                              + [e for e in endpoints
                               if isinstance(e, str) and e.startswith("/")
                               and ("/public/" in e or e.rstrip("/").endswith(
                                   ("/institutions", "/programs", "/reports")))]
                              [:10],
                 "cache_check": any(k in url for k in (
                     "pllum.org.pl", "bezpiecznymiesiac.pl", "science.nask.pl",
                     "116sos.pl", "dns.pl", "oad.nask.pl")),
                 "cms_api": cms_api})

            row = summarise(url, hits)
            row.update({"program": program, "tier": tier,
                        "root_status": root.status,
                        "baseline": {"status": base.status, "ctype": base.content_type,
                                     "len": base.length},
                        "tech": sorted(tech), "build_id": bid,
                        "next_routes": routes[:30],
                        "js_endpoints": sorted({f.value for f in js_findings
                                                if f.kind == "endpoint"})[:60],
                        "js_chunks": {k: v for k, v in chunk_info.items()
                                      if k in ("chunks_total", "chunks_fetched",
                                               "api_paths", "params", "hot_fields",
                                               "secrets", "skipped")},
                        "probes": [p.as_dict() for p in found]})
            hosts.append(row)
            hits_all.extend(hits)
            probes_all.extend(found)
            checkpoint(out, hosts, probes_all, budget - fetcher.budget.left)
            print(f"    kandydaci: {len(hits)}, sondy: {len(found)}, "
                  f"budżet: {fetcher.budget.left}", flush=True)
            for p in found:
                print(f"    !! {p.code} [{p.severity}] {p.title} → {p.url}", flush=True)
        except ScopeViolation as exc:
            print(f"    ODMOWA: {exc}", file=sys.stderr)
        except RuntimeError as exc:
            # `Budget.spend()` rzuca RuntimeError po wyczerpaniu. Wcześniej ten
            # wyjątek wychodził z pętli i **zabijał cały przebieg** — udało się
            # tylko dlatego, że budżet 900 wystarczył na 16 hostów. Przy
            # wąskim budżecie traciliśmy wszystkie pozostałe hosty i plik wyniku.
            print(f"    PRZERWANO (budżet): {exc}", file=sys.stderr)
            checkpoint(out, hosts, probes_all, budget - fetcher.budget.left)
            break

    probes_all.sort(key=lambda p: SEVERITY_ORDER.get(p.severity, 9))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requests_used": budget - fetcher.budget.left,
        "hosts_scanned": len(hosts),
        "probe_findings": [p.as_dict() for p in probes_all],
        "hosts": hosts,
    }
    checkpoint(out, hosts, probes_all, payload["requests_used"])
    (out / "hunt.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    # Ślad przebiegu w repo. Powód: logi Actions i artefakty są z sandboxa
    # nieosiągalne (EOF z blob storage), a bez parametrów nie da się odróżnić
    # „nie znalazł, bo nie szukał” od „nie znalazł, bo nie ma”.
    _append_run_log(out, payload, budget, chunks_n)
    (out / "hunt-summary.md").write_text(render(payload, hits_all), encoding="utf-8")
    print(f"\n{payload['requests_used']} żądań, {len(probes_all)} trafień sond")
    return 0


def _append_run_log(out: Path, payload: dict, budget: int, chunks_n: int) -> None:
    totals = {"chunks_total": 0, "chunks_fetched": 0, "api_paths": 0, "params": 0}
    for h in payload.get("hosts", []):
        c = h.get("js_chunks") or {}
        totals["chunks_total"] += c.get("chunks_total") or 0
        totals["chunks_fetched"] += c.get("chunks_fetched") or 0
        totals["api_paths"] += len(c.get("api_paths") or [])
        totals["params"] += len(c.get("params") or [])
    by_sev: dict[str, int] = {}
    for f in payload.get("probe_findings", []):
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    line = ("| {ts} | {req}/{budget} | {hosts} | {chunks} | {chunks_fetched} | "
            "{api} | {params} | {find} | {sev} |").format(
        ts=payload["generated_at"], req=payload["requests_used"], budget=budget,
        hosts=payload["hosts_scanned"], chunks=chunks_n, chunks_fetched=totals["chunks_fetched"],
        api=totals["api_paths"], params=totals["params"],
        find=len(payload.get("probe_findings", [])),
        sev=", ".join(f"{k}:{v}" for k, v in sorted(by_sev.items())) or "brak")
    path = out / "RUNS.md"
    header = ("# Przebiegi nask-hunt\n\n"
              "| czas (UTC) | żądania/budżet | hosty | chunków na host | chunków pobranych "
              "| ścieżek API | parametrów | trafień | wg wagi |\n"
              "|---|---:|---:|---:|---:|---:|---:|---:|---|\n")
    old = path.read_text(encoding="utf-8") if path.exists() else header
    if not old.endswith("\n"):
        old += "\n"
    path.write_text(old + line + "\n", encoding="utf-8")


def checkpoint(out: Path, hosts: list, found: list, used: int) -> None:
    """Zapis częściowy po każdym hoście.

    Powód jest praktyczny, nie teoretyczny: pierwszy przebieg trwał dłużej niż
    zakładałem i gdyby wpadł na limit czasu joba, straciłbym wszystkie wyniki,
    bo zapis był dopiero na końcu. Teraz każdy ukończony host jest na dysku.
    """
    part = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "partial": True,
        "requests_used": used,
        "hosts_scanned": len(hosts),
        "probe_findings": [p.as_dict() for p in found],
        "hosts": hosts,
    }
    (out / "hunt.json").write_text(json.dumps(part, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    (out / "hunt-summary.md").write_text(render(part, []), encoding="utf-8")


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
    ap.add_argument("--chunks", type=int, default=0, dest="chunks_n",
                    help="ile leniwie ładowanych chunków JS pobrać na host (0 = nie)")
    ap.add_argument("--timeout", type=float, default=10.0,
                    help="timeout pojedynczego żądania; martwe hosty nie mogą "
                         "zjeść całego okna joba")
    args = ap.parse_args(argv)
    return run(Path(args.out), args.budget, args.hosts, args.rps, args.timeout,
               args.chunks_n)


if __name__ == "__main__":
    sys.exit(main())
