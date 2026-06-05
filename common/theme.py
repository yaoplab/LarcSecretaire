from dataclasses import dataclass, field
from typing import Optional
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QApplication


@dataclass
class Palette:
    primary: str = '#1565C0'
    on_primary: str = '#FFFFFF'
    primary_container: str = '#D1E4FF'
    secondary: str = '#625B71'
    on_secondary: str = '#FFFFFF'
    secondary_container: str = '#E8DEF8'
    tertiary: str = '#7D5260'
    on_tertiary: str = '#FFFFFF'
    tertiary_container: str = '#FFD8E4'
    error: str = '#BA1A1A'
    on_error: str = '#FFFFFF'
    error_container: str = '#FFDAD6'
    surface: str = '#FDFCFF'
    surface_variant: str = '#E0E3E8'
    background: str = '#FDFCFF'
    outline: str = '#73777E'
    outline_variant: str = '#C4C6D0'
    text_strong: str = '#1B1B1F'
    text_soft: str = '#45464F'
    text_disabled: str = '#9B9DA5'
    error: str = '#BA1A1A'
    error_container: str = '#FFDAD6'
    success: str = '#2E7D32'
    card_bg: str = '#FFFFFF'
    card_hover: str = '#E9ECEF'
    header_bg: str = '#E8DEF8'
    header_text: str = '#1D192B'
    active: str = '#1565C0'
    inactive: str = '#9B9DA5'
    border: str = '#C4C6D0'
    border_light: str = '#DEE0E6'
    button_primary: str = '#1565C0'
    button_danger: str = '#BA1A1A'
    button_accent: str = '#625B71'
    button_success: str = '#2E7D32'
    text_secondary: str = '#45464F'
    accent: str = '#625B71'
    danger: str = '#BA1A1A'


@dataclass
class FontScale:
    base: int = 12
    small: int = 10
    title: int = 14
    header: int = 16
    button: int = 12
    multiplier: float = 1.0


@dataclass
class Theme:
    name: str
    label: str
    palette: Palette = field(default_factory=Palette)
    fonts: FontScale = field(default_factory=FontScale)


_BUILTIN_THEMES: dict[str, Theme] = {}


def _init_themes():
    if _BUILTIN_THEMES:
        return

    _BUILTIN_THEMES['material_light'] = Theme(
        name='material_light',
        label='Material Light',
        palette=Palette(
            primary='#1565C0', on_primary='#FFFFFF', primary_container='#D1E4FF',
            secondary='#625B71', on_secondary='#FFFFFF', secondary_container='#E8DEF8',
            tertiary='#7D5260', on_tertiary='#FFFFFF', tertiary_container='#FFD8E4',
            error='#BA1A1A', on_error='#FFFFFF', error_container='#FFDAD6', success='#2E7D32',
            card_bg='#FFFFFF', card_hover='#E9ECEF',
            header_bg='#E8DEF8', header_text='#1D192B',
            active='#1565C0', inactive='#9B9DA5',
        ),
    )

    _BUILTIN_THEMES['material_dark'] = Theme(
        name='material_dark',
        label='Material Dark',
        palette=Palette(
            primary='#9ECAFF', on_primary='#003258', primary_container='#00497D',
            secondary='#CCC2DC', on_secondary='#332D41', secondary_container='#4A4458',
            tertiary='#EFB8C8', on_tertiary='#492532', tertiary_container='#633B48',
            error='#FFB4AB', on_error='#690005', error_container='#93000A', success='#81C784',
            card_bg='#2D2D31', card_hover='#3D3D42',
            header_bg='#4A4458', header_text='#E8DEF8',
            active='#9ECAFF', inactive='#8E9099',
        ),
    )

    _BUILTIN_THEMES['material_contrast'] = Theme(
        name='material_contrast',
        label='Material Contrast',
        palette=Palette(
            primary='#003258', on_primary='#FFFFFF', primary_container='#D1E4FF',
            secondary='#1D192B', on_secondary='#FFFFFF', secondary_container='#E8DEF8',
            tertiary='#7D5260', on_tertiary='#FFFFFF', tertiary_container='#FFD8E4',
            error='#93000A', on_error='#FFFFFF', error_container='#FFDAD6', success='#1B5E20',
            card_bg='#FFFFFF', card_hover='#DEE3E9',
            header_bg='#1D192B', header_text='#FFFFFF',
            active='#003258', inactive='#73777E',
        ),
    )


class ThemeManager:
    def __init__(self):
        _init_themes()
        self._themes = _BUILTIN_THEMES
        self._active: str = 'material_light'
        self._theme: Theme = self._themes[self._active]
        self._app: Optional[QApplication] = None

    @property
    def theme(self) -> Theme:
        return self._theme

    @property
    def palette(self) -> Palette:
        return self._theme.palette

    @property
    def fonts(self) -> FontScale:
        return self._theme.fonts

    def names(self) -> list[tuple[str, str]]:
        return [(k, v.label) for k, v in self._themes.items()]

    def set_active(self, name: str) -> bool:
        if name in self._themes:
            self._active = name
            self._theme = self._themes[name]
            self._reapply()
            return True
        return False

    def font_size(self, base: int) -> int:
        return max(7, int(base * self._theme.fonts.multiplier))

    def font(self, base: int, weight=QFont.Normal, family='Segoe UI') -> QFont:
        return QFont(family, self.font_size(base), weight)

    def bind(self, app: QApplication) -> None:
        self._app = app
        self._reapply()

    def _reapply(self):
        if self._app is not None:
            self._app.setStyleSheet(self._generate_global_qss())

    def _generate_global_qss(self) -> str:
        p = self._theme.palette
        f = self._theme.fonts
        s = self.font_size
        return f"""
            QToolTip {{
                background: {p.surface_variant}; color: {p.text_strong};
                border: 1px solid {p.outline}; padding: 4px;
                font-size: {s(f.small)}px;
            }}
            QMenu {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline};
                font-size: {s(f.base)}px;
            }}
            QMenu::item:selected {{
                background: {p.primary_container}; color: {p.text_strong};
            }}
            QScrollBar:vertical {{
                background: {p.surface_variant}; width: 8px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {p.outline}; border-radius: 4px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """


theme_manager = ThemeManager()
