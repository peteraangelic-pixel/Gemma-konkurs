"""Skaner autoryzacji po kodzie źródłowym aplikacji (offline).

Po co: w tym konkursie limit to 5 req/s, więc *myślenie* jest darmowe, a żądania
kosztują. Czytanie cudzego kodu jest jedyną pracą, której limit nie dotyczy —
i jedyną, w której mamy przewagę nad uczestnikami fuzzującymi na ślepo.

Co robi: dla każdej metody widoku (get/post/put/delete) zbiera **dekoratory**
i **ciało**, a następnie klasyfikuje:

  GUARDED   — wymaga uwierzytelnienia I sprawdza dostęp do obiektu
              (`access_object`, `.access(`, `has_rights`, `requires_capabilities`)
  PARTIAL   — wymaga tylko uwierzytelnienia; obiekt brany po identyfikatorze
              z żądania, bez widocznego sprawdzenia właściciela
  OPEN      — brak dekoratora `requires_authorization` i brak sprawdzenia

Dlaczego pierwsza wersja tego skryptu się myliła: patrzyła tylko na ciało funkcji,
a `mwdb-core` trzyma kontrolę dostępu w dekoratorach. Efekt: 30 fałszywych trafień
„BRAK KONTROLI" na endpointach, które są poprawnie zabezpieczone. Klasyfikator,
który oznacza wszystko jako podejrzane, jest gorszy niż brak klasyfikatora.

To NIE jest skaner podatności. To lista miejsc, które człowiek ma przeczytać.
Regulamin §8 poz. 14.4 wprost odrzuca raporty z automatów bez ręcznego potwierdzenia.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

VIEW_DEF = re.compile(
    r"^(?P<decorators>(?:[ \t]*@[^\n]*\n|[ \t]*@[^\n]*\n[ \t]*\([^)]*\)\n)*)"
    r"[ \t]*def (?P<name>(?:get|post|put|delete|patch))\((?P<args>[^)]*)\)",
    re.MULTILINE,
)
DECORATOR = re.compile(r"@([\w\.]+)")
ROUTE = re.compile(r"@api\.route\(\s*[\"']([^\"']+)[\"']")
CLASS_NAME = re.compile(r"^class (\w+)\((\w+)\)", re.MULTILINE)

# Sygnały sprawdzenia dostępu do KONKRETNEGO obiektu.
OBJECT_CHECK = ("access_object", ".access(", "get_by_download_token", "ensure_file_download_access")
# Sygnały kontroli uprawnień globalnych / ról. UWAGA: `requires_authorization`
# celowo tu NIE MA — to tylko uwierzytelnienie. Dopóki był na tej liście, endpoint
# „zalogowany + obiekt po ID" wychodził jako GUARDED, czyli najbardziej
# interesujący przypadek (PARTIAL) nigdy się nie pokazywał.
CAP_CHECK = ("has_rights", "requires_capabilities", "requires_file_download_access")
# Parametry, które wyglądają na identyfikator obiektu podany przez użytkownika.
ID_PARAM = re.compile(r"(identifier|_id\b|\bid\b|login|name|path|token|key)")


@dataclass
class Finding:
    file: str
    line: int
    klass: str
    method: str
    args: str
    verdict: str
    reason: str


def _classify(decorators: str, body: str, args: str) -> tuple[str, str]:
    has_auth = "requires_authorization" in decorators or "requires_authorization" in body
    has_cap = any(sig in decorators or sig in body for sig in CAP_CHECK)
    has_obj = any(sig in body for sig in OBJECT_CHECK)

    takes_id = bool(ID_PARAM.search(args)) and "self" in args
    fetches_by_id = bool(re.search(
        r"(query\(|get_by_|get_or_404|filter_by\(|\.filter\()", body)) and takes_id

    if has_obj:
        return "GUARDED", "sprawdza dostęp do obiektu"
    if has_cap:
        # `requires_capabilities` sam wymaga zalogowanego użytkownika
        # (`g.auth_user.has_rights`), więc capability implikuje uwierzytelnienie.
        return "GUARDED", "wymaga uprawnienia (implikuje zalogowanie)"
    if has_auth and takes_id and fetches_by_id:
        return "PARTIAL", "uwierzytelnienie jest, dostępu do obiektu nie widać"
    if has_auth:
        return "GUARDED", "uwierzytelnienie, brak identyfikatora w żądaniu"
    if takes_id and fetches_by_id:
        return "OPEN", "brak uwierzytelnienia i brak sprawdzenia obiektu"
    return "OPEN", "brak jakiejkolwiek kontroli w metodzie"


def scan(path: str | Path) -> list[Finding]:
    out: list[Finding] = []
    for f in sorted(Path(path).rglob("*.py")):
        if any(part in {".git", "tests", "migrations", "__pycache__"} for part in f.parts):
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        classes = [(m.start(), m.group(1)) for m in CLASS_NAME.finditer(src)]
        for m in VIEW_DEF.finditer(src):
            start = m.end()
            nxt = re.search(r"\n    @|\nclass |\ndef ", src[start:])
            body = src[start:start + (nxt.start() if nxt else len(src))]
            klass = "?"
            for pos, name in classes:
                if pos < m.start():
                    klass = name
            decorators = m.group("decorators")
            route = ""
            r = ROUTE.search(src, m.start() - 400)
            if r:
                route = r.group(1)
            verdict, reason = _classify(decorators, body, m.group("args"))
            out.append(Finding(
                file=str(f), line=src[:m.start()].count("\n") + 1,
                klass=klass, method=m.group("name").upper(),
                args=m.group("args").replace("self, ", "").replace("self", ""),
                verdict=verdict, reason=reason + (f" [route {route}]" if route else ""),
            ))
    return out


RANK = {"OPEN": 0, "PARTIAL": 1, "GUARDED": 2}


def rank(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (RANK[f.verdict], f.file, f.line))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="katalog z kodem aplikacji")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only-suspect", action="store_true",
                    help="pokaż tylko OPEN i PARTIAL")
    args = ap.parse_args(argv)

    findings = rank(scan(args.path))
    if args.only_suspect:
        findings = [f for f in findings if f.verdict != "GUARDED"]

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False))
        return 0

    for f in findings:
        mark = {"OPEN": "!!", "PARTIAL": " ?", "GUARDED": "  "}[f.verdict]
        print(f"{mark} {f.klass}.{f.method}({f.args})  {f.file}:{f.line}")
        print(f"     {f.verdict}: {f.reason}")
    counts = {v: sum(1 for f in findings if f.verdict == v) for v in RANK}
    print(f"\nOPEN={counts['OPEN']} PARTIAL={counts['PARTIAL']} GUARDED={counts['GUARDED']}")
    print("To lista do PRZECZYTANIA, nie lista podatności (§8 poz. 14.4).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
