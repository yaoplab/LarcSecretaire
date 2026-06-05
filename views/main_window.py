from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QStackedWidget, QTabWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from LarcSecretaire.common.database import db
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from LarcSecretaire.common.network import detect_network, NetworkMode
from LarcSecretaire.common.logger import log


class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self._students: list[dict] = []
        self._classes: list[tuple] = []
        self._stats: dict = {}

        self.setWindowTitle(f"LarcSecrétariat — {session.full_name}")
        self.setMinimumSize(1100, 700)
        self._setup_ui()
        self._load_initial_data()

        # Timer rafraîchissement
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60000)
        self._refresh_timer.timeout.connect(self._update_status_bar)
        self._refresh_timer.start()

    def _style(self) -> str:
        p = theme_manager.palette
        return f"""
            QFrame#panel {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 6px; }}
            QFrame#kpi {{ background: {p.surface_variant}; border-radius: 8px; }}
            QFrame#sidebar {{ background: {p.surface}; border-right: 1px solid {p.border}; }}
            QLabel#panel_title {{ color: {p.text_strong}; font-size: {theme_manager.font_size(13)}px; font-weight: bold; }}
            QTableWidget {{ background: {p.surface}; color: {p.text_strong}; }}
            QHeaderView::section {{ background: {p.surface_variant}; color: {p.text_strong}; }}
            QTableWidget::item {{ color: {p.text_strong}; }}
        """

    def _setup_ui(self):
        self.setStyleSheet(self._style())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top bar
        top = QFrame()
        top.setObjectName("panel")
        top.setFixedHeight(48)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 4, 12, 4)

        self._title = QLabel(f"📋 LarcSecrétariat — {session.full_name}")
        self._title.setObjectName("panel_title")
        top_layout.addWidget(self._title)
        top_layout.addStretch()

        self._date_label = QLabel()
        self._date_label.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px;")
        top_layout.addWidget(self._date_label)

        self._network_label = QLabel()
        self._network_label.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px;")
        top_layout.addWidget(self._network_label)

        self._theme_btn = QPushButton("🎨")
        self._theme_btn.setFixedSize(36, 32)
        self._theme_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {theme_manager.palette.border}; "
            f"border-radius: 4px; font-size: 16px; }}"
            f"QPushButton:hover {{ background: {theme_manager.palette.surface_variant}; }}")
        self._theme_btn.clicked.connect(self._cycle_theme)
        top_layout.addWidget(self._theme_btn)

        outer.addWidget(top)

        # Main layout: sidebar + content
        main_h = QHBoxLayout()
        main_h.setContentsMargins(0, 0, 0, 0)
        main_h.setSpacing(0)

        # Sidebar
        self._sidebar = QFrame()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(220)
        self._sidebar_layout = QVBoxLayout(self._sidebar)
        self._sidebar_layout.setContentsMargins(8, 8, 8, 8)
        self._sidebar_layout.setSpacing(4)

        self._build_sidebar()
        main_h.addWidget(self._sidebar)

        # Content stack
        self._content_stack = QStackedWidget()

        # Page 0 : Tableau de bord
        self._dashboard_page = self._build_dashboard()
        self._content_stack.addWidget(self._dashboard_page)

        # Page 1 : Vue classe (à implémenter)
        self._class_page = QWidget()
        self._content_stack.addWidget(self._class_page)

        # Page 2 : Fiche élève (à implémenter)
        self._student_page = QWidget()
        self._content_stack.addWidget(self._student_page)

        main_h.addWidget(self._content_stack, 1)
        outer.addLayout(main_h, 1)

        # Status bar
        self._status_bar = QLabel()
        self._status_bar.setFixedHeight(24)
        self._status_bar.setStyleSheet(
            f"background: {theme_manager.palette.surface_variant}; "
            f"color: {theme_manager.palette.text_soft}; "
            f"font-size: {theme_manager.font_size(10)}px; padding: 2px 12px;")
        outer.addWidget(self._status_bar)

        self._update_datetime()
        self._update_status_bar()

    def _build_sidebar(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        # Vider layout
        while self._sidebar_layout.count():
            item = self._sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        def _make_btn(text, obj_name="", min_h=36):
            btn = QPushButton(text)
            btn.setMinimumHeight(min_h)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {p.text_strong}; "
                f"border: none; border-radius: 4px; "
                f"font-size: {s(10)}px; padding: 4px 8px; text-align: left; }}"
                f"QPushButton:hover {{ background: {p.surface_variant}; }}")
            if obj_name:
                btn.setObjectName(obj_name)
            return btn

        # Titre sidebar
        title = QLabel("Navigation")
        title.setStyleSheet(f"font-size: {s(11)}px; font-weight: bold; color: {p.text_strong}; padding: 4px;")
        self._sidebar_layout.addWidget(title)
        self._sidebar_layout.addSpacing(4)

        # Section Tableau de bord
        btn = _make_btn("📊 Tableau de bord", "nav_dashboard")
        btn.clicked.connect(lambda: self._content_stack.setCurrentIndex(0))
        self._sidebar_layout.addWidget(btn)

        # Section Inscriptions
        sec_title = QLabel("Inscriptions")
        sec_title.setStyleSheet(
            f"font-size: {s(9)}px; font-weight: bold; color: {p.text_disabled}; "
            f"padding: 8px 4px 2px 4px; text-transform: uppercase;")
        self._sidebar_layout.addWidget(sec_title)

        btn = _make_btn("🔍 Rechercher un élève", "nav_search")
        self._sidebar_layout.addWidget(btn)

        btn = _make_btn("➕ Nouvelle fiche")
        self._sidebar_layout.addWidget(btn)

        # Section Classes
        sec_title = QLabel("Classes")
        sec_title.setStyleSheet(
            f"font-size: {s(9)}px; font-weight: bold; color: {p.text_disabled}; "
            f"padding: 8px 4px 2px 4px;")
        self._sidebar_layout.addWidget(sec_title)

        self._class_buttons_layout = QVBoxLayout()
        self._class_buttons_layout.setSpacing(2)
        self._sidebar_layout.addLayout(self._class_buttons_layout)

        self._sidebar_layout.addStretch()

        # État réseau en bas
        self._sidebar_status = QLabel()
        self._sidebar_status.setStyleSheet(f"font-size: {s(9)}px; padding: 4px;")
        self._sidebar_status.setAlignment(Qt.AlignCenter)
        self._sidebar_layout.addWidget(self._sidebar_status)

    def _build_dashboard(self) -> QWidget:
        p = theme_manager.palette
        s = theme_manager.font_size

        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # KPIs
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)
        self._kpi_widgets = {}
        for key, label in [
            ('total', 'Total élèves'),
            ('college', 'Collège'),
            ('lycee', 'Lycée'),
            ('places', 'Places libres'),
        ]:
            f = QFrame()
            f.setObjectName("kpi")
            f.setMinimumHeight(100)
            fl = QVBoxLayout(f)
            fl.setAlignment(Qt.AlignCenter)
            v = QLabel("—")
            v.setStyleSheet(f"font-size: {s(28)}px; font-weight: bold; color: {p.primary};")
            v.setAlignment(Qt.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft};")
            l.setAlignment(Qt.AlignCenter)
            fl.addWidget(v)
            fl.addWidget(l)
            self._kpi_widgets[key] = v
            kpi_row.addWidget(f, 1)
        layout.addLayout(kpi_row)

        # Répartition par programme
        prog_title = QLabel("Répartition par programme")
        prog_title.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(prog_title)

        self._prog_table = QTableWidget()
        self._prog_table.setColumnCount(4)
        self._prog_table.setHorizontalHeaderLabels(["Programme", "Élèves actifs", "Places", "Taux remplissage"])
        self._prog_table.horizontalHeader().setStretchLastSection(True)
        self._prog_table.setMaximumHeight(200)
        self._prog_table.setAlternatingRowColors(True)
        self._prog_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._prog_table)

        # Alertes
        alert_title = QLabel("Alertes")
        alert_title.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(alert_title)

        self._alert_label = QLabel()
        self._alert_label.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; padding: 8px;")
        self._alert_label.setWordWrap(True)
        self._alert_label.setObjectName("panel")
        layout.addWidget(self._alert_label)

        layout.addStretch()
        page.setWidget(inner)
        return page

    def _load_initial_data(self):
        conn = db.server_conn
        if not conn:
            self._status_bar.setText("Non connecté au serveur.")
            return

        try:
            cur = conn.cursor()

            # Stats globales
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE enabled = TRUE) AS total_actifs,
                    COUNT(*) FILTER (WHERE enabled = FALSE) AS places_libres
                FROM larcauth_student
            """)
            r = cur.fetchone()
            total_actifs, places_libres = r if r else (0, 0)
            self._kpi_widgets['total'].setText(str(total_actifs))
            self._kpi_widgets['places'].setText(str(places_libres))

            # Par programme
            cur.execute("""
                SELECT pr.sigle,
                       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE) AS actifs,
                       COUNT(s.aecuser_ptr_id) AS total_slots
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                JOIN larcauth_student s ON s.s_classroom_id = c.id
                GROUP BY pr.sigle
                ORDER BY pr.sigle
            """)
            prog_rows = cur.fetchall()
            self._prog_table.setRowCount(len(prog_rows))
            college = lycee = 0
            for i, (sigle, actifs, slots) in enumerate(prog_rows):
                taux = f"{actifs / slots * 100:.0f}%" if slots else "—"
                self._prog_table.setItem(i, 0, QTableWidgetItem(sigle))
                self._prog_table.setItem(i, 1, QTableWidgetItem(str(actifs)))
                self._prog_table.setItem(i, 2, QTableWidgetItem(str(slots)))
                self._prog_table.setItem(i, 3, QTableWidgetItem(taux))
                if sigle in ('PEI', 'MYP'):
                    college += actifs
                elif sigle in ('DP', 'DPEn'):
                    lycee += actifs
            self._prog_table.resizeColumnsToContents()
            self._kpi_widgets['college'].setText(str(college))
            self._kpi_widgets['lycee'].setText(str(lycee))

            # Alertes
            cur.execute("""
                SELECT COUNT(*)
                FROM larcauth_student s
                WHERE s.enabled = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM larcauth_aecuser p
                      WHERE p.id = s.aecuser_ptr_id AND p.fk_parent_id IS NOT NULL
                  )
            """)
            no_parent = cur.fetchone()[0]
            self._alert_label.setText(
                f"⚠ {no_parent} élève(s) actif(s) sans parent/tuteur rattaché." if no_parent
                else "✓ Aucune alerte."
            )

            # Classes pour la sidebar
            cur.execute("""
                SELECT DISTINCT c.id, c.label, l.label AS level_label, pr.sigle
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                WHERE EXISTS (SELECT 1 FROM larcauth_student s WHERE s.s_classroom_id = c.id)
                ORDER BY pr.sigle, l.label, c.label
            """)
            classes = cur.fetchall()
            self._classes = classes
            self._populate_class_buttons()

            self._status_bar.setText("Données chargées.")

        except Exception as e:
            log(f"_load_initial_data: {e}")
            self._status_bar.setText(f"Erreur de chargement : {e}")

    def _populate_class_buttons(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        # Vider layout
        while self._class_buttons_layout.count():
            item = self._class_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_prog = ""
        for cid, label, level, sigle in self._classes:
            if sigle != current_prog:
                current_prog = sigle
                sep = QLabel(f"  {sigle}")
                sep.setStyleSheet(
                    f"font-size: {s(9)}px; font-weight: bold; color: {p.text_disabled}; "
                    f"padding: 4px 4px 0 4px;")
                self._class_buttons_layout.addWidget(sep)

            btn = QPushButton(f"  {label}")
            btn.setMinimumHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {p.text_strong}; "
                f"border: none; border-radius: 3px; "
                f"font-size: {s(9)}px; padding: 2px 8px; text-align: left; }}"
                f"QPushButton:hover {{ background: {p.surface_variant}; }}")
            btn.clicked.connect(lambda checked, c=cid: self._on_class_clicked(c))
            self._class_buttons_layout.addWidget(btn)

    def _on_class_clicked(self, class_id: int):
        self._status_bar.setText(f"Classe sélectionnée (à implémenter) — ID {class_id}")

    def _cycle_theme(self):
        themes = ['material_light', 'material_dark', 'material_contrast']
        current = theme_manager._active
        idx = (themes.index(current) + 1) % len(themes) if current in themes else 0
        theme_manager.set_active(themes[idx])
        self.setStyleSheet(self._style())
        self._build_sidebar()
        self._update_status_bar()
        self._update_datetime()

    def _update_datetime(self):
        from datetime import datetime
        now = datetime.now()
        self._date_label.setText(now.strftime("%A %d %B %Y %H:%M") + "  ")

    def _update_status_bar(self):
        net = detect_network()
        p = theme_manager.palette
        if net == NetworkMode.INTRANET:
            txt, color = "Intranet ●", p.success
        elif net == NetworkMode.INTERNET:
            txt, color = "Cloud ●", p.primary
        else:
            txt, color = "Hors ligne", p.text_disabled
        self._network_label.setText(txt)
        self._network_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: {theme_manager.font_size(11)}px;")
        self._sidebar_status.setText(txt)
        self._sidebar_status.setStyleSheet(f"font-size: {theme_manager.font_size(9)}px; color: {color};")
