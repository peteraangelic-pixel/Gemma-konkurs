#!/usr/bin/env python3
"""Selftest for the boundary-wait step inside the official-submit workflow.

The workflow sleeps until the next 00:05 UTC when it is ARMED by a trigger push (that is 02:05
Warsaw, the moment the competition's daily submission slot refreshes). Getting that arithmetic
wrong is expensive - sending too early wastes the following day's slot, and sending too late
misses the window - so the step's own code is executed here with a frozen clock and a recording
`time.sleep` instead of a real multi-hour wait:

    A) armed at 20:19 UTC      -> waits 3 h 46 min for 00:05 UTC
    B) armed at 12:00 UTC      -> refuses (boundary 12 h away), nothing sent, trigger kept
    C) manual dispatch send_now-> no wait at all
    D) manual wait_boundary    -> honours the same boundary arithmetic

Run: python3 gemma4-agent/tools/selftest_wait_step.py   (exit 0 = all cases pass)
"""
from __future__ import annotations

import datetime as real_dt
import os
import pathlib
import re
import sys
import types

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/gemma-kaggle-official-submit-next.yml"
STEP_SENTINEL = "- name: Wait for the next UTC daily boundary when arming for the night"
NEXT_SENTINEL = "      - name: Set up Python"
UTC = real_dt.timezone.utc


def extract_step_code(text: str) -> str:
    step = text.split(STEP_SENTINEL, 1)[1].split(NEXT_SENTINEL, 1)[0]
    body = re.search(r"<<'PY'\n(.*?)\n\s*PY\n", step, re.S)
    if not body:
        raise SystemExit("the wait step no longer contains a PY heredoc; update this selftest")
    return "\n".join(line[10:] if line.startswith(" " * 10) else line for line in body.group(1).splitlines())


def run_case(code: str, *, event: str, mode: str, now: real_dt.datetime, max_wait: str):
    sleeps: list[float] = []
    fake_dt = types.ModuleType("datetime")
    fake_dt.datetime = type("datetime", (), {"now": staticmethod(lambda tz=None: now)})
    fake_dt.timedelta = real_dt.timedelta
    fake_dt.timezone = real_dt.timezone
    import time as real_time

    fake_time = types.ModuleType("time")
    fake_time.__dict__.update({k: v for k, v in real_time.__dict__.items() if not k.startswith("__")})
    fake_time.sleep = lambda seconds: sleeps.append(seconds)

    saved_modules = {name: sys.modules.get(name) for name in ("datetime", "time")}
    saved_env = {name: os.environ.get(name) for name in ("EVENT_NAME", "REQUESTED_MODE", "MAX_WAIT_HOURS")}
    sys.modules["datetime"], sys.modules["time"] = fake_dt, fake_time
    os.environ["EVENT_NAME"], os.environ["REQUESTED_MODE"], os.environ["MAX_WAIT_HOURS"] = event, mode, max_wait
    try:
        exec(compile(code, "wait-step", "exec"), {"__name__": "__main__"})
        rc: int | None = 0
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 0
    finally:
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
    cases = [
        (
            "armed at 20:19 UTC -> waits to 00:05 UTC",
            dict(event="push", mode="", now=real_dt.datetime(2026, 10, 15, 20, 19, tzinfo=UTC), max_wait="5"),
            0,
            3 * 3600 + 46 * 60,
        ),
        (
            "armed at 12:00 UTC -> refuses without consuming the trigger",
            dict(event="push", mode="", now=real_dt.datetime(2026, 10, 15, 12, 0, tzinfo=UTC), max_wait="5"),
            1,
            None,
        ),
        (
            "manual send_now -> no wait",
            dict(event="workflow_dispatch", mode="send_now", now=real_dt.datetime(2026, 10, 16, 1, 30, tzinfo=UTC), max_wait="5"),
            0,
            0,
        ),
        (
            "manual wait_boundary at 23:50 UTC -> waits 15 min",
            dict(event="workflow_dispatch", mode="wait_boundary", now=real_dt.datetime(2026, 10, 15, 23, 50, tzinfo=UTC), max_wait="5"),
            0,
            15 * 60,
        ),
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
