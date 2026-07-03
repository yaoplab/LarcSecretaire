"""
DossierPanel — Sections documentaires avec notes + fichiers joints.
Remplace NotesPanel dans la vue Dossiers du StudentEditDialog.
Stockage : notes_json (JSONB) dans larcauth_student.
"""

import os

from larccommon.widgets import FilePanel
from LarcSecretaire.common.theme import theme_manager
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

SECTIONS = [
    ("medicale", "Médicale"),
    ("pedagogique", "Pédagogique"),
    ("administrative", "Administrative"),
    ("communication", "Communication"),
    ("orientation", "Orientation"),
    ("autre", "Autre"),
]


class _SectionPage(QWidget):
    """Une section du DossierPanel : date + titre + notes + fichiers."""

    def __init__(self, key: str, label: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._label = label
        self._build()

    def _build(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        sp = 13

        layout = QVBoxLayout(self)
        layout.setSpacing(sp)
        layout.setContentsMargins(sp, sp, sp, 0)

        self._date = QDateEdit()
        self._date.setDisplayFormat("yyyy-MM-dd")
        self._date.setCalendarPopup(True)
        self._date.setSpecialValueText(" ")
        self._date.setDate(QDate())
        self._date.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; font-size: {s(13)}px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        layout.addWidget(self._date)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Titre du document")
        self._title.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; font-size: {s(13)}px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        layout.addWidget(self._title)

        self._doc = QTextEdit()
        self._doc.setPlaceholderText("Notes, description, observations...")
        self._doc.setFixedHeight(144)
        self._doc.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; font-size: {s(13)}px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        layout.addWidget(self._doc)

        sep = QLabel("Fichiers joints")
        sep.setStyleSheet(f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(sep)

        self._file_panel = FilePanel()
        layout.addWidget(self._file_panel, 1)

    def set_directory(self, path: str):
        self._file_panel.set_directory(path)

    def load_entry(self, entry: dict | None):
        if not entry:
            self._date.setDate(QDate())
            self._title.clear()
            self._doc.clear()
            return
        try:
            self._date.setDate(QDate.fromString(entry.get("date", ""), "yyyy-MM-dd"))
        except Exception:
            self._date.setDate(QDate())
        self._title.setText(entry.get("titre", ""))
        self._doc.setPlainText(entry.get("doc", ""))

    def get_entry(self) -> dict:
        return {
            "no": 1,
            "date": self._date.date().toString("yyyy-MM-dd") if self._date.date().isValid() else "",
            "titre": self._title.text(),
            "doc": self._doc.toPlainText(),
        }


class DossierPanel(QWidget):
    """Panneau Dossiers : boutons de section + contenu + fichiers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: dict[str, _SectionPage] = {}
        self._current_key: str | None = None
        self._build()

    def _build(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Boutons de section
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._btns: dict[str, QPushButton] = {}
        btn_base = (
            f"QPushButton {{ border: none; border-radius: {d.radius_lg}px; padding: 8px 16px; font-size: {s(12)}px; font-weight: bold; cursor: pointer; }}"
        )

        self._stack = QStackedWidget()
        first = True

        for key, label in SECTIONS:
            btn = QPushButton(label)
            if first:
                btn.setStyleSheet(btn_base + f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; }}")
                first = False
            else:
                btn.setStyleSheet(
                    btn_base + f"QPushButton {{ background: transparent; color: {p.text_strong}; }}QPushButton:hover {{ background: {p.surface_variant}; }}"
                )
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._select(k))
            btn_row.addWidget(btn)
            self._btns[key] = btn

            page = _SectionPage(key, label)
            self._pages[key] = page
            self._stack.addWidget(page)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self._stack)
        layout.addWidget(scroll, 1)

        self._current_key = SECTIONS[0][0]

    def _select(self, key: str):
        p = theme_manager.palette
        btn_base = (
            f"QPushButton {{ border: none; border-radius: {theme_manager.design.radius_lg}px; "
            f"padding: 8px 16px; font-size: {theme_manager.font_size(12)}px; "
            f"font-weight: bold; cursor: pointer; }}"
        )
        for k, btn in self._btns.items():
            if k == key:
                btn.setStyleSheet(btn_base + f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; }}")
            else:
                btn.setStyleSheet(
                    btn_base + f"QPushButton {{ background: transparent; color: {p.text_strong}; }}QPushButton:hover {{ background: {p.surface_variant}; }}"
                )
        self._current_key = key
        self._stack.setCurrentWidget(self._pages[key])

    def set_directory(self, base_dir: str):
        for key in self._pages:
            d = os.path.join(base_dir, key)
            os.makedirs(d, exist_ok=True)
            self._pages[key].set_directory(d)

    def set_data(self, data: dict):
        """Charge les données depuis notes_json."""
        for key, page in self._pages.items():
            section = data.get(key, {})
            entries = section.get("entries", [])
            if entries:
                page.load_entry(entries[0])
            else:
                page.load_entry(None)

    def get_data(self) -> dict:
        """Retourne les données au format notes_json."""
        result = {}
        for key, page in self._pages.items():
            result[key] = {
                "intro": "",
                "entries": [page.get_entry()],
            }
        return result

    def clear(self):
        for page in self._pages.values():
            page.load_entry(None)
