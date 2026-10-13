#!/usr/bin/env python3
"""Compare screening results across candidates and rewrite kaggle_results/screening_history.md.

Usage:
    python3 gemma4-agent/tools/compare_screenings.py            # writes the markdown report
    python3 gemma4-agent/tools/compare_screenings.py --json     # machine-readable summary too
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "gemma4-agent" / "kaggle_results"
SCRATCH = ("issue.txt", "locate.py", "repro.py", "notes.txt")
CLOCK_CAP = 315.0

CANDIDATES = [
    ("V3", "v3-benchmark"),
    ("V4", "v4-benchmark"),
    ("V5", "v5-benchmark"),
    ("V6.1", "v6-1-benchmark"),
    ("V6.2", "v6-benchmark"),
    ("V6.3-mini", "v6-3-miniscreen"),
    ("V6.3", "v6-3-benchmark"),
    # V6.4 mini-screen: the six mechanism tasks. Recorded for the paired comparison on the common
    # six tasks; its CI95 over n=6 is not a score estimate (E5: the mini-screen is not a forecast).
    ("V6.4-mini", "v6-4-miniscreen"),
    ("V6.4", "v6-4-benchmark"),
]
EARLY_END_SECONDS = 280.0  # a session ending well before the 315 s cap
DOCS_RE = re.compile(r"(^|/)(docs|doc)(/|$)|\\.md$|\\.rst$")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 1.0
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def stats(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks") or []
    total = len(tasks) or 1
    scratch_tasks = [r.get("task_id") for r in tasks
                     if any(f in SCRATCH for f in (r.get("touched_files") or []))]
    scratch_only = [r.get("task_id") for r in tasks
                    if any(f in SCRATCH for f in (r.get("touched_files") or []))
                    and not any(f.endswith((".py", ".pyi")) and f.split("/")[-1] not in SCRATCH
                                for f in (r.get("touched_files") or []))]
    empty = [r.get("task_id") for r in tasks if (r.get("patch_chars") or 0) == 0]
    clock = [r.get("task_id") for r in tasks if (r.get("duration_seconds") or 0) >= CLOCK_CAP]
    resolved = [r.get("task_id") for r in tasks if r.get("resolved")]
    def source_like(name: str) -> bool:
        return (name.endswith((".py", ".pyi")) and "/docs/" not in name
                and not name.startswith(("docs/", "doc/")) and "_test" not in name)

    premature = [r.get("task_id") for r in tasks
                 if (r.get("patch_chars") or 0) == 0
                 and (r.get("duration_seconds") or 0) < EARLY_END_SECONDS]
    docs_only = [r.get("task_id") for r in tasks
                 if (r.get("touched_files") or [])
                 and not any(source_like(f) for f in r["touched_files"])
                 and any(DOCS_RE.search(f) for f in r["touched_files"])]
    low, high = wilson(len(resolved), len(tasks))
    stored = data.get("score_ci95_wilson")
    if stored and (abs(stored[0] - low) > 0.002 or abs(stored[1] - high) > 0.002):
        raise SystemExit(f"{path}: stored CI {stored} disagrees with recomputed [{low:.4f}, {high:.4f}]")
    return {
        "total": len(tasks),
        "ids": [r.get("task_id") for r in tasks],
        "ci95": [round(low * 100, 1), round(high * 100, 1)],
        "resolved": len(resolved),
        "resolved_ids": resolved,
        "empty": len(empty),
        "empty_ids": empty,
        "clock_deaths": len(clock),
        "clock_ids": clock,
        "scratch": len(scratch_tasks),
        "scratch_ids": scratch_tasks,
        "scratch_only": len(scratch_only),
        "scratch_only_ids": scratch_only,
        "premature_empty": len(premature),
        "premature_empty_ids": premature,
        "docs_only": len(docs_only),
        "docs_only_ids": docs_only,
        "localization_hits": data.get("localization_hits"),
        "touching_tests": data.get("tasks_touching_tests"),
        "mean_seconds": round(data.get("mean_task_duration_seconds") or 0, 1),
        "sha": data.get("submission_sha256"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=RESULTS / "screening_history.md")
    args = parser.parse_args()

    rows = [(tag, stats(RESULTS / folder / "agent_benchmark_result.json")) for tag, folder in CANDIDATES]
    present = [(tag, s) for tag, s in rows if s]

    lines = [
        "# Historia screeningów: co każdy wynik zmienił",
        "",
        "Pełne przebiegi: te same 30 zadań i seed 20261009. Mini-screen V6.3 to 4 zadania z tej",
        "samej próbki (diagnozowane przypadki), więc jego wiersz czyta się jako test mechanizmu,",
        "nie jako oszacowanie wyniku. Kolumny diagnostyczne istnieją dopiero od V6.1.",
        "",
        "| kandydat | rozwiązane | CI95 Wilsona | puste drzewa (zero edycji) | z tego przedwczesne | śmierci na zegarze | pliki-śmieci | tylko dokumentacja | trafienia lokalizatora | średni czas |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for tag, s in present:
        loc = "—" if s["localization_hits"] is None else f"{s['localization_hits']}/{s['total']}"
        lines.append(
            f"| {tag} | **{s['resolved']}/{s['total']}** "
            f"| [{s['ci95'][0]} %, {s['ci95'][1]} %] | {s['empty']} | {s['premature_empty']} "
            f"| {s['clock_deaths']} | {s['scratch']} | {s['docs_only']} | {loc} | {s['mean_seconds']} s |")

    lines += ["", "## Zmiany statusu między kolejnymi kandydatami", "",
              "Porównanie liczy się **wyłącznie na zadaniach wspólnych** — inaczej mini-screen",
              "zaraportowałby jako straty zadania, których w ogóle nie uruchamiał.", ""]
    for (tag_a, a), (tag_b, b) in zip(present, present[1:]):
        shared = set(a["ids"]) & set(b["ids"])
        note = ""
        if len(shared) < max(a["total"], b["total"]):
            note = (f" — na {len(shared)} wspólnych zadaniach "
                    f"({tag_a}: {a['total']}, {tag_b}: {b['total']} uruchomionych)")
        gained = sorted((set(b["resolved_ids"]) & shared) - set(a["resolved_ids"]))
        lost = sorted((set(a["resolved_ids"]) & shared) - set(b["resolved_ids"]))
        lines.append(f"- {tag_a} → {tag_b}: +{len(gained)} ({', '.join(gained) or '—'}), "
                     f"-{len(lost)} ({', '.join(lost) or '—'}){note}")

    for tag, s in present:
        if s["scratch"]:
            lines += ["", f"### {tag}: zadania z plikami-śmieciami w diffie", "",
                      f"- wszystkie: {', '.join(s['scratch_ids'])}",
                      f"- **bez żadnej edycji kodu: {', '.join(s['scratch_only_ids'])}**"]
    for tag, s in present:
        if s["empty"]:
            lines += ["", f"### {tag}: puste drzewa ({s['empty']})", "",
                      f"- {', '.join(s['empty_ids'])}"]

    lines += ["", "## Bramki jakości V6.3 (pre-registered 2026-10-12, przed przebiegiem)", "",
              "Bramki są **osobne od liczby rozwiązanych zadań** i nie przesuwa się ich po zobaczeniu wyniku.", ""]
    for tag, s_ in present:
        if tag not in ("V6.3-mini", "V6.3"):
            continue
        g1 = s_["scratch"] == 0
        g2 = s_["premature_empty"] == 0
        g3 = s_["docs_only"] == 0
        lines.append(f"- **{tag}**: G1 brak plików-śmieci: {'PASS' if g1 else 'FAIL'} "
                     f"({s_['scratch']}); G2 brak przedwczesnych submisji bez edycji: "
                     f"{'PASS' if g2 else 'FAIL'} ({s_['premature_empty']}); "
                     f"G3 zero diffów wyłącznie dokumentacyjnych: {'PASS' if g3 else 'FAIL'} "
                     f"({s_['docs_only']}); G4 cel: puste drzewa <= 4 (jest {s_['empty']}); "
                     f"wynik zgłaszany osobno: {s_['resolved']}/{s_['total']} "
                     f"CI95 [{s_['ci95'][0]} %, {s_['ci95'][1]} %]")

    by_tag = dict(present)
    if "V6.3-mini" in by_tag and "V6.3" in by_tag:
        both = (by_tag["V6.3-mini"], by_tag["V6.3"])
        gates_zero = all(x["scratch"] == 0 and x["premature_empty"] == 0 and x["docs_only"] == 0
                         for x in both)
        enough = by_tag["V6.3"]["resolved"] >= 9
        verdict = "SPEŁNIONA -> submissja możliwa" if (gates_zero and enough) else "NIESPEŁNIONA -> submissja zablokowana"
        reasons = []
        for tag, x in (("V6.3-mini", both[0]), ("V6.3", both[1])):
            if x["premature_empty"]:
                reasons.append(f"{tag}: G2={x['premature_empty']}")
            if x["scratch"]:
                reasons.append(f"{tag}: G1={x['scratch']}")
            if x["docs_only"]:
                reasons.append(f"{tag}: G3={x['docs_only']}")
        if not enough:
            reasons.append(f"V6.3: rozwiązane {by_tag['V6.3']['resolved']}/30 < 9")
        lines += ["", f"- **reguła decyzyjna z GATES_V6_3.md** (G1=G2=G3=0 w obu przebiegach "
                      f"i ≥9/30 w pełnym): **{verdict}**"
                      + (f" — powody: {', '.join(reasons)}" if reasons else "")]

    mini = dict(present).get("V6.3-mini")
    if mini:
        o1 = ("rich_3105" not in mini["empty_ids"] and "rich_3934" not in mini["empty_ids"]
              and mini["premature_empty"] == 0)
        o2 = "fastapi_14487" not in mini["docs_only_ids"]
        o3 = "rich_3006" in mini["clock_ids"]
        lines += ["", "## Werdykt pre-registered oczekiwań (V6.3-mini)", "",
                  "Zapisane w GATES_V6_3.md **przed** przebiegiem; werdykt liczony maszynowo z JSON-a.", ""]
        lines.append(f"- **O1** `rich_3105` i `rich_3934` kończą z edycją na dysku (nie pustym drzewem) "
                     f"i G2 = 0: **{'SPEŁNIONE' if o1 else 'OBALONE'}** — puste drzewa "
                     f"{', '.join(i for i in ('rich_3105', 'rich_3934') if i in mini['empty_ids']) or 'brak'}, "
                     f"przedwczesne {mini['premature_empty']}")
        lines.append(f"- **O2** `fastapi_14487` bez diffu wyłącznie dokumentacyjnego: "
                     f"**{'SPEŁNIONE' if o2 else 'OBALONE'}** (docs-only: {mini['docs_only']})")
        lines.append(f"- **O3** `rich_3006` (kontrola) nadal pada na zegarze: "
                     f"**{'SPEŁNIONE' if o3 else 'OBALONE'}** — gdyby został rozwiązany, byłby to sygnał szumu, "
                     f"nie sukcesu zmian (a)/(c)")
        lines.append("")
        lines.append("Skutek OBALONEGO O1: zmiana (a) usuwa przedwczesną submissję bez edycji "
                     "(G2 = 0), ale **nie zamienia jej na edycję** — te sesje nadal kończą z pustym "
                     "drzewem, tyle że po wyczerpaniu zegara. Zysk punktowy na tych zadaniach: nadal zero. "
                     "Bezpośredni zapis tego wniosku: GATES_V6_3.md, sekcja o przebiegu zdarzeń.")

    lines += [
        "",
        "## Reguły interpretacji (wyuczone na tych przebiegach)",
        "",
        "1. **Śmierć na zegarze nie przekreśla zadania** — oceniany jest diff drzewa roboczego, także gdy",
        "   sesja padnie przed `submit_patch()` (dowód: V3 miał 16/30 takich sesji i 11/30 rozwiązanych).",
        "2. **Przekreśla ją brak użytecznej edycji** — V5 (6 pustych drzew) i V6.1 (7 drzew bez edycji kodu,",
        "   bo diff wypełniły pliki robocze) to dwa różne objawy tej samej przyczyny.",
        "3. **Publiczny screening 30 zadań nie przewiduje ukrytego wyniku** (V3/V4/V5: 10–11/30 przy",
        "   oficjalnym 0.03), ale z diagnostyką per zadanie niezawodnie wskazuje mechanizmy porażek.",
        "4. **Bramki jakości raportuje się osobno od wyniku** i ustala przed przebiegiem; próg na",
        "   liczbie rozwiązań nie jest dowodem przewagi przy n=30 (V5 vs V6.2: przedziały nachodzą).",
        "5. **Przedziały CI95 w tabeli są liczone z JSON-ów** (`score_ci95_wilson` jest dodatkowo",
        "   kontrolowane przy generowaniu). Prozy nie wolno przepisywać ręcznie — pilnuje tego",
        "   `python3 gemma4-agent/tools/check_docs_consistency.py` (wykrył realną rozbieżność",
        "   [11 %, 30 %] vs [16.7 %, 47.9 %] w V6.2).",
        "",
    ]

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:14]))
    if args.json:
        print(json.dumps({tag: s for tag, s in present}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
