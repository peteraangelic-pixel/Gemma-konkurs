#!/usr/bin/env python3
"""Zbuduj duck-v17: champion v3 + kontroler `template` + guard (limit + kill-switch).

Wejście: `src/base-v3-template.ipynb` — notebook autora (gałąź codex/arc-local-lab-v18-20261030,
SHA256 550eb185…d5fa), który JEST championem v3 (`ARC3_VARIANT.name = "v3-world-model"`,
patche 0001+0002, zmierzony wynik 26,25) plus kontroler `template` (3 poziomy ft09 / 25 akcji).

Zmiany (wszystkie odwracalne):
  1. do patcha dochodzi czwarty plik `codex_template_guarded.py` (limit 32 propozycji/poziom
     + przełącznik `ARC3_TEMPLATE`), wzięty z `src/vendor/`,
  2. snippet instalacyjny w `tool_agent.py` instaluje warstwę guard zamiast gołego hooka,
  3. nazwa wariantu `v17-champion-template`.

`ARC3_TEMPLATE=0` → zachowanie identyczne z championem v3 (hook nie jest instalowany
i analyze wraca do oryginału).

    python3 tools/build_v17.py [--src ...] [--out ...]
"""
import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent

GUARD_SRC = PKG / "src/vendor/codex_template_guarded.py"
GUARD_PATH = "ARC3-Inference/inference/utils/codex_template_guarded.py"

NAME_FROM = 'ARC3_VARIANT["name"] = "codex-template-lab"'
NAME_TO = 'ARC3_VARIANT["name"] = "v17-champion-template"'

# stary koniec patcha: instalacja gołego hooka
ORIG_TAIL = (
    "+\\n"
    "+\\n"
    "+from inference.utils.codex_template_transfer import TemplateTransfer as _TemplateTransfer\\n"
    "+from inference.utils.codex_template_hook import install as _install_template_controller\\n"
    "+_install_template_controller(__import__(__name__, fromlist=[\"ToolAgent\"]),_TemplateTransfer)\\n"
)
# nowy koniec: instalacja warstwy guard (sama sprawdza ARC3_TEMPLATE)
NEW_TAIL = (
    "+\\n"
    "+from inference.utils.codex_template_guarded import install as _install_guarded_template\\n"
    "+_install_guarded_template(__import__(__name__, fromlist=[\"ToolAgent\"]))\\n"
)
# 3 linie kontekstu + 5 dodanych (stary ogon) → 3 + 3 (nowy ogon) = 6
HUNK_FROM = "@@ -7432,3 +7432,8 @@"
HUNK_TO = "@@ -7432,3 +7432,6 @@"


def _cell_escape(line: str) -> str:
    """Jedna linia patcha → forma w literale Pythona w komórce (bez realnych newline'ów)."""
    return line.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def guard_segment() -> str:
    body = GUARD_SRC.read_text()
    if not body.endswith("\n"):
        body += "\n"
    lines = body.split("\n")[:-1]
    out = [f"diff --git a/{GUARD_PATH} b/{GUARD_PATH}",
           "new file mode 100644",
           "index 0000000..1111111",
           "--- /dev/null",
           f"+++ b/{GUARD_PATH}",
           f"@@ -0,0 +1,{len(lines)} @@"]
    out.extend("+" + l for l in lines)
    return "\\n".join(_cell_escape(l) for l in out) + "\\n"


def build(src: pathlib.Path, out: pathlib.Path) -> dict:
    raw = src.read_bytes()
    nb = json.loads(raw)
    hits = {"tail": 0, "name": 0, "segment": 0}

    for cell in nb["cells"]:
        text = "".join(cell.get("source", []))
        original = text
        if ORIG_TAIL in text:
            if HUNK_FROM not in text:
                raise SystemExit("brak nagłówka hunka do przeliczenia")
            text = text.replace(HUNK_FROM, HUNK_TO)
            text = text.replace(ORIG_TAIL, NEW_TAIL)
            # nowy plik wstawiamy przed hunkiem tool_agent.py
            text = text.replace("diff --git a/ARC3-Inference/inference/agent/tool_agent.py",
                                guard_segment() + "diff --git a/ARC3-Inference/inference/agent/tool_agent.py", 1)
            hits["tail"] += 1
            hits["segment"] += 1
        if NAME_FROM in text:
            text = text.replace(NAME_FROM, NAME_TO)
            hits["name"] += 1
        if text != original:
            cell["source"] = text.splitlines(keepends=True)

    for key, want in (("tail", 1), ("name", 1), ("segment", 1)):
        if hits[key] != want:
            raise SystemExit(f"{key}: oczekiwano {want}, jest {hits[key]}")

    payload = json.dumps(nb, ensure_ascii=False, indent=1) + "\n"
    out.write_text(payload)
    return {
        "src_bytes": len(raw),
        "src_sha256": hashlib.sha256(raw).hexdigest(),
        "out_bytes": len(payload.encode()),
        "out_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "cells": len(nb["cells"]),
        "hits": hits,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=pathlib.Path, default=PKG / "src/base-v3-template.ipynb")
    ap.add_argument("--out", type=pathlib.Path, default=PKG / "arc3-duck-v17.ipynb")
    a = ap.parse_args(argv)
    info = build(a.src, a.out)
    print(f"src  {a.src}  {info['src_bytes']} B  sha256 {info['src_sha256']}")
    print(f"out  {a.out}  {info['out_bytes']} B  sha256 {info['out_sha256']}")
    print(f"komórek {info['cells']}; podmiany {info['hits']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
