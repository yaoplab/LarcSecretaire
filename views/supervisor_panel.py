from larccommon.l10n import _
from larccommon.widgets import PHI_MEDIUM, StudentCard
from LarcSecretaire.common.audit import audit
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from phibuilder.widgets import (
    M3Button,
    M3ComboBox,
    M3DialogButtonBox,
    M3Frame,
    M3HeaderView,
    M3Label,
    M3ScrollArea,
    M3StackedWidget,
    M3TableWidget,
    M3TabWidget,
    M3TextEdit,
)
from phibuilder.widgets.button import ButtonVariant
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

EVENT_TYPES = [
    ("arrival", _("event_label.arrival")),
    ("departure", _("event_label.departure")),
    ("exit", _("event_label.exit")),
    ("return", _("event_label.return")),
    ("absence", _("event_label.absence")),
    ("late", _("event_label.late")),
    ("justified", _("event_label.justified")),
]
EVENT_COLORS = {
    "arrival": "#27ae60",
    "departure": "#2980b9",
    "exit": "#e67e22",
    "return": "#2ecc71",
    "absence": "#e74c3c",
    "justified": "#95a5a6",
    "late": "#f1c40f",
}


def _event_icon(event_type: str) -> str:
    """Retourne l'icône pour un type d'événement (legacy ou hiérarchique)."""
    legacy = {"arrival": "▲", "departure": "▼", "exit": "→", "return": "←", "absence": "✕", "justified": "✓", "late": "⏰"}
    if event_type in legacy:
        return legacy[event_type]
    if event_type.startswith("Bureau BI"):
        return "🔴"
    if event_type.startswith("Médical"):
        return "🏥"
    if event_type.startswith("Sortie"):
        return "🚪"
    if event_type.startswith("Suivi"):
        return "👁"
    return "●"


def _event_color(event_type: str) -> str:
    """Retourne la couleur pour un type d'événement (legacy ou hiérarchique)."""
    legacy = {
        "arrival": "#27ae60",
        "departure": "#2980b9",
        "exit": "#e67e22",
        "return": "#2ecc71",
        "absence": "#e74c3c",
        "justified": "#95a5a6",
        "late": "#f1c40f",
    }
    if event_type in legacy:
        return legacy[event_type]
    if event_type.startswith("Bureau BI"):
        return "#d32f2f"
    if event_type.startswith("Médical"):
        return "#1976d2"
    if event_type.startswith("Sortie"):
        return "#e65100"
    if event_type.startswith("Suivi"):
        return "#f9a825"
    return "#555"


def _event_label(event_type: str) -> str:
    """Retourne le label lisible pour un type d'événement."""
    legacy = {
        "arrival": _("event_label.arrival"),
        "departure": _("event_label.departure"),
        "exit": _("event_label.exit"),
        "return": _("event_label.return"),
        "absence": _("event_label.absence"),
        "justified": _("event_label.justified"),
        "late": _("event_label.late"),
    }
    if event_type in legacy:
        return legacy[event_type]
    return f"{_event_icon(event_type)} {event_type}"


