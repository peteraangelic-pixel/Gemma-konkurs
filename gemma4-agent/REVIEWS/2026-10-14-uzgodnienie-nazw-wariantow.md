# Uzgodnienie nazw wariantów między gałęziami (2026-10-14)

Powód: recenzja drugiej gałęzi słusznie zauważyła, że **warianty o tej samej nazwie na obu
gałęziach to różne pliki**. Ten dokument jest kanonem na dziś — obowiązuje hasło, nie numer.

## Kanon: identyfikuj artefakt hashem, nie numerem

| nazwa u nas | co to jest | artefakt | druga gałąź |
| --- | --- | --- | --- |
| V6.4 | baza: M1–M4, brak `submit_patch`, termin call 4 | `aaea34e4…` (13 455 B, kopia historyczna) | ich `submission-v6.4.zip` (12 375 B) — **inny plik**, ta sama intencja |
| V6.5 | V6.4 + framing edycji | `cb847599…` (13 782 B) | brak |
| V6.6 | V6.4 + inline lokalizator | `b6686c53…` (13 721 B) | brak |
| **V6.7 (nasz)** | **V6.4 + reguły kontraktu narzędzi (L4)** | **`df7364e2…` (13 959 B)** | **nie istnieje** |
| V6.7 (ich, lokalny) | V6.4 + framing + inline = suma V6.5+V6.6 | `0cd0d2bf…` — **nie ma go w repo** (ich tip: `8eb94cd`) | ich sesja, nie da się zweryfikować |
| V6.8 | V6.4 + ewoluowany lokalizator | `8c816fc8…` (13 307 B) | brak |
| V6.9 (nasz) | V6.4 + framing + inline = **odpowiednik ich V6.7** | `c99f3d81…` (13 564 B) | ich `0cd0d2bf…` — ta sama intencja, **inny build** |
| V6.10 (nasz) | V6.4 + kontrakt + ewoluowany lokalizator + inline (kandydat) | `523d43fb…` (14 385 B) | brak |

## Reguły

1. **Nigdy nie porównuj ani nie wysyłaj wariantu po numerze.** W komunikacji między sesjami
   podawaj hasha skróconego do 8 znaków; numer bez hasha jest niejednoznaczny od 2026-10-14.
2. **Artefakt, którego nie ma w repozytorium, nie istnieje** dla planu przebiegów: nie da się go
   zweryfikować, zapakować w workflow ani wysłać. Ich `0cd0d2bf…` jest właśnie w tej kategorii —
   jeśli druga sesja chce, żeby był w planie, musi go najpierw wypchnąć na swoją gałąź.
3. **V6.9 nie jest „ich V6.7"** i nie należy ich porównywać bajt w bajt; równy jest tylko pomysł.
4. Jeśli druga gałąź wypchnie swój `0cd0d2bf…`, porównanie jest proste: rozpakować oba archiwa
   i porównać `prompts/system.md` oraz `tools/locate.py` (przy identycznej zawartości hashe ZIP-ów
   mogą się różnić wyłącznie przez znacznik czasu archiwum).
