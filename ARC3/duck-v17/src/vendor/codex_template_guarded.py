"""Warstwa guard nad kontrolerem `template`: limit propozycji na poziom + kill-switch.

Pochodzenie: `analysis/template_guarded.py` z gałęzi `codex/arc-local-lab-v18-20261030`
(commit c0b47ca), autor: sesja Codex. Zmiany wobec oryginału: importy bezwzględne na
`inference.utils.*` (bo plik leci do pakietu, nie obok modułu), jeden przełącznik
`ARC3_TEMPLATE` zamiast `ARC3_TEMPLATE_ENABLED` i polski docstring. Logika limitu
i idempotencji instalacji nietknięta.

Po co: sprawdzenie koloru po akcji wykrywa tylko przewidywania bezpośrednio sprzeczne.
Na planszy oscylującej kontroler potrafił zrobić 60 akcji przy 0 sprzecznościach
(kontrprzykład zmierzony przez sesję Codex 31.10). Limit 32 propozycji na poziom
przerywa taką pętlę, nie zmieniając żadnego z 25 zmierzonych śladów publicznych.
"""
import os

from inference.utils.codex_template_transfer import TemplateTransfer
from inference.utils.codex_template_hook import install as install_base

DEFAULT_MAX_ACTIONS_PER_LEVEL = 32


class GuardedTemplateTransfer(TemplateTransfer):
    def __init__(self, *args, max_actions_per_level=DEFAULT_MAX_ACTIONS_PER_LEVEL, **kwargs):
        if max_actions_per_level < 1:
            raise ValueError("Positive action cap required")
        super().__init__(*args, **kwargs)
        self.max_actions_per_level = max_actions_per_level
        self.level_actions = 0
        self.cap_hits = 0

    def act(self, grid, available, level):
        if self.level != level:
            self.level_actions = 0
            if self.level is not None and level < self.level:
                self.learned = None
        if self.level_actions >= self.max_actions_per_level:
            self.cap_hits += 1
            return None
        action = super().act(grid, available, level)
        if action is not None:
            self.level_actions += 1
        return action


def install(ta, controller_class=GuardedTemplateTransfer):
    original = ta.ToolAgent.analyze
    if getattr(original, "_arc3_guarded_template", False):
        return
    install_base(ta, controller_class)
    enabled = ta.ToolAgent.analyze

    def analyze(self, *args, **kwargs):
        if os.environ.get("ARC3_TEMPLATE", "1") == "0":
            return original(self, *args, **kwargs)
        return enabled(self, *args, **kwargs)

    analyze._arc3_guarded_template = True
    ta.ToolAgent.analyze = analyze
