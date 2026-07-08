"""
DossierPanel — Sections documentaires avec notes + fichiers joints.
Stockage : notes_json (JSONB) dans larcauth_student.
Chaque entrée = un document avec ses propres fichiers joints.
"""

import os

from larccommon.l10n import _
from larccommon.widgets.table_settings import TableSettings
from LarcSecretaire.common.theme import theme_manager
from phibuilder.widgets import M3Button, M3Card, M3DateEdit, M3HeaderView, M3Label, M3StackedWidget, M3TableWidget, M3TextEdit, M3TextField
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

SECTIONS = [
    ("medicale", _("dossier.section.medical")),
    ("pedagogique", _("dossier.section.pedagogic")),
    ("administrative", _("dossier.section.administrative")),
    ("communication", _("dossier.section.communication")),
    ("orientation", _("dossier.section.orientation")),
    ("autre", _("dossier.section.other")),
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
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
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

        self._table = M3TableWidget(theme=phi)
        self._table.set_headers([_("dossier.table_headers"), _("dossier.table_headers_title"), _("dossier.table_headers_description")])
        self._table.horizontalHeader().setSectionResizeMode(0, M3HeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, M3HeaderView.Interactive)
        self._table.setColumnWidth(1, 120)
        self._table.horizontalHeader().setSectionResizeMode(2, M3HeaderView.Stretch)
        self._table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._on_select)
        self._table.cellClicked.connect(lambda r, c: self._on_select_row(r))
        self._table.horizontalHeader().sectionResized.connect(self._on_col_resize)
        TableSettings.restore(self._table, f"dossier/{self._key}")
        left_col.addWidget(self._table)

        top.addLayout(left_col, 5)

        # --- Colonne droite : Édition ---
        right_col = QVBoxLayout()
        right_col.setSpacing(sp)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._title = M3TextField(placeholder=_("dossier.title_placeholder"), theme=phi)
        self._title.textChanged.connect(self._save_current)
        title_row.addWidget(self._title, 1)
        add_btn = M3Button("+", theme=phi, variant=ButtonVariant.FILLED)
        add_btn.setFixedSize(24, 24)
        add_btn.clicked.connect(self._add_entry)
        title_row.addWidget(add_btn)
        del_btn = M3Button("−", theme=phi, variant=ButtonVariant.OUTLINED)
        del_btn.setFixedSize(24, 24)
        del_btn.clicked.connect(self._delete_entry)
        title_row.addWidget(del_btn)
        right_col.addLayout(title_row)

        self._date = M3DateEdit()
        self._date.setDisplayFormat("yyyy-MM-dd")
        self._date.setCalendarPopup(True)
        self._date.setSpecialValueText(" ")
        self._date.setDate(QDate())
        self._date.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: 12px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._date.dateChanged.connect(self._save_current)
        right_col.addWidget(self._date)

        self._doc = M3TextEdit()
        self._doc.setPlaceholderText(_("dossier.description_placeholder"))
        self._doc.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: 12px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._doc.textChanged.connect(self._save_current)
        right_col.addWidget(self._doc, 1)

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = M3Button(_("dossier.save_button"), theme=phi, variant=ButtonVariant.FILLED)
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

        self._file_table = M3TableWidget(theme=phi)
        self._file_table.set_headers([_("dossier.file_headers_name"), _("dossier.file_headers_doc")])
        self._file_table.horizontalHeader().setSectionResizeMode(0, M3HeaderView.Interactive)
        self._file_table.setColumnWidth(0, 144)
        self._file_table.horizontalHeader().setSectionResizeMode(1, M3HeaderView.Stretch)
        self._file_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._file_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._file_table.itemSelectionChanged.connect(self._on_file_selected)
        self._file_table.cellDoubleClicked.connect(self._on_preview_file_row)
        file_layout.addWidget(self._file_table)

        file_btns = QHBoxLayout()
        file_btns.setSpacing(4)
        add_f = M3Button("+", theme=phi, variant=ButtonVariant.FILLED)
        add_f.setFixedSize(22, 22)
        add_f.clicked.connect(self._add_file)
        file_btns.addWidget(add_f)
        open_f = M3Button("📂", theme=phi, variant=ButtonVariant.OUTLINED)
        open_f.setFixedSize(22, 22)
        open_f.clicked.connect(self._open_file_dir)
        file_btns.addWidget(open_f)
        del_f = M3Button("−", theme=phi, variant=ButtonVariant.OUTLINED)
        del_f.setFixedSize(22, 22)
        del_f.clicked.connect(self._delete_file)
        file_btns.addWidget(del_f)
        save_f = M3Button("✓", theme=phi, variant=ButtonVariant.FILLED)
        save_f.setFixedSize(22, 22)
        save_f.clicked.connect(self._refresh_files)
        file_btns.addWidget(save_f)
        file_btns.addStretch()
        file_layout.addLayout(file_btns)
        bottom.addWidget(file_widget, 5)

        self._preview_frame = M3Card(theme=phi, variant=CardVariant.FILLED, parent=self)
        self._preview_layout = self._preview_frame.content_layout()
        self._preview_widget = M3Label(_("dossier.preview_placeholder"))
        self._preview_widget.setAlignment(Qt.AlignCenter)
        self._preview_widget.setStyleSheet(f"font-size: 11px; color: {p.text_disabled};")
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
        paths, _ = QFileDialog.getOpenFileNames(self, _("dossier.add_files"), "")
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
        r = QMessageBox.question(self, _("dossier.confirm_delete"), _("dossier.confirm_delete_file").format(name=name), QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        path = os.path.join(self._entry_dir(), name)
        try:
            os.remove(path)
            self._refresh_files()
        except Exception as e:
            QMessageBox.critical(self, _("dossier.error"), str(e))

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

            lbl = M3Label()
            pix = QPixmap(path)
            lbl.setPixmap(pix.scaled(300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lbl.setAlignment(Qt.AlignCenter)
            self._preview_layout.addWidget(lbl)
        elif ext in {".txt", ".csv", ".md", ".json", ".py", ".sql"}:
            ed = M3TextEdit()
            ed.setReadOnly(True)
            ed.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px;")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    ed.setPlainText(f.read()[:5000])
            except Exception:
                ed.setPlainText(_("dossier.fallback_text"))
            self._preview_layout.addWidget(ed)
        else:
            lbl = M3Label(_("dossier.file_info").format(name=name.text(), bytes=f"{os.path.getsize(path):,}"))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px; color: {theme_manager.palette.text_soft};")
            self._preview_layout.addWidget(lbl)

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
        self._select_row(rows[0].row())

    def _on_select_row(self, row: int):
        self._select_row(row)

    def _select_row(self, idx: int):
        self._save_current()
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

    def _delete_entry(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._entries):
            return
        e = self._entries[idx]
        r = QMessageBox.question(
            self, _("dossier.confirm_delete_entry"), _("dossier.confirm_delete_entry_msg").format(title=e.get("titre", "")), QMessageBox.Yes | QMessageBox.No
        )
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
        self._btns: list[M3Button] = []
        self._stack_info: list[tuple] = []

        visible_sections = list(SECTIONS)

        btn_base = (
            f"M3Button {{ border: none; border-radius: {d.radius_lg}px; "
            f"padding: {d.spacing * 2}px {d.spacing * 4}px; "
            f"font-size: {s(13)}px; font-weight: bold; }}"
        )

        for key, label in visible_sections:
            btn = M3Button(label)
            btn.setStyleSheet(
                btn_base + f"M3Button {{ background: transparent; color: {p.text_strong}; }}M3Button:hover {{ background: {p.surface_variant}; }}"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._select(k))
            btn_row.addWidget(btn)
            self._btns.append(btn)
            self._stack_info.append((key, label))

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._stack = M3StackedWidget()
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
            f"M3Button {{ border: none; border-radius: {theme_manager.design.radius_lg}px; "
            f"padding: {sp}px {sp * 2}px; font-size: {theme_manager.font_size(13)}px; "
            f"font-weight: bold; }}"
        )
        for i, (k, _) in enumerate(self._stack_info):
            if k == key:
                self._btns[i].setStyleSheet(btn_base + f"M3Button {{ background: {p.primary}; color: {p.on_primary}; }}")
                self._stack.setCurrentIndex(i)
            else:
                self._btns[i].setStyleSheet(
                    btn_base + f"M3Button {{ background: transparent; color: {p.text_strong}; }}M3Button:hover {{ background: {p.surface_variant}; }}"
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
