"""
DossierPanel — Sections documentaires avec notes + fichiers joints.
Stockage : notes_json (JSONB) dans larcauth_student.
Chaque entrée = un document avec ses propres fichiers joints.
"""

import os

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

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("✓ Enregistrer")
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius_lg}px; padding: {d.spacing}px {d.spacing * 4}px; "
            f"font-size: {s(13)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.success}; }}"
        )
        save_btn.clicked.connect(self._save_and_refresh)
        save_row.addWidget(save_btn)
        right_col.addLayout(save_row)

        top.addLayout(right_col, 8)

        layout.addLayout(top, 5)

        # ── Bottom row : Fichiers + Aperçu ──
        bottom = QHBoxLayout()
        bottom.setSpacing(sp)

        # Table fichiers avec en-têtes
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(4)

        self._file_table = QTableWidget()
        self._file_table.setColumnCount(2)
        self._file_table.setHorizontalHeaderLabels(["Pièce jointe", "Document associé"])
        self._file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self._file_table.setColumnWidth(0, 144)
        self._file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._file_table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {p.outline_variant}; "
            f"gridline-color: {p.outline_variant}; font-size: {s(11)}px; "
            f"background: {p.surface}; color: {p.text_strong}; }}"
            f"QTableWidget::item {{ padding: 2px 4px; }}"
            f"QHeaderView::section {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"font-weight: bold; padding: 3px 4px; border: none; font-size: {s(11)}px; }}"
        )
        self._file_table.itemSelectionChanged.connect(self._on_file_selected)
        self._file_table.cellDoubleClicked.connect(self._on_preview_file_row)
        file_layout.addWidget(self._file_table)

        file_btns = QHBoxLayout()
        file_btns.setSpacing(4)
        add_f = QPushButton("+")
        add_f.setFixedSize(22, 22)
        add_f.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: 11px; font-size: {s(12)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
        )
        add_f.clicked.connect(self._add_file)
        file_btns.addWidget(add_f)
        open_f = QPushButton("📂")
        open_f.setFixedSize(22, 22)
        open_f.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: 1px solid {p.outline_variant}; border-radius: 11px; font-size: {s(10)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}"
        )
        open_f.clicked.connect(self._open_file_dir)
        file_btns.addWidget(open_f)
        del_f = QPushButton("−")
        del_f.setFixedSize(22, 22)
        del_f.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.error}; "
            f"border: 1px solid {p.error}; border-radius: 11px; "
            f"font-size: {s(14)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.error_container}; }}"
        )
        del_f.clicked.connect(self._delete_file)
        file_btns.addWidget(del_f)
        save_f = QPushButton("✓")
        save_f.setFixedSize(22, 22)
        save_f.setStyleSheet(
            f"QPushButton {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: 11px; font-size: {s(11)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.success}; }}"
        )
        save_f.clicked.connect(self._refresh_files)
        file_btns.addWidget(save_f)
        file_btns.addStretch()
        file_layout.addLayout(file_btns)
        bottom.addWidget(file_widget, 5)

        self._preview_frame = QFrame()
        self._preview_frame.setStyleSheet(f"background: {p.surface_variant}; border-radius: {d.radius_lg}px;")
        self._preview_layout = QVBoxLayout(self._preview_frame)
        self._preview_widget = QLabel("Sélectionnez un fichier")
        self._preview_widget.setAlignment(Qt.AlignCenter)
        self._preview_widget.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_disabled};")
        self._preview_layout.addWidget(self._preview_widget)
        bottom.addWidget(self._preview_frame, 8)

        layout.addLayout(bottom, 8)

    def _refresh_files(self):
        d = self._entry_dir()
        if not d:
            return
        self._file_table.setRowCount(0)
        try:
            files = sorted(os.listdir(d))
        except Exception:
            return
        titre = self._current_entry.get("titre", "") if self._current_entry else ""
        for i, fname in enumerate(files):
            self._file_table.setRowCount(i + 1)
            self._file_table.setItem(i, 0, QTableWidgetItem(fname))
            self._file_table.setItem(i, 1, QTableWidgetItem(titre))

    def _add_file(self):
        from PySide6.QtWidgets import QFileDialog

        d = self._entry_dir()
        if not d:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Ajouter des fichiers", "")
        if not paths:
            return
        import shutil

        for p in paths:
            shutil.copy2(p, os.path.join(d, os.path.basename(p)))
        self._refresh_files()

    def _delete_file(self):
        rows = self._file_table.selectionModel().selectedRows()
        if not rows:
            return
        name = self._file_table.item(rows[0].row(), 0).text()
        r = QMessageBox.question(self, "Confirmation", f"Supprimer {name} ?", QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        path = os.path.join(self._entry_dir(), name)
        try:
            os.remove(path)
            self._refresh_files()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def _open_file_dir(self):
        d = self._entry_dir()
        if d:
            import subprocess

            subprocess.Popen(["explorer", d])

    def _on_preview_file_row(self, row: int, col: int):
        name = self._file_table.item(row, 0)
        if not name:
            return
        path = os.path.join(self._entry_dir(), name.text())
        from larccommon.widgets import FileViewer

        dlg = FileViewer(path, self)
        dlg.exec()

    def _on_file_selected(self):
        rows = self._file_table.selectionModel().selectedRows()
        if not rows or not self._base_dir:
            return
        name = self._file_table.item(rows[0].row(), 0)
        if not name:
            return
        path = os.path.join(self._entry_dir(), name.text())
        ext = os.path.splitext(name.text())[1].lower()

        w = self._preview_layout.takeAt(0)
        if w and w.widget():
            w.widget().deleteLater()

        if ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp"}:
            from PySide6.QtGui import QPixmap

            lbl = QLabel()
            pix = QPixmap(path)
            lbl.setPixmap(pix.scaled(300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lbl.setAlignment(Qt.AlignCenter)
            self._preview_layout.addWidget(lbl)
        elif ext in {".txt", ".csv", ".md", ".json", ".py", ".sql"}:
            ed = QTextEdit()
            ed.setReadOnly(True)
            ed.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px;")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    ed.setPlainText(f.read()[:5000])
            except Exception:
                ed.setPlainText("(Illisible)")
            self._preview_layout.addWidget(ed)
        else:
            lbl = QLabel(f"{name.text()}\n\n{os.path.getsize(path):,} octets\n\nDouble-clic pour ouvrir")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px; color: {theme_manager.palette.text_soft};")
            self._preview_layout.addWidget(lbl)
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
        self._save_current()
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
            self._refresh_files()

    def _save_and_refresh(self):
        self._save_current()
        self._refresh_table()
        self._refresh_files()

    def _save_current(self):
        if self._current_entry is None:
            return
        self._current_entry["date"] = self._date.date().toString("yyyy-MM-dd") if self._date.date().isValid() else ""
        self._current_entry["titre"] = self._title.text()
        self._current_entry["doc"] = self._doc.toPlainText()
        self._refresh_files()

    def _add_entry(self):
        from datetime import date

        today = date.today().isoformat()
        self._entries.append({"no": len(self._entries) + 1, "date": today, "titre": "", "doc": ""})
        self._refresh_table()

    def set_directory(self, base_dir: str):
        self._base_dir = base_dir
        if self._current_entry:
            self._refresh_files()

    def _entry_dir(self) -> str:
        if not self._base_dir:
            return ""
        no = self._current_entry.get("no", 0) if self._current_entry else 0
        d = os.path.join(self._base_dir, str(no))
        os.makedirs(d, exist_ok=True)
        return d

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
