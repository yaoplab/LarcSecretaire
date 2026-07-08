"""
Fiche élève — recherche, consultation et édition des informations élèves.

Architecture :
  - StudentForm       : widget principal (barre recherche + contenu)
  - _StudentSearch    : zone de recherche + résultats
  - _StudentDetail    : onglets Coordonnées / Adresse / Parents + mode édition

Dépendances :
  - LarcSecretaire.common.database  (db.server_conn)
  - LarcSecretaire.common.theme     (theme_manager)
  - LarcSecretaire.common.session   (session)
"""

import json
import os

from larccommon.l10n import _
from LarcSecretaire.common.audit import audit
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.photos import get_photo_path
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from LarcSecretaire.views.notes_panel import NotesPanel
from LarcSecretaire.views.supervisor_panel import _event_color, _event_label
from phibuilder.widgets import (
    M3Button,
    M3Card,
    M3ComboBox,
    M3DateEdit,
    M3Dialog,
    M3DialogButtonBox,
    M3Frame,
    M3HeaderView,
    M3Label,
    M3ScrollArea,
    M3StackedWidget,
    M3TableWidget,
    M3TabWidget,
    M3TextEdit,
    M3TextField,
)
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from phibuilder.widgets import M3SidebarNav
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ──────────────────────────────────────────────
#   Classe utilitaire : cercle avatar initiales
# ──────────────────────────────────────────────


