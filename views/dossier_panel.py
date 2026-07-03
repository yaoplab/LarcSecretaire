"""
DossierPanel — Sections documentaires avec notes + fichiers joints.
Stockage : notes_json (JSONB) dans larcauth_student.
Chaque entrée = un document avec ses propres fichiers joints.
"""

import os

from larccommon.widgets import FilePanel
from larccommon.widgets.table_settings import TableSettings
from LarcSecretaire.common.session import UserRole, session
from LarcSecretaire.common.theme import theme_manager
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
        self._base_dir = ""
        self._build()

    def _build(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        sp = d.spacing * 2

        layout = QVBoxLayout(self)
        layout.setContentsMargins(sp, sp, sp, 0)
        layout.setSpacing(sp)

        # ── Top row : 2 colonnes ──
        top = QHBoxLayout()
        top.setSpacing(sp)

        # --- Colonne gauche : Table ---
        left_col = QVBoxLayout()
        left_col.setSpacing(4)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Date", "Titre", "Description"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self._table.setColumnWidth(1, 120)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {p.outline_variant}; "
            f"gridline-color: {p.outline_variant}; font-size: {s(12)}px; "
            f"background: {p.surface}; color: {p.text_strong}; }}"
            f"QTableWidget::item {{ padding: 3px 6px; }}"
            f"QHeaderView::section {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"font-weight: bold; padding: 4px 6px; border: none; font-size: {s(12)}px; }}"
        )
        self._table.itemSelectionChanged.connect(self._on_select)
        self._table.horizontalHeader().sectionResized.connect(self._on_col_resize)
        TableSettings.restore(self._table, f"dossier/{self._key}")
        left_col.addWidget(self._table)

        top.addLayout(left_col, 5)

        # --- Colonne droite : Édition ---
        right_col = QVBoxLayout()
        right_col.setSpacing(sp)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._title = QLineEdit()
        self._title.setPlaceholderText("Titre")
        self._title.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: {s(12)}px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._title.textChanged.connect(self._save_current)
        title_row.addWidget(self._title, 1)
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: 12px; font-size: {s(14)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
        )
        add_btn.clicked.connect(self._add_entry)
        title_row.addWidget(add_btn)
        del_btn = QPushButton("−")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.error}; "
            f"border: 1px solid {p.error}; border-radius: 12px; "
            f"font-size: {s(14)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.error_container}; }}"
        )
        del_btn.clicked.connect(self._delete_entry)
        title_row.addWidget(del_btn)
        right_col.addLayout(title_row)

        self._date = QDateEdit()
        self._date.setDisplayFormat("yyyy-MM-dd")
        self._date.setCalendarPopup(True)
        self._date.setSpecialValueText(" ")
        self._date.setDate(QDate())
        self._date.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: {s(12)}px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._date.dateChanged.connect(self._save_current)
        right_col.addWidget(self._date)

        self._doc = QTextEdit()
        self._doc.setPlaceholderText("Description / note...")
        self._doc.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: {s(12)}px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._doc.textChanged.connect(self._save_current)
        right_col.addWidget(self._doc, 1)

        top.addLayout(right_col, 8)

        layout.addLayout(top, 5)

        # ── Bottom row : Fichiers + Aperçu ──
        bottom = QHBoxLayout()
        bottom.setSpacing(sp)

        self._file_panel = FilePanel()
        bottom.addWidget(self._file_panel, 5)

        self._preview_frame = QFrame()
        self._preview_frame.setStyleSheet(f"background: {p.surface_variant}; border-radius: {d.radius_lg}px;")
        preview_layout = QVBoxLayout(self._preview_frame)
        self._preview_label = QLabel("Sélectionnez un fichier\npour l'aperçu")
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_disabled};")
        preview_layout.addWidget(self._preview_label)
        bottom.addWidget(self._preview_frame, 8)

        self._file_panel._list.itemDoubleClicked.connect(self._on_preview_file)

        layout.addLayout(bottom, 8)

    def set_directory(self, base_dir: str):
        """Appelé quand le dossier racine change."""
        self._base_dir = base_dir
        if self._current_entry:
            self._file_panel.set_directory(self._entry_dir())

    def _entry_dir(self) -> str:
        if not self._base_dir:
            return ""
        no = self._current_entry.get("no", 0) if self._current_entry else 0
        d = os.path.join(self._base_dir, str(no))
        os.makedirs(d, exist_ok=True)
        return d

    def _refresh_table(self):
        self._table.blockSignals(True)
        self._table.setRowCount(len(self._entries))
        sorted_entries = sorted(self._entries, key=lambda e: e.get("date", ""), reverse=True)
        for i, e in enumerate(sorted_entries):
            doc = e.get("doc", "")
            snippet = doc[:80].replace("\n", " ") + ("…" if len(doc) > 80 else "")
            self._table.setItem(i, 0, QTableWidgetItem(e.get("date", "")))
            self._table.setItem(i, 1, QTableWidgetItem(e.get("titre", "")))
            self._table.setItem(i, 2, QTableWidgetItem(snippet))
        self._table.blockSignals(False)
        if sorted_entries:
            self._table.selectRow(0)

    def _on_select(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        sorted_entries = sorted(self._entries, key=lambda e: e.get("date", ""), reverse=True)
        if 0 <= idx < len(sorted_entries):
            self._current_entry = sorted_entries[idx]
            try:
                self._date.setDate(QDate.fromString(self._current_entry.get("date", ""), "yyyy-MM-dd"))
            except Exception:
                self._date.setDate(QDate())
            self._title.setText(self._current_entry.get("titre", ""))
            self._doc.setPlainText(self._current_entry.get("doc", ""))
            self._file_panel.set_directory(self._entry_dir())

    def _save_current(self):
        if self._current_entry is None:
            return
        self._current_entry["date"] = self._date.date().toString("yyyy-MM-dd") if self._date.date().isValid() else ""
        self._current_entry["titre"] = self._title.text()
        self._current_entry["doc"] = self._doc.toPlainText()

    def _add_entry(self):
        from datetime import date

        today = date.today().isoformat()
        self._entries.append({"no": len(self._entries) + 1, "date": today, "titre": "", "doc": ""})
        self._refresh_table()

    def _on_file_selected(self, item):
        """Met à jour le label d'aperçu avec le nom du fichier."""
        self._preview_label.setText(f"Fichier : {item.text()}\nDouble-clic pour ouvrir")

    def _on_col_resize(self):
        TableSettings.save(self._table, f"dossier/{self._key}")

    def _on_preview_file(self, item):
        """Ouvre le fichier dans le viewer."""
        path = os.path.join(self._entry_dir(), item.text())
        from larccommon.widgets import FileViewer

        dlg = FileViewer(path, self)
        dlg.exec()

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
            f"QPushButton {{ border: none; border-radius: {d.radius_lg}px; "
            f"padding: {d.spacing * 2}px {d.spacing * 4}px; "
            f"font-size: {s(13)}px; font-weight: bold; cursor: pointer; }}"
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
        sp = theme_manager.design.spacing * 2
        btn_base = (
            f"QPushButton {{ border: none; border-radius: {theme_manager.design.radius_lg}px; "
            f"padding: {sp}px {sp * 2}px; font-size: {theme_manager.font_size(13)}px; "
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
