#!/usr/bin/env python3
"""Exercise the submission guard chain without touching Kaggle.

tools/submit_kaggle_once.py runs unattended (a workflow fires it once, hours after the decision),
so its guards are tested here by monkeypatching the two functions that talk to the CLI. Every case
below is one failure mode that has actually been observed or that the competition rules make likely:

    python3 gemma4-agent/tools/selftest_submit_guard.py
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUBMITTER = ROOT / "gemma4-agent" / "tools" / "submit_kaggle_once.py"


def load_module():
    spec = importlib.util.spec_from_file_location("submit_kaggle_once", SUBMITTER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["submit_kaggle_once"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def rows(*entries: tuple[str, str]) -> list[dict[str, str]]:
    """Build fake submission rows: (date, message) pairs."""
    return [
        {"ref": str(1000 + i), "fileName": "submission.zip", "date": date,
         "description": message, "status": "SubmissionStatus.COMPLETE",
         "publicScore": "0.13", "privateScore": ""}
        for i, (date, message) in enumerate(entries)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default="V6.12")
    parser.add_argument("--expected-sha256",
                        default="5381ae17398f88ba434313439d9b784103dbab514bd7a0a3798a142f3c84c515")
    args = parser.parse_args()

    module = load_module()
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "submission.zip"
        archive.write_bytes(b"reviewed build bytes")
        # The guard-logic cases need a hash that MATCHES, so they pin the temporary file's own
        # digest; the pinned production hash is verified separately in case 7 against the real
        # committed archive (a fabricated file cannot carry that digest).
        good_sha = hashlib.sha256(archive.read_bytes()).hexdigest()

        def run(history, cli_result=(0, "", "", None), archive_path=archive, sha=None):
            calls: list[list[str]] = []

            def fake_kaggle(cli_args, timeout=180):
                calls.append(cli_args)
                if cli_args[:2] == ["competitions", "submissions"]:
                    return 0, csv_text(history), "", None
                return cli_result

            def fake_submissions():
                return history, None

            def csv_text(entries):
                header = "ref,fileName,date,description,status,publicScore,privateScore\n"
                body = "".join(
                    f"{e['ref']},{e['fileName']},{e['date']},{e['description']},{e['status']},"
                    f"{e['publicScore']},{e['privateScore']}\n"
                    for e in entries
                )
                return header + body

            module.kaggle = fake_kaggle
            module.submissions = fake_submissions
            receipt = tmp_path / "receipt.json"
            sys.argv = ["submit_kaggle_once.py", "--archive", str(archive_path),
                        "--message", args.message, "--expected-sha256", sha or good_sha,
                        "--result-json", str(receipt)]
            try:
                code = module.main()
            except SystemExit as exc:  # pragma: no cover - main returns rather than raises
                code = exc.code or 0
            return code, json.loads(receipt.read_text()), calls

        # 1. the uploaded bytes are not the reviewed build
        code, record, calls = run(rows(), sha="0" * 64)
        if record["status"] != "archive_hash_mismatch" or code != 2:
            failures.append(f"hash mismatch not refused: {record['status']} exit {code}")
        if any(call[:2] == ["competitions", "submit"] for call in calls):
            failures.append("hash mismatch still triggered an upload")

        # 2. the same message is already in the history (workflow retry after a lost response)
        code, record, calls = run(rows(("2026-10-16 00:05:00", args.message)))
        if record["status"] != "already_submitted" or record["submission_created"] is not False:
            failures.append(f"duplicate message not refused: {record['status']}")
        if any(call[:2] == ["competitions", "submit"] for call in calls):
            failures.append("duplicate message still triggered an upload")

        # 3. a submission from today (the one-per-day rule)
        today = module.datetime.now(module.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        code, record, calls = run(rows((today, "V6.12-other")))
        if record["status"] != "daily_slot_guard_blocked":
            failures.append(f"same-day submission not blocked: {record['status']}")
        if any(call[:2] == ["competitions", "submit"] for call in calls):
            failures.append("same-day submission still triggered an upload")

        # 4. a submission 12 hours old (within the rolling 24 h window, different calendar day)
        twelve_hours_ago = (module.datetime.now(module.timezone.utc)
                            - module.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        code, record, calls = run(rows((twelve_hours_ago, "V6.11")))
        if record["status"] != "daily_slot_guard_blocked":
            failures.append(f"submission inside 24 h not blocked: {record['status']}")

        # 4b. the exact failure that cost the V7-b slot on 2026-10-17: the previous submission was
        # 23 h 59 m 58 s old and the strict window refused the upload by two seconds.
        almost_a_day = (module.datetime.now(module.timezone.utc)
                        - module.timedelta(hours=23, minutes=59, seconds=58)).strftime("%Y-%m-%d %H:%M:%S")
        code, record, calls = run(rows((almost_a_day, "V6.0")))
        if record["status"] == "daily_slot_guard_blocked":
            failures.append("a submission 23 h 59 m 58 s old still blocks (the two-second bug is back)")
        if record["status"] not in ("submitted", "submitted_unconfirmed"):
            failures.append(f"23 h 59 m 58 s old should upload, got {record['status']}")

        # 5. an unparseable date in the history must stop the run, not guess
        code, record, calls = run(rows(("not-a-date", "V6.0")))
        if record["status"] != "daily_slot_unverified" or code != 4:
            failures.append(f"unparseable date not refused: {record['status']} exit {code}")

        # 6. a clean slot: the upload happens once and the history confirms it
        code, record, calls = run(rows(("2026-10-14 15:58:54", "V5")),
                                  cli_result=(0, "Successfully submitted", "", None))
        if record["status"] not in ("submitted", "submitted_unconfirmed"):
            failures.append(f"clean slot did not submit: {record['status']}")
        uploads = [call for call in calls if call[:2] == ["competitions", "submit"]]
        if len(uploads) != 1:
            failures.append(f"expected exactly one upload attempt, saw {len(uploads)}")
        if args.message not in uploads[0]:
            failures.append("the upload did not carry the requested message")

        # 7. the pinned sha of the real V6.12 archive (only when the caller did not override it)
        if args.expected_sha256 == "5381ae17398f88ba434313439d9b784103dbab514bd7a0a3798a142f3c84c515":
            committed = ROOT / "gemma4-agent" / "submission-v6.12.zip"
            actual = hashlib.sha256(committed.read_bytes()).hexdigest()
            if actual != args.expected_sha256:
                failures.append(f"submission-v6.12.zip hashes to {actual}, not the pinned value")

    if failures:
        print("SUBMIT-GUARD SELFTEST FAILURES:", file=sys.stderr)
        for item in failures:
            print("  - " + item, file=sys.stderr)
        return 1
    print("submit-guard selftest: 8/8 cases pass "
          "(hash mismatch, duplicate message, same-day slot, 24 h window, unparseable date, "
          "clean submit, pinned V6.12 hash)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
