from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QDialogButtonBox, QRadioButton,
    QButtonGroup, QTextEdit, QStackedWidget, QTabWidget, QCheckBox,
)
import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QPainter

from LarcSecretaire.common.database import db
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.audit import audit

PHOTOS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 '..', 'LarcSuperviseur', 'photos'))

EVENT_TYPES = [
    ('arrival', '▲ Arrivée'), ('departure', '▼ Départ'), ('exit', '→ Sortie'),
    ('return', '← Retour'), ('absence', '✕ Absence'), ('late', '⏰ Retard'),
    ('justified', '✓ Justifié'),
]
EVENT_COLORS = {
    'arrival': '#27ae60', 'departure': '#2980b9', 'exit': '#e67e22',
    'return': '#2ecc71', 'absence': '#e74c3c', 'justified': '#95a5a6',
    'late': '#f1c40f',
}


def _event_icon(event_type: str) -> str:
    """Retourne l'icône pour un type d'événement (legacy ou hiérarchique)."""
    legacy = {'arrival': '▲', 'departure': '▼', 'exit': '→', 'return': '←',
              'absence': '✕', 'justified': '✓', 'late': '⏰'}
    if event_type in legacy:
        return legacy[event_type]
    if event_type.startswith('Bureau BI'):
        return '🔴'
    if event_type.startswith('Médical'):
        return '🏥'
    if event_type.startswith('Sortie'):
        return '🚪'
    if event_type.startswith('Suivi'):
        return '👁'
    return '●'


def _event_color(event_type: str) -> str:
    """Retourne la couleur pour un type d'événement (legacy ou hiérarchique)."""
    legacy = {'arrival': '#27ae60', 'departure': '#2980b9', 'exit': '#e67e22',
              'return': '#2ecc71', 'absence': '#e74c3c', 'justified': '#95a5a6',
              'late': '#f1c40f'}
    if event_type in legacy:
        return legacy[event_type]
    if event_type.startswith('Bureau BI'):
        return '#d32f2f'
    if event_type.startswith('Médical'):
        return '#1976d2'
    if event_type.startswith('Sortie'):
        return '#e65100'
    if event_type.startswith('Suivi'):
        return '#f9a825'
    return '#555'


def _event_label(event_type: str) -> str:
    """Retourne le label lisible pour un type d'événement."""
    legacy = {'arrival': '▲ Arrivée', 'departure': '▼ Départ', 'exit': '→ Sortie',
              'return': '← Retour', 'absence': '✕ Absence', 'justified': '✓ Justifié',
              'late': '⏰ Retard'}
    if event_type in legacy:
        return legacy[event_type]
    return f"{_event_icon(event_type)} {event_type}"


class StudentCard(QFrame):
    clicked = Signal(int)

    def __init__(self, student_id: int, last_name: str, first_name: str):
        super().__init__()
        self._sid = student_id
        self._last_name = last_name
        self._first_name = first_name
        self.setFrameShape(QFrame.StyledPanel)
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        self._style_idle = (
            f"StudentCard {{ background: {p.surface}; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius_lg}px; padding: 8px; }}"
            f"StudentCard:hover {{ background: {p.surface_variant}; border-color: {p.outline}; }}"
        )
        self._style_absent = (
            f"StudentCard {{ background: {p.error_container}; border: 2px solid {p.error}; "
            f"border-radius: {d.radius_lg}px; padding: 8px; }}"
            f"StudentCard:hover {{ background: #FFC9C0; border-color: {p.error}; }}"
        )
        self.setStyleSheet(self._style_idle)
        self.setFixedSize(160, 200)
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()

    def _build_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)
        d = theme_manager.design

        self._name_label = QLabel()
        self._name_label.setTextFormat(Qt.RichText)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setText(
            f"<b style='font-size:{s(13)}px'>{self._last_name}</b><br>"
            f"<span style='font-size:{s(12)}px; color:{p.text_soft}'>{self._first_name}</span>"
        )
        layout.addWidget(self._name_label)
        layout.addStretch()

        badge = QFrame()
        badge.setFixedSize(110, 110)
        badge.setStyleSheet(f"background: {p.primary_container}; border-radius: 12px;")
        bl = QVBoxLayout(badge)
        bl.setAlignment(Qt.AlignCenter)
        bl.setContentsMargins(0, 0, 0, 0)
        self._photo = QLabel()
        self._photo.setFixedSize(100, 100)
        self._photo.setAlignment(Qt.AlignCenter)
        px = QPixmap(os.path.join(PHOTOS_DIR, f"{self._sid}.png"))
        if px.isNull():
            px = self._make_avatar()
        else:
            px = px.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._photo.setPixmap(px)
        bl.addWidget(self._photo)
        layout.addWidget(badge, 0, Qt.AlignCenter)
        layout.addSpacing(10)

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold;")
        layout.addWidget(self._status_label)

    def _make_avatar(self) -> QPixmap:
        initials = (self._last_name[:1] + self._first_name[:1]).upper() or '?'
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
        c = colors[hash(self._last_name + self._first_name) % len(colors)]
        px = QPixmap(100, 100)
        px.fill(Qt.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(c))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, 100, 100)
        p.setPen(QColor('#fff'))
        f = p.font()
        f.setPixelSize(36)
        f.setBold(True)
        p.setFont(f)
        p.drawText(px.rect(), Qt.AlignCenter, initials)
        p.end()
        return px

    def mousePressEvent(self, event):
        self.clicked.emit(self._sid)
        super().mousePressEvent(event)

    def set_status(self, text: str, color: str):
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(10)}px; font-weight: bold; color: {color};")

    def set_absent(self, absent: bool):
        self.setStyleSheet(self._style_absent if absent else self._style_idle)


