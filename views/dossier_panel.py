"""
DossierPanel — Sections documentaires avec notes + fichiers joints.
Stockage : notes_json (JSONB) dans larcauth_student.
Chaque entrée = un document avec ses propres fichiers joints.
"""

import os

from larccommon.widgets import FilePanel
from LarcSecretaire.common.session import UserRole, session
from LarcSecretaire.common.theme import theme_manager
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
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
    """Section : table Date/Titre + détail (doc + fichiers) pour l'entrée sélectionnée."""

    def __init__(self, key: str, student_id: int, parent=None):
        super().__init__(parent)
        self._key = key
        self._sid = student_id
        self._entries: list[dict] = []
        self._current_entry: dict | None = None
        self._build()

    def _build(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        sp = d.spacing * 2

        layout = QVBoxLayout(self)
        layout.setContentsMargins(sp, sp, sp, 0)
        layout.setSpacing(sp)

        # --- Table ---
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Date", "Titre"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setMaximumHeight(144)
        self._table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {p.outline_variant}; "
            f"gridline-color: {p.outline_variant}; font-size: {s(12)}px; "
            f"background: {p.surface}; color: {p.text_strong}; }}"
            f"QTableWidget::item {{ padding: 3px 6px; }}"
            f"QHeaderView::section {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"font-weight: bold; padding: 4px 6px; border: none; font-size: {s(12)}px; }}"
        )
        self._table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        add_btn = QPushButton("+ Ajouter")
        add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; padding: 4px 12px; font-size: {s(11)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
        )
        add_btn.clicked.connect(self._add_entry)
        btn_row.addWidget(add_btn)
        del_btn = QPushButton("Supprimer")
        del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.error}; "
            f"border: 1px solid {p.error}; border-radius: {d.radius}px; "
            f"padding: 4px 12px; font-size: {s(11)}px; }}"
            f"QPushButton:hover {{ background: {p.error_container}; }}"
        )
        del_btn.clicked.connect(self._delete_entry)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # --- Détail ---
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(sp)

        self._doc = QTextEdit()
        self._doc.setPlaceholderText("Description / note...")
        self._doc.setMinimumHeight(55)
        self._doc.setMaximumHeight(89)
        self._doc.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: {s(12)}px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._doc.textChanged.connect(self._save_current)
        detail_layout.addWidget(self._doc)

        self._file_label = QLabel("Fichiers joints")
        self._file_label.setStyleSheet(f"font-size: {s(11)}px; font-weight: bold; color: {p.text_soft};")
        detail_layout.addWidget(self._file_label)

        self._file_panel = FilePanel()
        detail_layout.addWidget(self._file_panel, 1)

        layout.addWidget(detail, 3)

    def set_directory(self, base_dir: str):
        """Appelé quand le dossier racine change. Le répertoire par entrée sera défini au clic."""
        self._base_dir = base_dir

    def _entry_dir(self) -> str:
        no = self._current_entry.get("no", 0) if self._current_entry else 0
        d = os.path.join(self._base_dir, str(no))
        os.makedirs(d, exist_ok=True)
        return d

    def _refresh_table(self):
        self._table.blockSignals(True)
        self._table.setRowCount(len(self._entries))
        for i, e in enumerate(self._entries):
            self._table.setItem(i, 0, QTableWidgetItem(e.get("date", "")))
            self._table.setItem(i, 1, QTableWidgetItem(e.get("titre", "")))
        self._table.blockSignals(False)
        if self._entries:
            self._table.selectRow(0)

    def _on_select(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._entries):
            self._current_entry = self._entries[idx]
            self._doc.setPlainText(self._current_entry.get("doc", ""))
            self._file_panel.set_directory(self._entry_dir())

    def _save_current(self):
        if self._current_entry is None:
            return
        self._current_entry["doc"] = self._doc.toPlainText()

    def _add_entry(self):
        self._entries.append({"no": len(self._entries) + 1, "date": "", "titre": "", "doc": ""})
        self._refresh_table()

    def _delete_entry(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._entries):
            return
        e = self._entries[idx]
        r = QMessageBox.question(self, "Confirmation", f"Supprimer «{e.get('titre', '')}» ?", QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        self._entries.pop(idx)
        self._current_entry = None
        self._doc.clear()
        self._refresh_table()

    def load_entries(self, entries: list[dict]):
        self._entries = list(entries) if entries else []
        self._current_entry = None
        self._doc.clear()
        self._refresh_table()

    def get_entries(self) -> list[dict]:
        self._save_current()
        return self._entries


class DossierPanel(QWidget):
    """Panneau Dossiers : boutons M3 + contenu table/détail pour chaque section."""

    def __init__(self, student_id: int = 0, parent=None):
        super().__init__(parent)
        self._sid = student_id
        self._pages: list[_SectionPage] = []
        self._build()

    def _build(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._btns: list[QPushButton] = []
        self._stack_info: list[tuple] = []

        role = session.role
        visible_sections = list(SECTIONS)
        if role in (UserRole.ADMIN, UserRole.COORD, UserRole.SECR):
            visible_sections.append(("confidentielle", "Confidentiel"))

        btn_base = (
            f"QPushButton {{ border: none; border-radius: {d.radius_lg}px; padding: 6px 16px; font-size: {s(12)}px; font-weight: bold; cursor: pointer; }}"
        )

        for key, label in visible_sections:
            btn = QPushButton(label)
            btn.setStyleSheet(
                btn_base + f"QPushButton {{ background: transparent; color: {p.text_strong}; }}QPushButton:hover {{ background: {p.surface_variant}; }}"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._select(k))
            btn_row.addWidget(btn)
            self._btns.append(btn)
            self._stack_info.append((key, label))

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._stack = QStackedWidget()
        for key, label in self._stack_info:
            self._stack.addWidget(_SectionPage(key, self._sid))
            self._pages.append(self._stack.widget(self._stack.count() - 1))
        layout.addWidget(self._stack, 1)

        if self._btns:
            self._select(visible_sections[0][0])

    def _select(self, key: str):
        p = theme_manager.palette
        btn_base = (
            f"QPushButton {{ border: none; border-radius: {theme_manager.design.radius_lg}px; "
            f"padding: 6px 16px; font-size: {theme_manager.font_size(12)}px; "
            f"font-weight: bold; cursor: pointer; }}"
        )
        for i, (k, _) in enumerate(self._stack_info):
            if k == key:
                self._btns[i].setStyleSheet(btn_base + f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; }}")
                self._stack.setCurrentIndex(i)
            else:
                self._btns[i].setStyleSheet(
                    btn_base + f"QPushButton {{ background: transparent; color: {p.text_strong}; }}QPushButton:hover {{ background: {p.surface_variant}; }}"
                )

    def set_directory(self, base_dir: str):
        self._base_dir = base_dir
        for page in self._pages:
            page.set_directory(base_dir)

    def set_data(self, data: dict):
        for (key, _), page in zip(self._stack_info, self._pages):
            section = data.get(key, {})
            page.load_entries(section.get("entries", []))

    def get_data(self) -> dict:
        result = {}
        for (key, _), page in zip(self._stack_info, self._pages):
            result[key] = {"intro": "", "entries": page.get_entries()}
        return result

    def clear(self):
        for page in self._pages:
            page.load_entries([])
