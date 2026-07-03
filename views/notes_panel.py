"""
NotesPanel — Éditeur structuré de notes élèves en JSON.
7 sections (confidentielle, medicale, pedagogique, administrative,
           communication, orientation, autre).
Stockage : colonne notes_json JSONB dans larcauth_student.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QStyledItemDelegate, QPlainTextEdit, QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QTextDocument, QPageSize
from PySide6.QtPrintSupport import QPrinter
from LarcSecretaire.common.theme import theme_manager

import os

SECTIONS = [
    ("confidentielle", "Confidentielle",
     "Réserver aux informations sensibles ne devant pas être diffusées "
     "sans autorisation : situation familiale, signalements, mesures "
     "disciplinaires, décisions de la direction. Ne rien inscrire ici "
     "qui pourrait être lu par l'élève ou un tiers non autorisé."),
    ("medicale", "Médicale",
     "Noter les allergies connues, traitements en cours, PAI (Projet "
     "d'Accueil Individualisé), visites à l'infirmerie récurrentes, "
     "handicaps déclarés et aménagements prescrits. Joindre les "
     "documents médicaux (certificats, ordonnances) dans les lignes "
     "ci-dessous."),
    ("pedagogique", "Pédagogique",
     "Suivi éducatif : PPRE, aménagements pédagogiques, soutien, "
     "résultats aux évaluations nationales, bilans de compétences, "
     "décisions du conseil de classe. Indiquer les dates et le "
     "document ou compte-rendu associé."),
    ("administrative", "Administrative",
     "Bourses (type, montant, période), assurances scolaires, "
     "conventions de stage, documents fournis par la famille "
     "(certificats de scolarité, autorisations), correspondance "
     "avec l'administration."),
    ("communication", "Communication",
     "Historique des échanges avec les parents/responsables : "
     "entretiens (date, motif, conclusion), appels téléphoniques, "
     "courriers/emails envoyés ou reçus. Chaque ligne = un contact."),
    ("orientation", "Orientation",
     "Vœux d'orientation émis par la famille, stages effectués "
     "ou demandés, rendez-vous avec le PsyEN, CV et lettres de "
     "motivation, résultats aux tests d'orientation, décisions "
     "d'affectation."),
    ("autre", "Autre",
     "Informations diverses ne relevant pas des catégories ci-dessus. "
     "Si une catégorie devient récurrente, envisager de la remonter "
     "en section dédiée."),
]

TEMPLATE_ENTRIES = [
    {"no": 1, "date": QDate.currentDate().toString("yyyy-MM-dd"),
     "titre": "Exemple — Premier document",
     "doc": "Description ou nom du document associé"},
]

for i in range(2, 7):
    TEMPLATE_ENTRIES.append({"no": i, "date": "", "titre": "", "doc": ""})


def _empty_entries() -> list[dict]:
    return [dict(e) for e in TEMPLATE_ENTRIES]


def _default_section(intro_text: str) -> dict:
    return {"intro": f"<p>{intro_text}</p>", "entries": _empty_entries()}


def _init_structure() -> dict:
    return {key: _default_section(intro) for key, _, intro in SECTIONS}


class _MultilineDelegate(QStyledItemDelegate):
    """Delegate pour édition multi-lignes dans la colonne Document/Note."""

    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        editor.setStyleSheet(
            f"border: 1px solid {p.primary}; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; background: {p.surface}; color: {p.text_strong};")
        editor.setMinimumHeight(89)
        return editor

    def setEditorData(self, editor, index):
        editor.setPlainText(index.data() or '')

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText())

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def sizeHint(self, option, index):
        text = index.data() or ''
        lines = max(1, text.count('\n') + 1, len(text) // 50 + 1)
        return QSize(option.rect.width(), min(lines * 20, 200))


class _SectionTab(QWidget):
    """Un onglet = une section de notes : intro éditable + tableau entries."""

    def __init__(self, section_key: str, title: str, intro_text: str,
                 on_export_pdf=None, on_export_word=None, parent=None):
        super().__init__(parent)
        self._key = section_key
        self._intro_text = intro_text
        self._on_export_pdf = on_export_pdf
        self._on_export_word = on_export_word
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        fs = 10

        layout = QVBoxLayout(self)
        layout.setSpacing(d.spacing)
        layout.setContentsMargins(d.margin, d.margin, d.margin, d.margin)

        # --- Intro contextuelle (statique) ---
        intro_lbl = QLabel(intro_text)
        intro_lbl.setWordWrap(True)
        intro_lbl.setStyleSheet(
            f"padding: {d.field_pad_v + 2}px {d.field_pad_h}px; "
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(fs - 1)}px; color: {p.text_soft}; "
            f"background: {p.surface_variant};")
        layout.addWidget(intro_lbl)

        # --- Tableau entries ---
        table_label = QLabel("Pièces jointes / Documents :")
        table_label.setStyleSheet(
            f"font-size: {s(fs)}px; color: {p.text_soft}; font-weight: bold;")
        layout.addWidget(table_label)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["N°", "Date", "Titre", "Document / Note"])
        hh = self._table.horizontalHeader()
        for c in range(4):
            hh.setSectionResizeMode(c, QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        self._table.setWordWrap(True)
        self._table.verticalHeader().setSectionsMovable(False)
        self._table.verticalHeader().setMinimumSectionSize(21)
        self._table.setStyleSheet(
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};")
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.ExtendedSelection)
        self._table.setItemDelegateForColumn(3, _MultilineDelegate(self._table))
        layout.addWidget(self._table, 1)

        # --- Boutons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(d.spacing)

        add_btn = QPushButton("+ Ligne")
        add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius}px; padding: 3px 13px; font-size: {s(fs)}px; }}"
        f"QPushButton:hover {{ background: {p.success}; }}")
        add_btn.clicked.connect(self._add_row)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("− Ligne")
        remove_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.error}; "
            f"border: 1px solid {p.error}; border-radius: {d.radius}px; "
            f"padding: 3px 13px; font-size: {s(fs)}px; }}"
            f"QPushButton:hover {{ background: {p.error_container}; }}")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch()

        def _exp_btn(text, tip, color_key):
            b = QPushButton(text)
            bg = getattr(p, color_key, p.primary)
            b.setStyleSheet(
                f"QPushButton {{ background: {bg}; color: white; border: none; "
                f"border-radius: {d.radius}px; padding: 3px 8px; font-size: {s(fs - 1)}px; }}"
                f"QPushButton:hover {{ background: {p.primary_container}; }}")
            b.setToolTip(tip)
            return b

        if self._on_export_pdf:
            epub = _exp_btn("PDF", "Exporter toutes les sections en PDF", 'primary')
            epub.clicked.connect(self._on_export_pdf)
            btn_row.addWidget(epub)
        if self._on_export_word:
            eword = _exp_btn("Word", "Exporter toutes les sections en Word", 'tertiary')
            eword.clicked.connect(self._on_export_word)
            btn_row.addWidget(eword)

        layout.addLayout(btn_row)

        self._populate_table(_empty_entries())

    def _populate_table(self, entries: list[dict]):
        self._table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            no_item = QTableWidgetItem(str(e.get('no', i + 1)))
            no_item.setFlags(no_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(i, 0, no_item)
            self._table.setItem(i, 1, QTableWidgetItem(str(e.get('date', ''))))
            ti = QTableWidgetItem(str(e.get('titre', '')))
            ti.setToolTip(str(e.get('titre', '')))
            self._table.setItem(i, 2, ti)
            di = QTableWidgetItem(str(e.get('doc', '')))
            di.setToolTip(str(e.get('doc', '')))
            self._table.setItem(i, 3, di)
        self._table.resizeRowsToContents()

    def _renumber(self):
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            if item:
                item.setText(str(i + 1))

    def _add_row(self):
        row = self._table.rowCount()
        self._table.insertRow(row)
        no_item = QTableWidgetItem(str(row + 1))
        no_item.setFlags(no_item.flags() & ~Qt.ItemIsEditable)
        self._table.setItem(row, 0, no_item)
        self._table.setItem(row, 1, QTableWidgetItem(""))
        self._table.setItem(row, 2, QTableWidgetItem(""))
        self._table.setItem(row, 3, QTableWidgetItem(""))
        self._table.setRowHeight(row, 34)

    def _remove_selected(self):
        rows = set()
        for item in self._table.selectedItems():
            rows.add(item.row())
        for r in sorted(rows, reverse=True):
            self._table.removeRow(r)
        self._renumber()

    def get_data(self) -> dict:
        entries = []
        for i in range(self._table.rowCount()):
            no_item = self._table.item(i, 0)
            if not no_item:
                continue
            entries.append({
                "no": int(no_item.text() or i + 1),
                "date": self._table.item(i, 1).text() if self._table.item(i, 1) else "",
                "titre": self._table.item(i, 2).text() if self._table.item(i, 2) else "",
                "doc": self._table.item(i, 3).text() if self._table.item(i, 3) else "",
            })
        return {
            "intro": self._intro_text,
            "entries": entries,
        }

    def get_export_data(self) -> tuple[str, list[dict]]:
        raw = self._intro_text
        entries = []
        for i in range(self._table.rowCount()):
            no_item = self._table.item(i, 0)
            if not no_item:
                continue
            t = (self._table.item(i, 2).text() if self._table.item(i, 2) else "").strip()
            d = (self._table.item(i, 3).text() if self._table.item(i, 3) else "").strip()
            dt = (self._table.item(i, 1).text() if self._table.item(i, 1) else "").strip()
            if t or d or dt:
                entries.append({"date": dt, "titre": t, "doc": d})
        return raw, entries

    def set_data(self, data: dict):
        entries = data.get('entries', [])
        if entries:
            self._populate_table(entries)
        else:
            self._populate_table(_empty_entries())

    def clear(self):
        self._populate_table(_empty_entries())


class NotesPanel(QWidget):
    """Panneau complet de notes structurées.

    Utilisation :
        panel = NotesPanel()
        panel.set_student_name("Nom Prénom")
        panel.set_json(data)   # data = dict JSON depuis la DB
        json_data = panel.get_json()   # → dict prêt pour JSONB
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._student_name = "Élève"

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._sections: dict[str, _SectionTab] = {}

        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        fs = 10

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(d.spacing)
        layout.addWidget(self._tabs, 1)

        for key, title, intro in SECTIONS:
            tab = _SectionTab(key, title, intro,
                              on_export_pdf=self._export_pdf,
                              on_export_word=self._export_word)
            self._sections[key] = tab
            self._tabs.addTab(tab, title)

    def set_student_name(self, name: str):
        self._student_name = name

    def _build_html(self) -> str:
        parts = [f"<html><head><meta charset='utf-8'></head><body>"]
        parts.append(f"<h1>{self._student_name}</h1>")
        section_labels = {k: t for k, t, _ in SECTIONS}
        for key, tab in self._sections.items():
            raw_intro, entries = tab.get_export_data()
            if not raw_intro and not entries:
                continue
            parts.append(f"<h2>{section_labels.get(key, key)}</h2>")
            if raw_intro:
                parts.append(f"<p>{raw_intro}</p>")
            if entries:
                parts.append("<table border='1' cellpadding='4' cellspacing='0' "
                             "style='border-collapse: collapse; width: 100%;'>")
                parts.append("<tr><th>Date</th><th>Titre</th><th>Document / Note</th></tr>")
                for e in entries:
                    parts.append(f"<tr><td>{e['date']}</td><td>{e['titre']}</td>"
                                 f"<td>{e['doc']}</td></tr>")
                parts.append("</table>")
        parts.append("</body></html>")
        return "\n".join(parts)

    def _export_pdf(self):
        html = self._build_html()
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en PDF",
            f"{self._student_name} — Notes",
            "Fichier PDF (*.pdf)")
        if not path:
            return
        try:
            doc = QTextDocument()
            doc.setHtml(html)
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPageSize(QPageSize.A4))
            doc.print_(printer)
            QMessageBox.information(self, "Export PDF",
                f"Notes exportées vers :\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur export PDF", str(e))

    def _export_word(self):
        html = self._build_html()
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en Word",
            f"{self._student_name} — Notes",
            "Document HTML (*.html *.htm)")
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            QMessageBox.information(self, "Export Word",
                f"Notes exportées vers :\n{path}\n\n"
                "Ouvrir ce fichier HTML dans Word pour le modifier.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur export Word", str(e))

    def get_json(self) -> dict:
        result = {}
        for key, tab in self._sections.items():
            data = tab.get_data()
            if data['intro'] or any(e['titre'] or e['doc'] for e in data['entries']):
                result[key] = data
            else:
                result[key] = {"intro": "", "entries": []}
        return result

    def set_json(self, data: dict):
        if not data:
            data = {}
        for key, tab in self._sections.items():
            section_data = data.get(key, {})
            if section_data:
                tab.set_data(section_data)
            else:
                tab.clear()

    def clear(self):
        for tab in self._sections.values():
            tab.clear()
