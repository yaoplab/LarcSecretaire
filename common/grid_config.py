"""Grid configuration loader.

Loads grid configs from ``grid_configs/*.json``.
Usage::

    from common.grid_config import pei_config
    color = pei_config.color_for(6)          # → ('#a5d6a7', '#1b5e20', False)
    bold  = pei_config.note_on_7_bold
    width = pei_config.student_width
"""

import json
import os
from typing import Optional

_ROOT = os.path.join(os.path.dirname(__file__), '..', 'grid_configs')


class _GradeRange:
    def __init__(self, d: dict):
        self.min: int = d['min']
        self.max: int = d['max']
        self.bg: str = d['bg']
        self.fg: str = d['fg']
        self.bold: bool = d.get('bold', False)

    def matches(self, value: Optional[float]) -> bool:
        if value is None:
            return False
        return self.min <= value <= self.max


class GridConfig:
    """Immutable config object wrapping a grid JSON file."""

    def __init__(self, path: str):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        sc = data['student_column']
        self.student_width: int = sc['width']
        self.student_min_width: int = sc.get('min_width', 80)
        self.student_max_width: int = sc.get('max_width', 500)

        nc = data['note_column']
        self.note_width: int = nc['default_width']
        self.note_min_width: int = nc.get('min_width', 30)
        self.note_max_width: int = nc.get('max_width', 150)

        rc = data['remark_column']
        self.remark_width: int = rc['default_width']
        self.remark_min_width: int = rc.get('min_width', 60)
        self.remark_max_width: int = rc.get('max_width', 400)

        n7 = data['note_on_7']
        self.note_on_7_color: str = n7['color']
        self.note_on_7_bold: bool = n7['bold']

        self._ranges = [_GradeRange(r) for r in data['grade_ranges']]

    def color_for(self, value: Optional[float]) -> tuple[str, str, bool]:
        """Return (bg, fg, bold) for *value*, or (None, None, False) if no range matches."""
        for r in self._ranges:
            if r.matches(value):
                return r.bg, r.fg, r.bold
        return '#ffffff', '#212121', False


class _GridConfigManager:
    """Lazy-loaded singleton per grid type."""

    def __init__(self):
        self._cache: dict[str, GridConfig] = {}

    def get(self, name: str) -> Optional[GridConfig]:
        if name not in self._cache:
            path = os.path.join(_ROOT, f'{name}.json')
            if not os.path.isfile(path):
                return None
            self._cache[name] = GridConfig(path)
        return self._cache[name]


_manager = _GridConfigManager()
pei_config: GridConfig = _manager.get('pei')
"""Pre-loaded singleton for ``grid_configs/pei.json``."""
