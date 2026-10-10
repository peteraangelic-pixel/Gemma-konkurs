#!/usr/bin/env python3
"""Submit the verified V2 ZIP once, with a Kaggle history/daily-slot guard.

Authentication is provided by the GitHub Actions runner's standard Kaggle CLI
credential file. This script never reads, prints, or writes the API token.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any

COMPETITION = "gemma-4-developer-agent"
EXPECTED_SHA256 = "853fe9845c879465d2df55d00d052f3adde9f466b36dffeef5785f0a75eaa000"
EXPECTED_FILENAME = "submission-v2.zip"
SUBMISSION_MESSAGE = "V2"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def kaggle(args: list[str], timeout: int = 180) -> tuple[int | None, str, str, str | None]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "kaggle", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "", "", "timeout"
    except OSError as exc:
        return None, "", "", type(exc).__name__
    return completed.returncode, completed.stdout, completed.stderr, None


def submissions() -> tuple[list[dict[str, str]] | None, str | None]:
    code, stdout, _, error = kaggle(
        [
            "competitions",
            "submissions",
            "-c",
            COMPETITION,
            "--format",
            "csv",
            "--page-size",
            "200",
            "-q",
        ]
    )
    if error:
        return None, error
    if code != 0:
        return None, f"Kaggle submissions query failed (CLI exit {code})."
    content = stdout.removeprefix("\ufeff").strip()
    if not content:
        return [], None
    try:
        return list(csv.DictReader(io.StringIO(content))), None
    except csv.Error:
        return None, "Kaggle submissions response was not valid CSV."


def field(row: dict[str, str], *names: str) -> str:
    lowered = {key.strip().casefold(): (value or "").strip() for key, value in row.items() if key}
    for name in names:
        if name.casefold() in lowered:
            return lowered[name.casefold()]
    return ""


def submission_ref(row: dict[str, str]) -> dict[str, Any]:
    return {
        "ref": field(row, "ref", "id"),
        "file_name": field(row, "fileName", "filename", "file"),
        "date": field(row, "date", "submitted", "submissionDate"),
        "description": field(row, "description", "message"),
        "status": field(row, "status"),
        "public_score": field(row, "publicScore", "score"),
        "private_score": field(row, "privateScore"),
    }


def matching_v2(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row for row in rows
        if field(row, "fileName", "filename", "file").casefold() == EXPECTED_FILENAME.casefold()
    ]


def latest_submission(rows: list[dict[str, str]]) -> dict[str, str]:
    return max(
        rows,
        key=lambda row: parse_utc_date(field(row, "date", "submitted", "submissionDate"))
        or datetime.min.replace(tzinfo=timezone.utc),
    )


def classify_cli_error(*outputs: str) -> str:
    """Return a coarse, non-sensitive category; never persist raw CLI output."""
    text = "\n".join(outputs).casefold()
    categories = (
        ("daily_submission_limit", ("daily limit", "one submission per day", "24 hour", "24-hour", "too many submissions")),
        ("authentication_or_permission", ("unauthorized", "forbidden", "permission denied", "not authorized", "401", "403", "invalid token")),
        ("competition_access_or_rules", ("accept the competition rules", "not joined", "competition is closed", "not accepting submissions", "competition not found", "404")),
        ("network_or_service", ("timed out", "timeout", "connection error", "connection reset", "502", "503", "504", "internal server error")),
        ("upload_or_archive", ("file too large", "upload failed", "invalid zip", "archive", "no such file")),
    )
    for category, markers in categories:
        if any(marker in text for marker in markers):
            return category
    return "unclassified" if text.strip() else "no_diagnostic_text"


def parse_utc_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def finish(path: Path, record: dict[str, Any], exit_code: int = 0) -> int:
    record["checked_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json(path, record)
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return exit_code


def reconcile_submission(
    record: dict[str, Any],
    code: int | None,
    submit_error: str | None,
    stdout: str,
    stderr: str,
) -> int:
    """Check Kaggle history after every attempt without exposing raw CLI output."""
    if code is not None:
        record["cli_exit_code"] = code
    if submit_error:
        record["error_type"] = submit_error
    if code != 0 or submit_error:
        record["cli_error_category"] = classify_cli_error(stdout, stderr)

    after_rows, after_error = submissions()
    if after_rows is None:
        record.update(
            {
                "status": "submission_inconclusive",
                "submission_created": "unknown",
                "post_submit_query_error": after_error,
                "retry_warning": "Do not retry until a read-only Kaggle submissions check confirms the V2 status.",
            }
        )
        return finish_code_for_attempt(code, submit_error)

    matches = matching_v2(after_rows)
    if matches:
        record.update(
            {
                "status": "submitted" if code == 0 and not submit_error else "submitted_despite_cli_error",
                "submission_created": True,
                "submission": submission_ref(latest_submission(matches)),
                "retry_warning": "Do not resubmit this ZIP; use the recorded submission ref/status.",
            }
        )
        return 0

    if code == 0 and not submit_error:
        record.update(
            {
                "status": "submitted_unconfirmed",
                "submission_created": "accepted_by_cli",
                "post_submit_history_check": "Kaggle CLI accepted the upload, but no V2 row is visible yet.",
                "retry_warning": "Do not resubmit this ZIP; check Kaggle history/status first.",
            }
        )
        return 0

    record.update(
        {
            "status": "submission_inconclusive",
            "submission_created": "unknown",
            "post_submit_history_check": "No matching V2 row was visible in the immediate post-submit history query.",
            "retry_warning": "Do not retry until a later read-only Kaggle submissions check confirms the V2 ZIP is absent.",
        }
    )
    return finish_code_for_attempt(code, submit_error)


def finish_code_for_attempt(code: int | None, submit_error: str | None) -> int:
    return 5 if submit_error else 6 if code != 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()

    record: dict[str, Any] = {
        "competition": COMPETITION,
        "filename": EXPECTED_FILENAME,
        "message": SUBMISSION_MESSAGE,
        "sha256_expected": EXPECTED_SHA256,
        "status": "preflight",
        "official_submission_requested": True,
    }
    try:
        archive = args.archive.read_bytes()
    except OSError as exc:
        record.update({"status": "archive_missing", "error_type": type(exc).__name__})
        return finish(args.result_json, record, 2)

    actual_sha = hashlib.sha256(archive).hexdigest()
    record["sha256_actual"] = actual_sha
    if actual_sha != EXPECTED_SHA256:
        record.update({"status": "archive_hash_mismatch", "submission_created": False})
        return finish(args.result_json, record, 2)

    rows, query_error = submissions()
    if rows is None:
        record.update({"status": "preflight_failed", "submission_created": False, "error": query_error})
        return finish(args.result_json, record, 3)

    # Never send the same V2 file twice, including after a workflow retry where
    # the upload may have succeeded but the original runner lost its response.
    prior_v2 = [
        row for row in rows
        if field(row, "fileName", "filename", "file").casefold() == EXPECTED_FILENAME.casefold()
    ]
    if prior_v2:
        record.update(
            {
                "status": "already_submitted",
                "submission_created": False,
                "existing_submission": submission_ref(prior_v2[0]),
            }
        )
        return finish(args.result_json, record)

    now = datetime.now(timezone.utc)
    parsed_dates: list[tuple[datetime, dict[str, str]]] = []
    dates_unparseable: list[str] = []
    for row in rows:
        value = field(row, "date", "submitted", "submissionDate")
        if not value:
            continue
        parsed = parse_utc_date(value)
        if parsed is None:
            dates_unparseable.append(value)
        else:
            parsed_dates.append((parsed, row))

    if dates_unparseable:
        record.update(
            {
                "status": "daily_slot_unverified",
                "submission_created": False,
                "unparseable_submission_date_count": len(dates_unparseable),
            }
        )
        return finish(args.result_json, record, 4)

    recent = [
        row
        for submitted_at, row in parsed_dates
        if submitted_at.date() == now.date() or now - submitted_at < timedelta(hours=24)
    ]
    if recent:
        newest = max(
            (item for item in parsed_dates if item[1] in recent),
            key=lambda item: item[0],
        )
        record.update(
            {
                "status": "daily_slot_guard_blocked",
                "submission_created": False,
                "recent_submission": submission_ref(newest[1]),
                "daily_slot_guard": "One submission today or within the last 24 hours was found; no upload attempted.",
            }
        )
        return finish(args.result_json, record)

    # The file has been hash-checked and both duplicate/daily-slot checks passed.
    # Never print or persist raw CLI output. Always query history after the attempt.
    code, stdout, stderr, submit_error = kaggle(
        [
            "competitions",
            "submit",
            "-c",
            COMPETITION,
            "-f",
            str(args.archive),
            "-m",
            SUBMISSION_MESSAGE,
        ],
        timeout=600,
    )
    exit_code = reconcile_submission(record, code, submit_error, stdout, stderr)
    return finish(args.result_json, record, exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
