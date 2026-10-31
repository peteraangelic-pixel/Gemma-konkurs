# template-audit — kod autora, do odtworzenia audytu (31.10)

Skopiowane z gałęzi `codex/arc-local-lab-v18-20261030` (Smak-Domu-Konkurs), commit `3926007e`:

| plik | pochodzenie | uwaga |
|---|---|---|
| `template_transfer.py` | `arc-agi-3/analysis/template_transfer.py` | nietknięty; **identyczny** z modułem w notebooku (kom. 8) |
| `template_hook.py` | `arc-agi-3/analysis/template_hook.py` | nietknięty; identyczny z hookiem w notebooku |
| `test_template_transfer_adapted.py` | `arc-agi-3/analysis/tests/test_template_transfer.py` | jedyna zmiana: ścieżka do `ft09-initial-grid.json`; 35 passed |
| `ft09-*.json` | `analysis/causal-agent-20261031/` | zapisane plansze; startowa == klatka silnika przy `seed=731` |

Uruchomienie (silnik trzeba zbudować osobno — patrz recenzja §10):
`PYTHONPATH=/tmp/ae:/tmp/agx python3 -m pytest template-audit/test_template_transfer_adapted.py -q`
