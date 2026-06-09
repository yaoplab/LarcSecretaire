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
class DesignTokens:
    radius: int = 4
    radius_lg: int = 8
    radius_xl: int = 12
    spacing: int = 6
    margin: int = 16
    field_pad_v: int = 8
    field_pad_h: int = 12
    label_pad_v: int = 6
    label_pad_h: int = 0
    btn_pad_v: int = 8
    btn_pad_h: int = 20
    btn_sm_pad_v: int = 6
    btn_sm_pad_h: int = 16
    btn_border: int = 1


@dataclass
class Theme:
    name: str
    label: str
    palette: Palette = field(default_factory=Palette)
    fonts: FontScale = field(default_factory=FontScale)
    design: DesignTokens = field(default_factory=DesignTokens)


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
            surface='#FDFCFF', surface_variant='#E0E3E8', background='#F5F6FA',
            outline='#73777E', outline_variant='#C4C6D0',
            text_strong='#1B1B1F', text_soft='#45464F', text_disabled='#9B9DA5',
            card_bg='#FFFFFF', card_hover='#E9ECEF',
            header_bg='#E8DEF8', header_text='#1D192B',
            active='#1565C0', inactive='#9B9DA5',
            border='#C4C6D0', border_light='#DEE0E6',
            button_primary='#1565C0', button_success='#2E7D32',
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
            surface='#1C1C1F', surface_variant='#44474E', background='#121214',
            outline='#8E9099', outline_variant='#44474E',
            text_strong='#E4E2E6', text_soft='#C4C2C8', text_disabled='#8E9099',
            card_bg='#2D2D31', card_hover='#3D3D42',
            header_bg='#4A4458', header_text='#E8DEF8',
            active='#9ECAFF', inactive='#8E9099',
            border='#44474E', border_light='#383A3F',
            button_primary='#9ECAFF', button_success='#81C784',
        ),
        design=DesignTokens(
            radius=6, radius_lg=10, radius_xl=14,
            field_pad_v=10, field_pad_h=14,
            btn_sm_pad_v=8, btn_sm_pad_h=18,
            btn_pad_v=10, btn_pad_h=22,
        ),
    )

    _BUILTIN_THEMES['material_contrast'] = Theme(
        name='material_contrast',
        label='Material Contrast',
        palette=Palette(
            primary='#004B8D', on_primary='#FFFFFF', primary_container='#D1E4FF',
            secondary='#1D192B', on_secondary='#FFFFFF', secondary_container='#E8DEF8',
            tertiary='#7D5260', on_tertiary='#FFFFFF', tertiary_container='#FFD8E4',
            error='#93000A', on_error='#FFFFFF', error_container='#FFDAD6', success='#1B5E20',
            surface='#FFFFFF', surface_variant='#E0E3E8', background='#F5F6FA',
            outline='#000000', outline_variant='#6B6F76',
            text_strong='#000000', text_soft='#1B1B1F', text_disabled='#6B6F76',
            card_bg='#FFFFFF', card_hover='#DEE3E9',
            header_bg='#000000', header_text='#FFFFFF',
            active='#004B8D', inactive='#6B6F76',
            border='#000000', border_light='#6B6F76',
            button_primary='#004B8D', button_success='#1B5E20',
        ),
        design=DesignTokens(
            radius=6, radius_lg=10, radius_xl=14,
            spacing=8, margin=20,
            field_pad_v=10, field_pad_h=16,
            label_pad_v=8,
            btn_pad_v=10, btn_pad_h=24,
            btn_sm_pad_v=8, btn_sm_pad_h=18,
            btn_border=2,
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

    @property
    def design(self) -> DesignTokens:
        return self._theme.design

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
        d = self._theme.design
        return f"""
            QToolTip {{
                background: {p.surface_variant}; color: {p.text_strong};
                border: 1px solid {p.outline}; padding: {d.radius}px;
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
                background: {p.outline}; border-radius: {d.radius}px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """


theme_manager = ThemeManager()
