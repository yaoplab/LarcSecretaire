"""
Gestion des parents / tuteurs.

Fonctionnalités :
  - Liste des parents avec recherche, filtre par nature/ville
  - Création d'un nouveau parent (aecuser + larcauth_parent + foyer)
  - Lien/délien élève ↔ parent
  - Gestion du foyer (adresse, partage d'adresse)

Architecture :
  ParentManager      : widget principal (liste + détails)
  ParentEditDialog   : dialogue de création/édition d'un parent
"""

from larccommon.l10n import _
from LarcSecretaire.common.audit import audit
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from phibuilder.widgets import (
    M3Button,
    M3Card,
    M3ComboBox,
    M3DialogButtonBox,
    M3GroupBox,
    M3Label,
    M3Splitter,
    M3TableWidget,
    M3TextField,
)
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ParentManager(QWidget):
    def __init__(self):
        super().__init__()
        self._parents: list[dict] = []
        self._students: list[dict] = []
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 13, 13, 13)
        layout.setSpacing(8)

        hdr = M3Label(_("parent.title"), theme=phi, style="title_medium")
        layout.addWidget(hdr)

        # Search row
        search_row = QHBoxLayout()
        self._search_input = M3TextField(placeholder=_("parent.search_placeholder"), theme=phi)
        self._search_input.textChanged.connect(self._filter_parents)
        search_row.addWidget(self._search_input, 1)

        self._add_btn = M3Button(_("parent.add_button"), theme=phi, variant=ButtonVariant.FILLED)
        self._add_btn.clicked.connect(self._on_add_parent)
        search_row.addWidget(self._add_btn)
        layout.addLayout(search_row)

        # Splitter: parent list (left) / student links (right)
        splitter = M3Splitter(Qt.Horizontal)

        # Left: parent table
        left = M3Card(theme=phi, variant=CardVariant.ELEVATED, parent=self)
        left_layout = left.content_layout()
        left_layout.setContentsMargins(3, 3, 3, 3)

        lbl = M3Label(_("parent.list_title"), theme=phi, style="label_large")
        left_layout.addWidget(lbl)

        self._parent_table = M3TableWidget(theme=phi)
        self._parent_table.set_headers(
            [
                _("parent.table_headers"),
                _("parent.table_headers_email"),
                _("parent.table_headers_phone"),
                _("parent.table_headers_nature"),
                _("parent.table_headers_city"),
                _("parent.table_headers_id"),
            ]
        )
        self._parent_table.setColumnHidden(5, True)
        self._parent_table.horizontalHeader().setStretchLastSection(True)
        self._parent_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._parent_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._parent_table.setAlternatingRowColors(True)
        self._parent_table.itemSelectionChanged.connect(self._on_parent_selected)
        left_layout.addWidget(self._parent_table, 1)
        splitter.addWidget(left)

        # Right: students linked to selected parent
        right = M3Card(theme=phi, variant=CardVariant.ELEVATED, parent=self)
        right_layout = right.content_layout()
        right_layout.setContentsMargins(3, 3, 3, 3)

        self._right_header = M3Label(_("parent.select_prompt"), theme=phi, style="label_large")
        right_layout.addWidget(self._right_header)

        self._foyer_info = M3Label(theme=phi, style="body_small")
        self._foyer_info.setWordWrap(True)
        self._foyer_info.hide()
        right_layout.addWidget(self._foyer_info)

        # Boutons foyer
        foyer_btn_row = QHBoxLayout()
        self._edit_foyer_btn = M3Button(_("parent.edit_address"), theme=phi, variant=ButtonVariant.OUTLINED)
        self._edit_foyer_btn.clicked.connect(self._on_edit_foyer)
        self._edit_foyer_btn.hide()
        foyer_btn_row.addWidget(self._edit_foyer_btn)

        self._share_foyer_btn = M3Button(_("parent.share_address"), theme=phi, variant=ButtonVariant.OUTLINED)
        self._share_foyer_btn.clicked.connect(self._on_share_foyer)
        self._share_foyer_btn.hide()
        foyer_btn_row.addWidget(self._share_foyer_btn)

        right_layout.addLayout(foyer_btn_row)

        self._student_table = M3TableWidget(theme=phi)
        self._student_table.set_headers([_("parent.linked_students"), _("parent.linked_students_class"), _("parent.linked_students_nature")])
        self._student_table.horizontalHeader().setStretchLastSection(True)
        self._student_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._student_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._student_table.setAlternatingRowColors(True)
        right_layout.addWidget(self._student_table, 1)

        # Link/unlink row
        link_row = QHBoxLayout()
        self._link_student_combo = M3ComboBox(theme=phi)
        self._link_student_combo.setMinimumWidth(144)
        link_row.addWidget(M3Label(_("parent.link_to"), theme=phi, style="body_small"))
        link_row.addWidget(self._link_student_combo, 1)

        self._nature_combo = M3ComboBox([""] + _("parent.nature_items").split(","), theme=phi)
        link_row.addWidget(M3Label(_("parent.nature_label"), theme=phi, style="body_small"))
        link_row.addWidget(self._nature_combo)

        self._link_btn = M3Button(_("parent.link_button"), theme=phi, variant=ButtonVariant.FILLED)
        self._link_btn.clicked.connect(self._on_link)
        link_row.addWidget(self._link_btn)

        self._unlink_btn = M3Button(_("parent.unlink_button"), theme=phi, variant=ButtonVariant.TONAL)
        self._unlink_btn.clicked.connect(self._on_unlink)
        link_row.addWidget(self._unlink_btn)
        right_layout.addLayout(link_row)

        splitter.addWidget(right)
        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

    def _load_data(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()

            # All parents (type_parentutor = TRUE)
            cur.execute("""
                SELECT aec.id, aec.last_name, aec.first_name, aec.email,
                       COALESCE(aec.tel_smartphone_1, aec.tel_maison, '') AS tel,
                       par.nature,
                       foyer.city, foyer.address_line1
                FROM larcauth_aecuser aec
                JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                LEFT JOIN foyer ON foyer.id = aec.fk_foyer_id
                WHERE aec.type_parentutor = TRUE AND aec.is_active = TRUE AND par.enabled = TRUE
                ORDER BY aec.last_name, aec.first_name
            """)
            self._parents = [
                {"id": r[0], "last_name": r[1], "first_name": r[2], "email": r[3], "tel": r[4], "nature": r[5], "city": r[6] or "", "address": r[7] or ""}
                for r in cur.fetchall()
            ]

            # All students (Collège + Lycée)
            cur.execute("""
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name,
                       c.label AS classroom
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                WHERE s.enabled = TRUE AND pr.sigle IN ('PEI', 'MYP', 'DPEn', 'DPFr')
                ORDER BY aec.last_name, aec.first_name
            """)
            self._students = [{"id": r[0], "last_name": r[1], "first_name": r[2], "classroom": r[3]} for r in cur.fetchall()]

            self._populate_parents()
        except Exception as e:
            log(f"ParentManager._load_data: {e}")

    def _populate_parents(self, filter_text: str = ""):
        self._parent_table.setRowCount(0)
        ft = filter_text.lower()
        for p in self._parents:
            if ft and ft not in p["last_name"].lower() and ft not in p["first_name"].lower() and ft not in p["email"].lower():
                continue
            row = self._parent_table.rowCount()
            self._parent_table.insertRow(row)
            self._parent_table.setItem(row, 0, QTableWidgetItem(f"{p['last_name']} {p['first_name']}"))
            self._parent_table.setItem(row, 1, QTableWidgetItem(p["email"]))
            self._parent_table.setItem(row, 2, QTableWidgetItem(p["tel"]))
            self._parent_table.setItem(row, 3, QTableWidgetItem(p.get("nature", "")))
            self._parent_table.setItem(row, 4, QTableWidgetItem(p.get("city", "")))
            self._parent_table.setItem(row, 5, QTableWidgetItem(str(p["id"])))
        self._parent_table.resizeColumnsToContents()

    def _filter_parents(self, text: str):
        self._populate_parents(text)

    def _on_parent_selected(self):
        rows = self._parent_table.selectedItems()
        if not rows:
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 5).text())
        parent = next((p for p in self._parents if p["id"] == parent_id), None)
        if not parent:
            return

        # Charger les infos détaillées (y compris foyer complet)
        conn = db.server_conn
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT f.address_line1, f.address_line2, f.postal_code,
                           f.city, f.country, aec.fk_foyer_id
                    FROM larcauth_aecuser aec
                    LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                    WHERE aec.id = %s
                """,
                    (parent_id,),
                )
                r = cur.fetchone()
                if r:
                    parent["address"] = r[0] or ""
                    parent["address2"] = r[1] or ""
                    parent["postal_code"] = r[2] or ""
                    parent["city"] = r[3] or ""
                    parent["country"] = r[4] or "France"
                    parent["fk_foyer_id"] = r[5]
            except Exception as e:
                log(f"ParentManager._on_parent_selected: {e}")

        self._right_header.setText(_("parent.linked_students_title").format(name=f"{parent['last_name']} {parent['first_name']}"))

        # Afficher l'adresse complète
        addr_parts = []
        if parent.get("address"):
            addr_parts.append(parent["address"])
        if parent.get("address2"):
            addr_parts.append(parent["address2"])
        cp = parent.get("postal_code", "") or ""
        city = parent.get("city", "") or ""
        if cp or city:
            addr_parts.append(f"{cp} {city}".strip())
        if parent.get("country", "France") != "France":
            addr_parts.append(parent["country"])

        if addr_parts:
            self._foyer_info.setText(_("parent.address_prefix") + ", ".join(addr_parts))
            self._foyer_info.show()
            self._edit_foyer_btn.show()
            self._share_foyer_btn.show()
        else:
            self._foyer_info.hide()
            self._edit_foyer_btn.hide()
            self._share_foyer_btn.hide()

        self._load_links(parent_id)
        self._populate_student_combo(parent_id)

    def _load_links(self, parent_id: int):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name,
                       c.label, sp.nature
                FROM student_parent sp
                JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE sp.parent_id = %s
                ORDER BY aec.last_name, aec.first_name
            """,
                (parent_id,),
            )
            rows = cur.fetchall()
            self._student_table.setRowCount(len(rows))
            for i, (sid, ln, fn, cls, nature) in enumerate(rows):
                self._student_table.setItem(i, 0, QTableWidgetItem(f"{ln} {fn}"))
                self._student_table.setItem(i, 1, QTableWidgetItem(cls))
                self._student_table.setItem(i, 2, QTableWidgetItem(nature or ""))
            self._student_table.resizeColumnsToContents()
        except Exception as e:
            log(f"ParentManager._load_links: {e}")

    def _populate_student_combo(self, parent_id: int):
        self._link_student_combo.clear()
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name, c.label
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE s.enabled = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM student_parent sp
                      WHERE sp.student_id = s.aecuser_ptr_id AND sp.parent_id = %s
                  )
                ORDER BY aec.last_name, aec.first_name
            """,
                (parent_id,),
            )
            for sid, ln, fn, cls in cur.fetchall():
                self._link_student_combo.addItem(f"{ln} {fn} ({cls})", sid)
        except Exception as e:
            log(f"ParentManager._populate_student_combo: {e}")

    def _on_link(self):
        parent_row = self._parent_table.currentRow()
        if parent_row < 0:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_parent_selected"))
            return
        parent_id = int(self._parent_table.item(parent_row, 5).text())
        student_id = self._link_student_combo.currentData()
        if not student_id:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_student_available"))
            return
        nature = self._nature_combo.currentText() or None

        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO student_parent (student_id, parent_id, nature) VALUES (%s, %s, %s)", (student_id, parent_id, nature))
            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            audit.update_parent(parent_id, f"Lié à l'élève #{student_id}")
            conn.commit()
            self._load_links(parent_id)
            self._populate_student_combo(parent_id)
        except Exception as e:
            conn.rollback()
            log(f"ParentManager._on_link: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _on_unlink(self):
        parent_row = self._parent_table.currentRow()
        if parent_row < 0:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_parent_selected"))
            return
        parent_id = int(self._parent_table.item(parent_row, 5).text())
        student_row = self._student_table.currentRow()
        if student_row < 0:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.select_to_unlink"))
            return
        student_id_item = self._student_table.item(student_row, 0)
        if not student_id_item:
            return

        # Find student_id by name
        name = student_id_item.text()
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.aecuser_ptr_id FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                WHERE aec.last_name || ' ' || aec.first_name = %s
                AND s.s_classroom_id IN (
                    SELECT c.id FROM larcauth_classroom c
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program pr ON pr.id = l.fk_program_id
                    WHERE pr.sigle IN ('PEI', 'MYP', 'DPEn', 'DPFr')
                )
                LIMIT 1
            """,
                (name,),
            )
            r = cur.fetchone()
            if not r:
                return
            student_id = r[0]

            cur.execute("DELETE FROM student_parent WHERE student_id = %s AND parent_id = %s", (student_id, parent_id))
            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            audit.update_parent(parent_id, f"Délié de l'élève #{student_id}")
            conn.commit()
            self._load_links(parent_id)
            self._populate_student_combo(parent_id)
        except Exception as e:
            conn.rollback()
            log(f"ParentManager._on_unlink: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    # ──────────── Création d'un parent ────────────

    def _on_add_parent(self):
        """Ouvre le dialogue de création d'un nouveau parent."""
        dlg = ParentEditDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()

    # ──────────── Gestion du foyer ────────────

    def _on_edit_foyer(self):
        """Ouvre le dialogue d'édition du foyer du parent sélectionné."""
        rows = self._parent_table.selectedItems()
        if not rows:
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 5).text())
        dlg = ParentEditDialog(self, parent_id=parent_id)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()

    def _on_share_foyer(self):
        """Partage l'adresse du parent sélectionné avec un autre utilisateur."""
        rows = self._parent_table.selectedItems()
        if not rows:
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 5).text())
        parent = next((p for p in self._parents if p["id"] == parent_id), None)
        if not parent:
            return

        conn = db.server_conn
        if not conn:
            return

        try:
            cur = conn.cursor()
            # Récupérer le foyer actuel du parent
            cur.execute("SELECT fk_foyer_id FROM larcauth_aecuser WHERE id = %s", (parent_id,))
            r = cur.fetchone()
            if not r or not r[0]:
                QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_address"))
                return
            source_foyer_id = r[0]

            # Proposer une liste d'utilisateurs (parents, élèves) qui partagent
            # déjà le même foyer ou qui n'en ont pas
            cur.execute(
                """
                SELECT aec.id, aec.last_name, aec.first_name, aec.email,
                       aec.fk_foyer_id
                FROM larcauth_aecuser aec
                WHERE aec.id != %s
                  AND (aec.type_parentutor = TRUE OR aec.type_student = TRUE)
                  AND aec.is_active = TRUE
                  AND (aec.fk_foyer_id IS NULL OR aec.fk_foyer_id != %s)
                ORDER BY aec.last_name
                LIMIT 100
            """,
                (parent_id, source_foyer_id),
            )
            candidates = cur.fetchall()

            if not candidates:
                QMessageBox.information(self, _("parent.share_address"), _("parent.error.share_no_users"))
                return

            # Dialogue de sélection
            items = [f"{r[1]} {r[2]} ({r[3]}) {'⚠️ foyer#' + str(r[4]) if r[4] else '📭'}" for r in candidates]
            ids = [r[0] for r in candidates]

            from PySide6.QtWidgets import QInputDialog

            chosen, ok = QInputDialog.getItem(self, _("parent.share_address_title"), _("parent.share_address_prompt"), items, 0, False)

            if ok and chosen:
                idx = items.index(chosen)
                target_id = ids[idx]

                cur.execute("UPDATE larcauth_aecuser SET fk_foyer_id = %s WHERE id = %s", (source_foyer_id, target_id))
                cur.execute("SET LOCAL app.sync_source = 'intranet'")
                cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
                audit.update_foyer(target_id, f"Foyer partagé avec #{source_foyer_id}")
                conn.commit()
                QMessageBox.information(self, _("parent.share_address"), _("parent.share_success"))
                self._on_parent_selected()  # rafraîchir

        except Exception as e:
            conn.rollback()
            log(f"ParentManager._on_share_foyer: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def reload(self):
        self._load_data()


# ──────────────────────────────────────────────
#   ParentEditDialog — Création / édition d'un parent
# ──────────────────────────────────────────────


class ParentEditDialog(QDialog):
    """
    Dialogue de création ou d'édition d'un parent.

    Mode création (parent_id=None) :
      - Crée aecuser (type_parentutor=TRUE, ID 10001-10400)
      - Crée larcauth_parent (nature)
      - Crée ou rattache un foyer

    Mode édition (parent_id donné) :
      - Modifie aecuser (email, tel)
      - Modifie larcauth_parent (nature)
      - Modifie le foyer associé
    """

    NEXT_PARENT_ID = 10001  # Premier ID disponible pour les parents

    def __init__(self, parent=None, parent_id: int | None = None):
        """
        Args:
            parent: Widget parent Qt
            parent_id: ID aecuser existant (None = mode création)
        """
        super().__init__(parent)
        self._parent_id = parent_id
        self._existing_data: dict | None = None

        self.setWindowTitle(_("parent.edit_dialog_title") if parent_id else _("parent.add_dialog_title"))
        self.setMinimumWidth(610)
        self._init_ui()

        if parent_id:
            self._load_existing(parent_id)

    def _init_ui(self):
        """Construit le formulaire."""
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Titre
        title = M3Label(
            _("parent.edit_title") if self._parent_id else _("parent.add_title"),
            theme=phi,
            style="title_medium",
        )
        layout.addWidget(title)

        # ── Section Identité ──
        id_group = M3GroupBox(_("parent.identity_group"))
        id_group.setStyleSheet(
            f"M3GroupBox {{ font-weight: bold; font-size: 10px; "
            f"border: 1px solid {p.border}; border-radius: {theme_manager.design.radius}px; "
            f"margin-top: 8px; padding-top: 13px; }}"
            f"M3GroupBox::title {{ subcontrol-origin: margin; left: 8px; }}"
        )
        form = QFormLayout(id_group)
        form.setSpacing(3)

        self._dlg_nom = M3TextField(placeholder=_("parent.last_name_placeholder"), theme=phi)
        form.addRow(_("parent.last_name_label"), self._dlg_nom)

        self._dlg_prenom = M3TextField(placeholder=_("parent.first_name_placeholder"), theme=phi)
        form.addRow(_("parent.first_name_label"), self._dlg_prenom)

        self._dlg_email = M3TextField(placeholder=_("parent.email_placeholder"), theme=phi)
        form.addRow(_("parent.email_label"), self._dlg_email)

        self._dlg_tel = M3TextField(placeholder=_("parent.phone_placeholder"), theme=phi)
        form.addRow(_("parent.phone_label"), self._dlg_tel)

        self._dlg_nature = M3ComboBox(_("parent.nature_items").split(","), theme=phi)
        form.addRow(_("parent.nature_label_form"), self._dlg_nature)

        layout.addWidget(id_group)

        # ── Section Adresse (Foyer) ──
        addr_group = M3GroupBox(_("parent.address_group"))
        addr_group.setStyleSheet(id_group.styleSheet())
        addr_form = QFormLayout(addr_group)
        addr_form.setSpacing(3)

        self._dlg_addr1 = M3TextField(placeholder=_("parent.street_placeholder"), theme=phi)
        addr_form.addRow(_("parent.street_label"), self._dlg_addr1)

        self._dlg_addr2 = M3TextField(placeholder=_("parent.complement_placeholder"), theme=phi)
        addr_form.addRow(_("parent.complement_label"), self._dlg_addr2)

        self._dlg_cp = M3TextField(placeholder=_("parent.zip_placeholder"), theme=phi)
        addr_form.addRow(_("parent.zip_label"), self._dlg_cp)

        self._dlg_ville = M3TextField(placeholder=_("parent.city_placeholder"), theme=phi)
        addr_form.addRow(_("parent.city_label"), self._dlg_ville)

        self._dlg_pays = M3TextField(_("parent.default_country"), theme=phi)
        addr_form.addRow(_("parent.country_label"), self._dlg_pays)

        layout.addWidget(addr_group)

        # ── Boutons ──
        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_existing(self, parent_id: int):
        """Charge les données existantes pour le mode édition."""
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT aec.last_name, aec.first_name, aec.email,
                       aec.tel_smartphone_1, par.nature,
                       f.address_line1, f.address_line2, f.postal_code,
                       f.city, f.country
                FROM larcauth_aecuser aec
                JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                WHERE aec.id = %s
            """,
                (parent_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            self._existing_data = {
                "last_name": row[0],
                "first_name": row[1],
                "email": row[2],
                "tel": row[3],
                "nature": row[4],
                "addr1": row[5],
                "addr2": row[6],
                "cp": row[7],
                "city": row[8],
                "country": row[9],
            }
            # Remplir les champs
            self._dlg_nom.setText(row[0] or "")
            self._dlg_prenom.setText(row[1] or "")
            self._dlg_email.setText(row[2] or "")
            self._dlg_tel.setText(row[3] or "")
            idx = self._dlg_nature.findText(row[4] or "")
            if idx >= 0:
                self._dlg_nature.setCurrentIndex(idx)
            self._dlg_addr1.setText(row[5] or "")
            self._dlg_addr2.setText(row[6] or "")
            self._dlg_cp.setText(row[7] or "")
            self._dlg_ville.setText(row[8] or "")
            self._dlg_pays.setText(row[9] or _("parent.default_country"))
        except Exception as e:
            log(f"ParentEditDialog._load_existing: {e}")

    def _validate_and_save(self):
        """Valide et sauvegarde les données."""
        nom = self._dlg_nom.text().strip()
        prenom = self._dlg_prenom.text().strip()
        nature = self._dlg_nature.currentText().strip()

        if not nom or not prenom or not nature:
            QMessageBox.warning(self, _("parent.validation_title"), _("parent.validation_required"))
            return

        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_connection"))
            return

        try:
            cur = conn.cursor()
            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")

            if self._parent_id:
                # Mode édition : UPDATE aecuser + larcauth_parent + foyer
                self._save_existing(cur, nom, prenom, nature)
            else:
                # Mode création
                self._create_new(cur, nom, prenom, nature)

            conn.commit()
            audit.update_parent(self._parent_id or cur.lastrowid, f"{'Création' if not self._parent_id else 'Modification'} parent {nom} {prenom}")
            self.accept()

        except Exception as e:
            conn.rollback()
            log(f"ParentEditDialog._validate_and_save: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _save_existing(self, cur, nom: str, prenom: str, nature: str):
        """Sauvegarde les modifications d'un parent existant."""
        pid = self._parent_id
        email = self._dlg_email.text().strip() or None
        tel = self._dlg_tel.text().strip() or None

        # Mise à jour aecuser
        cur.execute(
            "UPDATE larcauth_aecuser SET last_name = %s, first_name = %s, "
            "email = COALESCE(%s, email), tel_smartphone_1 = COALESCE(%s, tel_smartphone_1) "
            "WHERE id = %s",
            (nom, prenom, email, tel, pid),
        )

        # Mise à jour larcauth_parent
        cur.execute("UPDATE larcauth_parent SET nature = %s WHERE aecuser_ptr_id = %s", (nature, pid))

        # Mise à jour foyer
        self._save_foyer(cur, pid)

    def _create_new(self, cur, nom: str, prenom: str, nature: str):
        """Crée un nouveau parent (aecuser + larcauth_parent + foyer) via gabarit."""
        email = self._dlg_email.text().strip() or _("parent.default_email").format(l=nom.lower(), f=prenom.lower())
        tel = self._dlg_tel.text().strip() or None
        from datetime import datetime

        now = datetime.now().isoformat()

        # Premier slot libre dans le gabarit parent
        cur.execute("""
            SELECT aecuser_ptr_id FROM larcauth_parent
            WHERE aecuser_ptr_id BETWEEN 10001 AND 10800 AND enabled = FALSE
            ORDER BY aecuser_ptr_id LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            raise Exception(_("parent.limit_reached"))
        next_id = row[0]

        cur.execute(
            """
            UPDATE larcauth_aecuser SET
                first_name = %s, last_name = %s,
                email = %s, username = %s, tel_smartphone_1 = %s,
                date_joined = %s, password = '', type_parentutor = TRUE,
                is_active = TRUE
            WHERE id = %s
        """,
            (prenom, nom, email, email, tel, now, next_id),
        )
        cur.execute(
            """
            UPDATE larcauth_parent SET enabled = TRUE, nature = %s
            WHERE aecuser_ptr_id = %s
        """,
            (nature, next_id),
        )
        cur.execute("DELETE FROM student_parent WHERE parent_id = %s", (next_id,))

        log(f"ParentEditDialog: created parent #{next_id}")
        self._save_foyer(cur, next_id)

    def _save_foyer(self, cur, aecuser_id: int):
        """Crée ou met à jour le foyer associé à un aecuser."""
        addr1 = self._dlg_addr1.text().strip() or None
        addr2 = self._dlg_addr2.text().strip() or None
        cp = self._dlg_cp.text().strip() or None
        city = self._dlg_ville.text().strip() or None
        country = self._dlg_pays.text().strip() or _("parent.default_country")

        # Vérifier si un foyer avec cette adresse existe déjà
        cur.execute(
            """
            SELECT id FROM foyer
            WHERE address_line1 IS NOT DISTINCT FROM %s
              AND postal_code IS NOT DISTINCT FROM %s
              AND city IS NOT DISTINCT FROM %s
              AND enabled = TRUE
            LIMIT 1
        """,
            (addr1, cp, city),
        )
        existing_addr = cur.fetchone()

        if existing_addr:
            # Réutiliser le foyer existant
            foyer_id = existing_addr[0]
        else:
            # Vérifier si le foyer du parent existe déjà (même ID)
            cur.execute("SELECT id FROM foyer WHERE id = %s", (aecuser_id,))
            existing = cur.fetchone()
            if existing:
                foyer_id = aecuser_id
                cur.execute(
                    """
                    UPDATE foyer SET
                        address_line1 = %s, address_line2 = %s,
                        postal_code = %s, city = %s, country = %s,
                        enabled = TRUE
                    WHERE id = %s
                """,
                    (addr1, addr2, cp, city, country, foyer_id),
                )
            else:
                foyer_id = aecuser_id
                cur.execute(
                    """
                    INSERT INTO foyer (id, address_line1, address_line2, postal_code,
                                       city, country, enabled)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                """,
                    (foyer_id, addr1, addr2, cp, city, country),
                )

        # S'assurer que aecuser pointe vers ce foyer
        cur.execute("UPDATE larcauth_aecuser SET fk_foyer_id = %s WHERE id = %s", (foyer_id, aecuser_id))
