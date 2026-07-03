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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
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
    """Une section : liste d'entrées (date+titre+doc) + fichiers."""

    def __init__(self, key: str, label: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._entries: list[dict] = []
        self._current = -1
        self._build()

    def _build(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        sp = 13

        layout = QVBoxLayout(self)
        layout.setSpacing(sp)
        layout.setContentsMargins(sp, sp, sp, 0)

        # --- Liste des entrées ---
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        lbl = QLabel("Documents")
        lbl.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        row1.addWidget(lbl)
        row1.addStretch()
        self._btn_add = QPushButton("+ Nouveau")
        self._btn_add.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; padding: 4px 12px; font-size: {s(12)}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
        )
        self._btn_add.clicked.connect(self._add_entry)
        row1.addWidget(self._btn_add)
        self._btn_del = QPushButton("− Supprimer")
        self._btn_del.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.error}; "
            f"border: 1px solid {p.error}; border-radius: {d.radius}px; "
            f"padding: 4px 12px; font-size: {s(12)}px; }}"
            f"QPushButton:hover {{ background: {p.error_container}; }}"
        )
        self._btn_del.clicked.connect(self._delete_entry)
        row1.addWidget(self._btn_del)
        layout.addLayout(row1)

        self._entry_list = QListWidget()
        self._entry_list.setFixedHeight(144)
        self._entry_list.setStyleSheet(
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; font-size: {s(13)}px; background: {p.surface}; color: {p.text_strong};"
        )
        self._entry_list.currentRowChanged.connect(self._on_select)
        layout.addWidget(self._entry_list)

        # --- Champs d'édition ---
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
        self._doc.setFixedHeight(89)
        self._doc.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; font-size: {s(13)}px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        layout.addWidget(self._doc)

        # --- Fichiers ---
        sep = QLabel("Fichiers joints")
        sep.setStyleSheet(f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(sep)

        self._file_panel = FilePanel()
        layout.addWidget(self._file_panel, 1)

    def set_directory(self, path: str):
        self._file_panel.set_directory(path)

    def _refresh_list(self):
        self._entry_list.blockSignals(True)
        self._entry_list.clear()
        for i, e in enumerate(self._entries):
            titre = e.get("titre", "") or "(sans titre)"
            date = e.get("date", "") or "??"
            item = QListWidgetItem(f"{date} — {titre}")
            item.setData(Qt.UserRole, i)
            self._entry_list.addItem(item)
        self._entry_list.blockSignals(False)
        if 0 <= self._current < len(self._entries):
            self._entry_list.setCurrentRow(self._current)
        elif self._entries:
            self._entry_list.setCurrentRow(0)
        else:
            self._entry_list.clear()
            self._current = -1
            self._clear_fields()

    def _clear_fields(self):
        self._date.setDate(QDate())
        self._title.clear()
        self._doc.clear()

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._entries):
            return
        self._save_current()
        self._current = row
        e = self._entries[row]
        try:
            self._date.setDate(QDate.fromString(e.get("date", ""), "yyyy-MM-dd"))
        except Exception:
            self._date.setDate(QDate())
        self._title.setText(e.get("titre", ""))
        self._doc.setPlainText(e.get("doc", ""))

    def _save_current(self):
        if self._current < 0 or self._current >= len(self._entries):
            return
        self._entries[self._current] = self._current_entry()

    def _current_entry(self) -> dict:
        return {
            "no": self._current + 1,
            "date": self._date.date().toString("yyyy-MM-dd") if self._date.date().isValid() else "",
            "titre": self._title.text(),
            "doc": self._doc.toPlainText(),
        }

    def _add_entry(self):
        self._save_current()
        no = len(self._entries) + 1
        self._entries.append({"no": no, "date": "", "titre": "", "doc": ""})
        self._current = len(self._entries) - 1
        self._refresh_list()

    def _delete_entry(self):
        if self._current < 0 or self._current >= len(self._entries):
            return
        r = QMessageBox.question(
            self, "Confirmation", f"Supprimer l'entrée «{self._entries[self._current].get('titre', '')}» ?", QMessageBox.Yes | QMessageBox.No
        )
        if r != QMessageBox.Yes:
            return
        self._entries.pop(self._current)
        self._current = min(self._current, len(self._entries) - 1)
        self._refresh_list()

    def load_entries(self, entries: list[dict]):
        self._entries = list(entries) if entries else []
        self._current = -1
        self._refresh_list()

    def get_entries(self) -> list[dict]:
        self._save_current()
        return self._entries


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
            active_s = btn_base + f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; }}"
            idle_s = btn_base + f"QPushButton {{ background: transparent; color: {p.text_strong}; }}QPushButton:hover {{ background: {p.surface_variant}; }}"
            btn.setStyleSheet(active_s if first else idle_s)
            first = False
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
            page.load_entries(section.get("entries", []))

    def get_data(self) -> dict:
        """Retourne les données au format notes_json."""
        result = {}
        for key, page in self._pages.items():
            result[key] = {"intro": "", "entries": page.get_entries()}
        return result

    def clear(self):
        for page in self._pages.values():
            page.load_entries([])
