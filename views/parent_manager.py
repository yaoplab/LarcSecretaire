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

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QComboBox, QSplitter, QDialog,
    QDialogButtonBox, QFormLayout, QGroupBox,
)
from PySide6.QtCore import Qt

from LarcSecretaire.common.database import db
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.audit import audit


class ParentManager(QWidget):
    def __init__(self):
        super().__init__()
        self._parents: list[dict] = []
        self._students: list[dict] = []
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        d = theme_manager.design

        hdr = QLabel("👪 Gestion des parents / tuteurs")
        hdr.setStyleSheet(f"font-size: {s(14)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(hdr)

        # Search row
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Rechercher un parent (nom, email)...")
        self._search_input.setStyleSheet(
            f"padding: {d.label_pad_v}px {d.btn_sm_pad_v}px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; background: {p.surface}; color: {p.text_strong};")
        self._search_input.textChanged.connect(self._filter_parents)
        search_row.addWidget(self._search_input, 1)

        self._add_btn = QPushButton("➕ Nouveau parent")
        self._add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; font-weight: bold; font-size: {s(10)}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}")
        self._add_btn.clicked.connect(self._on_add_parent)
        search_row.addWidget(self._add_btn)
        layout.addLayout(search_row)

        # Splitter: parent list (left) / student links (right)
        splitter = QSplitter(Qt.Horizontal)

        # Left: parent table
        left = QFrame()
        left.setObjectName("panel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        lbl = QLabel("Parents / tuteurs")
        lbl.setStyleSheet(f"font-weight: bold; font-size: {s(11)}px; color: {p.text_strong};")
        left_layout.addWidget(lbl)

        self._parent_table = QTableWidget()
        self._parent_table.setColumnCount(6)
        self._parent_table.setHorizontalHeaderLabels(["Nom", "Email", "Téléphone", "Nature", "Ville", "ID"])
        self._parent_table.setColumnHidden(5, True)
        self._parent_table.horizontalHeader().setStretchLastSection(True)
        self._parent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._parent_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._parent_table.setAlternatingRowColors(True)
        self._parent_table.itemSelectionChanged.connect(self._on_parent_selected)
        left_layout.addWidget(self._parent_table, 1)
        splitter.addWidget(left)

        # Right: students linked to selected parent
        right = QFrame()
        right.setObjectName("panel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self._right_header = QLabel("Sélectionnez un parent")
        self._right_header.setStyleSheet(
            f"font-weight: bold; font-size: {s(11)}px; color: {p.text_soft};")
        right_layout.addWidget(self._right_header)

        self._foyer_info = QLabel()
        self._foyer_info.setWordWrap(True)
        self._foyer_info.setStyleSheet(f"font-size: {s(9)}px; color: {p.text_soft}; padding: 4px;")
        self._foyer_info.hide()
        right_layout.addWidget(self._foyer_info)

        # Boutons foyer
        foyer_btn_row = QHBoxLayout()
        self._edit_foyer_btn = QPushButton("✏️ Modifier l'adresse")
        self._edit_foyer_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.primary}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; padding: 4px 10px; font-size: {s(9)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        self._edit_foyer_btn.clicked.connect(self._on_edit_foyer)
        self._edit_foyer_btn.hide()
        foyer_btn_row.addWidget(self._edit_foyer_btn)

        self._share_foyer_btn = QPushButton("🔗 Partager l'adresse")
        self._share_foyer_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.primary}; border: 1px solid {p.border}; "
            f"border-radius: {d.radius}px; padding: 4px 10px; font-size: {s(9)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        self._share_foyer_btn.clicked.connect(self._on_share_foyer)
        self._share_foyer_btn.hide()
        foyer_btn_row.addWidget(self._share_foyer_btn)

        right_layout.addLayout(foyer_btn_row)

        self._student_table = QTableWidget()
        self._student_table.setColumnCount(3)
        self._student_table.setHorizontalHeaderLabels(["Élève", "Classe", "Nature"])
        self._student_table.horizontalHeader().setStretchLastSection(True)
        self._student_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._student_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._student_table.setAlternatingRowColors(True)
        right_layout.addWidget(self._student_table, 1)

        # Link/unlink row
        link_row = QHBoxLayout()
        self._link_student_combo = QComboBox()
        self._link_student_combo.setMinimumWidth(200)
        self._link_student_combo.setStyleSheet(
            f"padding: 4px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; background: {p.surface}; color: {p.text_strong};")
        link_row.addWidget(QLabel("Lier à :"))
        link_row.addWidget(self._link_student_combo, 1)

        self._nature_combo = QComboBox()
        self._nature_combo.addItems(["", "père", "mère", "tuteur", "grand-parent", "autre"])
        self._nature_combo.setStyleSheet(
            f"padding: 4px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; background: {p.surface}; color: {p.text_strong};")
        link_row.addWidget(QLabel("Nature :"))
        link_row.addWidget(self._nature_combo)

        self._link_btn = QPushButton("Lier")
        self._link_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; font-weight: bold; font-size: {s(10)}px; }}"
            f"QPushButton:hover {{ background: {p.success}; }}")
        self._link_btn.clicked.connect(self._on_link)
        link_row.addWidget(self._link_btn)

        self._unlink_btn = QPushButton("Délier")
        self._unlink_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_danger}; color: white; border: none; "
            f"border-radius: {d.radius}px; padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; font-weight: bold; font-size: {s(10)}px; }}"
            f"QPushButton:hover {{ background: {p.danger}; }}")
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
                {'id': r[0], 'last_name': r[1], 'first_name': r[2],
                 'email': r[3], 'tel': r[4], 'nature': r[5],
                 'city': r[6] or '', 'address': r[7] or ''}
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
            self._students = [
                {'id': r[0], 'last_name': r[1], 'first_name': r[2], 'classroom': r[3]}
                for r in cur.fetchall()
            ]

            self._populate_parents()
        except Exception as e:
            log(f"ParentManager._load_data: {e}")

    def _populate_parents(self, filter_text: str = ""):
        self._parent_table.setRowCount(0)
        ft = filter_text.lower()
        for p in self._parents:
            if ft and ft not in p['last_name'].lower() and ft not in p['first_name'].lower() and ft not in p['email'].lower():
                continue
            row = self._parent_table.rowCount()
            self._parent_table.insertRow(row)
            self._parent_table.setItem(row, 0, QTableWidgetItem(f"{p['last_name']} {p['first_name']}"))
            self._parent_table.setItem(row, 1, QTableWidgetItem(p['email']))
            self._parent_table.setItem(row, 2, QTableWidgetItem(p['tel']))
            self._parent_table.setItem(row, 3, QTableWidgetItem(p.get('nature', '')))
            self._parent_table.setItem(row, 4, QTableWidgetItem(p.get('city', '')))
            self._parent_table.setItem(row, 5, QTableWidgetItem(str(p['id'])))
        self._parent_table.resizeColumnsToContents()

    def _filter_parents(self, text: str):
        self._populate_parents(text)

    def _on_parent_selected(self):
        rows = self._parent_table.selectedItems()
        if not rows:
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 5).text())
        parent = next((p for p in self._parents if p['id'] == parent_id), None)
        if not parent:
            return

        # Charger les infos détaillées (y compris foyer complet)
        conn = db.server_conn
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT f.address_line1, f.address_line2, f.postal_code,
                           f.city, f.country, aec.fk_foyer_id
                    FROM larcauth_aecuser aec
                    LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                    WHERE aec.id = %s
                """, (parent_id,))
                r = cur.fetchone()
                if r:
                    parent['address'] = r[0] or ''
                    parent['address2'] = r[1] or ''
                    parent['postal_code'] = r[2] or ''
                    parent['city'] = r[3] or ''
                    parent['country'] = r[4] or 'France'
                    parent['fk_foyer_id'] = r[5]
            except Exception as e:
                log(f"ParentManager._on_parent_selected: {e}")

        self._right_header.setText(f"Élèves liés à {parent['last_name']} {parent['first_name']}")

        # Afficher l'adresse complète
        addr_parts = []
        if parent.get('address'):
            addr_parts.append(parent['address'])
        if parent.get('address2'):
            addr_parts.append(parent['address2'])
        cp = parent.get('postal_code', '') or ''
        city = parent.get('city', '') or ''
        if cp or city:
            addr_parts.append(f"{cp} {city}".strip())
        if parent.get('country', 'France') != 'France':
            addr_parts.append(parent['country'])

        if addr_parts:
            self._foyer_info.setText("📍 " + ", ".join(addr_parts))
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
            cur.execute("""
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name,
                       c.label, sp.nature
                FROM student_parent sp
                JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE sp.parent_id = %s
                ORDER BY aec.last_name, aec.first_name
            """, (parent_id,))
            rows = cur.fetchall()
            self._student_table.setRowCount(len(rows))
            for i, (sid, ln, fn, cls, nature) in enumerate(rows):
                self._student_table.setItem(i, 0, QTableWidgetItem(f"{ln} {fn}"))
                self._student_table.setItem(i, 1, QTableWidgetItem(cls))
                self._student_table.setItem(i, 2, QTableWidgetItem(nature or ''))
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
            cur.execute("""
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
            """, (parent_id,))
            for sid, ln, fn, cls in cur.fetchall():
                self._link_student_combo.addItem(f"{ln} {fn} ({cls})", sid)
        except Exception as e:
            log(f"ParentManager._populate_student_combo: {e}")

    def _on_link(self):
        parent_row = self._parent_table.currentRow()
        if parent_row < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez d'abord un parent.")
            return
        parent_id = int(self._parent_table.item(parent_row, 5).text())
        student_id = self._link_student_combo.currentData()
        if not student_id:
            QMessageBox.warning(self, "Erreur", "Aucun élève disponible à lier.")
            return
        nature = self._nature_combo.currentText() or None

        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO student_parent (student_id, parent_id, nature) VALUES (%s, %s, %s)",
                (student_id, parent_id, nature)
            )
            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            audit.update_parent(parent_id, f"Lié à l'élève #{student_id}")
            conn.commit()
            self._load_links(parent_id)
            self._populate_student_combo(parent_id)
        except Exception as e:
            conn.rollback()
            log(f"ParentManager._on_link: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

    def _on_unlink(self):
        parent_row = self._parent_table.currentRow()
        if parent_row < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez d'abord un parent.")
            return
        parent_id = int(self._parent_table.item(parent_row, 5).text())
        student_row = self._student_table.currentRow()
        if student_row < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un élève à délien.dans la liste de droite.")
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
            cur.execute("""
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
            """, (name,))
            r = cur.fetchone()
            if not r:
                return
            student_id = r[0]

            cur.execute(
                "DELETE FROM student_parent WHERE student_id = %s AND parent_id = %s",
                (student_id, parent_id)
            )
            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            audit.update_parent(parent_id, f"Délié de l'élève #{student_id}")
            conn.commit()
            self._load_links(parent_id)
            self._populate_student_combo(parent_id)
        except Exception as e:
            conn.rollback()
            log(f"ParentManager._on_unlink: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

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
        parent = next((p for p in self._parents if p['id'] == parent_id), None)
        if not parent:
            return

        conn = db.server_conn
        if not conn:
            return

        try:
            cur = conn.cursor()
            # Récupérer le foyer actuel du parent
            cur.execute(
                "SELECT fk_foyer_id FROM larcauth_aecuser WHERE id = %s",
                (parent_id,))
            r = cur.fetchone()
            if not r or not r[0]:
                QMessageBox.warning(self, "Erreur",
                    "Ce parent n'a pas d'adresse à partager.")
                return
            source_foyer_id = r[0]

            # Proposer une liste d'utilisateurs (parents, élèves) qui partagent
            # déjà le même foyer ou qui n'en ont pas
            cur.execute("""
                SELECT aec.id, aec.last_name, aec.first_name, aec.email,
                       aec.fk_foyer_id
                FROM larcauth_aecuser aec
                WHERE aec.id != %s
                  AND (aec.type_parentutor = TRUE OR aec.type_student = TRUE)
                  AND aec.is_active = TRUE
                  AND (aec.fk_foyer_id IS NULL OR aec.fk_foyer_id != %s)
                ORDER BY aec.last_name
                LIMIT 100
            """, (parent_id, source_foyer_id))
            candidates = cur.fetchall()

            if not candidates:
                QMessageBox.information(self, "Partage",
                    "Aucun autre utilisateur disponible pour partager cette adresse.")
                return

            # Dialogue de sélection
            items = [f"{r[1]} {r[2]} ({r[3]}) {'⚠️ foyer#' + str(r[4]) if r[4] else '📭'}"
                     for r in candidates]
            ids = [r[0] for r in candidates]

            from PySide6.QtWidgets import QInputDialog
            chosen, ok = QInputDialog.getItem(
                self, "Partager l'adresse",
                "Sélectionnez la personne qui partagera cette adresse :",
                items, 0, False)

            if ok and chosen:
                idx = items.index(chosen)
                target_id = ids[idx]

                cur.execute(
                    "UPDATE larcauth_aecuser SET fk_foyer_id = %s WHERE id = %s",
                    (source_foyer_id, target_id))
                cur.execute("SET LOCAL app.sync_source = 'intranet'")
                cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
                audit.update_foyer(target_id, f"Foyer partagé avec #{source_foyer_id}")
                conn.commit()
                QMessageBox.information(self, "Partage",
                    "Adresse partagée !")
                self._on_parent_selected()  # rafraîchir

        except Exception as e:
            conn.rollback()
            log(f"ParentManager._on_share_foyer: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

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

        self.setWindowTitle(
            "Modifier le parent" if parent_id else "Nouveau parent")
        self.setMinimumWidth(500)
        self._init_ui()

        if parent_id:
            self._load_existing(parent_id)

    def _init_ui(self):
        """Construit le formulaire."""
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        d = theme_manager.design

        # Titre
        title = QLabel(
            "✏️ Modifier le parent" if self._parent_id else "➕ Nouveau parent")
        title.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(title)

        # ── Section Identité ──
        id_group = QGroupBox("Identité")
        id_group.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; font-size: {s(10)}px; "
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"margin-top: 8px; padding-top: 16px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}")
        form = QFormLayout(id_group)
        form.setSpacing(4)
        field_style = (
            f"padding: 4px; border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; background: {p.surface}; color: {p.text_strong};")

        self._dlg_nom = QLineEdit()
        self._dlg_nom.setStyleSheet(field_style)
        self._dlg_nom.setPlaceholderText("Nom de famille")
        form.addRow("Nom *", self._dlg_nom)

        self._dlg_prenom = QLineEdit()
        self._dlg_prenom.setStyleSheet(field_style)
        self._dlg_prenom.setPlaceholderText("Prénom")
        form.addRow("Prénom *", self._dlg_prenom)

        self._dlg_email = QLineEdit()
        self._dlg_email.setStyleSheet(field_style)
        self._dlg_email.setPlaceholderText("email@exemple.com")
        form.addRow("Email", self._dlg_email)

        self._dlg_tel = QLineEdit()
        self._dlg_tel.setStyleSheet(field_style)
        self._dlg_tel.setPlaceholderText("Téléphone portable")
        form.addRow("Téléphone", self._dlg_tel)

        self._dlg_nature = QComboBox()
        self._dlg_nature.setStyleSheet(field_style)
        self._dlg_nature.addItems(["père", "mère", "tuteur légal", "grand-parent", "autre"])
        form.addRow("Nature *", self._dlg_nature)

        layout.addWidget(id_group)

        # ── Section Adresse (Foyer) ──
        addr_group = QGroupBox("Adresse (foyer)")
        addr_group.setStyleSheet(id_group.styleSheet())
        addr_form = QFormLayout(addr_group)
        addr_form.setSpacing(4)

        self._dlg_addr1 = QLineEdit()
        self._dlg_addr1.setStyleSheet(field_style)
        self._dlg_addr1.setPlaceholderText("Numéro et rue")
        addr_form.addRow("Adresse", self._dlg_addr1)

        self._dlg_addr2 = QLineEdit()
        self._dlg_addr2.setStyleSheet(field_style)
        self._dlg_addr2.setPlaceholderText("Complément (appartement, bâtiment...)")
        addr_form.addRow("Complément", self._dlg_addr2)

        self._dlg_cp = QLineEdit()
        self._dlg_cp.setStyleSheet(field_style)
        self._dlg_cp.setPlaceholderText("Code postal")
        addr_form.addRow("CP", self._dlg_cp)

        self._dlg_ville = QLineEdit()
        self._dlg_ville.setStyleSheet(field_style)
        self._dlg_ville.setPlaceholderText("Ville")
        addr_form.addRow("Ville", self._dlg_ville)

        self._dlg_pays = QLineEdit("France")
        self._dlg_pays.setStyleSheet(field_style)
        addr_form.addRow("Pays", self._dlg_pays)

        layout.addWidget(addr_group)

        # ── Boutons ──
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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
            cur.execute("""
                SELECT aec.last_name, aec.first_name, aec.email,
                       aec.tel_smartphone_1, par.nature,
                       f.address_line1, f.address_line2, f.postal_code,
                       f.city, f.country
                FROM larcauth_aecuser aec
                JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                WHERE aec.id = %s
            """, (parent_id,))
            row = cur.fetchone()
            if not row:
                return
            self._existing_data = {
                'last_name': row[0], 'first_name': row[1], 'email': row[2],
                'tel': row[3], 'nature': row[4],
                'addr1': row[5], 'addr2': row[6], 'cp': row[7],
                'city': row[8], 'country': row[9],
            }
            # Remplir les champs
            self._dlg_nom.setText(row[0] or '')
            self._dlg_prenom.setText(row[1] or '')
            self._dlg_email.setText(row[2] or '')
            self._dlg_tel.setText(row[3] or '')
            idx = self._dlg_nature.findText(row[4] or '')
            if idx >= 0:
                self._dlg_nature.setCurrentIndex(idx)
            self._dlg_addr1.setText(row[5] or '')
            self._dlg_addr2.setText(row[6] or '')
            self._dlg_cp.setText(row[7] or '')
            self._dlg_ville.setText(row[8] or '')
            self._dlg_pays.setText(row[9] or 'France')
        except Exception as e:
            log(f"ParentEditDialog._load_existing: {e}")

    def _validate_and_save(self):
        """Valide et sauvegarde les données."""
        nom = self._dlg_nom.text().strip()
        prenom = self._dlg_prenom.text().strip()
        nature = self._dlg_nature.currentText().strip()

        if not nom or not prenom or not nature:
            QMessageBox.warning(self, "Validation",
                "Les champs Nom, Prénom et Nature sont obligatoires.")
            return

        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, "Erreur", "Non connecté au serveur.")
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
            audit.update_parent(
                self._parent_id or cur.lastrowid,
                f"{'Création' if not self._parent_id else 'Modification'} parent {nom} {prenom}"
            )
            self.accept()

        except Exception as e:
            conn.rollback()
            log(f"ParentEditDialog._validate_and_save: {e}")
            QMessageBox.critical(self, "Erreur", str(e))

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
            (nom, prenom, email, tel, pid))

        # Mise à jour larcauth_parent
        cur.execute(
            "UPDATE larcauth_parent SET nature = %s WHERE aecuser_ptr_id = %s",
            (nature, pid))

        # Mise à jour foyer
        self._save_foyer(cur, pid)

    def _create_new(self, cur, nom: str, prenom: str, nature: str):
        """Crée un nouveau parent (aecuser + larcauth_parent + foyer) via gabarit."""
        email = self._dlg_email.text().strip() or f"parent.{nom.lower()}.{prenom.lower()}@arc-en-ciel.org"
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
            raise Exception("Plus de slots parents disponibles (limite 10800)")
        next_id = row[0]

        cur.execute("""
            UPDATE larcauth_aecuser SET
                first_name = %s, last_name = %s,
                email = %s, username = %s, tel_smartphone_1 = %s,
                date_joined = %s, password = '', type_parentutor = TRUE,
                is_active = TRUE
            WHERE id = %s
        """, (prenom, nom, email, email, tel, now, next_id))
        cur.execute("""
            UPDATE larcauth_parent SET enabled = TRUE, nature = %s
            WHERE aecuser_ptr_id = %s
        """, (nature, next_id))
        cur.execute("DELETE FROM student_parent WHERE parent_id = %s", (next_id,))

        log(f"ParentEditDialog: created parent #{next_id}")
        self._save_foyer(cur, next_id)

    def _save_foyer(self, cur, aecuser_id: int):
        """Crée ou met à jour le foyer associé à un aecuser."""
        addr1 = self._dlg_addr1.text().strip() or None
        addr2 = self._dlg_addr2.text().strip() or None
        cp = self._dlg_cp.text().strip() or None
        city = self._dlg_ville.text().strip() or None
        country = self._dlg_pays.text().strip() or 'France'

        # Vérifier si un foyer avec cette adresse existe déjà
        cur.execute("""
            SELECT id FROM foyer
            WHERE address_line1 IS NOT DISTINCT FROM %s
              AND postal_code IS NOT DISTINCT FROM %s
              AND city IS NOT DISTINCT FROM %s
              AND enabled = TRUE
            LIMIT 1
        """, (addr1, cp, city))
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
                cur.execute("""
                    UPDATE foyer SET
                        address_line1 = %s, address_line2 = %s,
                        postal_code = %s, city = %s, country = %s,
                        enabled = TRUE
                    WHERE id = %s
                """, (addr1, addr2, cp, city, country, foyer_id))
            else:
                foyer_id = aecuser_id
                cur.execute("""
                    INSERT INTO foyer (id, address_line1, address_line2, postal_code,
                                       city, country, enabled)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                """, (foyer_id, addr1, addr2, cp, city, country))

        # S'assurer que aecuser pointe vers ce foyer
        cur.execute(
            "UPDATE larcauth_aecuser SET fk_foyer_id = %s WHERE id = %s",
            (foyer_id, aecuser_id))
