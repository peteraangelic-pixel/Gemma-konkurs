#!/usr/bin/env python3
"""Fetch this account's Gemma submissions and the public Kaggle leaderboard.

This is called by the repository's GitHub Actions poll workflow. Credentials are
read from Kaggle CLI's standard ~/.kaggle/access_token location; the value is
never included in an output file. No submission is uploaded by this script.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
import zipfile

DEFAULT_COMPETITION = "gemma-4-developer-agent"


def csv_rows(text: str) -> list[dict[str, str]]:
    text = text.removeprefix("\ufeff").strip()
    if not text:
        return []
    return list(csv.DictReader(io.StringIO(text)))


def pick(row: dict[str, str], *names: str) -> str:
    lowered = {key.strip().lower(): value for key, value in row.items() if key}
    for name in names:
        if name.lower() in lowered:
            return (lowered[name.lower()] or "").strip()
    return ""


def _safe_error(stdout: str, stderr: str) -> str:
    message = (stderr or stdout or "Kaggle CLI returned a non-zero status.").strip()
    token = os.environ.get("KAGGLE_API_TOKEN", "")
    if token:
        message = message.replace(token, "[REDACTED]")
    return " ".join(message.split())[:600]


def kaggle(args: list[str], timeout: int = 300) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.setdefault("KAGGLE_QUIET", "1")
    command = [sys.executable, "-m", "kaggle", *args]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, env=env, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return result.returncode, result.stdout, result.stderr


def has_credentials() -> bool:
    if os.environ.get("KAGGLE_API_TOKEN", "").strip():
        return True
    return Path.home().joinpath(".kaggle", "access_token").is_file()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def leaderboard_csv(outdir: Path, competition: str) -> tuple[list[dict[str, str]], str | None]:
    archive_path = outdir / f"{competition}.zip"
    if archive_path.exists():
        archive_path.unlink()

    code, stdout, stderr = kaggle(
        ["competitions", "leaderboard", "-c", competition, "-d", "-p", str(outdir), "-q"]
    )
    if code != 0:
        return [], f"leaderboard request failed: {_safe_error(stdout, stderr)}"
    if not archive_path.is_file():
        return [], "leaderboard request returned success but did not create the expected ZIP."

    try:
        with zipfile.ZipFile(archive_path) as archive:
            csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not csv_names:
                return [], "leaderboard ZIP contained no CSV file."
            content = archive.read(csv_names[0]).decode("utf-8-sig", "replace")
        (outdir / "leaderboard.csv").write_text(content.rstrip() + "\n", encoding="utf-8")
        return csv_rows(content), None
    except (OSError, zipfile.BadZipFile, UnicodeError) as exc:
        return [], f"could not read leaderboard ZIP: {type(exc).__name__}: {exc}"
    finally:
        archive_path.unlink(missing_ok=True)


def _score(row: dict[str, str]) -> float | None:
    value = pick(row, "Score", "PublicScore", "publicScore", "ResolutionRate", "score")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def top_rows(rows: list[dict[str, str]], count: int = 10) -> list[dict[str, str]]:
    indexed = list(enumerate(rows))
    if any(_score(row) is not None for row in rows):
        indexed.sort(key=lambda item: (
            _score(item[1]) is None,
            -(_score(item[1]) or 0.0),
            item[0],
        ))
    return [row for _, row in indexed[:count]]


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _write_top10_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    outdir: Path,
    competition: str,
    submissions: list[dict[str, str]],
    leaderboard: list[dict[str, str]],
    team: str,
    problems: list[str],
) -> None:
    top10 = top_rows(leaderboard, 10)
    our_rows = []
    if team:
        our_rows = [
            row for row in leaderboard
            if pick(row, "TeamName", "teamName", "Team_Name", "Team", "User_Name", "UserName", "username").casefold()
            == team.casefold()
        ]

    summary = {
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "competition": competition,
        "team_filter": team or None,
        "leaderboard_rows": len(leaderboard),
        "submission_rows": len(submissions),
        "our_leaderboard_rows": our_rows,
        "top10": top10,
        "latest_submissions": submissions[:10],
        "problems": problems,
    }
    write_json(outdir / "summary.json", summary)
    _write_top10_csv(outdir / "leaderboard_top10.csv", top10)

    lines = [
        f"# Kaggle status — {competition}",
        "",
        f"_Fetched {summary['fetched_utc']}._",
        "",
        "This is a read-only poll: it does not upload or submit an agent.",
        "",
        "## Our latest submissions",
        "",
    ]
    if submissions:
        lines.extend([
            "| File | Status | Score | Submitted |",
            "|---|---|---:|---|",
        ])
        for row in submissions[:10]:
            filename = pick(row, "FileName", "fileName", "file")
            status = pick(row, "Status", "status")
            score = pick(row, "PublicScore", "publicScore", "Score", "score")
            submitted = pick(row, "Date", "date", "Submitted", "submitted", "SubmissionDate")
            lines.append(f"| `{_cell(filename)}` | {_cell(status)} | {_cell(score)} | {_cell(submitted)} |")
    else:
        lines.append("_No submission rows were returned._")

    lines.extend(["", "## Public leaderboard — top 10", ""])
    if top10:
        team_key = next((key for key in top10[0] if key.lower() in {
            "teamname", "team_name", "team", "username", "user_name"
        }), "")
        score_key = next((key for key in top10[0] if key.lower() in {
            "score", "publicscore", "resolutionrate", "resolution_rate"
        }), "")
        lines.extend(["| Rank | Team / user | Score |", "|---:|---|---:|"])
        for position, row in enumerate(top10, start=1):
            rank = pick(row, "Rank", "rank") or str(position)
            name = row.get(team_key, "") if team_key else ""
            score = row.get(score_key, "") if score_key else ""
            lines.append(f"| {_cell(rank)} | {_cell(name)} | {_cell(score)} |")
    else:
        lines.append("_No leaderboard rows were returned._")

    if team:
        lines.extend(["", f"## Matched row for `{_cell(team)}`", ""])
        if our_rows:
            lines.append("```json")
            lines.append(json.dumps(our_rows, indent=2, ensure_ascii=False))
            lines.append("```")
        else:
            lines.append("_No exact team/user-name match. Check `team_filter`._")
    else:
        lines.extend([
            "",
            "_Set the repository Actions variable `KAGGLE_TEAM` to identify our",
            "leaderboard row by exact team/user name._",
        ])

    if problems:
        lines.extend(["", "## Poll warnings", ""])
        lines.extend(f"- {problem}" for problem in problems)
    lines.extend([
        "",
        "## Benchmark limitation",
        "",
        "This competition scores software-repair tasks; it does not expose",
        "head-to-head game episodes or opponent replays. The leaderboard can show",
        "public scores, but it does not reveal private submissions or their prompts.",
        "",
    ])
    (outdir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition", default=DEFAULT_COMPETITION)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--team", default=os.environ.get("KAGGLE_TEAM", "").strip())
    args = parser.parse_args()
    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    submissions: list[dict[str, str]] = []
    leaderboard: list[dict[str, str]] = []

    if not has_credentials():
        problems.append("No Kaggle credentials found in this Actions run.")
    else:
        code, stdout, stderr = kaggle([
            "competitions", "submissions", "-c", args.competition,
            "--format", "csv", "--page-size", "200", "-q",
        ])
        if code == 0:
            submissions = csv_rows(stdout)
            (outdir / "submissions.csv").write_text(stdout.rstrip() + "\n", encoding="utf-8")
        else:
            problems.append(f"submissions request failed: {_safe_error(stdout, stderr)}")

        leaderboard, error = leaderboard_csv(outdir, args.competition)
        if error:
            problems.append(error)

        if leaderboard:
            (outdir / "leaderboard.csv").touch(exist_ok=True)

    write_summary(outdir, args.competition, submissions, leaderboard, args.team, problems)
    print(f"Wrote read-only Kaggle poll results to {outdir}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
