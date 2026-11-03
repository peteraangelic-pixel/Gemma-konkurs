"""Generator zgłoszenia — wymusza kompletność, zanim raport trafi na platformę.

Regulamin §8 poz. 14.1 wyklucza zgłoszenia bez PoC, a poz. 14.4 — raporty
z automatów bez ręcznego potwierdzenia. Ten generator **odmawia** wygenerowania
raportu, jeśli brakuje dowodu, kroków odtworzenia albo opisu wpływu. To celowe:
jeden dobry raport jest wart więcej niż pięć "potencjalnych".
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

REQUIRED = ("title", "host", "cls", "cvss", "summary", "impact",
            "steps", "evidence_path", "fix")

TEMPLATE = """# {title}

**Data:** {date}
**Program:** {program} ({tier})
**Host:** `{host}`
**Klasa (regulamin §8):** {cls}
**CVSS 4.0:** {cvss}
**Nagroda wg tabeli:** {payout} zł ({severity})

## Streszczenie

{summary}

## Wpływ na bezpieczeństwo

{impact}

## Kroki odtworzenia (PoC)

{steps}

## Dowody

- Plik dowodów (JSONL z surowymi żądaniami): `{evidence_path}`
- SHA-256 dowodów: `{evidence_sha}`
- Konta użyte: **wyłącznie własne** (regulamin §6 pkt 1)

## Propozycja poprawki

{fix}

## Oświadczenia

- [ ] Testy wykonano wyłącznie w zakresie programu (§5).
- [ ] Nie użyto kont innych użytkowników (§6 pkt 1).
- [ ] Nie wykonano żadnego testu obciążeniowego ani DoS (§8 poz. 10).
- [ ] Szybkość narzędzi ≤ 5 req/s (§6 pkt 2).
- [ ] Zgłoszenie zawiera działający PoC (§8 poz. 14.1).
- [ ] Nie upubliczniono luki (§9).
"""


@dataclass
class Report:
    title: str
    host: str
    program: str
    tier: str
    cls: str
    cvss: str
    summary: str
    impact: str
    steps: str
    evidence_path: str
    fix: str
    payout: int = 0
    severity: str = "sredni"

    def missing(self) -> list[str]:
        gaps = [f for f in REQUIRED if not str(getattr(self, f, "")).strip()]
        if self.evidence_path:
            p = Path(self.evidence_path)
            if not p.exists():
                gaps.append("evidence_path (plik nie istnieje)")
            elif p.stat().st_size == 0:
                gaps.append("evidence_path (plik pusty)")
        if len(self.steps.strip()) < 80:
            gaps.append("steps (mniej niż 80 znaków — to nie jest instrukcja odtworzenia)")
        if len(self.impact.strip()) < 60:
            gaps.append("impact (mniej niż 60 znaków — nie opisano wpływu)")
        return gaps

    def render(self) -> str:
        gaps = self.missing()
        if gaps:
            raise ValueError("Raport niekompletny, brakuje: " + "; ".join(gaps))
        data = Path(self.evidence_path).read_bytes()
        return TEMPLATE.format(
            date=date.today().isoformat(),
            evidence_sha=hashlib.sha256(data).hexdigest(),
            **{k: v for k, v in asdict(self).items()},
        )


def registry_entry(rep: Report) -> dict:
    return {**asdict(rep), "rendered": True}


def append_registry(path: str | Path, rep: Report) -> None:
    import json
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(registry_entry(rep), ensure_ascii=False) + "\n")
