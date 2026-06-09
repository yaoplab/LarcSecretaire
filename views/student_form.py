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

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QGridLayout, QMessageBox,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QDialog, QTextEdit, QPlainTextEdit,
    QListWidget, QSizePolicy, QCheckBox, QTabWidget,
    QColorDialog, QFileDialog, QInputDialog,
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QTextListFormat, QTextCursor,
    QTextCharFormat, QTextBlockFormat,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

import os

from LarcSecretaire.common.database import db
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from LarcSecretaire.common.logger import log

LARCSUPERVISEUR_PHOTOS = os.path.normpath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 '..', 'LarcSuperviseur', 'photos'))

# ──────────────────────────────────────────────
#   Classe utilitaire : cercle avatar initiales
# ──────────────────────────────────────────────

def _make_avatar(last_name: str, first_name: str, size: int = 120) -> QPixmap:
    """Génère un avatar rond avec les initiales."""
    initials = (last_name[:1] + first_name[:1]).upper() or '?'
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
    bg = colors[hash(last_name + first_name) % len(colors)]
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(bg))
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.setPen(QColor('#fff'))
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
        self._results: list[dict] = []            # Résultats de recherche
        self._dirty: bool = False                 # Modifications non sauvegardées

        # UI
        self._init_ui()

    # ──────────── Construction UI ────────────

    def _init_ui(self):
        """Construit l'interface complète."""
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        layout = QVBoxLayout(self)
        layout.setContentsMargins(d.margin, d.margin, d.margin, d.margin)
        layout.setSpacing(d.spacing + 2)

        # Titre + bouton +
        title_row = QHBoxLayout()
        title = QLabel("Fiche élève")
        title.setStyleSheet(f"font-size: {s(14)}px; font-weight: bold; color: {p.text_strong};")
        title_row.addWidget(title)
        title_row.addStretch()

        self._add_student_btn = QPushButton("+")
        self._add_student_btn.setFixedSize(36, 36)
        self._add_student_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius}px; font-size: {s(20)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.success}; }}")
        self._add_student_btn.clicked.connect(self._open_create_dialog)
        title_row.addWidget(self._add_student_btn)
        layout.addLayout(title_row)

        # Barre de recherche
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Rechercher par nom, prénom, email, ID ou classe...")
        self._search_input.setStyleSheet(
            f"padding: {d.label_pad_v}px {d.btn_sm_pad_v}px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; background: {p.surface}; color: {p.text_strong};")
        self._search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self._search_input, 1)

        self._search_btn = QPushButton("🔍 Rechercher")
        self._search_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; font-weight: bold; font-size: {s(10)}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}")
        self._search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)

        # Zone de contenu : résultats (gauche) + détail (droite)
        content = QHBoxLayout()
        content.setSpacing(d.spacing + 2)

        # ── Panneau résultats (gauche) ──
        self._results_panel = QFrame()
        self._results_panel.setObjectName("panel")
        self._results_panel.setStyleSheet(
            f"QFrame#panel {{ background: {p.surface}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; }}")
        rp_layout = QVBoxLayout(self._results_panel)
        rp_layout.setContentsMargins(d.radius, d.radius, d.radius, d.radius)

        self._results_label = QLabel("Résultats (0)")
        self._results_label.setStyleSheet(
            f"font-weight: bold; font-size: {s(10)}px; color: {p.text_soft}; padding: {d.radius}px;")
        rp_layout.addWidget(self._results_label)

        # Tableau des résultats
        self._results_table = QTableWidget()
        self._results_table.setColumnCount(4)
        self._results_table.setHorizontalHeaderLabels(["Nom", "Classe", "Email", "ID"])
        self._results_table.setColumnHidden(3, True)
        self._results_table.horizontalHeader().setStretchLastSection(True)
        self._results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._results_table.setAlternatingRowColors(True)
        self._results_table.itemSelectionChanged.connect(self._on_result_selected)
        rp_layout.addWidget(self._results_table, 1)
        content.addWidget(self._results_panel, 1)

        # ── Panneau détail (droite) — vignette info ──
        self._detail_panel = QFrame()
        self._detail_panel.setObjectName("panel")
        self._detail_panel.setStyleSheet(
            f"QFrame#panel {{ background: {p.surface}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; }}")
        dp_layout = QVBoxLayout(self._detail_panel)
        dp_layout.setContentsMargins(d.margin, d.margin, d.margin, d.margin)
        dp_layout.setSpacing(d.spacing + 2)
        dp_layout.setAlignment(Qt.AlignCenter)

        self._detail_photo = QLabel()
        self._detail_photo.setFixedSize(160, 160)
        self._detail_photo.setStyleSheet(
            f"background: {p.primary_container}; border-radius: {d.radius_xl + 2}px;")
        self._detail_photo.setAlignment(Qt.AlignCenter)
        self._detail_photo.setCursor(Qt.PointingHandCursor)
        self._detail_photo.installEventFilter(self)
        dp_layout.addWidget(self._detail_photo, 0, Qt.AlignCenter)

        self._detail_nom_label = QLabel("—")
        self._detail_nom_label.setStyleSheet(
            f"font-size: {s(18)}px; font-weight: bold; color: {p.text_strong};")
        self._detail_nom_label.setAlignment(Qt.AlignCenter)
        dp_layout.addWidget(self._detail_nom_label, 0, Qt.AlignCenter)

        self._detail_classe_label = QLabel("")
        self._detail_classe_label.setStyleSheet(
            f"font-size: {s(13)}px; color: {p.text_soft};")
        self._detail_classe_label.setAlignment(Qt.AlignCenter)
        dp_layout.addWidget(self._detail_classe_label)

        self._detail_id_label = QLabel("")
        self._detail_id_label.setStyleSheet(
            f"font-size: {s(13)}px; color: {p.text_soft};")
        self._detail_id_label.setAlignment(Qt.AlignCenter)
        dp_layout.addWidget(self._detail_id_label)

        dp_layout.addSpacing(12)

        self._open_btn = QPushButton("Ouvrir la fiche")
        self._open_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius_lg}px; padding: {d.btn_pad_v + 4}px {d.btn_pad_h + 4}px; font-size: {s(14)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.active}; }}")
        self._open_btn.clicked.connect(self._open_edit_dialog)
        self._open_btn.setMinimumWidth(180)
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
            QMessageBox.information(self, "Recherche",
                "Tapez un nom, prénom, email ou classe dans la barre de recherche.")
            return
        self.search(query)

    def search(self, query: str):
        """
        Recherche des élèves par nom, prénom, email ou classe.

        Les résultats sont affichés dans le panneau de gauche.
        """
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, "Erreur", "Non connecté au serveur.")
            return

        from psycopg2 import errors as pg_errors
        try:
            cur = conn.cursor()
            like = f"%{query}%"
            try:
                cur.execute("""
                    SELECT
                        s.aecuser_ptr_id AS id,
                        aec.last_name, aec.first_name,
                        aec.email, aec.emailperso,
                        aec.tel_smartphone_1, aec.tel_maison,
                        c.label AS classroom,
                        aec.date_entree, aec.fk_foyer_id,
                        aec.fk_gender_id, s.s_classroom_id,
                        s.notes,
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
                """, (like, like, like, like,))
            except pg_errors.UndefinedColumn:
                cur.execute("""
                    SELECT
                        s.aecuser_ptr_id AS id,
                        aec.last_name, aec.first_name,
                        aec.email, aec.emailperso,
                        aec.tel_smartphone_1, aec.tel_maison,
                        c.label AS classroom,
                        aec.date_entree, aec.fk_foyer_id,
                        aec.fk_gender_id, s.s_classroom_id,
                        NULL AS notes,
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
                """, (like, like, like, like,))

            cols = [desc[0] for desc in cur.description]
            self._results = [dict(zip(cols, row)) for row in cur.fetchall()]
            self._populate_results()

        except Exception as e:
            log(f"StudentForm.search: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

    def _populate_results(self):
        """Remplit le tableau des résultats de recherche."""
        self._results_table.setRowCount(0)
        for r in self._results:
            row = self._results_table.rowCount()
            self._results_table.insertRow(row)
            self._results_table.setItem(row, 0, QTableWidgetItem(f"{r['last_name']} {r['first_name']}"))
            self._results_table.setItem(row, 1, QTableWidgetItem(r.get('classroom', '')))
            self._results_table.setItem(row, 2, QTableWidgetItem(r.get('email', '')))
            self._results_table.setItem(row, 3, QTableWidgetItem(str(r['id'])))

        self._results_table.resizeColumnsToContents()
        count = len(self._results)
        self._results_label.setText(f"Résultats ({count})")

        if count == 0:
            self._detail_panel.hide()
            QMessageBox.information(self, "Recherche",
                "Aucun élève trouvé. Vérifiez l'orthographe ou essayez un autre terme.")
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

    def _open_student_dialog(self, student_id: int):
        """Ouvre la popup d'édition pour un élève."""
        # Chercher les données dans les résultats déjà chargés
        data = next((r for r in self._results if r['id'] == student_id), None)
        if not data:
            conn = db.server_conn
            if not conn:
                return
            from psycopg2 import errors as pg_errors
            try:
                cur = conn.cursor()
                try:
                    cur.execute("""
                        SELECT
                            s.aecuser_ptr_id AS id,
                            aec.last_name, aec.first_name, aec.email,
                            aec.emailperso, aec.tel_smartphone_1, aec.tel_maison,
                            c.label AS classroom, aec.date_entree,
                            aec.fk_foyer_id, aec.fk_gender_id,
                            s.s_classroom_id, s.notes,
                            f.address_line1, f.address_line2, f.postal_code,
                            f.city, f.country, f.phone AS foyer_phone, f.email AS foyer_email
                        FROM larcauth_student s
                        JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                        JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                        LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                        WHERE s.aecuser_ptr_id = %s
                    """, (student_id,))
                except pg_errors.UndefinedColumn:
                    cur.execute("""
                        SELECT
                            s.aecuser_ptr_id AS id,
                            aec.last_name, aec.first_name, aec.email,
                            aec.emailperso, aec.tel_smartphone_1, aec.tel_maison,
                            c.label AS classroom, aec.date_entree,
                            aec.fk_foyer_id, aec.fk_gender_id,
                            s.s_classroom_id, NULL AS notes,
                            f.address_line1, f.address_line2, f.postal_code,
                            f.city, f.country, f.phone AS foyer_phone, f.email AS foyer_email
                        FROM larcauth_student s
                        JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                        JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                        LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                        WHERE s.aecuser_ptr_id = %s
                    """, (student_id,))
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
        sid = data['id']
        photo_path = os.path.join(LARCSUPERVISEUR_PHOTOS, f"{sid}.png")
        px = QPixmap(photo_path)
        if px.isNull():
            px = _make_avatar(data['last_name'], data['first_name'], 160)
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
            self._open_student_dialog(self._current_student['id'])

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
        self._data = data
        self._sid = data['id']
        self.setWindowTitle(f"Modifier — {data['last_name']} {data['first_name']}")
        self.setMinimumSize(900, 860)
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        fs = 10
        layout = QVBoxLayout(self)
        layout.setSpacing(d.spacing + 2)
        layout.setContentsMargins(d.margin, d.margin, d.margin, d.margin)

        title = QLabel("Modifier l'élève")
        title.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(title)

        field_style = (
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};")
        label_style = f"font-size: {s(fs)}px; color: {p.text_soft}; font-weight: bold; padding: {d.label_pad_v}px {d.label_pad_h}px;"

        def _lbl(t):
            lbl = QLabel(t)
            lbl.setStyleSheet(label_style)
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            return lbl

        # Photo + identité (toujours visible)
        photo_row = QHBoxLayout()
        self._photo = QLabel()
        self._photo.setFixedSize(120, 120)
        self._photo.setStyleSheet(f"background: {p.primary_container}; border-radius: {d.radius_xl}px;")
        self._photo.setAlignment(Qt.AlignCenter)
        photo_row.addWidget(self._photo)

        id_col = QVBoxLayout()
        self._id_name = QLabel("")
        self._id_name.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        id_col.addWidget(self._id_name)
        self._id_info = QLabel("")
        self._id_info.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft};")
        id_col.addWidget(self._id_info)
        id_col.addStretch()
        photo_row.addLayout(id_col, 1)
        layout.addLayout(photo_row)

        # Champs (créés avant les onglets)
        self._inp_nom = QLineEdit(); self._inp_nom.setStyleSheet(field_style)
        self._inp_prenom = QLineEdit(); self._inp_prenom.setStyleSheet(field_style)
        self._inp_email = QLineEdit(); self._inp_email.setStyleSheet(field_style)
        self._inp_emailperso = QLineEdit(); self._inp_emailperso.setStyleSheet(field_style)
        self._inp_tel = QLineEdit(); self._inp_tel.setStyleSheet(field_style)
        self._inp_tel2 = QLineEdit(); self._inp_tel2.setStyleSheet(field_style)
        self._inp_date = QLineEdit(); self._inp_date.setStyleSheet(field_style)
        self._inp_date.setPlaceholderText("AAAA-MM-JJ")
        self._inp_genre = QComboBox()
        self._inp_genre.setStyleSheet(field_style + f" min-width: 180px;")
        self._load_genders()
        self._inp_addr1 = QLineEdit(); self._inp_addr1.setStyleSheet(field_style)
        self._inp_addr2 = QLineEdit(); self._inp_addr2.setStyleSheet(field_style)
        self._inp_cp = QLineEdit(); self._inp_cp.setStyleSheet(field_style)
        self._inp_ville = QLineEdit(); self._inp_ville.setStyleSheet(field_style)
        self._inp_pays = QLineEdit("Togo"); self._inp_pays.setStyleSheet(field_style)

        # Onglets
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # --- Tab 1 : Identité ---
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        tab1_layout.setSpacing(d.spacing)
        g1 = QGridLayout()
        g1.setSpacing(d.spacing)
        g1.addWidget(_lbl("Nom *"), 0, 0); g1.addWidget(_lbl("Prénom *"), 0, 1)
        g1.addWidget(self._inp_nom, 1, 0); g1.addWidget(self._inp_prenom, 1, 1)
        g1.addWidget(_lbl("Date d'entrée"), 2, 0); g1.addWidget(_lbl("Genre"), 2, 1)
        g1.addWidget(self._inp_date, 3, 0); g1.addWidget(self._inp_genre, 3, 1)
        tab1_layout.addLayout(g1)
        tab1_layout.addStretch()
        tabs.addTab(tab1, "Identité")

        # --- Tab 2 : Contact ---

        # --- Tab 3 : Adresse ---
        tab3 = QWidget()
        tab3_layout = QVBoxLayout(tab3)
        tab3_layout.setSpacing(d.spacing)
        g3 = QGridLayout()
        g3.setSpacing(d.spacing)
        g3.addWidget(_lbl("Adresse"), 0, 0); g3.addWidget(_lbl("Complément"), 0, 1)
        g3.addWidget(self._inp_addr1, 1, 0); g3.addWidget(self._inp_addr2, 1, 1)
        g3.addWidget(_lbl("Code postal"), 2, 0); g3.addWidget(_lbl("Ville"), 2, 1)
        g3.addWidget(self._inp_cp, 3, 0); g3.addWidget(self._inp_ville, 3, 1)
        g3.addWidget(_lbl("Pays"), 4, 0)
        g3.addWidget(self._inp_pays, 5, 0, 1, 2)
        tab3_layout.addLayout(g3)
        tab3_layout.addStretch()
        tabs.addTab(tab3, "Adresse")

        # --- Tab 4 : Notes (éditeur HTML complet) ---
        tab4 = QWidget()
        tab4_layout = QVBoxLayout(tab4)
        tab4_layout.setSpacing(d.spacing)

        btn_style = (
            f"QPushButton {{ background: {p.surface_variant}; color: {p.text_strong}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; padding: 4px 6px; font-size: {s(fs + 2)}px; min-width: 26px; }}"
            f"QPushButton:hover {{ background: {p.primary_container}; }}")

        def _tb_btn(text, tip, slot):
            b = QPushButton(text)
            b.setStyleSheet(btn_style)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            return b

        tb = QHBoxLayout()
        tb.setSpacing(3)

        tb.addWidget(_tb_btn("B", "Gras", self._toggle_bold))
        tb.addWidget(_tb_btn("I", "Italique", self._toggle_italic))
        tb.addWidget(_tb_btn("U", "Souligné", self._toggle_underline))
        sep1 = QFrame(); sep1.setFrameShape(QFrame.VLine); sep1.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep1)
        tb.addWidget(_tb_btn("H1", "Titre 1", lambda: self._toggle_heading(1)))
        tb.addWidget(_tb_btn("H2", "Titre 2", lambda: self._toggle_heading(2)))
        tb.addWidget(_tb_btn("H3", "Titre 3", lambda: self._toggle_heading(3)))
        sep2 = QFrame(); sep2.setFrameShape(QFrame.VLine); sep2.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep2)
        tb.addWidget(_tb_btn("🎨", "Couleur du texte", self._pick_color))
        tb.addWidget(_tb_btn("⬜", "Surlignage", self._pick_bg_color))
        sep3 = QFrame(); sep3.setFrameShape(QFrame.VLine); sep3.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep3)
        tb.addWidget(_tb_btn("•", "Liste à puces", lambda: self._toggle_list(QTextListFormat.ListDisc)))
        tb.addWidget(_tb_btn("1.", "Liste numérotée", lambda: self._toggle_list(QTextListFormat.ListDecimal)))
        sep4 = QFrame(); sep4.setFrameShape(QFrame.VLine); sep4.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep4)
        tb.addWidget(_tb_btn("≡", "Ligne horizontale", self._insert_hr))
        tb.addWidget(_tb_btn("🖼", "Insérer une image", self._insert_image))
        tb.addWidget(_tb_btn("⬛", "Insérer un tableau", self._insert_table_dialog))
        sep5 = QFrame(); sep5.setFrameShape(QFrame.VLine); sep5.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep5)
        b_align_l = _tb_btn("◀", "Aligner à gauche", lambda: self._set_align(Qt.AlignLeft))
        b_align_c = _tb_btn("■", "Centrer", lambda: self._set_align(Qt.AlignCenter))
        b_align_r = _tb_btn("▶", "Aligner à droite", lambda: self._set_align(Qt.AlignRight))
        tb.addWidget(b_align_l); tb.addWidget(b_align_c); tb.addWidget(b_align_r)
        sep6 = QFrame(); sep6.setFrameShape(QFrame.VLine); sep6.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep6)
        tb.addWidget(_tb_btn("↔", "Diminuer retrait", lambda: self._change_indent(-1)))
        tb.addWidget(_tb_btn("↕", "Augmenter retrait", lambda: self._change_indent(1)))
        sep7 = QFrame(); sep7.setFrameShape(QFrame.VLine); sep7.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep7)
        self._btn_source = _tb_btn("</>", "Code source", self._toggle_source)
        tb.addWidget(self._btn_source)
        tb.addStretch()
        tab4_layout.addLayout(tb)

        self._inp_notes = QTextEdit()
        self._inp_notes.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};")
        self._inp_notes.setPlaceholderText("Écrire vos notes ici...")
        tab4_layout.addWidget(self._inp_notes, 1)

        self._source_edit = QPlainTextEdit()
        self._source_edit.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface_variant}; color: {p.text_strong}; "
            f"font-family: Consolas, 'Courier New', monospace;")
        self._source_edit.hide()
        tab4_layout.addWidget(self._source_edit, 1)

        self._source_notes_info = QLabel(
            "Les images sont stockées dans data/students/{id}/notes_img/")
        self._source_notes_info.setStyleSheet(
            f"font-size: {s(fs - 2)}px; color: {p.text_disabled};")
        tab4_layout.addWidget(self._source_notes_info)
        tabs.addTab(tab4, "Notes")

        # --- Tab 5 : Fichiers & Parents ---
        tab5 = QWidget()
        tab5_layout = QVBoxLayout(tab5)
        tab5_layout.setSpacing(d.spacing)
        files_label = QLabel("Fichiers joints :")
        files_label.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft}; font-weight: bold;")
        tab5_layout.addWidget(files_label)
        self._file_list = QListWidget()
        self._file_list.setStyleSheet(
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};")
        self._file_list.setMaximumHeight(100)
        self._file_list.itemDoubleClicked.connect(self._open_file)
        tab5_layout.addWidget(self._file_list)
        file_btn_row = QHBoxLayout()
        self._btn_add_file = QPushButton("Ajouter un fichier")
        self._btn_add_file.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; font-size: {s(fs)}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}")
        self._btn_add_file.clicked.connect(self._add_file)
        file_btn_row.addWidget(self._btn_add_file)
        self._btn_open_folder = QPushButton("Ouvrir le dossier")
        self._btn_open_folder.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; "
            f"font-size: {s(fs)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        self._btn_open_folder.clicked.connect(self._open_folder)
        file_btn_row.addWidget(self._btn_open_folder)
        self._btn_del_file = QPushButton("Supprimer")
        self._btn_del_file.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.error}; "
            f"border: 1px solid {p.error}; border-radius: {d.radius}px; padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; "
            f"font-size: {s(fs)}px; }}"
            f"QPushButton:hover {{ background: {p.error_container}; }}")
        self._btn_del_file.clicked.connect(self._delete_file)
        file_btn_row.addWidget(self._btn_del_file)
        file_btn_row.addStretch()
        tab5_layout.addLayout(file_btn_row)
        parents_title = QLabel("Parents / tuteurs")
        parents_title.setStyleSheet(f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong};")
        tab5_layout.addWidget(parents_title)
        self._parents_table = QTableWidget()
        self._parents_table.setColumnCount(4)
        self._parents_table.setHorizontalHeaderLabels(["Nom", "Nature", "Email", "Téléphone"])
        self._parents_table.horizontalHeader().setStretchLastSection(True)
        self._parents_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._parents_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._parents_table.setMaximumHeight(120)
        tab5_layout.addWidget(self._parents_table)
        tab5_layout.addStretch()
        tabs.addTab(tab5, "Fichiers & Parents")

        # --- Tab 6 : Événements (lecture seule) ---
        tab6 = QWidget()
        tab6_layout = QVBoxLayout(tab6)
        tab6_layout.setSpacing(d.spacing)
        evt_label = QLabel("Événements (consultation seule)")
        evt_label.setStyleSheet(f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong};")
        tab6_layout.addWidget(evt_label)
        self._evt_table = QTableWidget()
        self._evt_table.setColumnCount(5)
        self._evt_table.setHorizontalHeaderLabels(["Date/Heure", "Type", "Note", "Par", "Validé"])
        self._evt_table.horizontalHeader().setStretchLastSection(True)
        self._evt_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._evt_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._evt_table.setAlternatingRowColors(True)
        tab6_layout.addWidget(self._evt_table, 1)
        tabs.addTab(tab6, "Événements")

        layout.addWidget(tabs, 1)

        # Boutons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Enregistrer")
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_pad_v}px {d.btn_pad_h}px; font-size: {s(fs)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.success}; }}")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        print_btn = QPushButton("Imprimer")
        print_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_pad_v}px {d.btn_pad_h - 2}px; font-size: {s(fs)}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}")
        print_btn.clicked.connect(self._print)
        btn_row.addWidget(print_btn)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.text_soft}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; padding: {d.btn_pad_v}px {d.btn_pad_h - 2}px; font-size: {s(fs)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _get_class_language(self, classroom_id: int) -> int | None:
        conn = db.server_conn
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT l.fk_language_id
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                WHERE c.id = %s
            """, (classroom_id,))
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            log(f"StudentEditDialog._get_class_language: {e}")
            return None

    def _load_genders(self, lang_id: int | None = None):
        self._inp_genre.clear()
        self._inp_genre.addItem("— Non précisé —", 0)
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
            log(f"StudentEditDialog._load_genders: {e}")

    def _load_data(self):
        """Pré-remplit le formulaire avec les données existantes."""
        d = self._data
        sid = d['id']

        # Photo
        px = QPixmap(os.path.join(LARCSUPERVISEUR_PHOTOS, f"{sid}.png"))
        if px.isNull():
            px = _make_avatar(d['last_name'], d['first_name'], 120)
        else:
            px = px.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._photo.setPixmap(px)

        # Identité
        self._id_name.setText(f"{d['last_name']} {d['first_name']}")
        self._id_info.setText(f"ID : {sid}  |  Classe : {d.get('classroom', '—')}")

        # Champs
        self._inp_nom.setText(d.get('last_name', ''))
        self._inp_prenom.setText(d.get('first_name', ''))
        self._inp_email.setText(d.get('email', ''))
        self._inp_emailperso.setText(d.get('emailperso', '') or '')
        self._inp_tel.setText(d.get('tel_smartphone_1', '') or '')
        self._inp_tel2.setText(d.get('tel_maison', '') or '')
        self._inp_date.setText(str(d.get('date_entree', '') or ''))
        # Recharger les genres selon la langue de la classe
        classroom_id = d.get('s_classroom_id')
        if classroom_id:
            lang_id = self._get_class_language(classroom_id)
            self._load_genders(lang_id)
        gid = d.get('fk_gender_id') or 0
        idx = self._inp_genre.findData(gid)
        if idx >= 0:
            self._inp_genre.setCurrentIndex(idx)
        self._inp_addr1.setText(d.get('address_line1', '') or '')
        self._inp_addr2.setText(d.get('address_line2', '') or '')
        self._inp_cp.setText(d.get('postal_code', '') or '')
        self._inp_ville.setText(d.get('city', '') or '')
        self._inp_pays.setText(d.get('country', '') or 'Togo')
        raw_notes = d.get('notes', '') or ''
        if raw_notes:
            base = self._student_dir().replace('\\', '/')
            import re
            raw_notes = re.sub(
                r'(["\'])(' + re.escape('notes_img/') + r'[^"\']+)\1',
                lambda m: f'{m.group(1)}file:///{base}/{m.group(2)}{m.group(1)}',
                raw_notes)
        self._inp_notes.setHtml(raw_notes)
        self._refresh_files()

        # Parents
        conn = db.server_conn
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT aec.last_name || ' ' || aec.first_name AS name,
                           COALESCE(sp.nature, par.nature, 'parent'),
                           aec.email,
                           COALESCE(aec.tel_smartphone_1, aec.tel_maison, '')
                    FROM student_parent sp
                    JOIN larcauth_aecuser aec ON aec.id = sp.parent_id
                    LEFT JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                    WHERE sp.student_id = %s
                    ORDER BY aec.last_name
                """, (sid,))
                rows = list(cur.fetchall())
                self._parents_table.setRowCount(len(rows))
                for i, (name, nat, em, tel) in enumerate(rows):
                    self._parents_table.setItem(i, 0, QTableWidgetItem(name))
                    self._parents_table.setItem(i, 1, QTableWidgetItem(nat or ''))
                    self._parents_table.setItem(i, 2, QTableWidgetItem(em or ''))
                    self._parents_table.setItem(i, 3, QTableWidgetItem(tel or ''))
                self._parents_table.resizeColumnsToContents()
            except Exception as e:
                log(f"StudentEditDialog._load_parents: {e}")

        self._load_events()

    def _load_events(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT se.event_at, se.event_type, se.note,
                       aec.last_name || ' ' || aec.first_name AS author,
                       CASE WHEN se.validated_by IS NOT NULL THEN '✓' ELSE '—' END
                FROM student_event se
                JOIN larcauth_aecuser aec ON aec.id = se.created_by
                WHERE se.student_id = %s
                ORDER BY se.event_at DESC LIMIT 100
            """, (self._sid,))
            rows = cur.fetchall()
            self._evt_table.setRowCount(len(rows))
            for i, (evt_at, etype, note, author, validated) in enumerate(rows):
                self._evt_table.setItem(i, 0, QTableWidgetItem(str(evt_at)[:16]))
                self._evt_table.setItem(i, 1, QTableWidgetItem(etype or ''))
                self._evt_table.setItem(i, 2, QTableWidgetItem(note or ''))
                self._evt_table.setItem(i, 3, QTableWidgetItem(author))
                self._evt_table.setItem(i, 4, QTableWidgetItem(validated))
            self._evt_table.resizeColumnsToContents()
        except Exception as e:
            log(f"StudentEditDialog._load_events: {e}")

    def _save(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            from datetime import datetime
            now = datetime.now().isoformat()

            aec = {
                'last_name': self._inp_nom.text().strip(),
                'first_name': self._inp_prenom.text().strip(),
                'email': self._inp_email.text().strip() or '',
                'emailperso': self._inp_emailperso.text().strip() or None,
                'tel_smartphone_1': self._inp_tel.text().strip() or None,
                'tel_maison': self._inp_tel2.text().strip() or None,
                'date_entree': self._inp_date.text().strip() or None,
                'fk_gender_id': self._inp_genre.currentData() or None,
                'updated': now,
            }
            cur.execute(
                "UPDATE larcauth_aecuser SET " +
                ", ".join(f"{k}=%s" for k in aec) + " WHERE id=%s",
                list(aec.values()) + [self._sid])

            addr = {
                'address_line1': self._inp_addr1.text().strip() or None,
                'address_line2': self._inp_addr2.text().strip() or None,
                'postal_code': self._inp_cp.text().strip() or None,
                'city': self._inp_ville.text().strip() or None,
                'country': self._inp_pays.text().strip() or None,
            }
            fid = self._data.get('fk_foyer_id') or self._sid
            cols = list(addr.keys())
            vals = list(addr.values())
            cur.execute(
                "INSERT INTO foyer (id, " + ", ".join(cols) +
                ") VALUES (%s, " + ", ".join("%s" for _ in cols) +
                ") ON CONFLICT (id) DO UPDATE SET " +
                ", ".join(f"{k}=EXCLUDED.{k}" for k in cols),
                [fid] + vals)

            notes = self._inp_notes.toHtml().strip()
            if notes:
                base = self._student_dir().replace('\\', '/')
                import re
                notes = re.sub(
                    r'(["\'])file:///' + re.escape(base) + r'/(notes_img/[^"\']+)\1',
                    r'\1\2\1', notes)
            cur.execute("UPDATE larcauth_student SET notes = %s WHERE aecuser_ptr_id = %s",
                        (notes or None, self._sid))

            conn.commit()
            log(f"StudentEditDialog: saved #{self._sid}")
            QMessageBox.information(self, "Succès", "Élève mis à jour.")
            self.accept()
        except Exception as e:
            conn.rollback()
            log(f"StudentEditDialog._save: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

    # ── Notes (formatage HTML) ──

    def _apply_char_format(self, fmt: QTextCharFormat):
        c = self._inp_notes.textCursor()
        if c.hasSelection():
            c.mergeCharFormat(fmt)
        else:
            self._inp_notes.mergeCurrentCharFormat(fmt)
        self._inp_notes.setFocus()

    def _toggle_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold)
        c = self._inp_notes.textCursor()
        cur_fmt = c.charFormat()
        if cur_fmt.fontWeight() == QFont.Weight.Bold:
            fmt.setFontWeight(QFont.Weight.Normal)
        self._apply_char_format(fmt)

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        c = self._inp_notes.textCursor()
        cur_fmt = c.charFormat()
        fmt.setFontItalic(not cur_fmt.fontItalic())
        self._apply_char_format(fmt)

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        c = self._inp_notes.textCursor()
        cur_fmt = c.charFormat()
        fmt.setFontUnderline(not cur_fmt.fontUnderline())
        self._apply_char_format(fmt)

    def _toggle_heading(self, level: int):
        c = self._inp_notes.textCursor()
        c.beginEditBlock()
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(Qt.AlignLeft)
        char_fmt = QTextCharFormat()
        sizes = {1: 24, 2: 20, 3: 16}
        char_fmt.setFontPointSize(sizes.get(level, 14))
        char_fmt.setFontWeight(QFont.Weight.Bold)
        if c.hasSelection():
            c.mergeBlockFormat(block_fmt)
            c.mergeCharFormat(char_fmt)
        else:
            c.setBlockFormat(block_fmt)
            c.mergeCharFormat(char_fmt)
        c.endEditBlock()
        self._inp_notes.setFocus()

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._inp_notes.textColor()), self, "Couleur du texte")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._apply_char_format(fmt)

    def _pick_bg_color(self):
        color = QColorDialog.getColor(QColor(Qt.yellow), self, "Couleur de surlignage")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self._apply_char_format(fmt)

    def _toggle_list(self, style):
        cursor = self._inp_notes.textCursor()
        cursor.beginEditBlock()
        block = cursor.block()
        if block.textList():
            block.textList().remove(block)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(style)
            cursor.createList(fmt)
        cursor.endEditBlock()

    def _insert_hr(self):
        self._inp_notes.textCursor().insertHtml("<hr>")

    def _insert_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Insérer une image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        if not path:
            return
        notes_dir = self._notes_dir()
        import shutil
        basename = os.path.basename(path)
        dest = os.path.join(notes_dir, basename)
        try:
            shutil.copy2(path, dest)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de copier l'image : {e}")
            return
        cursor = self._inp_notes.textCursor()
        cursor.insertHtml(
            f'<img src="file:///{dest.replace(chr(92), "/")}" alt="{basename}" />')

    def _notes_dir(self) -> str:
        d = os.path.join(self._student_dir(), 'notes_img')
        os.makedirs(d, exist_ok=True)
        return d

    def _insert_table_dialog(self):
        rows, ok = QInputDialog.getInt(self, "Tableau", "Nombre de lignes :", 3, 1, 20, 1)
        if not ok:
            return
        cols, ok2 = QInputDialog.getInt(self, "Tableau", "Nombre de colonnes :", 3, 1, 10, 1)
        if not ok2:
            return
        self._inp_notes.textCursor().insertTable(rows, cols)

    def _set_align(self, align):
        c = self._inp_notes.textCursor()
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(align)
        c.mergeBlockFormat(block_fmt)
        self._inp_notes.setFocus()

    def _change_indent(self, direction: int):
        c = self._inp_notes.textCursor()
        block_fmt = QTextBlockFormat()
        indent = c.blockFormat().indent() + direction
        if indent < 0:
            indent = 0
        block_fmt.setIndent(indent)
        c.mergeBlockFormat(block_fmt)
        self._inp_notes.setFocus()

    def _toggle_source(self):
        if self._source_edit.isVisible():
            html = self._source_edit.toPlainText()
            self._source_edit.hide()
            self._inp_notes.setHtml(html)
            self._inp_notes.show()
            self._btn_source.setStyleSheet(
                f"QPushButton {{ background: {theme_manager.palette.surface_variant}; color: {theme_manager.palette.text_strong}; "
                f"border: 1px solid {theme_manager.palette.border}; "
                f"border-radius: {theme_manager.design.radius}px; padding: 4px 6px; "
                f"font-size: {theme_manager.font_size(10)}px; min-width: 26px; }}"
                f"QPushButton:hover {{ background: {theme_manager.palette.primary_container}; }}")
        else:
            html = self._inp_notes.toHtml()
            self._inp_notes.hide()
            self._source_edit.setPlainText(html)
            self._source_edit.show()
            self._source_edit.setFocus()
            self._btn_source.setStyleSheet(
                f"QPushButton {{ background: {theme_manager.palette.primary}; color: {theme_manager.palette.on_primary}; "
                f"border: 1px solid {theme_manager.palette.primary}; "
                f"border-radius: {theme_manager.design.radius}px; padding: 4px 6px; "
                f"font-size: {theme_manager.font_size(10)}px; min-width: 26px; }}")

    # ── Fichiers élèves ──

    def _student_dir(self) -> str:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'students')
        d = os.path.join(base, str(self._sid))
        os.makedirs(d, exist_ok=True)
        return d

    def _refresh_files(self):
        self._file_list.clear()
        d = self._student_dir()
        try:
            for f in sorted(os.listdir(d)):
                self._file_list.addItem(f)
        except Exception:
            pass

    def _add_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Ajouter des fichiers", "",
                                                 "Tous les fichiers (*)")
        if not paths:
            return
        d = self._student_dir()
        for p in paths:
            name = os.path.basename(p)
            import shutil
            shutil.copy2(p, os.path.join(d, name))
        self._refresh_files()

    def _delete_file(self):
        item = self._file_list.currentItem()
        if not item:
            return
        name = item.text()
        r = QMessageBox.question(self, "Confirmation",
                                  f"Supprimer {name} ?",
                                  QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        path = os.path.join(self._student_dir(), name)
        try:
            os.remove(path)
            self._refresh_files()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def _open_file(self, item):
        path = os.path.join(self._student_dir(), item.text())
        import subprocess
        subprocess.Popen(['explorer', path], shell=True)

    def _open_folder(self):
        import subprocess
        subprocess.Popen(['explorer', self._student_dir()], shell=True)

    def _print(self):
        d = self._data
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() != QDialog.Accepted:
            return
        from PySide6.QtGui import QTextDocument
        html = (
            f"<html><head><meta charset='utf-8'></head><body>"
            f"<h1>Fiche élève</h1>"
            f"<p><b>{d['last_name']} {d['first_name']}</b></p>"
            f"<p>Classe : {d.get('classroom','')} | ID : {d['id']}</p><hr>"
            f"<p>Email : {d.get('email','')}</p>"
            f"<p>Tél : {d.get('tel_smartphone_1','')}</p><hr><h2>Adresse</h2>"
            f"<p>{d.get('address_line1','')}<br>{d.get('address_line2','')}<br>"
            f"{d.get('postal_code','')} {d.get('city','')}</p><hr><h2>Notes</h2>"
            f"{self._inp_notes.toHtml()}</body></html>")
        doc = QTextDocument()
        doc.setHtml(html)
        doc.print_(printer)


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
        self.setWindowTitle("Nouvel élève")
        self.setMinimumSize(900, 860)
        self._result_data: dict | None = None
        self._class_id: int | None = None
        self._next_free: int | None = None
        self._sid: int | None = None
        self._classes: list[tuple] = []
        self._class_btns: dict[int, QPushButton] = {}
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

        self._class_title = QLabel("Nouvel élève")
        self._class_title.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(self._class_title)

        if self._preselected_class:
            self._class_info = QLabel()
            self._class_info.setStyleSheet(f"font-size: {s(13)}px; color: {p.text_soft}; padding-bottom: 8px;")
            layout.addWidget(self._class_info)
            self._class_grid = None
        else:
            cl_label = QLabel("Classe :")
            cl_label.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft}; font-weight: bold;")
            layout.addWidget(cl_label)
            self._class_grid = QWidget()
            self._class_grid_layout = QVBoxLayout(self._class_grid)
            self._class_grid_layout.setContentsMargins(0, 0, 0, 0)
            self._class_grid_layout.setSpacing(4)
            layout.addWidget(self._class_grid)

        # Photo + identité (placeholder)
        photo_row = QHBoxLayout()
        self._photo = QLabel()
        self._photo.setFixedSize(120, 120)
        self._photo.setStyleSheet(f"background: {p.primary_container}; border-radius: {d.radius_xl}px;")
        self._photo.setAlignment(Qt.AlignCenter)
        photo_row.addWidget(self._photo)

        id_col = QVBoxLayout()
        self._id_name = QLabel("Nouvel élève")
        self._id_name.setStyleSheet(f"font-size: {s(15)}px; font-weight: bold; color: {p.text_strong};")
        id_col.addWidget(self._id_name)
        self._id_info = QLabel("Remplissez les informations ci-dessous")
        self._id_info.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft};")
        id_col.addWidget(self._id_info)
        id_col.addStretch()
        photo_row.addLayout(id_col, 1)
        layout.addLayout(photo_row)

        field_style = (
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};")
        label_style = f"font-size: {s(fs)}px; color: {p.text_soft}; font-weight: bold; padding: {d.label_pad_v}px {d.label_pad_h}px;"

        def _lbl(t):
            lbl = QLabel(t)
            lbl.setStyleSheet(label_style)
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            return lbl

        # Champs (créés avant les onglets)
        self._inp_nom = QLineEdit(); self._inp_nom.setStyleSheet(field_style)
        self._inp_nom.setPlaceholderText("Nom de famille")
        self._inp_prenom = QLineEdit(); self._inp_prenom.setStyleSheet(field_style)
        self._inp_prenom.setPlaceholderText("Prénom")
        self._inp_email = QLineEdit(); self._inp_email.setStyleSheet(field_style)
        self._inp_email.setPlaceholderText("email@ecole.org")
        self._inp_emailperso = QLineEdit(); self._inp_emailperso.setStyleSheet(field_style)
        self._inp_emailperso.setPlaceholderText("email.perso@exemple.com")
        self._inp_tel = QLineEdit(); self._inp_tel.setStyleSheet(field_style)
        self._inp_tel.setPlaceholderText("+228 XX XX XX XX")
        self._inp_tel2 = QLineEdit(); self._inp_tel2.setStyleSheet(field_style)
        self._inp_tel2.setPlaceholderText("+228 XX XX XX XX")
        self._inp_date = QLineEdit(); self._inp_date.setStyleSheet(field_style)
        self._inp_date.setPlaceholderText("AAAA-MM-JJ (ex: 2026-09-01)")
        self._inp_genre = QComboBox(); self._inp_genre.setStyleSheet(field_style + " min-width: 180px;")
        self._load_genders()
        self._inp_addr1 = QLineEdit(); self._inp_addr1.setStyleSheet(field_style)
        self._inp_addr1.setPlaceholderText("Numéro et rue")
        self._inp_addr2 = QLineEdit(); self._inp_addr2.setStyleSheet(field_style)
        self._inp_addr2.setPlaceholderText("Appartement, bâtiment...")
        self._inp_cp = QLineEdit(); self._inp_cp.setStyleSheet(field_style)
        self._inp_cp.setPlaceholderText("75001")
        self._inp_ville = QLineEdit(); self._inp_ville.setStyleSheet(field_style)
        self._inp_ville.setPlaceholderText("Lomé")
        self._inp_pays = QLineEdit("Togo"); self._inp_pays.setStyleSheet(field_style)

        # Onglets (même structure que EditDialog)
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # --- Tab 1 : Identité ---
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        tab1_layout.setSpacing(d.spacing)
        g1 = QGridLayout()
        g1.setSpacing(d.spacing)
        g1.addWidget(_lbl("Nom *"), 0, 0); g1.addWidget(_lbl("Prénom *"), 0, 1)
        g1.addWidget(self._inp_nom, 1, 0); g1.addWidget(self._inp_prenom, 1, 1)
        g1.addWidget(_lbl("Date d'entrée"), 2, 0); g1.addWidget(_lbl("Genre"), 2, 1)
        g1.addWidget(self._inp_date, 3, 0); g1.addWidget(self._inp_genre, 3, 1)
        tab1_layout.addLayout(g1)
        tab1_layout.addStretch()
        tabs.addTab(tab1, "Identité")

        # --- Tab 2 : Contact ---
        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)
        tab2_layout.setSpacing(d.spacing)
        g2 = QGridLayout()
        g2.setSpacing(d.spacing)
        g2.addWidget(_lbl("Email"), 0, 0); g2.addWidget(_lbl("Email personnel"), 0, 1)
        g2.addWidget(self._inp_email, 1, 0); g2.addWidget(self._inp_emailperso, 1, 1)
        g2.addWidget(_lbl("Téléphone portable"), 2, 0); g2.addWidget(_lbl("Téléphone fixe"), 2, 1)
        g2.addWidget(self._inp_tel, 3, 0); g2.addWidget(self._inp_tel2, 3, 1)
        tab2_layout.addLayout(g2)
        tab2_layout.addStretch()
        tabs.addTab(tab2, "Contact")

        # --- Tab 3 : Adresse ---
        tab3 = QWidget()
        tab3_layout = QVBoxLayout(tab3)
        tab3_layout.setSpacing(d.spacing)
        g3 = QGridLayout()
        g3.setSpacing(d.spacing)
        g3.addWidget(_lbl("Adresse"), 0, 0); g3.addWidget(_lbl("Complément"), 0, 1)
        g3.addWidget(self._inp_addr1, 1, 0); g3.addWidget(self._inp_addr2, 1, 1)
        g3.addWidget(_lbl("Code postal"), 2, 0); g3.addWidget(_lbl("Ville"), 2, 1)
        g3.addWidget(self._inp_cp, 3, 0); g3.addWidget(self._inp_ville, 3, 1)
        g3.addWidget(_lbl("Pays"), 4, 0)
        g3.addWidget(self._inp_pays, 5, 0, 1, 2)
        tab3_layout.addLayout(g3)
        tab3_layout.addStretch()
        tabs.addTab(tab3, "Adresse")

        # --- Tab 4 : Notes (éditeur HTML) ---
        tab4 = QWidget()
        tab4_layout = QVBoxLayout(tab4)
        tab4_layout.setSpacing(d.spacing)

        btn_style = (
            f"QPushButton {{ background: {p.surface_variant}; color: {p.text_strong}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; padding: 4px 6px; font-size: {s(fs + 2)}px; min-width: 26px; }}"
            f"QPushButton:hover {{ background: {p.primary_container}; }}")

        def _tb_btn(text, tip, slot):
            b = QPushButton(text)
            b.setStyleSheet(btn_style)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            return b

        tb = QHBoxLayout()
        tb.setSpacing(3)

        tb.addWidget(_tb_btn("B", "Gras", self._toggle_bold))
        tb.addWidget(_tb_btn("I", "Italique", self._toggle_italic))
        tb.addWidget(_tb_btn("U", "Souligné", self._toggle_underline))
        sep1 = QFrame(); sep1.setFrameShape(QFrame.VLine); sep1.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep1)
        tb.addWidget(_tb_btn("H1", "Titre 1", lambda: self._toggle_heading(1)))
        tb.addWidget(_tb_btn("H2", "Titre 2", lambda: self._toggle_heading(2)))
        tb.addWidget(_tb_btn("H3", "Titre 3", lambda: self._toggle_heading(3)))
        sep2 = QFrame(); sep2.setFrameShape(QFrame.VLine); sep2.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep2)
        tb.addWidget(_tb_btn("🎨", "Couleur du texte", self._pick_color))
        tb.addWidget(_tb_btn("⬜", "Surlignage", self._pick_bg_color))
        sep3 = QFrame(); sep3.setFrameShape(QFrame.VLine); sep3.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep3)
        tb.addWidget(_tb_btn("•", "Liste à puces", lambda: self._toggle_list(QTextListFormat.ListDisc)))
        tb.addWidget(_tb_btn("1.", "Liste numérotée", lambda: self._toggle_list(QTextListFormat.ListDecimal)))
        sep4 = QFrame(); sep4.setFrameShape(QFrame.VLine); sep4.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep4)
        tb.addWidget(_tb_btn("≡", "Ligne horizontale", self._insert_hr))
        tb.addWidget(_tb_btn("🖼", "Insérer une image", self._insert_image))
        tb.addWidget(_tb_btn("⬛", "Insérer un tableau", self._insert_table_dialog))
        sep5 = QFrame(); sep5.setFrameShape(QFrame.VLine); sep5.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep5)
        b_align_l = _tb_btn("◀", "Aligner à gauche", lambda: self._set_align(Qt.AlignLeft))
        b_align_c = _tb_btn("■", "Centrer", lambda: self._set_align(Qt.AlignCenter))
        b_align_r = _tb_btn("▶", "Aligner à droite", lambda: self._set_align(Qt.AlignRight))
        tb.addWidget(b_align_l); tb.addWidget(b_align_c); tb.addWidget(b_align_r)
        sep6 = QFrame(); sep6.setFrameShape(QFrame.VLine); sep6.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep6)
        tb.addWidget(_tb_btn("↔", "Diminuer retrait", lambda: self._change_indent(-1)))
        tb.addWidget(_tb_btn("↕", "Augmenter retrait", lambda: self._change_indent(1)))
        sep7 = QFrame(); sep7.setFrameShape(QFrame.VLine); sep7.setStyleSheet(f"color: {p.border};")
        tb.addWidget(sep7)
        self._btn_source = _tb_btn("</>", "Code source", self._toggle_source)
        tb.addWidget(self._btn_source)
        tb.addStretch()
        tab4_layout.addLayout(tb)

        self._inp_notes = QTextEdit()
        self._inp_notes.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface}; color: {p.text_strong};")
        self._inp_notes.setPlaceholderText("Écrire vos notes ici...")
        tab4_layout.addWidget(self._inp_notes, 1)

        self._source_edit = QPlainTextEdit()
        self._source_edit.setStyleSheet(
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline}; border-radius: {d.radius}px; "
            f"font-size: {s(fs)}px; background: {p.surface_variant}; color: {p.text_strong}; "
            f"font-family: Consolas, 'Courier New', monospace;")
        self._source_edit.hide()
        tab4_layout.addWidget(self._source_edit, 1)

        self._source_notes_info = QLabel(
            "Les images sont stockées dans data/students/{id}/notes_img/")
        self._source_notes_info.setStyleSheet(
            f"font-size: {s(fs - 2)}px; color: {p.text_disabled};")
        tab4_layout.addWidget(self._source_notes_info)
        tabs.addTab(tab4, "Notes")

        # --- Tab 5 : Fichiers & Parents (placeholder) ---
        tab5 = QWidget()
        tab5_layout = QVBoxLayout(tab5)
        tab5_layout.setSpacing(d.spacing)
        ph5 = QLabel("Les fichiers et parents seront disponibles après la création de l'élève.")
        ph5.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft}; font-style: italic;")
        ph5.setAlignment(Qt.AlignCenter)
        tab5_layout.addWidget(ph5)
        tab5_layout.addStretch()
        tabs.addTab(tab5, "Fichiers & Parents")

        # --- Tab 6 : Événements (placeholder) ---
        tab6 = QWidget()
        tab6_layout = QVBoxLayout(tab6)
        tab6_layout.setSpacing(d.spacing)
        ph6 = QLabel("Les événements seront visibles après la création de l'élève.")
        ph6.setStyleSheet(f"font-size: {s(fs)}px; color: {p.text_soft}; font-style: italic;")
        ph6.setAlignment(Qt.AlignCenter)
        tab6_layout.addWidget(ph6)
        tab6_layout.addStretch()
        tabs.addTab(tab6, "Événements")

        layout.addWidget(tabs, 1)

        # Infos slot
        self._slot_info = QLabel("Sélectionnez une classe")
        self._slot_info.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.text_soft}; padding: {d.radius}px; font-style: italic;")
        layout.addWidget(self._slot_info)

        # Boutons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._create_btn = QPushButton("Créer l'élève")
        self._create_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_pad_v}px {d.btn_pad_h}px; font-size: {s(fs)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.success}; }}"
            f"QPushButton:disabled {{ background: {p.border_light}; color: {p.text_disabled}; }}")
        self._create_btn.setEnabled(False)
        self._create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(self._create_btn)

        self._cancel_btn = QPushButton("Annuler")
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.text_soft}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; padding: {d.btn_pad_v}px {d.btn_pad_h - 2}px; font-size: {s(fs)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

    def _load_classes(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            if self._preselected_class:
                # Mode classe connue : pas de grille, juste le label
                cur.execute("""
                    SELECT c.label
                    FROM larcauth_classroom c
                    WHERE c.id = %s
                """, (self._preselected_class,))
                row = cur.fetchone()
                if row:
                    self._class_info.setText(
                        f"Nouvel élève dans la classe : {row[0]}")
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
        if not hasattr(self, '_class_grid_layout') or not self._class_grid:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design

        prog_style = {
            'PEI':  (p.primary, p.primary_container, p.on_primary),
            'MYP':  (p.secondary, p.secondary_container, p.on_secondary),
            'DPFr': (p.error, p.error_container, p.on_error),
            'DPEn': (p.tertiary, p.tertiary_container, p.on_tertiary),
        }

        groups = {k: [] for k in ['PEI', 'MYP', 'DPEn', 'DPFr']}
        for cid, label, pid, sigle in self._classes:
            if sigle in groups:
                groups[sigle].append((cid, label))

        sections = [
            ('Collège', [('PEI', 'PEI'), ('MYP', 'MYP')]),
            ('Lycée',   [('DP', 'DPFr'), ('DPEn', 'DPEn')]),
        ]

        # Vider le layout
        self._clear_class_grid()
        self._class_btns.clear()

        for sec_name, columns in sections:
            sec_hdr = QLabel(sec_name)
            sec_hdr.setStyleSheet(
                f"font-weight: bold; font-size: {s(11)}px; color: {p.text_strong}; "
                f"border-bottom: 2px solid {p.outline_variant}; padding: 2px 0;")
            self._class_grid_layout.addWidget(sec_hdr)

            grd = QGridLayout()
            grd.setSpacing(3)

            for col_idx, (hdr_text, prog_key) in enumerate(columns):
                if prog_key not in groups:
                    continue
                fg, bg, on_fg = prog_style[prog_key]
                items = groups[prog_key]

                col_hdr = QLabel(hdr_text)
                col_hdr.setStyleSheet(
                    f"background: {fg}; color: {on_fg}; border-radius: {d.radius}px; "
                    f"font-weight: bold; font-size: {s(10)}px; padding: 3px;")
                col_hdr.setAlignment(Qt.AlignCenter)
                col_hdr.setFixedHeight(26)
                grd.addWidget(col_hdr, 0, col_idx)

                for i, (cid, label) in enumerate(items):
                    btn = QPushButton(label)
                    btn.setFixedHeight(32)
                    btn.setStyleSheet(
                        f"QPushButton {{ background: {bg}; color: {fg}; border: 2px solid transparent; "
                        f"border-radius: {d.radius}px; font-size: {s(10)}px; padding: 2px; }}"
                        f"QPushButton:hover {{ background: {fg}; color: {bg}; }}")
                    btn.clicked.connect(lambda checked, c=cid: self._on_class_changed(c))
                    self._class_btns[cid] = btn
                    grd.addWidget(btn, i + 1, col_idx)

            self._class_grid_layout.addLayout(grd)
            self._class_grid_layout.addSpacing(4)

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
                    'PEI': (p.primary, p.primary_container, p.on_primary),
                    'MYP': (p.secondary, p.secondary_container, p.on_secondary),
                    'DPFr': (p.error, p.error_container, p.on_error),
                    'DPEn': (p.tertiary, p.tertiary_container, p.on_tertiary),
                }
                fg, bg, on_fg = prog_map.get(sigle, (p.text_strong, p.surface_variant, p.text_strong))
                if cid == class_id:
                    btn.setStyleSheet(
                        f"QPushButton {{ background: {fg}; color: {bg}; border: 2px solid {fg}; "
                        f"border-radius: {theme_manager.design.radius}px; font-size: {theme_manager.font_size(10)}px; padding: 2px; }}"
                        f"QPushButton:hover {{ background: {fg}; color: {bg}; }}")
                else:
                    btn.setStyleSheet(
                        f"QPushButton {{ background: {bg}; color: {fg}; border: 2px solid transparent; "
                        f"border-radius: {theme_manager.design.radius}px; font-size: {theme_manager.font_size(10)}px; padding: 2px; }}"
                        f"QPushButton:hover {{ background: {fg}; color: {bg}; }}")

        # Filtrer les genres selon la langue de la classe
        lang_id = self._get_class_language(class_id)
        self._load_genders(lang_id)

        conn = db.server_conn
        if not conn:
            return

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.aecuser_ptr_id, aec.last_name, s.enabled
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                WHERE s.s_classroom_id = %s
                ORDER BY s.aecuser_ptr_id
            """, (self._class_id,))
            all_rows = list(cur.fetchall())

            # Prochain slot libre (01→40) : enabled=FALSE et nom placeholder
            free = None
            for rid, ln, en in all_rows:
                slot = rid % 100
                if 1 <= slot <= 40 and not en and ('Name of' in (ln or '')):
                    free = slot
                    break

            self._next_free = free
            if free:
                self._sid = self._class_id * 100 + free
                os.makedirs(os.path.join(self._student_dir(), 'notes_img'), exist_ok=True)
            else:
                self._sid = None

            p = theme_manager.palette
            s = theme_manager.font_size
            d = theme_manager.design
            if free:
                self._slot_info.setText(f"Slot libre : N°{free:02d} (ID = {self._class_id * 100 + free})")
                self._slot_info.setStyleSheet(
                    f"font-size: {s(13)}px; color: {p.success}; padding: {d.radius}px; font-weight: bold;")
                self._create_btn.setEnabled(True)
            else:
                self._slot_info.setText("Aucun slot libre dans cette classe")
                self._slot_info.setStyleSheet(
                    f"font-size: {s(13)}px; color: {p.error}; padding: {d.radius}px;")
                self._create_btn.setEnabled(False)
        except Exception as e:
            log(f"StudentCreateDialog._on_class_changed: {e}")

    def _get_class_language(self, classroom_id: int) -> int | None:
        conn = db.server_conn
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT l.fk_language_id
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                WHERE c.id = %s
            """, (classroom_id,))
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            log(f"StudentCreateDialog._get_class_language: {e}")
            return None

    def _load_genders(self, lang_id: int | None = None):
        self._inp_genre.clear()
        self._inp_genre.addItem("— Non précisé —", 0)
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
            QMessageBox.warning(self, "Validation", "Nom et prénom sont obligatoires.")
            return
        self._create_student()

    # ── Notes (formatage HTML) ──

    def _apply_char_format(self, fmt: QTextCharFormat):
        c = self._inp_notes.textCursor()
        if c.hasSelection():
            c.mergeCharFormat(fmt)
        else:
            self._inp_notes.mergeCurrentCharFormat(fmt)
        self._inp_notes.setFocus()

    def _toggle_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold)
        c = self._inp_notes.textCursor()
        cur_fmt = c.charFormat()
        if cur_fmt.fontWeight() == QFont.Weight.Bold:
            fmt.setFontWeight(QFont.Weight.Normal)
        self._apply_char_format(fmt)

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        c = self._inp_notes.textCursor()
        cur_fmt = c.charFormat()
        fmt.setFontItalic(not cur_fmt.fontItalic())
        self._apply_char_format(fmt)

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        c = self._inp_notes.textCursor()
        cur_fmt = c.charFormat()
        fmt.setFontUnderline(not cur_fmt.fontUnderline())
        self._apply_char_format(fmt)

    def _toggle_heading(self, level: int):
        c = self._inp_notes.textCursor()
        c.beginEditBlock()
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(Qt.AlignLeft)
        char_fmt = QTextCharFormat()
        sizes = {1: 24, 2: 20, 3: 16}
        char_fmt.setFontPointSize(sizes.get(level, 14))
        char_fmt.setFontWeight(QFont.Weight.Bold)
        if c.hasSelection():
            c.mergeBlockFormat(block_fmt)
            c.mergeCharFormat(char_fmt)
        else:
            c.setBlockFormat(block_fmt)
            c.mergeCharFormat(char_fmt)
        c.endEditBlock()
        self._inp_notes.setFocus()

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._inp_notes.textColor()), self, "Couleur du texte")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._apply_char_format(fmt)

    def _pick_bg_color(self):
        color = QColorDialog.getColor(QColor(Qt.yellow), self, "Couleur de surlignage")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self._apply_char_format(fmt)

    def _toggle_list(self, style):
        cursor = self._inp_notes.textCursor()
        cursor.beginEditBlock()
        block = cursor.block()
        if block.textList():
            block.textList().remove(block)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(style)
            cursor.createList(fmt)
        cursor.endEditBlock()

    def _insert_hr(self):
        self._inp_notes.textCursor().insertHtml("<hr>")

    def _insert_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Insérer une image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        if not path:
            return
        if not self._sid:
            QMessageBox.warning(self, "Info", "Sélectionnez d'abord une classe.")
            return
        notes_dir = self._notes_dir()
        import shutil
        basename = os.path.basename(path)
        dest = os.path.join(notes_dir, basename)
        try:
            shutil.copy2(path, dest)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de copier l'image : {e}")
            return
        cursor = self._inp_notes.textCursor()
        cursor.insertHtml(
            f'<img src="file:///{dest.replace(chr(92), "/")}" alt="{basename}" />')

    def _notes_dir(self) -> str:
        d = os.path.join(self._student_dir(), 'notes_img')
        os.makedirs(d, exist_ok=True)
        return d

    def _student_dir(self) -> str:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'students')
        d = os.path.join(base, str(self._sid))
        os.makedirs(d, exist_ok=True)
        return d

    def _insert_table_dialog(self):
        rows, ok = QInputDialog.getInt(self, "Tableau", "Nombre de lignes :", 3, 1, 20, 1)
        if not ok:
            return
        cols, ok2 = QInputDialog.getInt(self, "Tableau", "Nombre de colonnes :", 3, 1, 10, 1)
        if not ok2:
            return
        self._inp_notes.textCursor().insertTable(rows, cols)

    def _set_align(self, align):
        c = self._inp_notes.textCursor()
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(align)
        c.mergeBlockFormat(block_fmt)
        self._inp_notes.setFocus()

    def _change_indent(self, direction: int):
        c = self._inp_notes.textCursor()
        block_fmt = QTextBlockFormat()
        indent = c.blockFormat().indent() + direction
        if indent < 0:
            indent = 0
        block_fmt.setIndent(indent)
        c.mergeBlockFormat(block_fmt)
        self._inp_notes.setFocus()

    def _toggle_source(self):
        if self._source_edit.isVisible():
            html = self._source_edit.toPlainText()
            self._source_edit.hide()
            self._inp_notes.setHtml(html)
            self._inp_notes.show()
            self._btn_source.setStyleSheet(
                f"QPushButton {{ background: {theme_manager.palette.surface_variant}; color: {theme_manager.palette.text_strong}; "
                f"border: 1px solid {theme_manager.palette.border}; "
                f"border-radius: {theme_manager.design.radius}px; padding: 4px 6px; "
                f"font-size: {theme_manager.font_size(10)}px; min-width: 26px; }}"
                f"QPushButton:hover {{ background: {theme_manager.palette.primary_container}; }}")
        else:
            html = self._inp_notes.toHtml()
            self._inp_notes.hide()
            self._source_edit.setPlainText(html)
            self._source_edit.show()
            self._source_edit.setFocus()
            self._btn_source.setStyleSheet(
                f"QPushButton {{ background: {theme_manager.palette.primary}; color: {theme_manager.palette.on_primary}; "
                f"border: 1px solid {theme_manager.palette.primary}; "
                f"border-radius: {theme_manager.design.radius}px; padding: 4px 6px; "
                f"font-size: {theme_manager.font_size(10)}px; min-width: 26px; }}")

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
        date_str = self._inp_date.text().strip() or None

        conn = db.server_conn
        if not conn:
            return

        try:
            cur = conn.cursor()
            from datetime import datetime
            now = datetime.now().isoformat()
            username = email or f"student.{nom.lower()}.{prenom.lower()}"

            cur.execute("""
                UPDATE larcauth_aecuser SET
                    first_name = %s, last_name = %s, email = %s,
                    username = %s, is_active = TRUE, updated = %s,
                    emailperso = %s, tel_smartphone_1 = %s, tel_maison = %s,
                    date_entree = %s, fk_gender_id = %s
                WHERE id = %s
            """, (prenom, nom, email or '', username, now,
                  emailperso, tel, tel2, date_str,
                  self._inp_genre.currentData() or None, student_id))

            notes = self._inp_notes.toHtml().strip()
            if notes:
                base = self._student_dir().replace('\\', '/')
                import re
                notes = re.sub(
                    r'(["\'])file:///' + re.escape(base) + r'/(notes_img/[^"\']+)\1',
                    r'\1\2\1', notes)
            cur.execute("""
                UPDATE larcauth_student SET enabled = TRUE, updated_s = %s, notes = %s
                WHERE aecuser_ptr_id = %s
            """, (now, notes or None, student_id))

            cur.execute("""
                INSERT INTO foyer (id, enabled, address_line1, address_line2,
                                   postal_code, city, country)
                VALUES (%s, TRUE, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    address_line1 = EXCLUDED.address_line1,
                    address_line2 = EXCLUDED.address_line2,
                    postal_code = EXCLUDED.postal_code,
                    city = EXCLUDED.city,
                    country = EXCLUDED.country
            """, (student_id,
                  self._inp_addr1.text().strip() or None,
                  self._inp_addr2.text().strip() or None,
                  self._inp_cp.text().strip() or None,
                  self._inp_ville.text().strip() or None,
                  self._inp_pays.text().strip() or None))
            cur.execute("UPDATE larcauth_aecuser SET fk_foyer_id = %s WHERE id = %s",
                       (student_id, student_id))

            conn.commit()
            self._result_data = {'id': student_id, 'last_name': nom, 'first_name': prenom}
            log(f"StudentCreateDialog: activated #{student_id} (slot {slot:02d})")

            QMessageBox.information(self, "Succès",
                f"Élève créé : {prenom} {nom}\n"
                f"ID : {student_id}  |  Classe : slot N°{slot:02d}")

            # Réinitialiser le formulaire pour une autre saisie
            for w in [self._inp_nom, self._inp_prenom, self._inp_email,
                      self._inp_emailperso, self._inp_tel, self._inp_tel2,
                      self._inp_date, self._inp_addr1, self._inp_addr2,
                      self._inp_cp, self._inp_ville]:
                w.clear()
            self._inp_notes.clear()
            self._inp_pays.setText("Togo")
            # Re-vérifier le slot libre
            self._on_class_changed(self._class_id)

        except Exception as e:
            conn.rollback()
            log(f"StudentCreateDialog._create_student: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

    def get_data(self) -> dict | None:
        return self._result_data