def _make_avatar(last_name: str, first_name: str, size: int = 120) -> QPixmap:
    """Génère un avatar rond avec les initiales."""
    initials = (last_name[:1] + first_name[:1]).upper() or "?"
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]
    bg = colors[hash(last_name + first_name) % len(colors)]
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(bg))
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.setPen(QColor("#fff"))
    f = p.font()
    f.setPixelSize(size // 3)
    f.setBold(True)
    p.setFont(f)
    p.drawText(px.rect(), Qt.AlignCenter, initials)
    p.end()
    return px


# ──────────────────────────────────────────────
#   StudentForm — widget principal
# ──────────────────────────────────────────────


class StudentForm(QWidget):
    """
    Page de gestion des fiches élèves.

    Utilisation :
        form = StudentForm()
        form.search("nom ou classe")   # Recherche programmatique
    """

    def __init__(self):
        super().__init__()
        # Données internes
        self._current_student: dict | None = None  # Élève actuellement affiché
        self._results: list[dict] = []  # Résultats de recherche
        self._dirty: bool = False  # Modifications non sauvegardées

        # UI
        self._init_ui()

    # ──────────── Construction UI ────────────

    def _init_ui(self):
        """Construit l'interface complète."""
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
        d = theme_manager.design
        layout = QVBoxLayout(self)
        layout.setContentsMargins(d.margin, d.margin, d.margin, d.margin)
        layout.setSpacing(d.spacing + 2)

        # Titre + bouton +
        title_row = QHBoxLayout()
        title = M3Label(_("student_form.title"), theme=phi, style="title_medium")
        title_row.addWidget(title)
        title_row.addStretch()

        self._add_student_btn = M3Button("+", theme=phi, variant=ButtonVariant.TONAL)
        self._add_student_btn.setFixedSize(34, 34)
        self._add_student_btn.clicked.connect(self._open_create_dialog)
        title_row.addWidget(self._add_student_btn)
        layout.addLayout(title_row)

        # Barre de recherche
        search_row = QHBoxLayout()
        self._search_input = M3TextField(placeholder=_("student_form.search_placeholder"), theme=phi)
        self._search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self._search_input, 1)

        self._search_btn = M3Button(_("student_form.search_button"), theme=phi, variant=ButtonVariant.FILLED)
        self._search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)

        # Zone de contenu : résultats (gauche) + détail (droite)
        content = QHBoxLayout()
        content.setSpacing(d.spacing + 2)

        # ── Panneau résultats (gauche) ──
        self._results_panel = M3Card(theme=phi, variant=CardVariant.ELEVATED, parent=self)
        rp_layout = self._results_panel.content_layout()
        rp_layout.setContentsMargins(d.radius, d.radius, d.radius, d.radius)

        self._results_label = M3Label(_("student_form.results_label").format(count=0), theme=phi, style="label_small")
        self._results_label.setStyleSheet("font-weight: bold;")
        rp_layout.addWidget(self._results_label)

        # Tableau des résultats
        self._results_table = M3TableWidget(theme=phi)
        self._results_table.set_headers(
            [_("student_form.table_headers"), _("student_form.table_headers_class"), _("student_form.table_headers_email"), _("student_form.table_headers_id")]
        )
        self._results_table.setColumnHidden(3, True)
        self._results_table.horizontalHeader().setStretchLastSection(True)
        self._results_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._results_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._results_table.setAlternatingRowColors(True)
        self._results_table.itemSelectionChanged.connect(self._on_result_selected)
        rp_layout.addWidget(self._results_table, 1)
        content.addWidget(self._results_panel, 1)

        # ── Panneau détail (droite) — vignette info ──
        self._detail_panel = M3Card(theme=phi, variant=CardVariant.ELEVATED, parent=self)
        dp_layout = self._detail_panel.content_layout()
        dp_layout.setContentsMargins(d.margin, d.margin, d.margin, d.margin)
        dp_layout.setSpacing(d.spacing + 2)
        dp_layout.setAlignment(Qt.AlignCenter)

        self._detail_photo = QLabel()
        self._detail_photo.setFixedSize(160, 160)
        self._detail_photo.setStyleSheet(f"background: {p.primary_container}; border-radius: {d.radius_xl + 2}px;")
        self._detail_photo.setAlignment(Qt.AlignCenter)
        self._detail_photo.setCursor(Qt.PointingHandCursor)
        self._detail_photo.installEventFilter(self)
        dp_layout.addWidget(self._detail_photo, 0, Qt.AlignCenter)

        self._detail_nom_label = M3Label("—", theme=phi, style="headline_small")
        self._detail_nom_label.setAlignment(Qt.AlignCenter)
        dp_layout.addWidget(self._detail_nom_label, 0, Qt.AlignCenter)

        self._detail_classe_label = M3Label("", theme=phi, style="body_medium")
        self._detail_classe_label.setAlignment(Qt.AlignCenter)
        dp_layout.addWidget(self._detail_classe_label)

        self._detail_id_label = M3Label("", theme=phi, style="body_medium")
        self._detail_id_label.setAlignment(Qt.AlignCenter)
        dp_layout.addWidget(self._detail_id_label)

        dp_layout.addSpacing(13)

        self._open_btn = M3Button(_("student_form.open_file"), theme=phi, variant=ButtonVariant.FILLED)
        self._open_btn.clicked.connect(self._open_edit_dialog)
        self._open_btn.setMinimumWidth(144)
        dp_layout.addWidget(self._open_btn, 0, Qt.AlignCenter)

        dp_layout.addStretch()

        self._detail_panel.hide()
        content.addWidget(self._detail_panel, 1)

        layout.addLayout(content, 1)

    # ──────────── Recherche ────────────

    def _on_search(self, checked: bool = False):
        """
        Déclenche la recherche quand l'utilisateur appuie sur Entrée ou clique Rechercher.

        Args:
            checked: Ignoré (requis par le signal clicked(bool) de QPushButton)
        """
        query = self._search_input.text().strip()
        if not query:
            QMessageBox.information(self, _("student_form.search_info_title"), _("student_form.search_info_msg"))
            return
        self.search(query)

    def search(self, query: str):
        """
        Recherche des élèves par nom, prénom, email ou classe.

        Les résultats sont affichés dans le panneau de gauche.
        """
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("student_form.error.no_connection"))
            return

        from psycopg2 import errors as pg_errors

        try:
            cur = conn.cursor()
            like = f"%{query}%"
            try:
                cur.execute(
                    """
                    SELECT
                        s.aecuser_ptr_id AS id,
                        aec.last_name, aec.first_name,
                        aec.email, aec.emailperso,
                        aec.tel_smartphone_1, aec.tel_maison,
                        c.label AS classroom,
                        aec.date_joined, aec.date_entree, aec.date_of_birth, aec.fk_foyer_id,
                        aec.fk_gender_id, s.s_classroom_id,
                        s.notes, s.notes_json,
                        f.address_line1, f.address_line2, f.postal_code,
                        f.city, f.country,
                        f.phone AS foyer_phone, f.email AS foyer_email
                    FROM larcauth_student s
                    JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                    JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                    LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                    WHERE s.enabled = TRUE
                      AND (aec.last_name ILIKE %s OR aec.first_name ILIKE %s
                        OR aec.email ILIKE %s OR c.label ILIKE %s)
                    ORDER BY aec.last_name, aec.first_name
                    LIMIT 200
                """,
                    (
                        like,
                        like,
                        like,
                        like,
                    ),
                )
            except pg_errors.UndefinedColumn:
                cur.execute(
                    """
                    SELECT
                        s.aecuser_ptr_id AS id,
                        aec.last_name, aec.first_name,
                        aec.email, aec.emailperso,
                        aec.tel_smartphone_1, aec.tel_maison,
                        c.label AS classroom,
                        aec.date_joined, aec.date_entree, aec.date_of_birth, aec.fk_foyer_id,
                        aec.fk_gender_id, s.s_classroom_id,
                        NULL AS notes, NULL AS notes_json,
                        f.address_line1, f.address_line2, f.postal_code,
                        f.city, f.country,
                        f.phone AS foyer_phone, f.email AS foyer_email
                    FROM larcauth_student s
                    JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                    JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                    LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                    WHERE s.enabled = TRUE
                      AND (aec.last_name ILIKE %s OR aec.first_name ILIKE %s
                        OR aec.email ILIKE %s OR c.label ILIKE %s)
                    ORDER BY aec.last_name, aec.first_name
                    LIMIT 200
                """,
                    (
                        like,
                        like,
                        like,
                        like,
                    ),
                )

            cols = [desc[0] for desc in cur.description]
            self._results = [dict(zip(cols, row)) for row in cur.fetchall()]
            self._populate_results()

        except Exception as e:
            log(f"StudentForm.search: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _populate_results(self):
        """Remplit le tableau des résultats de recherche."""
        self._results_table.setRowCount(0)
        for r in self._results:
            row = self._results_table.rowCount()
            self._results_table.insertRow(row)
            self._results_table.setItem(row, 0, QTableWidgetItem(f"{r['last_name']} {r['first_name']}"))
            self._results_table.setItem(row, 1, QTableWidgetItem(r.get("classroom", "")))
            self._results_table.setItem(row, 2, QTableWidgetItem(r.get("email", "")))
            self._results_table.setItem(row, 3, QTableWidgetItem(str(r["id"])))

        self._results_table.resizeColumnsToContents()
        count = len(self._results)
        self._results_label.setText(_("student_form.results_label").format(count=count))

        if count == 0:
            self._detail_panel.hide()
            QMessageBox.information(self, _("student_form.search_info_title"), _("student_form.search_no_results"))
        elif count == 1:
            # Sélection automatique si un seul résultat
            self._results_table.selectRow(0)

    # ──────────── Affichage du détail ────────────

    def _on_result_selected(self):
        """Sélection d'un résultat → ouvre la popup d'édition."""
        rows = self._results_table.selectedItems()
        if not rows:
            return
        student_id = int(self._results_table.item(rows[0].row(), 3).text())
        self._open_student_dialog(student_id)

    def _open_student_dialog(self, student_id: int, force_refresh: bool = False):
        """Ouvre la popup d'édition pour un élève."""
        data = None
        if not force_refresh:
            data = next((r for r in self._results if r["id"] == student_id), None)
        conn = db.server_conn
        if not conn:
            return
        from psycopg2 import errors as pg_errors

        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT
                        s.aecuser_ptr_id AS id,
                        aec.last_name, aec.first_name, aec.email,
                        aec.emailperso, aec.tel_smartphone_1, aec.tel_maison,
                        c.label AS classroom, aec.date_joined,
                        aec.date_entree,
                        aec.date_of_birth,
                        aec.fk_foyer_id, aec.fk_gender_id,
                        s.s_classroom_id, s.notes, s.notes_json,
                        f.address_line1, f.address_line2, f.postal_code,
                        f.city, f.country, f.phone AS foyer_phone, f.email AS foyer_email
                    FROM larcauth_student s
                    JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                    JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                    LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                    WHERE s.aecuser_ptr_id = %s
                """,
                    (student_id,),
                )
            except pg_errors.UndefinedColumn:
                cur.execute(
                    """
                    SELECT
                        s.aecuser_ptr_id AS id,
                        aec.last_name, aec.first_name, aec.email,
                        aec.emailperso, aec.tel_smartphone_1, aec.tel_maison,
                        c.label AS classroom, aec.date_joined,
                        aec.date_entree,
                        aec.date_of_birth,
                        aec.fk_foyer_id, aec.fk_gender_id,
                        s.s_classroom_id, NULL AS notes, NULL AS notes_json,
                        f.address_line1, f.address_line2, f.postal_code,
                        f.city, f.country, f.phone AS foyer_phone, f.email AS foyer_email
                    FROM larcauth_student s
                    JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                    JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                    LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                    WHERE s.aecuser_ptr_id = %s
                """,
                    (student_id,),
                )
            cols = [desc[0] for desc in cur.description]
            row = cur.fetchone()
            if not row:
                return
            data = dict(zip(cols, row))
        except Exception as e:
            log(f"StudentForm._open_student_dialog: {e}")
            return

        self._current_student = data
        self._update_info_card(data)
        self._detail_panel.show()

    def _update_info_card(self, data: dict):
        """Met à jour la vignette info."""
        sid = data["id"]
        px = QPixmap(get_photo_path(sid))
        if px.isNull():
            px = _make_avatar(data["last_name"], data["first_name"], 160)
        else:
            px = px.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._detail_photo.setPixmap(px)
        self._detail_nom_label.setText(f"{data['last_name']} {data['first_name']}")
        self._detail_classe_label.setText(f"Classe : {data.get('classroom', '—')}")
        self._detail_id_label.setText(f"ID : {sid}")

    def _open_edit_dialog(self):
        """Ouvre la popup d'édition pour l'élève courant."""
        if not self._current_student:
            return
        dlg = StudentEditDialog(self._current_student, self)
        if dlg.exec():
            self.search(self._search_input.text().strip())
            self._open_student_dialog(self._current_student["id"], force_refresh=True)

    def _open_create_dialog(self):
        dlg = StudentCreateDialog(self)
        dlg.exec()

    def eventFilter(self, obj, event):
        if obj == self._detail_photo and event.type() == QEvent.MouseButtonPress:
            self._open_edit_dialog()
            return True
        return super().eventFilter(obj, event)


# ──────────────────────────────────────────────
#   StudentEditDialog — Modification d'un élève (popup)
# ──────────────────────────────────────────────


class StudentEditDialog(QDialog):
    """Popup d'édition d'élève — grand formulaire comme la création."""

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self._sid = data["id"]
        self._data = self._fetch_fresh_data() or data
        self.setWindowTitle(_("student_form.edit_title").format(l=self._data.get("last_name", "?"), f=self._data.get("first_name", "?")))
        self.setMinimumSize(987, 610)
        self.showMaximized()
        self._init_ui()
        self._load_data()

    def _fetch_fresh_data(self) -> dict | None:
        conn = db.server_conn
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    s.aecuser_ptr_id AS id,
                    aec.last_name, aec.first_name, aec.email,
                    aec.emailperso, aec.tel_smartphone_1, aec.tel_maison,
                    c.label AS classroom, aec.date_joined,
                    aec.date_entree,
                    aec.date_of_birth,
                    aec.fk_foyer_id, aec.fk_gender_id,
                    s.s_classroom_id, s.notes, s.notes_json,
                    f.address_line1, f.address_line2, f.postal_code,
                    f.city, f.country, f.phone AS foyer_phone, f.email AS foyer_email
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                WHERE s.aecuser_ptr_id = %s
            """,
                (self._sid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
        except Exception as e:
            log(f"StudentEditDialog._fetch_fresh_data: {e}")
            return None

    def _init_ui(self):
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        sp = 13

        layout = QVBoxLayout(self)
        layout.setSpacing(sp)
        layout.setContentsMargins(d.margin, d.margin, d.margin, d.margin)

        title = M3Label(_("student_form.edit_label"), theme=phi, style="headline_medium")
        layout.addWidget(title)

        def _lbl(t):
            lbl = M3Label(t, theme=phi, style="body_medium")
            lbl.setStyleSheet("font-weight: bold;")
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            return lbl

        # Photo + identité + boutons
        photo_row = QHBoxLayout()
        photo_row.setSpacing(sp)
        self._photo = QLabel()
        self._photo.setFixedSize(144, 144)
        self._photo.setStyleSheet(f"background: {p.primary_container}; border-radius: {d.radius_xl}px;")
        self._photo.setAlignment(Qt.AlignCenter)
        photo_row.addWidget(self._photo)

        id_col = QVBoxLayout()
        id_col.setSpacing(sp // 2)
        self._id_name = M3Label("", theme=phi, style="display_small")
        self._id_name.setStyleSheet("font-weight: bold;")
        id_col.addWidget(self._id_name)
        self._id_info = M3Label("", theme=phi, style="headline_small")
        id_col.addWidget(self._id_info)
        id_col.addStretch()
        photo_row.addLayout(id_col, 1)

        # Boutons d'action
        btn_col = QVBoxLayout()
        btn_col.setSpacing(d.spacing)
        btn_col.setAlignment(Qt.AlignTop)

        def _m3_btn(text, variant, size="md"):
            b = M3Button(text, theme=phi, variant=variant)
            b.setMinimumHeight(34)
            return b

        save_btn = _m3_btn(_("student_form.save"), ButtonVariant.FILLED)
        save_btn.clicked.connect(self._save)
        btn_col.addWidget(save_btn)

        pdf_btn = _m3_btn(_("student_form.pdf"), ButtonVariant.TONAL)
        pdf_btn.clicked.connect(self._export_pdf)
        btn_col.addWidget(pdf_btn)

        word_btn = _m3_btn(_("student_form.word"), ButtonVariant.TONAL)
        word_btn.clicked.connect(self._export_word)
        btn_col.addWidget(word_btn)

        cancel_btn = _m3_btn(_("student_form.cancel"), ButtonVariant.OUTLINED)
        cancel_btn.clicked.connect(self.reject)
        btn_col.addWidget(cancel_btn)

        btn_col.addStretch()
        photo_row.addLayout(btn_col)

        layout.addLayout(photo_row)
        layout.addSpacing(sp)

        # Champs
        self._inp_nom = M3TextField(theme=phi)
        self._inp_prenom = M3TextField(theme=phi)
        self._inp_email = M3TextField(theme=phi)
        self._inp_emailperso = M3TextField(theme=phi)
        self._inp_tel = M3TextField(theme=phi)
        self._inp_tel2 = M3TextField(theme=phi)
        self._inp_date_joined = M3DateEdit()
        self._inp_date_joined.setDisplayFormat("yyyy-MM-dd")
        self._inp_date_joined.setCalendarPopup(True)
        self._inp_date_joined.setSpecialValueText(" ")
        self._inp_date_joined.setDate(QDate())
        self._inp_date = M3DateEdit()
        self._inp_date.setDisplayFormat("yyyy-MM-dd")
        self._inp_date.setCalendarPopup(True)
        self._inp_date.setSpecialValueText(" ")
        self._inp_date.setDate(QDate())
        self._inp_date.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; font-size: 13px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._inp_genre = M3ComboBox(theme=phi)
        self._load_genders()
        self._inp_birthdate = M3DateEdit()
        self._inp_birthdate.setDisplayFormat("yyyy-MM-dd")
        self._inp_birthdate.setCalendarPopup(True)
        self._inp_birthdate.setSpecialValueText(" ")
        self._inp_birthdate.setDate(QDate())
        self._inp_birthdate.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; font-size: 13px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._inp_addr1 = M3TextEdit()
        self._inp_addr1.setFixedHeight(144)
        self._inp_addr1.setPlaceholderText(_("student_form.street_placeholder"))
        self._inp_addr1.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; font-size: 13px; "
            f"background: {p.surface}; color: {p.text_strong};"
        )
        self._inp_addr2 = M3TextField(theme=phi)
        self._inp_cp = M3TextField(theme=phi)
        self._inp_ville = M3TextField(theme=phi)
        self._inp_pays = M3TextField(_("student_form.default_country"), theme=phi)

        # Sidebar verticale + QStackedWidget (remplace les onglets)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(sp)
        nav_side = QVBoxLayout()
        nav_side.setSpacing(d.spacing)
        nav_side.setContentsMargins(0, 0, sp, 0)

        nav_items = [
            _("student_form.tab_identity"),
            _("student_form.tab_address"),
            _("student_form.tab_events"),
            _("student_form.tab_documents"),
            _("student_form.tab_confidential"),
        ]

        self._nav_btns: list[M3Button] = []
        self._nav_pages: list[QWidget] = []

        # --- Page 1 : Identité & Contact ---
        p1 = QWidget()
        p1_layout = QVBoxLayout(p1)
        p1_layout.setSpacing(sp)
        g1 = QGridLayout()
        g1.setSpacing(sp)
        r = 0
        g1.addWidget(_lbl(_("student_form.last_name_label")), r, 0)
        g1.addWidget(_lbl(_("student_form.first_name_label")), r, 1)
        r += 1
        g1.addWidget(self._inp_nom, r, 0)
        g1.addWidget(self._inp_prenom, r, 1)
        r += 1
        g1.addWidget(_lbl(_("student_form.arrival_label")), r, 0, 1, 2)
        r += 1
        g1.addWidget(self._inp_date_joined, r, 0, 1, 2)
        r += 1
        g1.addWidget(_lbl(_("student_form.entry_date")), r, 0)
        g1.addWidget(_lbl(_("student_form.gender_label")), r, 1)
        r += 1
        g1.addWidget(self._inp_date, r, 0)
        g1.addWidget(self._inp_genre, r, 1)
        r += 1
        g1.addWidget(_lbl(_("student_form.birth_date")), r, 0)
        r += 1
        g1.addWidget(self._inp_birthdate, r, 0)
        r += 2
        g1.addWidget(_lbl(_("student_form.email_label")), r, 0)
        g1.addWidget(_lbl(_("student_form.email_personal")), r, 1)
        r += 1
        g1.addWidget(self._inp_email, r, 0)
        g1.addWidget(self._inp_emailperso, r, 1)
        r += 1
        g1.addWidget(_lbl(_("student_form.phone_mobile")), r, 0)
        g1.addWidget(_lbl(_("student_form.phone_fixed")), r, 1)
        r += 1
        g1.addWidget(self._inp_tel, r, 0)
        g1.addWidget(self._inp_tel2, r, 1)
        p1_layout.addLayout(g1)
        p1_layout.addStretch()
        self._nav_pages.append(p1)

        # --- Page 3 : Adresse & Parents ---
        p4 = QWidget()
        p4_layout = QVBoxLayout(p4)
        p4_layout.setSpacing(sp)
        addr_card = M3Frame()
        addr_card.setStyleSheet(f"M3Frame {{ background: {p.surface_variant}; border-radius: {d.radius_lg}px; padding: {sp}px; }}")
        addr_card_layout = QVBoxLayout(addr_card)
        addr_card_layout.setSpacing(d.spacing)
        addr_title = M3Label(_("student_form.address_title"))
        addr_title.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.text_strong};")
        addr_card_layout.addWidget(addr_title)
        addr_card_layout.addWidget(self._inp_addr1)
        addr_card_layout.addWidget(self._inp_addr2)
        addr_grid = QGridLayout()
        addr_grid.setSpacing(d.spacing)
        addr_grid.addWidget(_lbl(_("student_form.zip_label")), 0, 0)
        addr_grid.addWidget(_lbl(_("student_form.city_label")), 0, 1)
        addr_grid.addWidget(self._inp_cp, 1, 0)
        addr_grid.addWidget(self._inp_ville, 1, 1)
        addr_grid.addWidget(_lbl(_("student_form.country_label")), 2, 0)
        addr_grid.addWidget(self._inp_pays, 3, 0, 1, 2)
        addr_card_layout.addLayout(addr_grid)
        p4_layout.addWidget(addr_card)
        parents_title = M3Label(_("student_form.parents_title"))
        parents_title.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.text_strong}; margin-top: {sp}px;")
        p4_layout.addWidget(parents_title)
        self._parents_table = M3TableWidget(theme=phi)
        self._parents_table.set_headers(
            [
                _("student_form.parents_table_nom"),
                _("student_form.parents_table_nature"),
                _("student_form.parents_table_email"),
                _("student_form.parents_table_phone"),
            ]
        )
        self._parents_table.horizontalHeader().setStretchLastSection(True)
        self._parents_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._parents_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._parents_table.setMaximumHeight(144)
        p4_layout.addWidget(self._parents_table)
        parent_tools = QHBoxLayout()
        parent_tools.setSpacing(d.spacing)
        add_par_btn = M3Button(_("student_form.add_parent"), theme=phi, variant=ButtonVariant.FILLED)
        add_par_btn.clicked.connect(self._add_parent_link)
        parent_tools.addWidget(add_par_btn)
        edit_par_btn = M3Button(_("student_form.edit_nature"), theme=phi, variant=ButtonVariant.TONAL)
        edit_par_btn.clicked.connect(self._edit_parent_nature)
        parent_tools.addWidget(edit_par_btn)
        remove_par_btn = M3Button(_("student_form.remove_parent"), theme=phi, variant=ButtonVariant.OUTLINED)
        remove_par_btn.clicked.connect(self._remove_parent_link)
        parent_tools.addWidget(remove_par_btn)
        copy_btn = M3Button(_("student_form.copy_address"), theme=phi, variant=ButtonVariant.TONAL)
        copy_btn.clicked.connect(self._copy_parent_address)
        parent_tools.addWidget(copy_btn)
        parent_tools.addStretch()
        p4_layout.addLayout(parent_tools)
        p4_layout.addStretch()
        self._nav_pages.append(p4)

        # --- Page 4 : Événements ---
        p4 = QWidget()
        p4_layout = QVBoxLayout(p4)
        p4_layout.setSpacing(sp)
        evt_label = M3Label(_("student_form.events_title"))
        evt_label.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.text_strong};")
        p4_layout.addWidget(evt_label)
        self._evt_table = M3TableWidget(theme=phi)
        self._evt_table.set_headers(
            [
                _("student_form.events_table_date"),
                _("student_form.events_table_type"),
                _("student_form.events_table_note"),
                _("student_form.events_table_by"),
                _("student_form.events_table_validated"),
            ]
        )
        hh_evt = self._evt_table.horizontalHeader()
        hh_evt.setSectionResizeMode(0, M3HeaderView.Interactive)
        hh_evt.setSectionResizeMode(1, M3HeaderView.Interactive)
        hh_evt.setSectionResizeMode(2, M3HeaderView.Stretch)
        hh_evt.setSectionResizeMode(3, M3HeaderView.Interactive)
        hh_evt.setSectionResizeMode(4, M3HeaderView.ResizeToContents)
        self._evt_table.setColumnWidth(0, 150)
        self._evt_table.setColumnWidth(1, 110)
        self._evt_table.setColumnWidth(3, 140)
        self._evt_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._evt_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._evt_table.setAlternatingRowColors(True)
        p4_layout.addWidget(self._evt_table, 1)
        self._nav_pages.append(p4)

        # --- Dossiers (sections + fichiers) ---
        p2 = QWidget()
        p2_layout = QVBoxLayout(p2)
        p2_layout.setContentsMargins(0, 0, 0, 0)
        from LarcSecretaire.views.dossier_panel import DossierPanel

        self._dossier_panel = DossierPanel(self._sid)
        p2_layout.addWidget(self._dossier_panel, 1)
        self._nav_pages.append(p2)

        # --- Confidentiel (restreint) ---
        p5 = QWidget()
        p5_layout = QVBoxLayout(p5)
        p5_layout.setSpacing(sp)
        from LarcSecretaire.common.session import UserRole
        from LarcSecretaire.common.session import session as _ses

        if _ses.role in (UserRole.ADMIN, UserRole.COORD, UserRole.SECR):
            conf_label = M3Label(_("student_form.confidential_notes"))
            conf_label.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.text_strong};")
            p5_layout.addWidget(conf_label)
            conf_info = M3Label(_("student_form.confidential_desc"))
            conf_info.setStyleSheet(f"font-size: {s(13)}px; color: {p.text_soft}; padding-bottom: {sp}px;")
            conf_info.setWordWrap(True)
            p5_layout.addWidget(conf_info)
            from larccommon.widgets import FilePanel

            self._conf_file_panel = FilePanel()
            p5_layout.addWidget(self._conf_file_panel, 1)
        else:
            deny = M3Label(_("student_form.confidential_restricted"))
            deny.setStyleSheet(f"font-size: {s(15)}px; color: {p.text_disabled}; padding: 40px;")
            deny.setAlignment(Qt.AlignCenter)
            deny.setWordWrap(True)
            p5_layout.addWidget(deny)
        self._nav_pages.append(p5)

        # Construire la sidebar + stack
        self._nav_stack = M3StackedWidget()
        for idx, (label, page) in enumerate(zip(nav_items, self._nav_pages)):
            btn = M3Button(label, theme=phi, variant=ButtonVariant.TEXT)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.clicked.connect(lambda checked, i=idx: self._on_nav(i))
            nav_side.addWidget(btn)
            self._nav_btns.append(btn)
            self._nav_stack.addWidget(page)

        self._nav_stack.setCurrentIndex(0)
        nav_side.addStretch()
        nav_row.addLayout(nav_side)
        nav_row.addWidget(self._nav_stack, 1)
        layout.addLayout(nav_row, 1)
        layout.addStretch()

    def _on_nav(self, index: int):
        self._nav_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == index)

    def _get_class_language(self, classroom_id: int) -> int | None:
        conn = db.server_conn
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT l.fk_language_id
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                WHERE c.id = %s
            """,
                (classroom_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            log(f"StudentEditDialog._get_class_language: {e}")
            return None

    def _load_genders(self, lang_id: int | None = None, include_gid: int | None = None):
        self._inp_genre.clear()
        self._inp_genre.addItem(_("student_form.gender_not_specified"), 0)
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            if lang_id:
                cur.execute("SELECT id, label FROM larcauth_gender WHERE fk_language_id = %s ORDER BY id", (lang_id,))
            else:
                cur.execute("SELECT id, label FROM larcauth_gender ORDER BY id")
            loaded = set()
            for gid, label in cur.fetchall():
                self._inp_genre.addItem(label, gid)
                loaded.add(gid)
            # Si le genre existant de l'élève n'est pas dans la langue, l'ajouter
            if include_gid is not None and include_gid not in loaded:
                cur.execute("SELECT label FROM larcauth_gender WHERE id = %s", (include_gid,))
                row = cur.fetchone()
                if row:
                    self._inp_genre.addItem(row[0], include_gid)
        except Exception as e:
            log(f"StudentEditDialog._load_genders: {e}")

    def _load_data(self):
        """Pré-remplit le formulaire avec les données existantes."""
        d = self._data
        sid = d["id"]

        # Photo
        px = QPixmap(get_photo_path(sid))
        if px.isNull():
            px = _make_avatar(d["last_name"], d["first_name"], 120)
        else:
            px = px.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._photo.setPixmap(px)

        # Identité
        self._id_name.setText(f"{d['last_name']} {d['first_name']}")
        self._id_info.setText(_("student_form.id_class_info").format(id=sid, cls=d.get("classroom", "—")))

        # Champs
        self._inp_nom.setText(d.get("last_name", ""))
        self._inp_prenom.setText(d.get("first_name", ""))
        self._inp_email.setText(d.get("email", ""))
        self._inp_emailperso.setText(d.get("emailperso", "") or "")
        self._inp_tel.setText(d.get("tel_smartphone_1", "") or "")
        self._inp_tel2.setText(d.get("tel_maison", "") or "")
        raw_joined = d.get("date_joined", "")
        if raw_joined:
            self._inp_date_joined.setDate(QDate.fromString(str(raw_joined), "yyyy-MM-dd"))
        else:
            self._inp_date_joined.setDate(QDate())
        raw_date = d.get("date_entree", "")
        if raw_date:
            self._inp_date.setDate(QDate.fromString(str(raw_date), "yyyy-MM-dd"))
        else:
            self._inp_date.setDate(QDate())
        raw_birth = d.get("date_of_birth", "")
        if raw_birth:
            self._inp_birthdate.setDate(QDate.fromString(str(raw_birth), "yyyy-MM-dd"))
        else:
            self._inp_birthdate.setDate(QDate())
        # Recharger les genres selon la langue de la classe
        classroom_id = d.get("s_classroom_id")
        current_gid = d.get("fk_gender_id")
        if classroom_id:
            lang_id = self._get_class_language(classroom_id)
            self._load_genders(lang_id, include_gid=current_gid)
        gid = current_gid or 0
        idx = self._inp_genre.findData(gid)
        if idx >= 0:
            self._inp_genre.setCurrentIndex(idx)
        self._inp_addr1.setPlainText(d.get("address_line1", "") or "")
        self._inp_addr2.setText(d.get("address_line2", "") or "")
        self._inp_cp.setText(d.get("postal_code", "") or "")
        self._inp_ville.setText(d.get("city", "") or "")
        self._inp_pays.setText(d.get("country", "") or _("student_form.default_country"))
        raw_notes_json = d.get("notes_json") or None
        if raw_notes_json:
            if isinstance(raw_notes_json, str):
                import json

                try:
                    raw_notes_json = json.loads(raw_notes_json)
                except json.JSONDecodeError:
                    raw_notes_json = None
        if raw_notes_json and isinstance(raw_notes_json, dict):
            self._dossier_panel.set_data(raw_notes_json)
        else:
            # Fallback : importer les anciennes notes TEXT dans la section Autre
            old_notes = d.get("notes", "") or ""
            if old_notes:
                import json

                old_data = {
                    "autre": {
                        "intro": "<p>Notes importées de l'ancien système.</p>",
                        "entries": [
                            {
                                "no": 1,
                                "date": "",
                                "titre": "Anciennes notes",
                                "doc": old_notes[:500] + ("…" if len(old_notes) > 500 else ""),
                            }
                        ],
                    }
                }
                self._dossier_panel.set_data(old_data)
            else:
                self._dossier_panel.clear()

        # Initialiser les dossiers de fichiers
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "students", str(self._sid))
        dossiers_dir = os.path.join(base_dir, "dossiers")
        os.makedirs(dossiers_dir, exist_ok=True)
        conf_dir = os.path.join(base_dir, "confidentiel")
        os.makedirs(conf_dir, exist_ok=True)
        self._dossier_panel.set_directory(dossiers_dir)
        if hasattr(self, "_conf_file_panel"):
            self._conf_file_panel.set_directory(conf_dir)

        self._load_parents()
        self._load_events()

    def _load_parents(self):
        self._parent_ids = []
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT sp.parent_id,
                       aec.last_name || ' ' || aec.first_name AS name,
                       COALESCE(sp.nature, par.nature, 'parent'),
                       aec.email,
                       COALESCE(aec.tel_smartphone_1, aec.tel_maison, '')
                FROM student_parent sp
                JOIN larcauth_aecuser aec ON aec.id = sp.parent_id
                LEFT JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                WHERE sp.student_id = %s
                ORDER BY aec.last_name
            """,
                (self._sid,),
            )
            rows = list(cur.fetchall())
            self._parent_ids = []
            self._parents_table.setRowCount(len(rows))
            for i, (pid, name, nat, em, tel) in enumerate(rows):
                self._parent_ids.append(pid)
                self._parents_table.setItem(i, 0, QTableWidgetItem(name))
                self._parents_table.setItem(i, 1, QTableWidgetItem(nat or ""))
                self._parents_table.setItem(i, 2, QTableWidgetItem(em or ""))
                self._parents_table.setItem(i, 3, QTableWidgetItem(tel or ""))
            self._parents_table.resizeColumnsToContents()
            self._parents_table.selectRow(0)
        except Exception as e:
            log(f"StudentEditDialog._load_parents: {e}")

    def _load_events(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT se.event_at, se.event_type, se.note,
                       aec.last_name || ' ' || aec.first_name AS author,
                       CASE WHEN se.validated_by IS NOT NULL THEN '✓' ELSE '—' END
                FROM student_event se
                JOIN larcauth_aecuser aec ON aec.id = se.created_by
                WHERE se.student_id = %s
                ORDER BY se.event_at DESC LIMIT 100
            """,
                (self._sid,),
            )
            rows = cur.fetchall()
            self._evt_table.setRowCount(len(rows))
            for i, (evt_at, etype, note, author, validated) in enumerate(rows):
                self._evt_table.setItem(i, 0, QTableWidgetItem(str(evt_at)[:16]))
                it = QTableWidgetItem(_event_label(etype))
                it.setForeground(QColor(_event_color(etype)))
                self._evt_table.setItem(i, 1, it)
                self._evt_table.setItem(i, 2, QTableWidgetItem(note or ""))
                self._evt_table.setItem(i, 3, QTableWidgetItem(author))
                self._evt_table.setItem(i, 4, QTableWidgetItem(validated))
            self._evt_table.resizeColumnsToContents()
        except Exception as e:
            log(f"StudentEditDialog._load_events: {e}")

    def _save(self):
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("student_form.error.no_connection"))
            return
        try:
            cur = conn.cursor()
            from datetime import datetime

            now = datetime.now().isoformat()

            aec = {
                "last_name": self._inp_nom.text().strip(),
                "first_name": self._inp_prenom.text().strip(),
                "email": self._inp_email.text().strip() or "",
                "emailperso": self._inp_emailperso.text().strip() or None,
                "tel_smartphone_1": self._inp_tel.text().strip() or None,
                "tel_maison": self._inp_tel2.text().strip() or None,
                "date_joined": (
                    self._inp_date_joined.date().toString("yyyy-MM-dd")
                    if self._inp_date_joined.date().isValid() and not self._inp_date_joined.date().isNull()
                    else None
                ),
                "date_entree": (
                    self._inp_date.date().toString("yyyy-MM-dd") if self._inp_date.date().isValid() and not self._inp_date.date().isNull() else None
                ),
                "date_of_birth": (
                    self._inp_birthdate.date().toString("yyyy-MM-dd")
                    if self._inp_birthdate.date().isValid() and not self._inp_birthdate.date().isNull()
                    else None
                ),
                "fk_gender_id": self._inp_genre.currentData() or None,
                "updated": now,
            }
            cur.execute(
                "UPDATE larcauth_aecuser SET " + ", ".join(f"{k}=%s" for k in aec) + " WHERE id=%s",
                list(aec.values()) + [self._sid],
            )
            if cur.rowcount == 0:
                raise ValueError(f"Aucun enregistrement trouve pour l'ID {self._sid}")

            addr = {
                "address_line1": self._inp_addr1.toPlainText().strip() or None,
                "address_line2": self._inp_addr2.text().strip() or None,
                "postal_code": self._inp_cp.text().strip() or None,
                "city": self._inp_ville.text().strip() or None,
                "country": self._inp_pays.text().strip() or None,
            }
            fid = self._data.get("fk_foyer_id") or self._sid
            cols = list(addr.keys())
            vals = list(addr.values())
            cur.execute(
                "INSERT INTO foyer (id, "
                + ", ".join(cols)
                + ") VALUES (%s, "
                + ", ".join("%s" for _ in cols)
                + ") ON CONFLICT (id) DO UPDATE SET "
                + ", ".join(f"{k}=EXCLUDED.{k}" for k in cols),
                [fid] + vals,
            )
            notes_json = json.dumps(self._dossier_panel.get_data())
            cur.execute(
                "UPDATE larcauth_student SET notes_json = %s WHERE aecuser_ptr_id = %s",
                (notes_json, self._sid),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Aucun etudiant trouve pour l'ID {self._sid}")

            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            changes = []
            for k in aec:
                old_v = str(self._data.get(k, ""))
                new_v = str(aec[k] or "")
                if old_v != new_v:
                    changes.append(k)
            if changes:
                audit.update_student(self._sid, f"Modifiés : {', '.join(changes)}")
            elif any(v is not None for v in addr.values()):
                audit.update_student(self._sid, "Adresse modifiée")

            conn.commit()
            log(f"StudentEditDialog: saved #{self._sid}")

            QMessageBox.information(self, _("common.label.success"), _("student_form.success_updated"))
            self.accept()
        except Exception as e:
            conn.rollback()
            log(f"StudentEditDialog._save: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    # ── Notes (formatage HTML) — supprimé, remplacé par NotesPanel JSON

    # ── Fichiers élèves ──

    def _student_dir(self) -> str:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "students")
        d = os.path.join(base, str(self._sid))
        os.makedirs(d, exist_ok=True)
        return d

    def _copy_parent_address(self):
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.copy_address_title"), _("student_form.copy_address_none"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT address_line1, address_line2, postal_code, city, country
                FROM foyer WHERE id = %s
            """,
                (pid,),
            )
            row = cur.fetchone()
            if row and any(row):
                addr1, addr2, cp, ville, pays = row
                self._inp_addr1.setPlainText(addr1 or "")
                self._inp_addr2.setText(addr2 or "")
                self._inp_cp.setText(cp or "")
                self._inp_ville.setText(ville or "")
                if pays:
                    self._inp_pays.setText(pays)
                log(f"Copied address from parent #{pid} to student #{self._sid}")
            else:
                QMessageBox.information(self, _("student_form.copy_address_title"), _("student_form.copy_address_no_address"))
        except Exception as e:
            log(f"_copy_parent_address: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _add_parent_link(self):
        dlg = M3Dialog(self)
        dlg.setWindowTitle(_("student_form.add_parent"))
        dlg.setMinimumSize(377, 377)
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        fs = 10
        dlg.setStyleSheet(f"background: {p.surface}; color: {p.text_strong};")
        layout = QVBoxLayout(dlg)
        search_inp = M3TextField()
        search_inp.setPlaceholderText(_("student_form.search_parent_placeholder"))
        search_inp.setStyleSheet(
            f"padding: 6px; border: 1px solid {p.border}; border-radius: {d.radius}px; font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};"
        )
        layout.addWidget(search_inp)
        result_list = QListWidget()
        result_list.setStyleSheet(
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};"
        )
        layout.addWidget(result_list, 1)
        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        def on_search(text):
            if len(text.strip()) < 3:
                result_list.clear()
                return
            conn = db.server_conn
            if not conn:
                return
            try:
                cur = conn.cursor()
                q = "%" + text.strip() + "%"
                cur.execute(
                    """
                    SELECT id, last_name, first_name, email
                    FROM larcauth_aecuser
                    WHERE type_parentutor = TRUE
                      AND (LOWER(last_name) LIKE LOWER(%s)
                           OR LOWER(first_name) LIKE LOWER(%s)
                           OR LOWER(email) LIKE LOWER(%s))
                      AND id NOT IN (
                           SELECT parent_id FROM student_parent WHERE student_id = %s)
                    ORDER BY last_name, first_name
                    LIMIT 50
                """,
                    (q, q, q, self._sid),
                )
                result_list.clear()
                self._search_parents_data = []
                for pid, ln, fn, em in cur.fetchall():
                    disp = f"{ln or ''} {fn or ''} ({em or 'pas d e-mail'})"
                    result_list.addItem(disp)
                    self._search_parents_data.append(pid)
            except Exception as e:
                log(f"_add_parent_link search: {e}")

        search_inp.textChanged.connect(on_search)
        self._search_parents_data = []

        if dlg.exec() == QDialog.Accepted:
            cur_sel = result_list.currentRow()
            if cur_sel < 0 or cur_sel >= len(self._search_parents_data):
                return
            pid = self._search_parents_data[cur_sel]
            conn = db.server_conn
            if not conn:
                return
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO student_parent (student_id, parent_id) VALUES (%s, %s)
                    ON CONFLICT DO NOTHING""",
                    (self._sid, pid),
                )
                log(f"Linked parent #{pid} to student #{self._sid}")
            except Exception as e:
                log(f"_add_parent_link insert: {e}")
                QMessageBox.critical(self, _("common.dialog.error_title"), str(e))
            self._load_parents()

    def _edit_parent_nature(self):
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.nature_dialog_title"), _("parent.error.no_parent_selected"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        nature, ok = QInputDialog.getText(self, _("student_form.nature_prompt_title"), _("student_form.nature_prompt_msg"))
        if not ok:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE student_parent SET nature = %s WHERE student_id = %s AND parent_id = %s",
                (nature.strip(), self._sid, pid),
            )
            log(f"Updated nature for parent #{pid} of student #{self._sid}: {nature.strip()}")
            self._load_parents()
        except Exception as e:
            log(f"_edit_parent_nature: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _remove_parent_link(self):
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.remove_parent"), _("parent.error.no_parent_selected"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        confirm = QMessageBox.question(
            self,
            _("student_form.remove_confirm_title"),
            _("student_form.remove_confirm_msg"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM student_parent WHERE student_id = %s AND parent_id = %s", (self._sid, pid))
            log(f"Removed parent #{pid} from student #{self._sid}")
            self._load_parents()
        except Exception as e:
            log(f"_remove_parent_link: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _build_full_html(self) -> str:
        d = self._data
        parts = ["<html><head><meta charset='utf-8'></head><body>"]

        def esc(s):
            import html

            return html.escape(str(s or ""))

        # En-tête
        parts.append(f"<h1>{esc(d.get('last_name', ''))} {esc(d.get('first_name', ''))}</h1>")
        parts.append("<table cellpadding='3' cellspacing='0' style='margin-bottom:12px;'>")
        parts.append(
            f"<tr><td><b>ID</b></td><td>{esc(d.get('id', ''))}</td><td style='padding-left:24px;'><b>Classe</b></td><td>{esc(d.get('classroom', ''))}</td></tr>"
        )
        parts.append(
            f"<tr><td><b>Date naissance</b></td><td>{esc(d.get('date_of_birth', ''))}</td>"
            f"<td style='padding-left:24px;'><b>Date entrée</b></td><td>{esc(d.get('date_entree', ''))}</td></tr>"
        )

        # Genre — requêter le label depuis la DB
        gid = d.get("fk_gender_id")
        gender_label = ""
        if gid:
            try:
                cur = db.server_conn.cursor()
                cur.execute("SELECT label FROM larcauth_gender WHERE id = %s", (gid,))
                row = cur.fetchone()
                if row:
                    gender_label = row[0]
            except Exception:
                pass
        parts.append(
            f"<tr><td><b>Genre</b></td><td>{esc(gender_label)}</td>"
            f"<td style='padding-left:24px;'><b>ID Foyer</b></td><td>{esc(d.get('fk_foyer_id', ''))}</td></tr>"
        )
        parts.append("</table>")

        # Contact
        parts.append("<h2>Contact</h2>")
        parts.append("<table cellpadding='3' cellspacing='0' style='margin-bottom:12px;'>")
        parts.append(f"<tr><td><b>Email</b></td><td>{esc(d.get('email', ''))}</td></tr>")
        parts.append(f"<tr><td><b>Email personnel</b></td><td>{esc(d.get('emailperso', ''))}</td></tr>")
        parts.append(f"<tr><td><b>Téléphone portable</b></td><td>{esc(d.get('tel_smartphone_1', ''))}</td></tr>")
        parts.append(f"<tr><td><b>Téléphone fixe</b></td><td>{esc(d.get('tel_maison', ''))}</td></tr>")
        parts.append("</table>")

        # Adresse
        parts.append("<h2>Adresse</h2>")
        parts.append(
            f"<p>{esc(d.get('address_line1', ''))}<br>"
            f"{esc(d.get('address_line2', ''))}<br>"
            f"{esc(d.get('postal_code', ''))} {esc(d.get('city', ''))}<br>"
            f"{esc(d.get('country', ''))}</p>"
        )

        # Parents
        parts.append("<h2>Parents / Tuteurs</h2>")
        if self._parents_table.rowCount() > 0:
            parts.append("<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:12px;'>")
            parts.append("<tr><th>Nom</th><th>Nature</th><th>Email</th><th>Téléphone</th></tr>")
            for i in range(self._parents_table.rowCount()):

                def _cell(col):
                    item = self._parents_table.item(i, col)
                    return esc(item.text()) if item and item.text() else ""

                parts.append(f"<tr><td>{_cell(0)}</td><td>{_cell(1)}</td><td>{_cell(2)}</td><td>{_cell(3)}</td></tr>")
            parts.append("</table>")
        else:
            parts.append("<p><i>Aucun parent/tuteur enregistré.</i></p>")

        # Notes structurées
        parts.append("<h2>Notes</h2>")
        section_labels = {
            "confidentielle": _("notes.section.confidential"),
            "medicale": _("notes.section.medical"),
            "pedagogique": _("notes.section.pedagogic"),
            "administrative": _("notes.section.administrative"),
            "communication": _("notes.section.communication"),
            "orientation": _("notes.section.orientation"),
            "autre": _("notes.section.other"),
        }
        notes_data = self._notes_panel.get_json()
        has_notes = False
        for key, label in section_labels.items():
            sec = notes_data.get(key, {})
            raw_intro = (sec.get("intro") or "").strip()
            entries = sec.get("entries", [])
            if not raw_intro and not any(e.get("titre") or e.get("doc") for e in entries):
                continue
            has_notes = True
            parts.append(f"<h3>{esc(label)}</h3>")
            if raw_intro:
                parts.append(f"<div>{raw_intro}</div>")
            if entries:
                parts.append("<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:8px;'>")
                parts.append("<tr><th>N°</th><th>Date</th><th>Titre</th><th>Document / Note</th></tr>")
                for e in entries:
                    if e.get("titre") or e.get("doc") or e.get("date"):
                        parts.append(
                            f"<tr><td>{esc(e.get('no', ''))}</td><td>{esc(e.get('date', ''))}</td>"
                            f"<td>{esc(e.get('titre', ''))}</td><td>{esc(e.get('doc', ''))}</td></tr>"
                        )
                parts.append("</table>")
        if not has_notes:
            parts.append("<p><i>Aucune note.</i></p>")

        # Événements
        parts.append("<h2>Événements</h2>")
        if self._evt_table.rowCount() > 0:
            parts.append("<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:12px;'>")
            parts.append("<tr><th>Date/Heure</th><th>Type</th><th>Note</th><th>Par</th><th>Validé</th></tr>")
            for i in range(self._evt_table.rowCount()):

                def _ecell(col):
                    item = self._evt_table.item(i, col)
                    return esc(item.text()) if item and item.text() else ""

                parts.append(f"<tr><td>{_ecell(0)}</td><td>{_ecell(1)}</td><td>{_ecell(2)}</td><td>{_ecell(3)}</td><td>{_ecell(4)}</td></tr>")
            parts.append("</table>")
        else:
            parts.append("<p><i>Aucun événement.</i></p>")

        parts.append("</body></html>")
        return "\n".join(parts)

    def _export_pdf(self):
        html = self._build_full_html()
        d = self._data
        default_name = _("student_form.export_pdf_file").format(last=d.get("last_name", ""), first=d.get("first_name", ""))
        path, _ = QFileDialog.getSaveFileName(self, _("student_form.pdf"), default_name, "Fichier PDF (*.pdf)")
        if not path:
            return
        try:
            doc = QTextDocument()
            doc.setHtml(html)
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPrinter.A4)
            doc.print_(printer)
            log(f"Export PDF #{d['id']}: {path}")
            QMessageBox.information(self, _("student_form.pdf"), _("student_form.export_pdf_success").format(path=path))
        except Exception as e:
            log(f"Export PDF error: {e}")
            QMessageBox.critical(self, _("student_form.export_pdf_error"), str(e))

    def _export_word(self):
        html = self._build_full_html()
        d = self._data
        default_name = _("student_form.export_word_file").format(last=d.get("last_name", ""), first=d.get("first_name", ""))
        path, _ = QFileDialog.getSaveFileName(self, _("student_form.word"), default_name, "Document HTML (*.html *.htm)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            log(f"Export Word #{d['id']}: {path}")
            QMessageBox.information(self, _("student_form.word"), _("student_form.export_word_success").format(path=path))
        except Exception as e:
            log(f"Export Word error: {e}")
            QMessageBox.critical(self, _("student_form.export_word_error"), str(e))


# ──────────────────────────────────────────────
#   StudentCreateDialog — Création d'un élève
# ──────────────────────────────────────────────


class StudentCreateDialog(QDialog):
    """
    Fenêtre de création d'élève — grand formulaire, polices larges.

    Le slot libre est détecté automatiquement.
    ID = classroom_id × 100 + slot (gabarit).
    """

    def __init__(self, parent=None, preselected_class: int | None = None):
        super().__init__(parent)
        self.setWindowTitle(_("student_form.new_student_title"))
        self.setMinimumSize(987, 610)
        self._result_data: dict | None = None
        self._class_id: int | None = None
        self._next_free: int | None = None
        self._sid: int | None = None
        self._parent_ids: list[int] = []
        self._search_parents_data: list[int] = []
        self._classes: list[tuple] = []
        self._class_btns: dict[int, M3Button] = {}
        self._preselected_class = preselected_class
        self._init_ui()
        self._load_classes()

    def _init_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        fs = 10
        layout = QVBoxLayout(self)
        layout.setSpacing(d.spacing + 2)
        layout.setContentsMargins(d.margin, d.margin, d.margin, d.margin)

        self._class_title = M3Label(_("student_form.new_student_label"))
        self._class_title.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(self._class_title)

        if self._preselected_class:
            self._class_info = M3Label()
            self._class_info.setStyleSheet(f"font-size: {s(13)}px; color: {p.text_soft}; padding-bottom: 8px;")
            layout.addWidget(self._class_info)
            self._class_grid = None
        else:
            cl_label = M3Label(_("student_form.class_selector"))
            cl_label.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft}; font-weight: bold;")
            layout.addWidget(cl_label)
            self._class_grid = QWidget()
            self._class_grid_layout = QVBoxLayout(self._class_grid)
            self._class_grid_layout.setContentsMargins(0, 0, 0, 0)
            self._class_grid_layout.setSpacing(3)
            layout.addWidget(self._class_grid)

        # Photo + identité + boutons (toujours visibles)
        photo_row = QHBoxLayout()
        self._photo = QLabel()
        self._photo.setFixedSize(120, 120)
        self._photo.setStyleSheet(f"background: {p.primary_container}; border-radius: {d.radius_xl}px;")
        self._photo.setAlignment(Qt.AlignCenter)
        photo_row.addWidget(self._photo)

        id_col = QVBoxLayout()
        self._id_name = M3Label(_("student_form.new_student_name"))
        self._id_name.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        id_col.addWidget(self._id_name)
        self._id_info = M3Label(_("student_form.new_student_info"))
        self._id_info.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft};")
        id_col.addWidget(self._id_info)
        id_col.addStretch()
        photo_row.addLayout(id_col, 1)

        # Boutons d'action verticaux à droite
        btn_col = QVBoxLayout()
        btn_col.setSpacing(d.spacing)

        self._create_btn = M3Button(_("student_form.create_button"))
        self._create_btn.setStyleSheet(
            f"M3Button {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_pad_v}px {d.btn_pad_h}px; font-size: {s(fs)}px; font-weight: bold; }}"
            f"M3Button:hover {{ background: {p.success}; }}"
            f"M3Button:disabled {{ background: {p.border_light}; color: {p.text_disabled}; }}"
        )
        self._create_btn.setEnabled(False)
        self._create_btn.clicked.connect(self._on_create)
        self._create_btn.setMinimumWidth(89)
        btn_col.addWidget(self._create_btn)

        self._cancel_btn = M3Button(_("student_form.cancel_button"))
        self._cancel_btn.setStyleSheet(
            f"M3Button {{ background: transparent; color: {p.text_soft}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; padding: {d.btn_pad_v}px {d.btn_pad_h - 2}px; font-size: {s(fs)}px; }}"
            f"M3Button:hover {{ background: {p.surface_variant}; }}"
        )
        self._cancel_btn.clicked.connect(self.reject)
        self._cancel_btn.setMinimumWidth(89)
        btn_col.addWidget(self._cancel_btn)

        btn_col.addStretch()
        photo_row.addLayout(btn_col)

        layout.addLayout(photo_row)

        field_style = (
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};"
        )
        label_style = f"font-size: {s(fs)}px; color: {p.text_soft}; font-weight: bold; padding: {d.label_pad_v}px {d.label_pad_h}px;"

        def _lbl(t):
            lbl = M3Label(t)
            lbl.setStyleSheet(label_style)
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            return lbl

        # Champs (créés avant les onglets)
        self._inp_nom = M3TextField()
        self._inp_nom.setStyleSheet(field_style)
        self._inp_nom.setPlaceholderText(_("student_form.last_name_placeholder"))
        self._inp_prenom = M3TextField()
        self._inp_prenom.setStyleSheet(field_style)
        self._inp_prenom.setPlaceholderText(_("student_form.first_name_placeholder"))
        self._inp_email = M3TextField()
        self._inp_email.setStyleSheet(field_style)
        self._inp_email.setPlaceholderText(_("student_form.email_placeholder"))
        self._inp_emailperso = M3TextField()
        self._inp_emailperso.setStyleSheet(field_style)
        self._inp_emailperso.setPlaceholderText(_("student_form.email_personal_placeholder"))
        self._inp_tel = M3TextField()
        self._inp_tel.setStyleSheet(field_style)
        self._inp_tel.setPlaceholderText(_("student_form.phone_placeholder"))
        self._inp_tel2 = M3TextField()
        self._inp_tel2.setStyleSheet(field_style)
        self._inp_tel2.setPlaceholderText(_("student_form.phone_fixed_placeholder"))
        self._inp_date_joined = M3DateEdit()
        self._inp_date_joined.setDisplayFormat("yyyy-MM-dd")
        self._inp_date_joined.setCalendarPopup(True)
        self._inp_date_joined.setSpecialValueText(" ")
        self._inp_date_joined.setDate(QDate())
        self._inp_date_joined.setStyleSheet(field_style)
        self._inp_date = M3DateEdit()
        self._inp_date.setDisplayFormat("yyyy-MM-dd")
        self._inp_date.setCalendarPopup(True)
        self._inp_date.setSpecialValueText(" ")
        self._inp_date.setDate(QDate())
        self._inp_date.setStyleSheet(field_style)
        self._inp_genre = M3ComboBox()
        self._inp_genre.setStyleSheet(field_style + " min-width: 180px;")
        self._load_genders()
        self._inp_birthdate = M3DateEdit()
        self._inp_birthdate.setDisplayFormat("yyyy-MM-dd")
        self._inp_birthdate.setCalendarPopup(True)
        self._inp_birthdate.setSpecialValueText(" ")
        self._inp_birthdate.setDate(QDate())
        self._inp_birthdate.setStyleSheet(field_style)
        self._inp_addr1 = M3TextEdit()
        self._inp_addr1.setStyleSheet(field_style)
        self._inp_addr1.setFixedHeight(89)
        self._inp_addr1.setPlaceholderText(_("student_form.street_placeholder"))
        self._inp_addr2 = M3TextField()
        self._inp_addr2.setStyleSheet(field_style)
        self._inp_addr2.setPlaceholderText(_("student_form.address_complement"))
        self._inp_cp = M3TextField()
        self._inp_cp.setStyleSheet(field_style)
        self._inp_cp.setPlaceholderText(_("student_form.zip_placeholder"))
        self._inp_ville = M3TextField()
        self._inp_ville.setStyleSheet(field_style)
        self._inp_ville.setPlaceholderText(_("student_form.city_placeholder"))
        self._inp_pays = M3TextField(_("student_form.default_country"))
        self._inp_pays.setStyleSheet(field_style)

        # Onglets (même structure que EditDialog)
        tabs = M3TabWidget()
        tabs.setDocumentMode(True)

        # --- Tab 1 : Identité ---
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        tab1_layout.setSpacing(d.spacing)
        g1 = QGridLayout()
        g1.setSpacing(d.spacing)
        g1.addWidget(_lbl(_("student_form.last_name_label")), 0, 0)
        g1.addWidget(_lbl(_("student_form.first_name_label")), 0, 1)
        g1.addWidget(self._inp_nom, 1, 0)
        g1.addWidget(self._inp_prenom, 1, 1)
        g1.addWidget(_lbl(_("student_form.arrival_label")), 2, 0, 1, 2)
        g1.addWidget(self._inp_date_joined, 3, 0, 1, 2)
        g1.addWidget(_lbl(_("student_form.entry_date")), 4, 0)
        g1.addWidget(_lbl(_("student_form.gender_label")), 4, 1)
        g1.addWidget(self._inp_date, 5, 0)
        g1.addWidget(self._inp_genre, 5, 1)
        g1.addWidget(_lbl(_("student_form.birth_date")), 6, 0)
        g1.addWidget(self._inp_birthdate, 7, 0)
        tab1_layout.addLayout(g1)
        tab1_layout.addStretch()
        tabs.addTab(tab1, _("student_form.tab_identity"))

        # --- Tab 2 : Contact ---
        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)
        tab2_layout.setSpacing(d.spacing)
        g2 = QGridLayout()
        g2.setSpacing(d.spacing)
        g2.addWidget(_lbl(_("student_form.email_label")), 0, 0)
        g2.addWidget(_lbl(_("student_form.email_personal")), 0, 1)
        g2.addWidget(self._inp_email, 1, 0)
        g2.addWidget(self._inp_emailperso, 1, 1)
        g2.addWidget(_lbl(_("student_form.phone_mobile")), 2, 0)
        g2.addWidget(_lbl(_("student_form.phone_fixed")), 2, 1)
        g2.addWidget(self._inp_tel, 3, 0)
        g2.addWidget(self._inp_tel2, 3, 1)
        tab2_layout.addLayout(g2)
        tab2_layout.addStretch()
        tabs.addTab(tab2, _("student_form.contact_tab"))

        # --- Tab 3 : Adresse & Parents ---
        tab3 = QWidget()
        tab3_layout = QVBoxLayout(tab3)
        tab3_layout.setSpacing(d.spacing)

        addr_scroll = M3ScrollArea()
        addr_scroll.setWidgetResizable(True)
        addr_scroll.setFrameShape(M3Frame.NoFrame)
        addr_inner = QWidget()
        addr_inner_layout = QVBoxLayout(addr_inner)
        addr_inner_layout.setSpacing(d.spacing)
        addr_inner_layout.setContentsMargins(0, 0, 0, 0)

        addr_inner_layout.addWidget(_lbl(_("student_form.address_title")))
        addr_inner_layout.addWidget(self._inp_addr1)
        addr_inner_layout.addWidget(_lbl(_("student_form.address_complement")))
        addr_inner_layout.addWidget(self._inp_addr2)
        g3 = QGridLayout()
        g3.setSpacing(d.spacing)
        g3.addWidget(_lbl(_("student_form.zip_label")), 0, 0)
        g3.addWidget(_lbl(_("student_form.city_label")), 0, 1)
        g3.addWidget(self._inp_cp, 1, 0)
        g3.addWidget(self._inp_ville, 1, 1)
        g3.addWidget(_lbl(_("student_form.country_label")), 2, 0)
        g3.addWidget(self._inp_pays, 3, 0, 1, 2)
        addr_inner_layout.addLayout(g3)

        addr_inner_layout.addSpacing(d.spacing + 3)
        sep = M3Frame()
        sep.setFrameShape(M3Frame.HLine)
        sep.setStyleSheet(f"color: {p.border};")
        addr_inner_layout.addWidget(sep)
        addr_inner_layout.addSpacing(d.spacing)

        parents_title = M3Label(_("student_form.parents_title"))
        parents_title.setStyleSheet(f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong};")
        addr_inner_layout.addWidget(parents_title)
        self._parents_table = M3TableWidget()
        self._parents_table.setColumnCount(4)
        self._parents_table.setHorizontalHeaderLabels(
            [
                _("student_form.parents_table_nom"),
                _("student_form.parents_table_nature"),
                _("student_form.parents_table_email"),
                _("student_form.parents_table_phone"),
            ]
        )
        self._parents_table.horizontalHeader().setStretchLastSection(True)
        self._parents_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._parents_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._parents_table.setMaximumHeight(89)
        addr_inner_layout.addWidget(self._parents_table)

        # Parent management toolbar
        parent_tools = QHBoxLayout()
        parent_tools.setSpacing(d.spacing)

        add_par_btn = M3Button(_("student_form.add_parent"))
        add_par_btn.setStyleSheet(
            f"M3Button {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius}px; padding: 3px 10px; font-size: {s(fs)}px; }}"
            f"M3Button:hover {{ background: {p.success}; }}"
        )
        add_par_btn.clicked.connect(self._add_parent_link)
        parent_tools.addWidget(add_par_btn)

        edit_par_btn = M3Button(_("student_form.edit_nature"))
        edit_par_btn.setStyleSheet(
            f"M3Button {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; padding: 3px 10px; font-size: {s(fs)}px; }}"
            f"M3Button:hover {{ background: {p.active}; }}"
        )
        edit_par_btn.clicked.connect(self._edit_parent_nature)
        parent_tools.addWidget(edit_par_btn)

        remove_par_btn = M3Button(_("student_form.remove_parent"))
        remove_par_btn.setStyleSheet(
            f"M3Button {{ background: transparent; color: {p.error}; "
            f"border: 1px solid {p.error}; border-radius: {d.radius}px; "
            f"padding: 3px 10px; font-size: {s(fs)}px; }}"
            f"M3Button:hover {{ background: {p.error_container}; }}"
        )
        remove_par_btn.clicked.connect(self._remove_parent_link)
        parent_tools.addWidget(remove_par_btn)

        parent_tools.addStretch()

        copy_btn = M3Button(_("student_form.copy_address"))
        copy_btn.setStyleSheet(
            f"M3Button {{ background: {p.primary_container}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; padding: 3px 10px; font-size: {s(fs)}px; }}"
            f"M3Button:hover {{ background: {p.primary}; }}"
        )
        copy_btn.clicked.connect(self._copy_parent_address)
        parent_tools.addWidget(copy_btn)

        addr_inner_layout.addLayout(parent_tools)

        addr_inner_layout.addStretch()
        addr_scroll.setWidget(addr_inner)
        tab3_layout.addWidget(addr_scroll, 1)
        tabs.addTab(tab3, _("student_form.tab_address"))

        # --- Tab 4 : Notes structurées (JSON) ---
        tab4 = QWidget()
        tab4_layout = QVBoxLayout(tab4)
        tab4_layout.setContentsMargins(0, 0, 0, 0)
        self._notes_panel = NotesPanel()
        tab4_layout.addWidget(self._notes_panel, 1)
        tabs.addTab(tab4, _("student_form.notes_tab"))
        self._inp_nom.textChanged.connect(
            lambda: self._notes_panel.set_student_name(f"{self._inp_nom.text()} {self._inp_prenom.text()}".strip() or _("student_form.new_student_name"))
        )
        self._inp_prenom.textChanged.connect(
            lambda: self._notes_panel.set_student_name(f"{self._inp_nom.text()} {self._inp_prenom.text()}".strip() or _("student_form.new_student_name"))
        )

        # --- Tab 5 : Fichiers ---
        tab5 = QWidget()
        tab5_layout = QVBoxLayout(tab5)
        tab5_layout.setSpacing(d.spacing)
        ph5 = M3Label(_("student_form.files_placeholder"))
        ph5.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft}; font-style: italic;")
        ph5.setAlignment(Qt.AlignCenter)
        tab5_layout.addWidget(ph5)
        tab5_layout.addStretch()
        tabs.addTab(tab5, _("student_form.files_tab"))

        # --- Tab 6 : Événements (placeholder) ---
        tab6 = QWidget()
        tab6_layout = QVBoxLayout(tab6)
        tab6_layout.setSpacing(d.spacing)
        ph6 = M3Label(_("student_form.events_placeholder"))
        ph6.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft}; font-style: italic;")
        ph6.setAlignment(Qt.AlignCenter)
        tab6_layout.addWidget(ph6)
        tab6_layout.addStretch()
        tabs.addTab(tab6, _("student_form.events_tab"))

        layout.addWidget(tabs, 1)

        # Infos slot
        self._slot_info = M3Label(_("student_form.select_class"))
        self._slot_info.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; padding: {d.radius}px; font-style: italic;")
        layout.addWidget(self._slot_info)

    def _load_classes(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            if self._preselected_class:
                # Mode classe connue : pas de grille, juste le label
                cur.execute(
                    """
                    SELECT c.label
                    FROM larcauth_classroom c
                    WHERE c.id = %s
                """,
                    (self._preselected_class,),
                )
                row = cur.fetchone()
                if row:
                    self._class_info.setText(_("student_form.class_slot").format(label=row[0]))
                self._on_class_changed(self._preselected_class)
            else:
                # Mode libre : grille de boutons
                cur.execute("""
                    SELECT c.id, c.label, l.fk_program_id, pr.sigle
                    FROM larcauth_classroom c
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program pr ON pr.id = l.fk_program_id
                    WHERE pr.sigle IN ('PEI', 'MYP', 'DPEn', 'DPFr')
                      AND c.enabled = TRUE
                    ORDER BY pr.sigle, l.label, c.label
                """)
                self._classes = list(cur.fetchall())
                self._build_class_buttons()
        except Exception as e:
            log(f"StudentCreateDialog._load_classes: {e}")

    def _build_class_buttons(self):
        if not hasattr(self, "_class_grid_layout") or not self._class_grid:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design

        prog_style = {
            "PEI": (p.primary, p.primary_container, p.on_primary),
            "MYP": (p.secondary, p.secondary_container, p.on_secondary),
            "DPFr": (p.error, p.error_container, p.on_error),
            "DPEn": (p.tertiary, p.tertiary_container, p.on_tertiary),
        }

        groups = {k: [] for k in ["PEI", "MYP", "DPEn", "DPFr"]}
        for cid, label, pid, sigle in self._classes:
            if sigle in groups:
                groups[sigle].append((cid, label))

        sections = [
            (_("sec_main.college"), [("PEI", "PEI"), ("MYP", "MYP")]),
            (_("sec_main.lycee"), [("DP", "DPFr"), ("DPEn", "DPEn")]),
        ]

        # Vider le layout
        self._clear_class_grid()
        self._class_btns.clear()

        for sec_name, columns in sections:
            sec_hdr = M3Label(sec_name)
            sec_hdr.setStyleSheet(
                f"font-weight: bold; font-size: {s(11)}px; color: {p.text_strong}; border-bottom: 2px solid {p.outline_variant}; padding: 2px 0;"
            )
            self._class_grid_layout.addWidget(sec_hdr)

            grd = QGridLayout()
            grd.setSpacing(3)

            for col_idx, (hdr_text, prog_key) in enumerate(columns):
                if prog_key not in groups:
                    continue
                fg, bg, on_fg = prog_style[prog_key]
                items = groups[prog_key]

                col_hdr = M3Label(hdr_text)
                col_hdr.setStyleSheet(f"background: {fg}; color: {on_fg}; border-radius: {d.radius}px; font-weight: bold; font-size: {s(10)}px; padding: 3px;")
                col_hdr.setAlignment(Qt.AlignCenter)
                col_hdr.setFixedHeight(21)
                grd.addWidget(col_hdr, 0, col_idx)

                for i, (cid, label) in enumerate(items):
                    btn = M3Button(label)
                    btn.setFixedHeight(34)
                    btn.setStyleSheet(
                        f"M3Button {{ background: {bg}; color: {fg}; border: 2px solid transparent; "
                        f"border-radius: {d.radius}px; font-size: {s(10)}px; padding: 2px; }}"
                        f"M3Button:hover {{ background: {fg}; color: {bg}; }}"
                    )
                    btn.clicked.connect(lambda checked, c=cid: self._on_class_changed(c))
                    self._class_btns[cid] = btn
                    grd.addWidget(btn, i + 1, col_idx)

            self._class_grid_layout.addLayout(grd)
            self._class_grid_layout.addSpacing(3)

        self._class_grid_layout.addStretch()

    def _clear_class_grid(self):
        if not self._class_grid:
            return
        while self._class_grid_layout.count():
            item = self._class_grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _on_class_changed(self, class_id: int):
        if not class_id:
            return
        self._class_id = class_id

        # Mettre à jour la sélection visuelle (si grille de boutons)
        if self._class_btns:
            for cid, btn in self._class_btns.items():
                p = theme_manager.palette
                _, _, _, sigle = next((c for c in self._classes if c[0] == cid), (None, None, None, None))
                prog_map = {
                    "PEI": (p.primary, p.primary_container, p.on_primary),
                    "MYP": (p.secondary, p.secondary_container, p.on_secondary),
                    "DPFr": (p.error, p.error_container, p.on_error),
                    "DPEn": (p.tertiary, p.tertiary_container, p.on_tertiary),
                }
                fg, bg, on_fg = prog_map.get(sigle, (p.text_strong, p.surface_variant, p.text_strong))
                if cid == class_id:
                    btn.setStyleSheet(
                        f"M3Button {{ background: {fg}; color: {bg}; border: 2px solid {fg}; "
                        f"border-radius: {theme_manager.design.radius}px; font-size: {theme_manager.font_size(10)}px; padding: 2px; }}"
                        f"M3Button:hover {{ background: {fg}; color: {bg}; }}"
                    )
                else:
                    btn.setStyleSheet(
                        f"M3Button {{ background: {bg}; color: {fg}; border: 2px solid transparent; "
                        f"border-radius: {theme_manager.design.radius}px; font-size: {theme_manager.font_size(10)}px; padding: 2px; }}"
                        f"M3Button:hover {{ background: {fg}; color: {bg}; }}"
                    )

        # Filtrer les genres selon la langue de la classe
        lang_id = self._get_class_language(class_id)
        self._load_genders(lang_id)

        conn = db.server_conn
        if not conn:
            return

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.aecuser_ptr_id, aec.last_name, s.enabled
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                WHERE s.s_classroom_id = %s
                ORDER BY s.aecuser_ptr_id
            """,
                (self._class_id,),
            )
            all_rows = list(cur.fetchall())

            # Prochain slot libre (01→40) : enabled=FALSE et nom placeholder
            free = None
            for rid, ln, en in all_rows:
                slot = rid % 100
                if 1 <= slot <= 40 and not en and ("Name of" in (ln or "")):
                    free = slot
                    break

            self._next_free = free
            if free:
                self._sid = self._class_id * 100 + free
                self._student_dir()
            else:
                self._sid = None

            p = theme_manager.palette
            s = theme_manager.font_size
            d = theme_manager.design
            if free:
                self._slot_info.setText(_("student_form.free_slot").format(n=free, id=self._class_id * 100 + free))
                self._slot_info.setStyleSheet(f"font-size: {s(13)}px; color: {p.success}; padding: {d.radius}px; font-weight: bold;")
                self._create_btn.setEnabled(True)
            else:
                self._slot_info.setText(_("student_form.no_slot"))
                self._slot_info.setStyleSheet(f"font-size: {s(13)}px; color: {p.error}; padding: {d.radius}px;")
                self._create_btn.setEnabled(False)
        except Exception as e:
            log(f"StudentCreateDialog._on_class_changed: {e}")

    def _get_class_language(self, classroom_id: int) -> int | None:
        conn = db.server_conn
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT l.fk_language_id
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                WHERE c.id = %s
            """,
                (classroom_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            log(f"StudentCreateDialog._get_class_language: {e}")
            return None

    def _load_genders(self, lang_id: int | None = None):
        self._inp_genre.clear()
        self._inp_genre.addItem(_("student_form.gender_not_specified"), 0)
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            if lang_id:
                cur.execute("SELECT id, label FROM larcauth_gender WHERE fk_language_id = %s ORDER BY id", (lang_id,))
            else:
                cur.execute("SELECT id, label FROM larcauth_gender ORDER BY id")
            for gid, label in cur.fetchall():
                self._inp_genre.addItem(label, gid)
        except Exception as e:
            log(f"StudentCreateDialog._load_genders: {e}")

    def _on_create(self):
        nom = self._inp_nom.text().strip()
        prenom = self._inp_prenom.text().strip()
        if not nom or not prenom:
            QMessageBox.warning(self, _("common.dialog.confirm_title"), _("student_form.validation_required"))
            return
        self._create_student()

    # ── Notes (formatage HTML) — supprimé, remplacé par NotesPanel JSON

    def _student_dir(self) -> str:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "students")
        d = os.path.join(base, str(self._sid))
        os.makedirs(d, exist_ok=True)
        return d

    def _create_student(self):
        slot = self._next_free
        if slot is None:
            return
        student_id = self._class_id * 100 + slot

        nom = self._inp_nom.text().strip()
        prenom = self._inp_prenom.text().strip()
        email = self._inp_email.text().strip()
        emailperso = self._inp_emailperso.text().strip() or None
        tel = self._inp_tel.text().strip() or None
        tel2 = self._inp_tel2.text().strip() or None
        date_str = self._inp_date.date().toString("yyyy-MM-dd") if self._inp_date.date().isValid() and not self._inp_date.date().isNull() else None

        conn = db.server_conn
        if not conn:
            return

        try:
            cur = conn.cursor()
            from datetime import datetime

            now = datetime.now().isoformat()
            birth_str = (
                self._inp_birthdate.date().toString("yyyy-MM-dd") if self._inp_birthdate.date().isValid() and not self._inp_birthdate.date().isNull() else None
            )
            username = email or f"student.{nom.lower()}.{prenom.lower()}"

            joined_str = (
                self._inp_date_joined.date().toString("yyyy-MM-dd")
                if self._inp_date_joined.date().isValid() and not self._inp_date_joined.date().isNull()
                else None
            )
            cur.execute(
                """
                UPDATE larcauth_aecuser SET
                    first_name = %s, last_name = %s, email = %s,
                    username = %s, is_active = TRUE, updated = %s,
                    emailperso = %s, tel_smartphone_1 = %s, tel_maison = %s,
                    date_joined = %s, date_entree = %s, date_of_birth = %s, fk_gender_id = %s
                WHERE id = %s
            """,
                (
                    prenom,
                    nom,
                    email or "",
                    username,
                    now,
                    emailperso,
                    tel,
                    tel2,
                    joined_str,
                    date_str,
                    birth_str,
                    self._inp_genre.currentData() or None,
                    student_id,
                ),
            )

            notes_json = json.dumps(self._notes_panel.get_json())
            cur.execute(
                """
                UPDATE larcauth_student SET enabled = TRUE, updated_s = %s, notes_json = %s
                WHERE aecuser_ptr_id = %s
            """,
                (now, notes_json, student_id),
            )

            cur.execute(
                """
                INSERT INTO foyer (id, enabled, address_line1, address_line2,
                                   postal_code, city, country)
                VALUES (%s, TRUE, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    address_line1 = EXCLUDED.address_line1,
                    address_line2 = EXCLUDED.address_line2,
                    postal_code = EXCLUDED.postal_code,
                    city = EXCLUDED.city,
                    country = EXCLUDED.country
            """,
                (
                    student_id,
                    self._inp_addr1.toPlainText().strip() or None,
                    self._inp_addr2.text().strip() or None,
                    self._inp_cp.text().strip() or None,
                    self._inp_ville.text().strip() or None,
                    self._inp_pays.text().strip() or None,
                ),
            )
            cur.execute("UPDATE larcauth_aecuser SET fk_foyer_id = %s WHERE id = %s", (student_id, student_id))

            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            audit.create_student(student_id, f"Création {prenom} {nom}")

            conn.commit()
            self._result_data = {"id": student_id, "last_name": nom, "first_name": prenom}
            self._sid = student_id
            log(f"StudentCreateDialog: activated #{student_id} (slot {slot:02d})")

            # Charger les parents maintenant que l'élève existe
            self._load_parents()

            QMessageBox.information(self, _("student_form.created"), _("student_form.created_msg").format(f=prenom, l=nom, sid=student_id, slot=slot))

            # Réinitialiser le formulaire pour une autre saisie
            for w in [
                self._inp_nom,
                self._inp_prenom,
                self._inp_email,
                self._inp_emailperso,
                self._inp_tel,
                self._inp_tel2,
                self._inp_date,
                self._inp_addr1,
                self._inp_addr2,
                self._inp_cp,
                self._inp_ville,
            ]:
                w.clear()
            self._notes_panel.clear()
            self._inp_pays.setText("Togo")
            self._sid = None
            self._parent_ids = []
            self._parents_table.setRowCount(0)
            # Re-vérifier le slot libre
            self._on_class_changed(self._class_id)

        except Exception as e:
            conn.rollback()
            log(f"StudentCreateDialog._create_student: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _load_parents(self):
        self._parent_ids = []
        conn = db.server_conn
        if not conn or not self._sid:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT aec.id, aec.last_name || ' ' || aec.first_name, sp.nature, aec.email, aec.tel_smartphone_1
                FROM student_parent sp
                JOIN larcauth_aecuser aec ON aec.id = sp.parent_id
                WHERE sp.student_id = %s
                ORDER BY aec.last_name, aec.first_name
            """,
                (self._sid,),
            )
            rows = cur.fetchall()
            self._parent_ids = []
            self._parents_table.setRowCount(len(rows))
            for i, (pid, name, nat, em, tel) in enumerate(rows):
                self._parent_ids.append(pid)
                self._parents_table.setItem(i, 0, QTableWidgetItem(name))
                if nat:
                    self._parents_table.setItem(i, 1, QTableWidgetItem(nat))
                self._parents_table.setItem(i, 2, QTableWidgetItem(em or ""))
                self._parents_table.setItem(i, 3, QTableWidgetItem(tel or ""))
            self._parents_table.resizeColumnsToContents()
            if rows:
                self._parents_table.selectRow(0)
        except Exception as e:
            log(f"StudentCreateDialog._load_parents: {e}")

    def _copy_parent_address(self):
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.copy_address_title"), _("student_form.copy_address_none"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT address_line1, address_line2, postal_code, city, country
                FROM foyer WHERE id = %s
            """,
                (pid,),
            )
            row = cur.fetchone()
            if row and any(row):
                addr1, addr2, cp, ville, pays = row
                self._inp_addr1.setPlainText(addr1 or "")
                self._inp_addr2.setText(addr2 or "")
                self._inp_cp.setText(cp or "")
                self._inp_ville.setText(ville or "")
                if pays:
                    self._inp_pays.setText(pays)
        except Exception as e:
            log(f"StudentCreateDialog._copy_parent_address: {e}")

    def _add_parent_link(self):
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        dlg = M3Dialog(self)
        dlg.setWindowTitle(_("student_form.add_parent"))
        dlg.setMinimumSize(377, 377)
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        dlg.setStyleSheet(f"background: {p.surface}; color: {p.text_strong};")
        layout = QVBoxLayout(dlg)
        search_inp = M3TextField()
        search_inp.setPlaceholderText(_("student_form.search_parent_placeholder"))
        search_inp.setStyleSheet(
            f"padding: 6px; border: 1px solid {p.border}; border-radius: {d.radius}px; font-size: {s(10)}px; background: {p.surface}; color: {p.text_strong};"
        )
        layout.addWidget(search_inp)
        result_list = QListWidget()
        result_list.setStyleSheet(
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; font-size: {s(10)}px; background: {p.surface}; color: {p.text_strong};"
        )
        layout.addWidget(result_list, 1)
        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        def on_search(text):
            if len(text.strip()) < 3:
                result_list.clear()
                return
            conn = db.server_conn
            if not conn:
                return
            try:
                cur = conn.cursor()
                q = "%" + text.strip() + "%"
                cur.execute(
                    """
                    SELECT id, last_name, first_name, email
                    FROM larcauth_aecuser
                    WHERE type_parentutor = TRUE
                      AND (LOWER(last_name) LIKE LOWER(%s) OR LOWER(first_name) LIKE LOWER(%s) OR LOWER(email) LIKE LOWER(%s))
                      AND id NOT IN (SELECT parent_id FROM student_parent WHERE student_id = %s)
                    ORDER BY last_name, first_name LIMIT 50
                """,
                    (q, q, q, self._sid),
                )
                result_list.clear()
                self._search_parents_data = []
                for pid, ln, fn, em in cur.fetchall():
                    result_list.addItem(f"{ln or ''} {fn or ''} ({em or 'pas d e-mail'})")
                    self._search_parents_data.append(pid)
            except Exception as e:
                log(f"_add_parent_link search: {e}")

        search_inp.textChanged.connect(on_search)
        self._search_parents_data = []

        if dlg.exec() == QDialog.Accepted:
            cur_sel = result_list.currentRow()
            if cur_sel < 0 or cur_sel >= len(self._search_parents_data):
                return
            pid = self._search_parents_data[cur_sel]
            conn = db.server_conn
            if not conn:
                return
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO student_parent (student_id, parent_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (self._sid, pid),
                )
            except Exception as e:
                log(f"_add_parent_link insert: {e}")
                QMessageBox.critical(self, _("common.dialog.error_title"), str(e))
            self._load_parents()

    def _edit_parent_nature(self):
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.nature_dialog_title"), _("parent.error.no_parent_selected"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        from PySide6.QtWidgets import QInputDialog

        nature, ok = QInputDialog.getText(self, _("student_form.nature_prompt_title"), _("student_form.nature_prompt_msg"))
        if not ok:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE student_parent SET nature = %s WHERE student_id = %s AND parent_id = %s",
                (nature.strip(), self._sid, pid),
            )
            self._load_parents()
        except Exception as e:
            log(f"_edit_parent_nature: {e}")

    def _remove_parent_link(self):
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.remove_parent"), _("student_form.edit_nature"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        confirm = QMessageBox.question(self, _("student_form.remove_confirm_title"), _("student_form.remove_confirm_msg"), QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM student_parent WHERE student_id = %s AND parent_id = %s", (self._sid, pid))
            self._load_parents()
        except Exception as e:
            log(f"_remove_parent_link: {e}")

    def get_data(self) -> dict | None:
        return self._result_data