class EventDialog(QDialog):
    def __init__(self, student_id: int, student_name: str, parent=None):
        super().__init__(parent)
        self._student_id = student_id
        self._selected_type = None
        self.setWindowTitle(f"Événement — {student_name}")
        self.setMinimumWidth(500)
        self._init_ui()

    def _init_ui(self):
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        info = QLabel(f"<b>Élève #{self._student_id}</b>")
        info.setStyleSheet(f"font-size: {s(14)}px; padding: 10px;")
        layout.addWidget(info)

        type_group = QButtonGroup(self)
        type_layout = QHBoxLayout()
        type_layout.setSpacing(4)
        for value, label in EVENT_TYPES:
            rb = QRadioButton(label)
            rb.toggled.connect(lambda checked, v=value: setattr(self, '_selected_type', v) if checked else None)
            type_group.addButton(rb)
            type_layout.addWidget(rb)
        layout.addWidget(QLabel("<b>Type d'événement :</b>"))
        layout.addLayout(type_layout)

        self._note = QTextEdit()
        self._note.setPlaceholderText("Note optionnelle (200 caractères max)")
        self._note.setMaximumHeight(80)
        layout.addWidget(QLabel("<b>Note :</b>"))
        layout.addWidget(self._note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self):
        if not self._selected_type:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un type d'événement.")
            return
        self.accept()

    def get_data(self) -> dict:
        from datetime import datetime
        return {
            'student_id': self._student_id,
            'event_type': self._selected_type,
            'event_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'note': self._note.toPlainText().strip()[:200],
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
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        d = theme_manager.design

        # Header avec titre + boutons liste / +
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 4, 0, 4)
        self._header = QLabel("Sélectionnez une classe dans la sidebar")
        self._header.setStyleSheet(
            f"padding: 8px; font-size: {s(13)}px; font-weight: bold; color: {p.text_strong};")
        hdr_row.addWidget(self._header, 1)

        hdr_row.addSpacing(8)
        self._list_btn = QPushButton("📋 Liste")
        self._list_btn.setFixedHeight(36)
        self._list_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_primary}; color: white; border: none; "
            f"border-radius: {d.radius}px; font-size: {s(11)}px; font-weight: bold; padding: 0 12px; }}"
            f"QPushButton:hover {{ background: {p.primary}; }}")
        self._list_btn.clicked.connect(self._on_class_list)
        self._list_btn.hide()
        hdr_row.addWidget(self._list_btn)

        hdr_row.addSpacing(6)
        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(36, 36)
        self._add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.button_success}; color: white; border: none; "
            f"border-radius: {d.radius}px; font-size: {s(20)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.success}; }}")
        self._add_btn.clicked.connect(self._on_add_student)
        self._add_btn.hide()
        hdr_row.addWidget(self._add_btn)
        hdr_row.addSpacing(4)
        layout.addLayout(hdr_row)

        self._stack = QStackedWidget()

        # Page 0: card grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._cards_widget = QWidget()
        self._cards_grid = QGridLayout(self._cards_widget)
        self._cards_grid.setSpacing(6)
        scroll.setWidget(self._cards_widget)
        self._stack.addWidget(scroll)

        # Page 1: student detail
        self._stack.addWidget(self._build_detail())
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, 1)

    def _build_detail(self) -> QWidget:
        p = theme_manager.palette
        s = theme_manager.font_size
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        d = theme_manager.design

        back = QPushButton("← Retour à la classe")
        back.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.primary}; border: none; "
            f"font-weight: bold; font-size: {s(10)}px; padding: 2px 6px; }}"
            f"QPushButton:hover {{ color: {p.active}; }}")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        layout.addWidget(back)

        self._sd_name = QLabel()
        self._sd_name.setStyleSheet(f"font-size: {s(14)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(self._sd_name)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # Tab 1: Coordonnées
        self._sd_info = QLabel()
        self._sd_info.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft};")
        self._sd_info.setWordWrap(True)
        tabs.addTab(self._sd_info, "Coordonnées")

        # Tab 2: Événements
        evt_w = QWidget()
        evt_layout = QVBoxLayout(evt_w)
        evt_layout.setContentsMargins(4, 4, 4, 4)

        self._sd_events = QTableWidget()
        self._sd_events.setColumnCount(7)
        self._sd_events.setHorizontalHeaderLabels(["Heure", "Type", "Matière", "Lieu", "Note", "Par", "Validé"])
        self._sd_events.horizontalHeader().setStretchLastSection(True)
        self._sd_events.setEditTriggers(QTableWidget.NoEditTriggers)
        self._sd_events.setSelectionBehavior(QTableWidget.SelectRows)
        self._sd_events.setAlternatingRowColors(True)
        evt_layout.addWidget(self._sd_events, 1)

        self._sd_add_btn = QPushButton("➕ Ajouter un événement")
        self._sd_add_btn.setMinimumHeight(40)
        self._sd_add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; font-weight: bold; font-size: {s(12)}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}")
        self._sd_add_btn.clicked.connect(self._on_add_event)
        evt_layout.addWidget(self._sd_add_btn)

        tabs.addTab(evt_w, "Événements")
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
            cur.execute("""
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                WHERE s.s_classroom_id = %s AND s.enabled = TRUE
                ORDER BY aec.last_name, aec.first_name
            """, (self._current_class_id,))
            self._students = [{'id': r[0], 'last_name': r[1], 'first_name': r[2]} for r in cur.fetchall()]
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
        cols = max(1, self.width() // 175)
        for i, s in enumerate(self._students):
            card = StudentCard(s['id'], s['last_name'], s['first_name'])
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
            cur.execute("""
                SELECT se.student_id,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM student_event e2
                           WHERE e2.student_id = se.student_id
                             AND DATE(e2.event_at) = %s
                              AND e2.event_type = 'absence' AND e2.validated_by IS NULL
                       ) THEN 'ABSENT'
                       WHEN EXISTS (
                           SELECT 1 FROM student_event e3
                           WHERE e3.student_id = se.student_id
                             AND DATE(e3.event_at) = %s
                             AND e3.event_type != 'absence'
                       ) THEN 'PRESENT'
                       ELSE 'UNKNOWN' END
                FROM larcauth_student s
                LEFT JOIN student_event se ON se.student_id = s.aecuser_ptr_id
                    AND DATE(se.event_at) = %s
                WHERE s.s_classroom_id = %s AND s.enabled = TRUE
                GROUP BY se.student_id
            """, (today, today, today, self._current_class_id))
            pmap = {}
            for r in cur.fetchall():
                pmap[r[0]] = r[1]
            for card in self._cards:
                st = pmap.get(card._sid, 'UNKNOWN')
                if st == 'PRESENT':
                    card.set_status('✓ Présent', '#27ae60')
                    card.set_absent(False)
                elif st == 'ABSENT':
                    card.set_status('✕ Absent', '#e74c3c')
                    card.set_absent(True)
                else:
                    card.set_status('— Inconnu', '#95a5a6')
                    card.set_absent(False)
        except Exception as e:
            log(f"SupervisorPanel._load_presence: {e}")

    def _on_student_clicked(self, student_id: int):
        s = next((s for s in self._students if s['id'] == student_id), None)
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
            cur = conn.cursor()
            try:
                cur.execute("""
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
                """, (student_id,))
            except Exception:
                cur.execute("""
                    SELECT se.event_at, se.event_type, se.note,
                           aec.last_name || ' ' || aec.first_name AS author,
                           CASE WHEN se.validated_by IS NOT NULL THEN '✓' ELSE '—' END,
                           se.event_id
                    FROM student_event se
                    JOIN larcauth_aecuser aec ON aec.id = se.created_by
                    WHERE se.student_id = %s
                    ORDER BY se.event_at DESC LIMIT 50
                """, (student_id,))
            rows = cur.fetchall()
            has_extra = len(rows) > 0 and len(rows[0]) >= 8
            self._sd_events.setRowCount(len(rows))
            for i, row in enumerate(rows):
                evt_at    = row[0]
                etype     = row[1]
                note      = row[2]
                author    = row[3]
                validated = row[4]
                lieu      = row[6] if has_extra else ''
                matiere   = row[7] if has_extra else ''
                color = _event_color(etype)
                label = _event_label(etype)
                self._sd_events.setItem(i, 0, QTableWidgetItem(str(evt_at)[:16]))
                it = QTableWidgetItem(label)
                it.setForeground(QColor(color))
                self._sd_events.setItem(i, 1, it)
                self._sd_events.setItem(i, 2, QTableWidgetItem(matiere))
                self._sd_events.setItem(i, 3, QTableWidgetItem(lieu))
                self._sd_events.setItem(i, 4, QTableWidgetItem(note or ''))
                self._sd_events.setItem(i, 5, QTableWidgetItem(author))
                self._sd_events.setItem(i, 6, QTableWidgetItem(validated))
            self._sd_events.resizeColumnsToContents()
        except Exception as e:
            log(f"SupervisorPanel._load_events: {e}")

    def _on_add_event(self):
        name = self._sd_name.text()
        sid = next((s['id'] for s in self._students
                    if f"{s['last_name']} {s['first_name']}" == name), 0)
        if not sid:
            return
        dlg = EventDialog(sid, name, self)
        if dlg.exec():
            data = dlg.get_data()
            conn = db.server_conn
            if not conn:
                QMessageBox.warning(self, "Erreur", "Non connecté au serveur.")
                return
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO student_event (student_id, event_type, event_at, note, source, created_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (data['student_id'], data['event_type'], data['event_at'],
                     data['note'], 'intranet', session.user_id)
                )
                conn.commit()
                audit.add_event(data['student_id'], data['event_type'], data.get('note', ''))
                self._load_events(sid)
                self._load_presence()
            except Exception as e:
                conn.rollback()
                log(f"SupervisorPanel._on_add_event: {e}")
                QMessageBox.critical(self, "Erreur", str(e))

    def _on_class_list(self):
        if not hasattr(self, '_current_class_id') or not self._current_class_id:
            return
        dlg = ClassListDialog(self._current_class_id, self._current_label, self)
        dlg.exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_cards') and self._cards:
            cols = max(1, self.width() // 175)
            for i, card in enumerate(self._cards):
                self._cards_grid.addWidget(card, i // cols, i % cols)


class ClassListDialog(QDialog):
    def __init__(self, class_id: int, class_label: str, parent=None):
        super().__init__(parent)
        self._class_id = class_id
        self.setWindowTitle(f"Liste — {class_label}")
        self.setMinimumSize(500, 400)
        self._init_ui()
        self._load()

    def _init_ui(self):
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setSpacing(d.spacing)

        hdr = QLabel(f"Liste des élèves — {self.windowTitle().replace('Liste — ', '')}")
        hdr.setStyleSheet(f"font-size: {s(13)}px; font-weight: bold; padding: 4px 0; color: {p.text_strong};")
        layout.addWidget(hdr)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["", "N°", "Nom", "Prénom"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(1, 36)
        self._table.setColumnWidth(2, 180)
        self._table.verticalHeader().hide()
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {p.border}; gridline-color: {p.border_light}; "
            f"font-size: {s(11)}px; }}"
            f"QTableWidget::item {{ padding: 4px; }}"
            f"QHeaderView::section {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"font-weight: bold; padding: 4px; border: none; }}")
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Fermer")
        close_btn.setStyleSheet(
            f"QPushButton {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"border: 1px solid {p.border}; border-radius: {d.radius}px; "
            f"font-size: {s(11)}px; padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; }}"
            f"QPushButton:hover {{ background: {p.card_hover}; }}")
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
                (self._class_id,))
            rows = cur.fetchall()
            self._table.setRowCount(len(rows))
            for i, (sid, ln, fn) in enumerate(rows):
                cb = QCheckBox()
                cw = QWidget()
                cl = QHBoxLayout(cw)
                cl.setContentsMargins(4, 0, 0, 0)
                cl.addWidget(cb)
                self._table.setCellWidget(i, 0, cw)
                _, slot = divmod(sid, 100)
                self._table.setItem(i, 1, QTableWidgetItem(str(slot).zfill(2)))
                self._table.setItem(i, 2, QTableWidgetItem(ln or ''))
                self._table.setItem(i, 3, QTableWidgetItem(fn or ''))
        except Exception as e:
            log(f"ClassListDialog._load: {e}")
