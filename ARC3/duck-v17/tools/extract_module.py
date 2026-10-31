#!/usr/bin/env python3
"""Wypakuj z notebooka patch template i porównaj z plikami źródłowymi autora.

Używane przez testy: dowodzi, że wysyłane bajty (notebook) == to, co testowano.
    python3 tools/extract_module.py arc3-duck-v17.ipynb [katalog_wyjściowy]
"""
import ast
import json
import pathlib
import re
import sys


def patch_text(nb_path):
    nb = json.loads(pathlib.Path(nb_path).read_text())
    for cell in nb["cells"]:
        text = "".join(cell.get("source", []))
        if "codex_template_transfer.py" not in text:
            continue
        for m in re.finditer(r"write_text\(", text):
            rest = text[m.end():]
            for end in range(len(rest), 0, -1):
                try:
                    return ast.literal_eval(rest[:end])
                except Exception:
                    continue
    raise SystemExit("nie znaleziono patcha template w notatniku")


def files(patch):
    out = {}
    for part in re.split(r"(?m)^diff --git ", patch)[1:]:
        name = re.findall(r"\+\+\+ b/(\S+)", part)[0]
        added = [l[1:] for l in part.splitlines() if l.startswith("+") and not l.startswith("+++")]
        out[name] = "\n".join(added)
    return out


def main(argv):
    nb = argv[1] if len(argv) > 1 else "arc3-duck-v17.ipynb"
    dest = pathlib.Path(argv[2] if len(argv) > 2 else "/tmp/v17-extract")
    dest.mkdir(parents=True, exist_ok=True)
    p = patch_text(nb)
    for name, body in files(p).items():
        target = dest / pathlib.Path(name).name
        target.write_text(body)
        print(f"{len(body):7} B  {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
