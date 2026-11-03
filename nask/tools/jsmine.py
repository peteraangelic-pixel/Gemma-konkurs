"""Wyciąganie powierzchni ataku z plików JS/HTML — offline, bez sieci, testowalne.

Po co: w aplikacji SPA (a takie jest większość celów: Next.js/Nuxt/Envoy) mapa
endpointów NIE jest w dokumentacji, tylko w bundlach. To najtańsze źródło
hipotez dla klas 9 (IDOR/BAC), 12 (API) i 13 (mass assignment) — czyli tych,
które płacą 4000-20000 zł.

Czego ten moduł NIE robi: nie wysyła żądań, nie ocenia "czy podatne". Wyciąga
kandydatów, a człowiek je weryfikuje (regulamin §8 poz. 14.4 wyklucza raporty
z automatów bez ręcznego potwierdzenia).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

# Endpointy: ścieżki w stringach JS oraz pełne URL-e do API.
_PATH_RE = re.compile(r"""["'`](/(?:api|v\d+|graphql|internal|admin|user|auth|rest|rpc)
                       [A-Za-z0-9_\-/{}.$:]{0,120})["'`]""", re.X)
_ABS_RE = re.compile(r"""["'`](https?://[A-Za-z0-9.\-]+(?::\d+)?
                      /[A-Za-z0-9_\-/{}.$:]{0,120})["'`]""", re.X)
# Parametry: pary klucz= w query stringach oraz typowe nazwy pól API.
_QUERY_RE = re.compile(r"[?&]([A-Za-z_][A-Za-z0-9_]{1,30})=")
# Wysoko-sygnałowe nazwy pól — dokładnie te, które dają IDOR/mass assignment.
_HOT_FIELDS = re.compile(
    r"""["']?(id|uid|user_?id|account_?id|owner_?id|tenant_?id|org_?id|role|roles
        |is_?admin|is_?verified|permissions?|status|email|phone|token
        |conversation_?id|message_?id|device_?id|attachment_?id)["']?\s*:""", re.X)
_SECRETS = re.compile(
    r"""(?i)\b(api[_-]?key|apikey|secret|client[_-]?secret|bearer|authorization
        |aws_access_key_id|private[_-]?key)\b\s*[:=]\s*["'][^"']{8,}["']""", re.X)
_IP_RE = re.compile(r"\b(?:10|127|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b")
_SOURCEMAP = re.compile(r"sourceMappingURL=([A-Za-z0-9_\-./]+\.map)")
_TECH = {
    "next.js": ("__NEXT_DATA__", "_next/static"),
    "nuxt": ("__NUXT__", "_nuxt/"),
    "react": ("react-dom", "ReactDOM"),
    "vue": ("__VUE__", "vue.runtime"),
    "angular": ("ng-version", "angular.min.js"),
    "wordpress": ("wp-content", "wp-json"),
    "drupal": ("drupal-settings-json", "/sites/default/files/"),
}


@dataclass(frozen=True)
class Finding:
    kind: str        # endpoint | url | param | hot_field | secret | internal_ip | sourcemap | tech
    value: str
    hint: str        # klasa podatności / dlaczego to ciekawe


def _dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def mine(text: str, base_host: str = "") -> list[Finding]:
    """Zwraca posortowaną listę kandydatów (bez duplikatów)."""
    found: list[Finding] = []

    for m in _PATH_RE.finditer(text):
        found.append(Finding("endpoint", m.group(1),
                             "klasa 12: sprawdź autoryzację i IDOR na tym endpoincie"))
    for m in _ABS_RE.finditer(text):
        url = m.group(1)
        host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]
        if base_host and host == base_host:
            found.append(Finding("endpoint", url, "klasa 12: endpoint tej samej aplikacji"))
        else:
            found.append(Finding("url", url,
                                 "inna domena — najpierw sprawdź scope, potem traktuj jako zależność"))
    for m in _QUERY_RE.finditer(text):
        found.append(Finding("param", m.group(1), "kandydat na IDOR/SSRF/open redirect"))
    for m in _HOT_FIELDS.finditer(text):
        found.append(Finding("hot_field", m.group(1),
                             "klasa 13/9: sprawdź, czy serwer przyjmuje to pole od klienta"))
    for m in _SECRETS.finditer(text):
        found.append(Finding("secret", m.group(0)[:80],
                             "klucz — ale uwaga: §8 poz. 12.1/12.2 wyklucza klucze bez możliwości nadużycia"))
    for m in _IP_RE.finditer(text):
        found.append(Finding("internal_ip", m.group(0),
                             "adres wewnętrzny w kodzie — trop pod SSRF (klasa 5)"))
    for m in _SOURCEMAP.finditer(text):
        found.append(Finding("sourcemap", m.group(1),
                             "mapa źródeł — jeśli publiczna, daje pełny kod frontendu"))
    low = text.lower()
    for tech, needles in _TECH.items():
        if any(n.lower() in low for n in needles):
            found.append(Finding("tech", tech, "technologia — dobierz testy do stacku"))

    # deduplikacja po (kind, value), zachowanie kolejności
    uniq, seen = [], set()
    for f in found:
        key = (f.kind, f.value)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    return uniq


def rank(findings: list[Finding]) -> list[Finding]:
    """Kolejność wg tego, co płaci: IDOR/API > SSRF > reszta > szum."""
    weight = {"hot_field": 0, "endpoint": 1, "param": 2, "internal_ip": 3,
              "sourcemap": 4, "tech": 5, "url": 6, "secret": 7}
    return sorted(findings, key=lambda f: (weight.get(f.kind, 9), f.value))


def as_dicts(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]
