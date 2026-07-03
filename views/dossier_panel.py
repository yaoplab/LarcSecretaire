"""
DossierPanel — Sections documentaires avec notes + fichiers joints.
Remplace NotesPanel dans la vue Dossiers du StudentEditDialog.
Stockage : notes_json (JSONB) dans larcauth_student.
Layout : boutons M3 horizontaux + split 2 colonnes (Fibonacci 8/5).
"""

import os

from larccommon.widgets import FilePanel
from LarcSecretaire.common.theme import theme_manager
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
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


class _DossierPage(QWidget):
    """Une section : colonne gauche (liste + champs), colonne droite (fichiers)."""

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._entries: list[dict] = []
        self._current = -1
        self._build()

    def _build(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        sp = d.spacing * 2  # ~13

        outer = QHBoxLayout(self)
        outer.setSpacing(sp)
        outer.setContentsMargins(sp, sp, sp, 0)

        # --- Colonne gauche : liste + édition (Fibonacci ~8/13) ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(sp)

        hdr_row = QHBoxLayout()
        lbl = QLabel("Documents")
        lbl.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        hdr_row.addWidget(lbl)
        hdr_row.addStretch()
        self._btn_add = QPushButton("+")
        self._btn_add.setFixedSize(28, 28)
        self._btn_add.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: 14px; font-size: {s(16)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
        )
        self._btn_add.clicked.connect(self._add_entry)
        hdr_row.addWidget(self._btn_add)
        self._btn_del = QPushButton("−")
        self._btn_del.setFixedSize(28, 28)
        self._btn_del.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.error}; "
            f"border: 1px solid {p.error}; border-radius: 14px; "
            f"font-size: {s(16)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.error_container}; }}"
        )
        self._btn_del.clicked.connect(self._delete_entry)
        hdr_row.addWidget(self._btn_del)
        left_layout.addLayout(hdr_row)

        self._entry_list = QListWidget()
        self._entry_list.setStyleSheet(
            f"border: 1px solid {p.outline_variant}; border-radius: {d.radius}px; font-size: {s(12)}px; background: {p.surface}; color: {p.text_strong};"
        )
        self._entry_list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._entry_list, 2)

        self._date = QDateEdit()
        self._date.setDisplayFormat("yyyy-MM-dd")
        self._date.setCalendarPopup(True)
        self._date.setSpecialValueText(" ")
        self._date.setDate(QDate())
        fld = (
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: {s(12)}px; background: {p.surface}; color: {p.text_strong};"
        )
        self._date.setStyleSheet(fld)
        left_layout.addWidget(self._date)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Titre")
        self._title.setStyleSheet(fld)
        left_layout.addWidget(self._title)

        self._doc = QTextEdit()
        self._doc.setPlaceholderText("Note...")
        self._doc.setStyleSheet(fld.replace(";", "; min-height: 55px;"))
        left_layout.addWidget(self._doc, 1)

        outer.addWidget(left, 8)

        # --- Colonne droite : fichiers (Fibonacci ~5/13) ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(sp)

        flabel = QLabel("Fichiers")
        flabel.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        right_layout.addWidget(flabel)

        self._file_panel = FilePanel()
        right_layout.addWidget(self._file_panel, 1)

        outer.addWidget(right, 5)

    def set_directory(self, path: str):
        self._file_panel.set_directory(path)

    def _refresh_list(self):
        self._entry_list.blockSignals(True)
        self._entry_list.clear()
        for i, e in enumerate(self._entries):
            dt = e.get("date", "") or "??"
            titre = e.get("titre", "") or "(sans titre)"
            item = QListWidgetItem(f"{dt}  {titre}")
            item.setData(Qt.UserRole, i)
            self._entry_list.addItem(item)
        self._entry_list.blockSignals(False)
        if 0 <= self._current < len(self._entries):
            self._entry_list.setCurrentRow(self._current)
        elif self._entries:
            self._entry_list.setCurrentRow(0)
        else:
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
        self._entries.append({"no": len(self._entries) + 1, "date": "", "titre": "", "doc": ""})
        self._current = len(self._entries) - 1
        self._refresh_list()

    def _delete_entry(self):
        if self._current < 0 or self._current >= len(self._entries):
            return
        r = QMessageBox.question(self, "Confirmation", f"Supprimer «{self._entries[self._current].get('titre', '')}» ?", QMessageBox.Yes | QMessageBox.No)
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
    """Panneau Dossiers : boutons de section M3 + contenu split 8/5."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: dict[str, _DossierPage] = {}
        self._build()

    def _build(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Boutons de section — style M3 chips
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._btns: dict[str, QPushButton] = {}
        btn_base = (
            f"QPushButton {{ border: none; border-radius: {d.radius_lg}px; padding: 6px 16px; font-size: {s(12)}px; font-weight: bold; cursor: pointer; }}"
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
            self._stack.addWidget(_DossierPage(key))

        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addWidget(self._stack, 1)

    def _select(self, key: str):
        p = theme_manager.palette
        btn_base = (
            f"QPushButton {{ border: none; border-radius: {theme_manager.design.radius_lg}px; "
            f"padding: 6px 16px; font-size: {theme_manager.font_size(12)}px; "
            f"font-weight: bold; cursor: pointer; }}"
        )
        for k, btn in self._btns.items():
            if k == key:
                btn.setStyleSheet(btn_base + f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; }}")
            else:
                btn.setStyleSheet(
                    btn_base + f"QPushButton {{ background: transparent; color: {p.text_strong}; }}QPushButton:hover {{ background: {p.surface_variant}; }}"
                )
        idx = [k for k in SECTIONS if k[0] == key]
        if idx:
            self._stack.setCurrentIndex(idx[0])

    def set_directory(self, base_dir: str):
        for i, (key, _) in enumerate(SECTIONS):
            d = os.path.join(base_dir, key)
            os.makedirs(d, exist_ok=True)
            self._stack.widget(i).set_directory(d)

    def set_data(self, data: dict):
        for i, (key, _) in enumerate(SECTIONS):
            section = data.get(key, {})
            self._stack.widget(i).load_entries(section.get("entries", []))

    def get_data(self) -> dict:
        result = {}
        for i, (key, _) in enumerate(SECTIONS):
            result[key] = {"intro": "", "entries": self._stack.widget(i).get_entries()}
        return result

    def clear(self):
        for i in range(self._stack.count()):
            self._stack.widget(i).load_entries([])