class EventDialog(QDialog):
    def __init__(self, student_id: int, student_name: str, parent=None, class_id: int | None = None):
        super().__init__(parent)
        self._student_id = student_id
        self._class_id = class_id
        self._selected_type = None
        self._selected_lieu_id = None
        self._selected_lieu_label = ""
        self._selected_termsubject_id = None
        self._selected_subject_label = ""
        self._selected_teacher_id = None
        self.setWindowTitle(_("supervisor.title").format(name=student_name))
        self.setMinimumWidth(610)
        self._init_ui()

    def _init_ui(self):
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
        d = theme_manager.design
        layout = QVBoxLayout(self)
        layout.setSpacing(d.spacing)

        info = M3Label(f"<b>{_('supervisor.student_label').format(id=self._student_id)}</b>", theme=phi, style="title_medium")
        layout.addWidget(info)

        # Lieu
        layout.addWidget(M3Label(_("supervisor.lieu_label"), theme=phi, style="body_medium"))
        self._lieu_combo = M3ComboBox(theme=phi)
        self._lieu_combo.addItem(_("supervisor.lieu_none"), None)
        self._load_lieux()
        layout.addWidget(self._lieu_combo)

        # Matière
        layout.addWidget(M3Label(_("supervisor.subject_label"), theme=phi, style="body_medium"))
        self._subject_combo = M3ComboBox(theme=phi)
        self._subject_combo.addItem(_("supervisor.subject_none"), None)
        self._load_subjects()
        self._subject_combo.currentIndexChanged.connect(self._on_subject_changed)
        layout.addWidget(self._subject_combo)

        # Professeur (lecture seule, auto-rempli)
        self._teacher_label = M3Label("", theme=phi, style="body_small")
        self._teacher_label.setStyleSheet("font-style: italic;")
        layout.addWidget(self._teacher_label)

        # Type d'événement
        layout.addWidget(M3Label(_("supervisor.type_label"), theme=phi, style="body_medium"))
        type_group = QButtonGroup(self)
        type_layout = QHBoxLayout()
        type_layout.setSpacing(3)
        for value, label in EVENT_TYPES:
            rb = QRadioButton(label)
            rb.toggled.connect(lambda checked, v=value: setattr(self, "_selected_type", v) if checked else None)
            type_group.addButton(rb)
            type_layout.addWidget(rb)
        layout.addLayout(type_layout)

        # Note
        self._note = M3TextEdit()
        self._note.setPlaceholderText(_("supervisor.note_placeholder"))
        self._note.setMaximumHeight(89)
        layout.addWidget(M3Label(_("supervisor.note_label"), theme=phi, style="body_medium"))
        layout.addWidget(self._note)

        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_lieux(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("SELECT IDLieu, Lieu FROM larcauth_lieu ORDER BY Lieu")
            for lid, label in cur.fetchall():
                self._lieu_combo.addItem(label, lid)
        except Exception as e:
            log(f"EventDialog._load_lieux: {e}")

    def _load_subjects(self):
        if not self._class_id:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT cts.id, cts.label, cts.fk_teacher_id,
                       aec.last_name || ' ' || aec.first_name AS teacher_name
                FROM larcauth_classroom_termsubject cts
                LEFT JOIN larcauth_aecuser aec ON aec.id = cts.fk_teacher_id
                WHERE cts.fk_classroom_id = %s AND cts.enabled = TRUE
                ORDER BY cts.label
            """,
                (self._class_id,),
            )
            self._subjects_data = []
            for sid, label, tid, tname in cur.fetchall():
                self._subjects_data.append({"id": sid, "label": label, "teacher_id": tid, "teacher_name": tname or ""})
                self._subject_combo.addItem(label, sid)
        except Exception as e:
            log(f"EventDialog._load_subjects: {e}")

    def _on_subject_changed(self, idx):
        idx_data = self._subject_combo.currentData()
        if idx_data is None:
            self._teacher_label.setText("")
            self._selected_termsubject_id = None
            self._selected_teacher_id = None
            self._selected_subject_label = ""
            return
        sub = next((s for s in self._subjects_data if s["id"] == idx_data), None)
        if sub:
            self._selected_termsubject_id = sub["id"]
            self._selected_teacher_id = sub["teacher_id"]
            self._selected_subject_label = sub["label"]
            if sub["teacher_name"]:
                self._teacher_label.setText(_("supervisor.teacher_label").format(name=sub["teacher_name"]))
            else:
                self._teacher_label.setText("")

    def _validate(self):
        if not self._selected_type:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("supervisor.error.no_type"))
            return
        self.accept()

    def get_data(self) -> dict:
        from datetime import datetime

        lieu_data = self._lieu_combo.currentData()
        return {
            "student_id": self._student_id,
            "event_type": self._selected_type,
            "event_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": self._note.toPlainText().strip()[:200],
            "lieu_label": self._lieu_combo.currentText() if lieu_data else "",
            "fk_lieu_id": lieu_data,
            "subject_label": self._selected_subject_label,
            "fk_termsubject_id": self._selected_termsubject_id,
            "fk_teacher_id": self._selected_teacher_id,
        }


class SupervisorPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._current_class_id = 0
        self._current_label = ""
        self._students: list[dict] = []
        self._cards: list[StudentCard] = []
        self._init_ui()

    def _init_ui(self):
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header avec titre + boutons liste / +
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 3, 0, 3)
        self._header = M3Label(_("supervisor.select_class"), theme=phi, style="title_small")
        self._header.setStyleSheet("padding: 8px;")
        hdr_row.addWidget(self._header, 1)

        hdr_row.addSpacing(8)
        self._list_btn = M3Button(_("supervisor.list_button"), theme=phi, variant=ButtonVariant.TONAL)
        self._list_btn.clicked.connect(self._on_class_list)
        self._list_btn.hide()
        hdr_row.addWidget(self._list_btn)

        hdr_row.addSpacing(5)
        # Boutons taille vignettes
        from larccommon.icons import icon as md3_icon
        from larccommon.widgets.card_config import PHI_COMPACT, PHI_LARGE, PHI_MEDIUM

        self._card_sizes = {"compact": PHI_COMPACT, "medium": PHI_MEDIUM, "large": PHI_LARGE}
        # Charger depuis la DB
        saved = getattr(session, "card_theme", "medium")
        if session.user_id:
            try:
                cur = db.server_conn.cursor()
                cur.execute(
                    "SELECT value FROM larcauth_config WHERE key = %s",
                    (f"user_{session.user_id}_card_theme",),
                )
                r = cur.fetchone()
                if r:
                    saved = r[0]
            except Exception:
                pass
        self._card_size = saved
        for key, icon_name in [("compact", "view_comfy"), ("medium", "view_module"), ("large", "dashboard")]:
            btn = QPushButton("")
            btn.setFixedSize(28, 28)
            btn.setCheckable(True)
            btn.setIcon(md3_icon(icon_name, color=theme_manager.palette.text_strong, size=16))
            btn.setToolTip(key.capitalize())
            btn.clicked.connect(lambda checked, k=key: self._on_card_size(k))
            if key == self._card_size:
                btn.setChecked(True)
            hdr_row.addWidget(btn)
        hdr_row.addSpacing(5)
        self._add_btn = M3Button("+", theme=phi, variant=ButtonVariant.FILLED)
        self._add_btn.setFixedSize(34, 34)
        self._add_btn.clicked.connect(self._on_add_student)
        self._add_btn.hide()
        hdr_row.addWidget(self._add_btn)
        hdr_row.addSpacing(3)
        layout.addLayout(hdr_row)

        self._stack = M3StackedWidget()

        # Page 0: card grid
        scroll = M3ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(M3Frame.NoFrame)
        self._cards_widget = QWidget()
        self._cards_grid = QGridLayout(self._cards_widget)
        self._cards_grid.setSpacing(5)
        scroll.setWidget(self._cards_widget)
        self._stack.addWidget(scroll)

        # Page 1: student detail
        self._stack.addWidget(self._build_detail())
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, 1)

    def _build_detail(self) -> QWidget:
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        back = M3Button(_("supervisor.back_to_class"), theme=phi, variant=ButtonVariant.TEXT)
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        layout.addWidget(back)

        self._sd_name = M3Label(theme=phi, style="title_medium")
        layout.addWidget(self._sd_name)

        tabs = M3TabWidget()
        tabs.setDocumentMode(True)

        # Tab 1: Coordonnées
        self._sd_info = M3Label(theme=phi, style="body_small")
        self._sd_info.setWordWrap(True)
        tabs.addTab(self._sd_info, _("supervisor.tab_coordinates"))

        # Tab 2: Événements
        evt_w = QWidget()
        evt_layout = QVBoxLayout(evt_w)
        evt_layout.setContentsMargins(3, 3, 3, 3)

        self._sd_events = M3TableWidget(theme=phi)
        self._sd_events.set_headers(
            [
                _("supervisor.events_table"),
                _("supervisor.events_table_type"),
                _("supervisor.events_table_lieu"),
                _("supervisor.events_table_subject"),
                _("supervisor.events_table_note"),
                _("supervisor.events_table_by"),
                _("supervisor.events_table_validated"),
            ]
        )
        hh_evt = self._sd_events.horizontalHeader()
        hh_evt.setSectionResizeMode(0, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(0, 150)
        hh_evt.setSectionResizeMode(1, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(1, 110)
        hh_evt.setSectionResizeMode(2, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(2, 89)
        hh_evt.setSectionResizeMode(3, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(3, 89)
        hh_evt.setSectionResizeMode(4, M3HeaderView.Stretch)
        hh_evt.setSectionResizeMode(5, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(5, 120)
        hh_evt.setSectionResizeMode(6, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(6, 55)
        self._sd_events.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._sd_events.setSelectionBehavior(M3TableWidget.SelectRows)
        self._sd_events.setAlternatingRowColors(True)
        evt_layout.addWidget(self._sd_events, 1)

        self._sd_add_btn = M3Button(_("supervisor.add_event"), theme=phi, variant=ButtonVariant.FILLED)
        self._sd_add_btn.clicked.connect(self._on_add_event)
        evt_layout.addWidget(self._sd_add_btn)

        tabs.addTab(evt_w, _("supervisor.tab_events"))
        layout.addWidget(tabs, 1)
        return w

    def reload(self):
        if self._current_class_id:
            self._load_students()
            self._load_presence()

    def load_class(self, class_id: int, class_label: str):
        self._current_class_id = class_id
        self._current_label = class_label
        self._header.setText(f"{class_label}")
        self._list_btn.show()
        self._add_btn.show()
        self._stack.setCurrentIndex(0)
        self._load_students()
        self._load_presence()

    def _on_add_student(self):
        """Ouvre le formulaire de création d'élève pour cette classe."""
        from LarcSecretaire.views.student_form import StudentCreateDialog

        dlg = StudentCreateDialog(self, preselected_class=self._current_class_id)
        dlg.exec()
        if dlg.get_data():
            self._load_students()
            self._load_presence()

    def _load_students(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                WHERE s.s_classroom_id = %s AND s.enabled = TRUE
                ORDER BY aec.last_name, aec.first_name
            """,
                (self._current_class_id,),
            )
            self._students = [{"id": r[0], "last_name": r[1], "first_name": r[2]} for r in cur.fetchall()]
        except Exception as e:
            log(f"SupervisorPanel._load_students: {e}")
            self._students = []

        self._rebuild_cards()

    def _rebuild_cards(self):
        for i in reversed(range(self._cards_grid.count())):
            w = self._cards_grid.itemAt(i).widget()
            if w:
                w.deleteLater()
        self._cards = []
        cfg = self._card_sizes.get(self._card_size, PHI_MEDIUM)
        card_w = cfg.card_w
        cols = max(1, self.width() // (card_w + 10))
        for i, s in enumerate(self._students):
            card = StudentCard(s["id"], s["last_name"], s["first_name"], cfg)
            card.clicked.connect(self._on_student_clicked)
            self._cards_grid.addWidget(card, i // cols, i % cols)
            self._cards.append(card)

    def _load_presence(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            from datetime import date

            today = date.today().isoformat()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT se.student_id,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM student_event e2
                           WHERE e2.student_id = se.student_id
                             AND DATE(e2.event_at) = %s
                              AND (e2.event_type = 'absence' OR e2.event_type ILIKE 'Suivi > Absence%%')
                              AND e2.validated_by IS NULL
                       ) THEN 'ABSENT'
                       WHEN EXISTS (
                           SELECT 1 FROM student_event e3
                           WHERE e3.student_id = se.student_id
                             AND DATE(e3.event_at) = %s
                             AND e3.event_type != 'absence' AND e3.event_type NOT ILIKE 'Suivi > Absence%%'
                       ) THEN 'PRESENT'
                       ELSE 'UNKNOWN' END
                FROM larcauth_student s
                LEFT JOIN student_event se ON se.student_id = s.aecuser_ptr_id
                    AND DATE(se.event_at) = %s
                WHERE s.s_classroom_id = %s AND s.enabled = TRUE
                GROUP BY se.student_id
            """,
                (today, today, today, self._current_class_id),
            )
            pmap = {}
            for r in cur.fetchall():
                pmap[r[0]] = r[1]
            for card in self._cards:
                st = pmap.get(card._sid, "UNKNOWN")
                if st == "PRESENT":
                    card.set_status(_("supervisor.status_present"), "#27ae60")
                    card.set_absent(False)
                elif st == "ABSENT":
                    card.set_status(_("supervisor.status_absent"), "#e74c3c")
                    card.set_absent(True)
                else:
                    card.set_status(_("supervisor.status_unknown"), "#95a5a6")
                    card.set_absent(False)
        except Exception as e:
            log(f"SupervisorPanel._load_presence: {e}")

    def _on_card_size(self, key: str):
        self._card_size = key
        session.card_theme = key
        if session.user_id:
            try:
                cur = db.server_conn.cursor()
                cur.execute(
                    "INSERT INTO larcauth_config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    (f"user_{session.user_id}_card_theme", key),
                )
                db.server_conn.commit()
            except Exception:
                pass
        self._rebuild_cards()
        self._load_presence()
        for btn in self.findChildren(QPushButton):
            if btn.toolTip() and btn.toolTip().lower() in self._card_sizes:
                btn.setChecked(btn.toolTip().lower() == key)

    def _on_student_clicked(self, student_id: int):
        s = next((s for s in self._students if s["id"] == student_id), None)
        if not s:
            return
        from LarcSecretaire.views.student_form import StudentEditDialog

        dlg = StudentEditDialog(s, self)
        if dlg.exec():
            self._load_students()
            self._load_presence()

    def _load_events(self, student_id: int):
        conn = db.server_conn
        if not conn:
            return
        try:
            from psycopg2 import errors as pg_errors

            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT se.event_at, se.event_type, se.note,
                           aec.last_name || ' ' || aec.first_name AS author,
                           CASE WHEN se.validated_by IS NOT NULL THEN '✓' ELSE '—' END,
                           se.event_id,
                           COALESCE(se.lieu_label, '') AS lieu_label,
                           COALESCE(se.subject_label, '') AS subject_label
                    FROM student_event se
                    JOIN larcauth_aecuser aec ON aec.id = se.created_by
                    WHERE se.student_id = %s
                    ORDER BY se.event_at DESC LIMIT 50
                """,
                    (student_id,),
                )
            except pg_errors.UndefinedColumn:
                cur.execute(
                    """
                    SELECT se.event_at, se.event_type, se.note,
                           aec.last_name || ' ' || aec.first_name AS author,
                           CASE WHEN se.validated_by IS NOT NULL THEN '✓' ELSE '—' END,
                           se.event_id,
                           '' AS lieu_label,
                           '' AS subject_label
                    FROM student_event se
                    JOIN larcauth_aecuser aec ON aec.id = se.created_by
                    WHERE se.student_id = %s
                    ORDER BY se.event_at DESC LIMIT 50
                """,
                    (student_id,),
                )
            rows = cur.fetchall()
            self._sd_events.setRowCount(len(rows))
            for i, row in enumerate(rows):
                evt_at = row[0]
                etype = row[1]
                note = row[2]
                author = row[3]
                validated = row[4]
                lieu = row[6] or ""
                matiere = row[7] or ""
                color = _event_color(etype)
                label = _event_label(etype)
                self._sd_events.setItem(i, 0, QTableWidgetItem(str(evt_at)[:16]))
                it = QTableWidgetItem(label)
                it.setForeground(QColor(color))
                self._sd_events.setItem(i, 1, it)
                self._sd_events.setItem(i, 2, QTableWidgetItem(lieu))
                self._sd_events.setItem(i, 3, QTableWidgetItem(matiere))
                self._sd_events.setItem(i, 4, QTableWidgetItem(note or ""))
                self._sd_events.setItem(i, 5, QTableWidgetItem(author))
                self._sd_events.setItem(i, 6, QTableWidgetItem(validated))
        except Exception as e:
            log(f"SupervisorPanel._load_events: {e}")

    def _on_add_event(self):
        name = self._sd_name.text()
        sid = next((s["id"] for s in self._students if f"{s['last_name']} {s['first_name']}" == name), 0)
        if not sid:
            return
        dlg = EventDialog(sid, name, self, class_id=self._current_class_id)
        if dlg.exec():
            data = dlg.get_data()
            conn = db.server_conn
            if not conn:
                QMessageBox.warning(self, _("common.dialog.error_title"), _("student_form.error.no_connection"))
                return
            try:
                from psycopg2 import errors as pg_errors

                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO student_event "
                        "(student_id, event_type, event_at, note, lieu_label, fk_lieu_id, "
                        " subject_label, fk_termsubject_id, fk_teacher_id, source, created_by) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            data["student_id"],
                            data["event_type"],
                            data["event_at"],
                            data["note"],
                            data.get("lieu_label", ""),
                            data.get("fk_lieu_id"),
                            data.get("subject_label", ""),
                            data.get("fk_termsubject_id"),
                            data.get("fk_teacher_id"),
                            "intranet",
                            session.user_id,
                        ),
                    )
                except pg_errors.UndefinedColumn:
                    cur.execute(
                        "INSERT INTO student_event (student_id, event_type, event_at, note, source, created_by) VALUES (%s, %s, %s, %s, %s, %s)",
                        (data["student_id"], data["event_type"], data["event_at"], data["note"], "intranet", session.user_id),
                    )
                cur.execute("SET LOCAL app.sync_source = 'intranet'")
                cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
                audit.add_event(data["student_id"], data["event_type"], data.get("note", ""))
                conn.commit()
                self._load_events(sid)
                self._load_presence()
            except Exception as e:
                conn.rollback()
                log(f"SupervisorPanel._on_add_event: {e}")
                QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _on_class_list(self):
        if not hasattr(self, "_current_class_id") or not self._current_class_id:
            return
        dlg = ClassListDialog(self._current_class_id, self._current_label, self)
        dlg.exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_cards") and self._cards:
            cols = max(1, self.width() // 175)
            for i, card in enumerate(self._cards):
                self._cards_grid.addWidget(card, i // cols, i % cols)


class ClassListDialog(QDialog):
    def __init__(self, class_id: int, class_label: str, parent=None):
        super().__init__(parent)
        self._class_id = class_id
        self._class_label = class_label
        self.setWindowTitle(_("supervisor.list_title").format(label=class_label))
        self.setMinimumSize(610, 377)
        self._init_ui()
        self._load()

    def _init_ui(self):
        phi = theme_manager.phibuilder.theme if theme_manager.phibuilder else None
        p = theme_manager.palette
        layout = QVBoxLayout(self)
        layout.setSpacing(theme_manager.design.spacing)

        hdr = M3Label(_("supervisor.list_header").format(name=self._class_label), theme=phi, style="title_small")
        layout.addWidget(hdr)

        self._table = M3TableWidget(theme=phi)
        self._table.set_headers(["", _("supervisor.list_table_num"), _("supervisor.list_table_last_name"), _("supervisor.list_table_first_name")])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 34)
        self._table.setColumnWidth(1, 36)
        self._table.setColumnWidth(2, 180)
        self._table.verticalHeader().hide()
        self._table.setSelectionMode(M3TableWidget.NoSelection)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = M3Button(_("supervisor.close_button"), theme=phi, variant=ButtonVariant.OUTLINED)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load(self):
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT s.id, a.last_name, a.first_name "
                "FROM larcauth_student s "
                "JOIN larcauth_aecuser a ON a.id = s.id "
                "WHERE s.s_classroom_id = %s AND s.enabled = TRUE "
                "ORDER BY a.last_name, a.first_name",
                (self._class_id,),
            )
            rows = cur.fetchall()
            self._table.setRowCount(len(rows))
            for i, (sid, ln, fn) in enumerate(rows):
                cb = QCheckBox()
                cw = QWidget()
                cl = QHBoxLayout(cw)
                cl.setContentsMargins(3, 0, 0, 0)
                cl.addWidget(cb)
                self._table.setCellWidget(i, 0, cw)
                _, slot = divmod(sid, 100)
                self._table.setItem(i, 1, QTableWidgetItem(str(slot).zfill(2)))
                self._table.setItem(i, 2, QTableWidgetItem(ln or ""))
                self._table.setItem(i, 3, QTableWidgetItem(fn or ""))
        except Exception as e:
            log(f"ClassListDialog._load: {e}")
