#!/usr/bin/env python3
"""Selftest for the send-now / wait-for-boundary step of the official-submit workflow.

That step decides whether a trigger push uploads immediately or sleeps until 00:10 UTC. Getting the
arithmetic wrong is expensive in both directions, and the failure mode is not hypothetical: on
2026-10-17 at 00:05:05 UTC the guard blocked the V7-b upload by two seconds because the previous
submission was 23 h 59 m 58 s old. So the step's own code runs here with a frozen clock, a recording
`time.sleep`, and fixture receipts:

    A) push, newest submission 25.4 h old  -> send now, no sleep
    B) push, newest submission 23.9 h old, boundary 22 h away -> refuse, trigger kept
    C) push, newest submission 23.9 h old, boundary 2 h away  -> sleep those 2 h
    D) no receipts at all                   -> send now
    E) manual dispatch send_now             -> no sleep
    F) manual dispatch wait_boundary        -> honours the same arithmetic

Run: python3 gemma4-agent/tools/selftest_wait_step.py   (exit 0 = all cases pass)
"""
from __future__ import annotations

import datetime as real_dt
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import types

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/gemma-kaggle-official-submit-next.yml"
STEP_SENTINEL = "- name: Decide whether to send now or wait for the daily boundary"
NEXT_SENTINEL = "      - name: Set up Python"
UTC = real_dt.timezone.utc
RECEIPT_DIR = pathlib.Path("gemma4-agent/kaggle_results")


def extract_step_code(text: str) -> str:
    step = text.split(STEP_SENTINEL, 1)[1].split(NEXT_SENTINEL, 1)[0]
    body = re.search(r"<<'PY'\n(.*?)\n\s*PY\n", step, re.S)
    if not body:
        raise SystemExit("the decision step no longer contains a PY heredoc; update this selftest")
    return "\n".join(line[10:] if line.startswith(" " * 10) else line for line in body.group(1).splitlines())


def write_receipt(root: pathlib.Path, name: str, submitted_at: str, created: bool = True) -> None:
    directory = root / RECEIPT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "status": "submitted" if created else "daily_slot_guard_blocked",
        "submission_created": created,
        "submission": {"ref": "00000000", "date": submitted_at},
    }
    (directory / name).write_text(json.dumps(record), encoding="utf-8")


def run_case(code: str, *, event: str, mode: str, now: real_dt.datetime, max_wait: str, receipts: list[tuple[str, str, bool]]):
    sleeps: list[float] = []
    fake_dt = types.ModuleType("datetime")
    fake_dt.datetime = type("datetime", (), {"now": staticmethod(lambda tz=None: now), "fromisoformat": staticmethod(real_dt.datetime.fromisoformat)})
    fake_dt.timedelta = real_dt.timedelta
    fake_dt.timezone = real_dt.timezone
    import time as real_time

    fake_time = types.ModuleType("time")
    fake_time.__dict__.update({k: v for k, v in real_time.__dict__.items() if not k.startswith("__")})
    fake_time.sleep = lambda seconds: sleeps.append(seconds)

    saved_modules = {name: sys.modules.get(name) for name in ("datetime", "time")}
    saved_env = {name: os.environ.get(name) for name in ("EVENT_NAME", "REQUESTED_MODE", "MAX_WAIT_HOURS")}
    saved_cwd = os.getcwd()
    rc: int | None = None
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for name, at, created in receipts:
            write_receipt(root, name, at, created)
        sys.modules["datetime"], sys.modules["time"] = fake_dt, fake_time
        os.environ["EVENT_NAME"], os.environ["REQUESTED_MODE"], os.environ["MAX_WAIT_HOURS"] = event, mode, max_wait
        os.chdir(root)
        try:
            exec(compile(code, "decision-step", "exec"), {"__name__": "__main__"})
            rc = 0
        except SystemExit as exc:
            rc = exc.code if isinstance(exc.code, int) else 0
        finally:
            os.chdir(saved_cwd)
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
            for name, value in saved_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
    return rc, sleeps


def main() -> int:
    code = extract_step_code(WORKFLOW.read_text(encoding="utf-8"))
    now_0130 = real_dt.datetime(2026, 10, 17, 1, 30, tzinfo=UTC)
    old = ("v612-official-submission.json", "2026-10-16 00:05:07.063000", True)
    fresh = ("v612-official-submission.json", "2026-10-17 01:42:00", True)
    blocked = ("v7b-official-submission.json", "2026-10-17 00:05:05", False)

    cases = [
        ("push, newest submission 25.4 h old -> send now", dict(event="push", mode="", now=now_0130, max_wait="5", receipts=[old, blocked]), 0, 0),
        ("push, newest submission 23.9 h old, boundary 22.5 h away -> refuse", dict(event="push", mode="", now=now_0130, max_wait="5", receipts=[fresh]), 1, None),
        ("push, recent submission, boundary 2 h away -> sleep 2 h", dict(event="push", mode="", now=real_dt.datetime(2026, 10, 17, 22, 10, tzinfo=UTC), max_wait="5", receipts=[("vX-official-submission.json", "2026-10-17 21:30:00", True)]), 0, 2 * 3600),
        ("push, no receipts at all -> send now", dict(event="push", mode="", now=now_0130, max_wait="5", receipts=[]), 0, 0),
        ("manual send_now -> no sleep", dict(event="workflow_dispatch", mode="send_now", now=now_0130, max_wait="5", receipts=[fresh]), 0, 0),
        ("manual wait_boundary, boundary 2 h away -> sleep", dict(event="workflow_dispatch", mode="wait_boundary", now=real_dt.datetime(2026, 10, 17, 22, 10, tzinfo=UTC), max_wait="5", receipts=[("vX-official-submission.json", "2026-10-17 21:30:00", True)]), 0, 2 * 3600),
        ("blocked receipt is not a submission -> send now", dict(event="push", mode="", now=now_0130, max_wait="5", receipts=[blocked]), 0, 0),
    ]
    failures = 0
    for name, kwargs, want_rc, want_sleep in cases:
        rc, sleeps = run_case(code, **kwargs)
        slept = sleeps[0] if sleeps else (0 if want_sleep == 0 else None)
        good = rc == want_rc and (want_sleep is None or (slept is not None and abs(slept - want_sleep) < 1))
        failures += 0 if good else 1
        shown = "no sleep" if slept is None else f"{round(slept)}s"
        print(f"[{'PASS' if good else 'FAIL'}] {name}: rc={rc} (want {want_rc}), slept {shown} (want {want_sleep})")
    print(f"{len(cases) - failures}/{len(cases)} cases pass" if not failures else f"{failures} case(s) FAILED")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
