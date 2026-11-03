"""Poświadczenia do testów uwierzytelnionych — wyłącznie z sekretów, nigdy z repo.

ZASADA: hasła i ciasteczka sesji nie przechodzą przez czat, nie trafiają do repo,
nie są wpisywane w kod. Wchodzą jedną drogą: jako **sekret GitHub Actions**
(`Settings → Secrets and variables → Actions`) i są odczytywane tutaj w czasie
wykonania. Ja ich nie widzę, a gdy sekret zostanie usunięty, ślad po nim znika.

Po co to w ogóle jest: §6 pkt 1 regulaminu pozwala testować uwierzytelnione
funkcje tylko z **własnych kont**. Bez tego modułu testy uwierzytelnione
kończą się na „nie da się" albo — gorzej — na ciasteczku wklejonym do skryptu.

Dwa formaty sekretu, oba jako jedna linia tekstu:

  NASK_COOKIE_MWDBCERTPL     = "session=abc123; csrf=xyz"        (nagłówek Cookie)
  NASK_TOKEN_N6PORTALCERTPL  = "Authorization: Bearer abc.def"   (cały nagłówek)

Nazwa sekretu = `NASK_COOKIE_` | `NASK_TOKEN_` + host bez kropek, wielkimi literami.
Dzięki temu jeden workflow obsługuje wiele celów, a dodanie celu nie wymaga
zmiany kodu.

Czego ten moduł NIE robi: nie loguje wartości, nie zapisuje jej do plików,
nie umieszcza w dzienniku dowodów (`fetch.py` zapisuje tylko nagłówki z białej
listy, a `cookie`/`authorization` na niej nie są).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ENV_PREFIXES = ("NASK_COOKIE_", "NASK_TOKEN_")

# Cele, dla których wolno wczytać poświadczenie. Świadomie WĄSKA lista, bo
# dopasowanie po fragmencie "token" złapałoby GITHUB_TOKEN i wysłało go do celu
# w scope. To byłby wyciek sekretu CI, nie ułatwienie.
ALLOWED_HOSTS = frozenset({
    "mwdb.cert.pl", "n6portal.cert.pl", "moje.cert.pl", "incydent.cert.pl",
    "dyzurnet.pl", "dns.pl", "nask.pl", "oad.nask.pl",
    "zglos-dezinformacje.nask.pl", "dataannotation.pllum.org.pl", "pllum.org.pl",
    "116sos.pl", "science.nask.pl", "bezpiecznymiesiac.pl", "bezpiecznewybory.pl",
    "secure.edu.pl", "komunikator.narodowy.gov.pl", "www.gov.pl", "cert.pl",
    "hack.cert.pl", "ctf.hack.cert.pl", "m.cert.pl",
})

# Detektor celowo szuka KSZTAŁTU poświadczenia, a nie słowa-klucza. Poprzednia
# wersja („linia zawiera 'session' i długi ciąg") flagowała mój własny plik
# testowy, bo tam jest `monkeypatch.setenv("NASK_COOKIE_...", "session=abc")`.
# Fałszywy alarm w bramce CI jest gorszy niż brak bramki: uczy ignorowania.
_CRED_SHAPES = (
    re.compile(r"\b(session|sess|sid|phpsessid|jsessionid|jwt|token|api[_-]?key|"
               r"authorization|auth)['\"]?\s*[=:]\s*['\"]?[A-Za-z0-9%_\-\.]{16,}", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),   # JWT
)
# Wyjątki: kod, który z założenia mówi o poświadczeniach, ale ich nie zawiera.
# `allowlist-secret` to jawny, audytowalny wyjątek dla atrap w testach — wzorzec
# znany z narzędzi typu Bandit/gitleaks. Wpisujemy go ŚWIADOMIE i tylko przy
# wartościach, które nie są prawdziwe.
_SAFE_MARKERS = ("os.environ", "getenv", "monkeypatch", "secrets.", "<", "${{", "xxxx",
                 "allowlist-secret")


class CredentialError(RuntimeError):
    pass


def env_key(host: str, kind: str = "cookie") -> str:
    """Nazwa sekretu dla hosta, np. `NASK_COOKIE_MWDB_CERT_PL`."""
    if kind not in ("cookie", "token"):
        raise CredentialError(f"nieznany rodzaj poświadczenia: {kind}")
    slug = host.lower().replace(".", "").replace("-", "").upper()
    return f"NASK_{kind.upper()}_{slug}"


def headers_for(host: str) -> dict[str, str]:
    """Nagłówki uwierzytelniające dla hosta (puste, gdy brak sekretu).

    Zwraca `{}` także wtedy, gdy sekret jest ustawiony dla hosta spoza listy —
    lepiej nie wysłać poświadczenia, niż wysłać je do złego miejsca.

    Kolejność: jawny nagłówek z `NASK_TOKEN_*` wygrywa z `NASK_COOKIE_*`,
    bo token jest bardziej szczegółowy niż sesja.
    """
    host = host.lower()
    if host not in ALLOWED_HOSTS:
        return {}
    out: dict[str, str] = {}
    cookie = (os.environ.get(env_key(host, "cookie")) or "").strip()
    if cookie:
        out["Cookie"] = cookie
    raw = (os.environ.get(env_key(host, "token")) or "").strip()
    if raw:
        first = raw.split(":", 1)[0]
        if ":" in raw and " " not in first:
            name, value = raw.split(":", 1)
            out[name.strip()] = value.strip()
        else:
            out["Authorization"] = raw
    return out


def audit() -> list[tuple[str, str, str]]:
    """Które sekrety są ustawione — BEZ wartości. Do logu workflow.

    Zwraca `(host, rodzaj, 'ustawiony'|'brak')`. Log pokazuje tylko nazwy hostów,
    więc można bezpiecznie wklejać go do artefaktu.
    """
    rows = []
    for name in sorted(os.environ):
        if not name.startswith(ENV_PREFIXES):
            continue
        kind = "cookie" if name.startswith("NASK_COOKIE_") else "token"
        host = name.split("_", 2)[2].lower()
        rows.append((host, kind, "ustawiony" if os.environ.get(name) else "brak"))
    return rows


def assert_no_plaintext_credentials(root: str | Path = ".") -> list[str]:
    """Skan repo: czy ktoś nie wkleił hasła/ciasteczka do pliku.

    Prosta heurystyka i taka ma być — to siatka bezpieczeństwa na wypadek
    zmęczenia, nie audyt bezpieczeństwa. Zwraca listę podejrzanych miejsc.
    """
    hits = []
    for path in Path(root).rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix not in {".py", ".json", ".md", ".yml", ".yaml", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(marker in line for marker in _SAFE_MARKERS):
                continue
            if any(shape.search(line) for shape in _CRED_SHAPES):
                hits.append(f"{path}:{lineno}")
    return hits
