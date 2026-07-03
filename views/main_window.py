from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QStackedWidget, QTabWidget, QDialog,
    QApplication, QMenu,
)
from PySide6.QtCore import Qt, QTimer, QMargins, QEvent
from PySide6.QtGui import QColor, QPainter, QFont, QBrush
from PySide6.QtCharts import (
    QChart, QChartView,
    QBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis,
)

from LarcSecretaire.common.database import db
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager, QssHelper
from LarcSecretaire.common.network import detect_network, NetworkMode
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.audit import audit
from LarcSecretaire.views.supervisor_panel import SupervisorPanel
from LarcSecretaire.views.parent_manager import ParentManager
from LarcSecretaire.views.student_form import StudentForm


class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self._students: list[dict] = []
        self._classes: list[tuple] = []
        self._stats: dict = {}

        self.setWindowTitle(f"LarcSecrétariat — {session.full_name}")
        self.setMinimumSize(987, 610)
        self._setup_ui()
        self._load_initial_data()

        # Timer rafraîchissement
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60000)
        self._refresh_timer.timeout.connect(self._update_status_bar)
        self._refresh_timer.start()

        # Timer inactivité (10 min → fermeture)
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(600_000)
        self._idle_timer.timeout.connect(self._on_idle_timeout)
        self._idle_timer.start()
        QApplication.instance().installEventFilter(self)

    def _style(self) -> str:
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        return f"""
            {QssHelper.top_bar(p, d)}
            {QssHelper.panel(p, d)}
            {QssHelper.table(p, d, s)}
            QPushButton:pressed {{ background: {p.primary}; color: {p.on_primary}; }}
            QFrame#kpi {{ background: {p.surface_variant}; border-radius: {d.radius_lg}px; }}
            {QssHelper.panel_title(p, s, 13)}
        """

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel):
            self._idle_timer.stop()
            self._idle_timer.start()
        return super().eventFilter(obj, event)

    def _on_idle_timeout(self):
        audit.logout(session.user_id, session.full_name)
        QMessageBox.information(self, "Session expirée",
            "Session inactive depuis 10 minutes.\nL'application va se fermer.")
        db.disconnect_all()
        QApplication.quit()

    def closeEvent(self, event):
        audit.logout(session.user_id, session.full_name)
        db.disconnect_all()
        super().closeEvent(event)

    def _setup_ui(self):
        d = theme_manager.design
        self.setStyleSheet(self._style())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # Top bar (style LarcSuperviseur)
        top = QFrame()
        top.setObjectName("top_bar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(10, 6, 10, 6)
        top_layout.setSpacing(6)

        self._title = QLabel(f"📋 LarcSecrétariat — {session.full_name}")
        self._title.setObjectName("panel_title")
        top_layout.addWidget(self._title)
        top_layout.addStretch()

        self._date_label = QLabel()
        self._date_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(13)}px; color: {theme_manager.palette.text_soft};")
        top_layout.addWidget(self._date_label)

        self._network_label = QLabel()
        self._network_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(12)}px; font-weight: bold;")
        top_layout.addWidget(self._network_label)

        self._theme_btn = QPushButton("🎨")
        self._theme_btn.setFixedSize(34, 34)
        self._theme_btn.setCursor(Qt.PointingHandCursor)
        self._theme_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {theme_manager.palette.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {theme_manager.palette.surface_variant}; }}")
        self._theme_btn.clicked.connect(self._cycle_theme)
        top_layout.addWidget(self._theme_btn)

        # Profil button (comme LarcSuperviseur)
        initials = ''.join(w[0].upper() for w in session.full_name.split() if w)[:2] or '?'
        self._profile_btn = QPushButton(initials)
        self._profile_btn.setFixedSize(34, 34)
        self._profile_btn.setCursor(Qt.PointingHandCursor)
        self._profile_btn.setStyleSheet(
            f"QPushButton {{ background: {theme_manager.palette.primary}; "
            f"color: {theme_manager.palette.on_primary}; font-weight: bold; "
            f"font-size: 13px; border: none; border-radius: 17px; }}"
            f"QPushButton:hover {{ background: {theme_manager.palette.active}; }}")
        self._profile_menu = QMenu(self)
        logout_action = self._profile_menu.addAction("Déconnexion")
        logout_action.triggered.connect(self._on_logout)
        self._profile_btn.setMenu(self._profile_menu)
        top_layout.addWidget(self._profile_btn)

        outer.addWidget(top)

        # Main layout: sidebar + content
        main_h = QHBoxLayout()
        main_h.setContentsMargins(0, 0, 0, 0)
        main_h.setSpacing(6)

        # Sidebar
        self._sidebar = QFrame()
        self._sidebar.setObjectName("panel")
        self._sidebar.setFixedWidth(233)
        self._sidebar_layout = QVBoxLayout(self._sidebar)
        self._sidebar_layout.setContentsMargins(6, 6, 6, 6)
        self._sidebar_layout.setSpacing(2)

        self._build_sidebar()
        main_h.addWidget(self._sidebar)

        # Content stack
        self._content_stack = QStackedWidget()

        # Page 0 : Tableau de bord
        self._dashboard_page = self._build_dashboard()
        self._content_stack.addWidget(self._dashboard_page)

        # Page 1 : Mode Supervision (présence, événements)
        self._supervisor_panel = SupervisorPanel()
        self._content_stack.addWidget(self._supervisor_panel)

        # Page 2 : Gestion des parents
        self._parent_manager = ParentManager()
        self._content_stack.addWidget(self._parent_manager)

        # Page 3 : Fiche élève
        self._student_form = StudentForm()
        self._content_stack.addWidget(self._student_form)

        main_h.addWidget(self._content_stack, 1)
        outer.addLayout(main_h, 1)

        # Status bar
        self._status_bar = QLabel()
        self._status_bar.setFixedHeight(21)
        self._status_bar.setStyleSheet(
            f"background: {theme_manager.palette.surface_variant}; "
            f"color: {theme_manager.palette.text_soft}; "
            f"font-size: {theme_manager.font_size(10)}px; padding: 2px 13px;")
        outer.addWidget(self._status_bar)

        self._update_datetime()
        self._update_status_bar()

    def _build_sidebar(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design

        self._clear_layout(self._sidebar_layout)

        def _make_btn(ss, min_h=34):
            b = QPushButton()
            b.setMinimumHeight(min_h)
            b.setStyleSheet(ss)
            b.setCursor(Qt.PointingHandCursor)
            return b

        self._selected_btn = None

        # Titre Navigation
        title = QLabel("Navigation")
        title.setStyleSheet(f"font-size: {s(11)}px; font-weight: bold; color: {p.text_strong}; padding: 3px;")
        self._sidebar_layout.addWidget(title)

        # Tableau de bord
        btn = _make_btn(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: none; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; padding: 3px 8px; text-align: left; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}",
            min_h=34
        )
        btn.setText("📊 Tableau de bord")
        btn.clicked.connect(lambda: self._content_stack.setCurrentIndex(0))
        self._sidebar_layout.addWidget(btn)

        # Section Inscriptions
        sec_title = QLabel("Inscriptions")
        sec_title.setStyleSheet(
            f"font-size: {s(9)}px; font-weight: bold; color: {p.text_disabled}; "
            f"padding: 8px 3px 2px 3px; text-transform: uppercase;")
        self._sidebar_layout.addWidget(sec_title)

        btn = _make_btn(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: none; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; padding: 3px 8px; text-align: left; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}",
            min_h=34
        )
        btn.setText("🔍 Rechercher un élève")
        btn.setObjectName("nav_search")
        btn.clicked.connect(lambda: self._content_stack.setCurrentIndex(3))
        self._sidebar_layout.addWidget(btn)

        btn = _make_btn(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: none; border-radius: {d.radius}px; "
            f"font-size: {s(10)}px; padding: 3px 8px; text-align: left; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}",
            min_h=34
        )
        btn.setText("👪 Gestion parents")
        btn.clicked.connect(lambda: self._content_stack.setCurrentIndex(2))
        self._sidebar_layout.addWidget(btn)

        self._sidebar_layout.addSpacing(d.spacing)

        # ---- Sections classes (style LarcSuperviseur) ----
        prog_style = {
            'PEI':  (p.primary, p.primary_container, p.on_primary, 'PEI'),
            'MYP':  (p.secondary, p.secondary_container, p.on_secondary, 'MYP'),
            'DPFr': (p.error, p.error_container, p.on_error, 'DP'),
            'DPEn': (p.tertiary, p.tertiary_container, p.on_tertiary, 'DPEn'),
        }

        groups = {k: [] for k in ['PEI', 'MYP', 'DPEn', 'DPFr']}
        for cid, label, pid, sigle in self._classes:
            if sigle in groups:
                groups[sigle].append((cid, label))

        sections = [
            ('Collège', [('PEI', 'PEI'), ('MYP', 'MYP')]),
            ('Lycée',   [('DP', 'DPFr'), ('DPEn', 'DPEn')]),
        ]

        for sec_name, columns in sections:
            sec_hdr = _make_btn(
                f"QPushButton {{ background: transparent; color: {p.text_strong}; "
                f"border: none; border-bottom: 2px solid {p.outline_variant}; "
                f"font-weight: bold; font-size: {s(13)}px; text-align: left; padding: 4px 2px; }}"
                f"QPushButton:hover {{ color: {p.primary}; border-bottom: 2px solid {p.primary}; }}",
                min_h=34
            )
            sec_hdr.setText(sec_name)
            self._sidebar_layout.addWidget(sec_hdr)

            grd = QGridLayout()
            grd.setSpacing(d.spacing)

            for col_idx, (hdr_text, prog_key) in enumerate(columns):
                fg, bg, on_fg, _ = prog_style[prog_key]
                items = groups.get(prog_key, [])

                col_hdr = _make_btn(
                    f"QPushButton {{ background: {fg}; color: {on_fg}; border: none; "
                    f"border-radius: {d.radius}px; font-weight: bold; font-size: {s(13)}px; padding: 3px; }}"
                    f"QPushButton:hover {{ opacity: 0.8; }}",
                    min_h=21
                )
                col_hdr.setText(hdr_text)
                grd.addWidget(col_hdr, 0, col_idx)

                for i, (cid, label) in enumerate(items):
                    btn = _make_btn(
                        f"QPushButton {{ background: {bg}; color: {fg}; border: none; "
                        f"border-radius: {d.radius}px; font-size: {s(13)}px; padding: 2px; }}"
                        f"QPushButton:hover {{ background: {fg}; color: {bg}; }}"
                        f"QPushButton:checked {{ background: {fg}; color: {bg}; "
                        f"border: 2px solid {fg}; }}",
                        min_h=34
                    )
                    btn.setCheckable(True)
                    btn.setText(label)
                    btn.clicked.connect(lambda checked, c=cid, b=btn: self._on_class_clicked(c, b))
                    grd.addWidget(btn, i + 1, col_idx)

            self._sidebar_layout.addLayout(grd)
            self._sidebar_layout.addSpacing(d.spacing)

        # Enseignants (placeholder)
        ens_hdr = _make_btn(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: none; border-bottom: 2px solid {p.outline_variant}; "
            f"font-weight: bold; font-size: {s(13)}px; text-align: left; padding: 4px 2px; }}"
            f"QPushButton:hover {{ color: {p.primary}; border-bottom: 2px solid {p.primary}; }}",
            min_h=34
        )
        ens_hdr.setText("Enseignants")
        self._sidebar_layout.addWidget(ens_hdr)

        # Staff non enseignant (placeholder)
        staff_hdr = _make_btn(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: none; border-bottom: 2px solid {p.outline_variant}; "
            f"font-weight: bold; font-size: {s(13)}px; text-align: left; padding: 4px 2px; }}"
            f"QPushButton:hover {{ color: {p.primary}; border-bottom: 2px solid {p.primary}; }}",
            min_h=34
        )
        staff_hdr.setText("Staff non enseignant")
        self._sidebar_layout.addWidget(staff_hdr)

        self._sidebar_layout.addSpacing(d.spacing)

        sup_btn = QPushButton("Lancer LarcSuperviseur")
        sup_btn.setMinimumHeight(55)
        sup_btn.setCursor(Qt.PointingHandCursor)
        sup_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {d.radius}px; font-size: {s(11)}px; font-weight: bold; padding: 8px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}")
        sup_btn.clicked.connect(self._launch_superviseur)
        self._sidebar_layout.addWidget(sup_btn)

        self._sidebar_layout.addStretch()

        # État réseau en bas
        self._sidebar_status = QLabel()
        self._sidebar_status.setStyleSheet(f"font-size: {s(9)}px; padding: 3px;")
        self._sidebar_status.setAlignment(Qt.AlignCenter)
        self._sidebar_layout.addWidget(self._sidebar_status)
        self._selected_btn = None

    def _build_dashboard(self) -> QWidget:
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design

        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(13, 13, 13, 13)
        layout.setSpacing(13)

        # KPIs
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)
        self._kpi_widgets = {}
        self._kpi_labels = {}
        for key, label in [
            ('total', 'Total élèves'),
            ('college', 'Collège'),
            ('lycee', 'Lycée'),
            ('enseignants', 'Enseignants'),
        ]:
            f = QFrame()
            f.setObjectName("kpi")
            f.setMinimumHeight(89)
            fl = QVBoxLayout(f)
            fl.setAlignment(Qt.AlignCenter)
            v = QLabel("—")
            v.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.primary};")
            v.setAlignment(Qt.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft};")
            l.setAlignment(Qt.AlignCenter)
            fl.addWidget(v)
            fl.addWidget(l)
            self._kpi_widgets[key] = v
            self._kpi_labels[key] = l
            kpi_row.addWidget(f, 1)
        layout.addLayout(kpi_row)

        # Corps : tables à gauche, graphiques à droite
        body_row = QHBoxLayout()
        body_row.setSpacing(13)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        # Tableau élèves
        self._dashboard_title = QLabel("Effectifs par programme")
        self._dashboard_title.setStyleSheet(
            f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong};")
        left_col.addWidget(self._dashboard_title)

        self._dashboard_table = QTableWidget()
        self._dashboard_table.setColumnCount(7)
        self._dashboard_table.setHorizontalHeaderLabels(
            ["Programme", "Actifs", "Places", "Taux", "♂", "♀", "Total"])
        hdr = self._dashboard_table.horizontalHeader()
        for i in range(7):
            hdr.setSectionResizeMode(i, QHeaderView.Stretch)
        self._dashboard_table.setMaximumHeight(233)
        self._dashboard_table.setAlternatingRowColors(True)
        self._dashboard_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._dashboard_table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        left_col.addWidget(self._dashboard_table)

        # Tableau enseignants
        self._teacher_title = QLabel("Statistiques enseignants")
        self._teacher_title.setStyleSheet(
            f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong};")
        left_col.addWidget(self._teacher_title)

        self._teacher_table = QTableWidget()
        self._teacher_table.setColumnCount(2)
        self._teacher_table.setHorizontalHeaderLabels(["Statut", "Actifs"])
        thdr = self._teacher_table.horizontalHeader()
        thdr.setSectionResizeMode(0, QHeaderView.Stretch)
        thdr.setSectionResizeMode(1, QHeaderView.Stretch)
        self._teacher_table.setMaximumHeight(144)
        self._teacher_table.setAlternatingRowColors(True)
        self._teacher_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._teacher_table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        left_col.addWidget(self._teacher_table)

        body_row.addLayout(left_col, 1)

        # Colonne droite : graphiques
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        self._niveau_chart_view = QChartView()
        self._niveau_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._niveau_chart_view.setMinimumHeight(377)
        right_col.addWidget(self._niveau_chart_view, 1)

        body_row.addLayout(right_col, 2)
        layout.addLayout(body_row)

        # Ratio filles / garçons (élèves uniquement)
        gender_row = QHBoxLayout()
        gender_row.setSpacing(3)
        gender_row.setAlignment(Qt.AlignCenter)
        self._gender_ratio_label = QLabel()
        self._gender_ratio_label.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; padding: 5px;")
        gender_row.addWidget(self._gender_ratio_label)
        layout.addLayout(gender_row)

        # Alertes
        self._alert_title = QLabel("Alertes")
        self._alert_title.setStyleSheet(
            f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(self._alert_title)

        self._alert_label = QLabel()
        self._alert_label.setStyleSheet(
            f"font-size: {s(10)}px; color: {p.text_soft}; padding: 8px;")
        self._alert_label.setWordWrap(True)
        self._alert_label.setObjectName("panel")
        layout.addWidget(self._alert_label)

        layout.addStretch()
        page.setWidget(inner)
        return page

    def _populate_niveau_chart(self, rows: list):
        bar_sets = {}
        categories = []
        prog_colors = {
            'PEI': QColor('#4A90D9'), 'MYP': QColor('#9B59B6'),
            'DPFr': QColor('#E74C3C'), 'DPEn': QColor('#1ABC9C'),
        }
        prog_labels = {'PEI': 'PEI', 'MYP': 'MYP', 'DPFr': 'DP', 'DPEn': 'DPEn'}
        by_cat = {}
        for niveau, sigle, cnt in rows:
            if niveau not in by_cat:
                by_cat[niveau] = {}
                categories.append(niveau)
            by_cat[niveau][sigle] = cnt
        for sigle in ('PEI', 'MYP', 'DPFr', 'DPEn'):
            bs = QBarSet(prog_labels[sigle])
            bs.setColor(prog_colors[sigle])
            for cat in categories:
                bs.append(by_cat[cat].get(sigle, 0))
            bar_sets[sigle] = bs

        series = QBarSeries()
        for sigle in ('PEI', 'MYP', 'DPFr', 'DPEn'):
            series.append(bar_sets[sigle])

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Effectifs par niveau")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(-45)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        mx = max((max(by_cat[c].values()) for c in categories), default=10)
        axis_y.setRange(0, mx + 5)
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setFont(QFont('Segoe UI', 8))
        chart.setBackgroundBrush(QBrush(QColor(theme_manager.palette.surface)))
        chart.setMargins(QMargins(0, 0, 0, 0))
        self._niveau_chart_view.setChart(chart)

    def _load_initial_data(self):
        conn = db.server_conn
        if not conn:
            self._status_bar.setText("Non connecté au serveur.")
            return

        try:
            cur = conn.cursor()

            _SEC_PROGS = ('PEI', 'MYP', 'DPEn', 'DPFr')

            # Stats globales + enseignants KPI
            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE enabled = TRUE) AS total_actifs
                FROM larcauth_student
                WHERE s_classroom_id IN (
                    SELECT c.id FROM larcauth_classroom c
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program pr ON pr.id = l.fk_program_id
                    WHERE pr.sigle IN %s
                )
            """, (_SEC_PROGS,))
            total_actifs = cur.fetchone()[0]
            self._kpi_widgets['total'].setText(str(total_actifs))
            cur.execute("SELECT COUNT(*) FROM larcauth_teachadm WHERE enabled = TRUE")
            self._kpi_widgets['enseignants'].setText(str(cur.fetchone()[0]))

            # Tableau fusionné programme + genre + ratio F/G élèves
            cur.execute("""
                SELECT pr.sigle,
                       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE) AS actifs,
                       COUNT(s.aecuser_ptr_id) AS slots,
                       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE AND g.sigle IN ('M','Mr')) AS garcons,
                       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE AND g.sigle IN ('F','Mme')) AS filles
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                LEFT JOIN larcauth_student s ON s.s_classroom_id = c.id
                LEFT JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                LEFT JOIN larcauth_gender g ON g.id = aec.fk_gender_id
                WHERE pr.sigle IN %s
                GROUP BY pr.id, pr.sigle
                ORDER BY pr.sigle
            """, (_SEC_PROGS,))
            prog_rows = cur.fetchall()
            self._dashboard_table.setRowCount(len(prog_rows))
            college = lycee = 0
            total_g = total_f = 0
            for i, (sigle, actifs, slots, garcons, filles) in enumerate(prog_rows):
                taux = f"{actifs / slots * 100:.0f}%" if slots else "—"
                tot_genre = garcons + filles
                for col, val in enumerate([sigle, str(actifs), str(slots), taux, str(garcons), str(filles), str(tot_genre)]):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    self._dashboard_table.setItem(i, col, item)
                if sigle in ('PEI', 'MYP'):
                    college += actifs
                elif sigle in ('DPFr', 'DPEn'):
                    lycee += actifs
                total_g += garcons
                total_f += filles
            self._kpi_widgets['college'].setText(str(college))
            self._kpi_widgets['lycee'].setText(str(lycee))

            # Ratio F/G élèves
            gt = total_g + total_f
            if gt:
                self._gender_ratio_label.setText(
                    f"Élèves — ♂ Garçons {total_g} ({total_g/gt*100:.0f}%)  "
                    f"┃  ♀ Filles {total_f} ({total_f/gt*100:.0f}%)")
            else:
                self._gender_ratio_label.setText("Élèves — ♂ —  ┃  ♀ —")

            # Tableau enseignants
            cur.execute("""
                SELECT 'Enseignants',
                       COUNT(*) FILTER (WHERE type_teacher = TRUE) FROM larcauth_aecuser WHERE is_active = TRUE
                UNION ALL
                SELECT 'Admins',
                       COUNT(*) FILTER (WHERE type_director = TRUE) FROM larcauth_aecuser WHERE is_active = TRUE
                UNION ALL
                SELECT 'Coordinateurs',
                       COUNT(*) FILTER (WHERE type_coordonator = TRUE) FROM larcauth_aecuser WHERE is_active = TRUE
                UNION ALL
                SELECT 'Secrétaires',
                       COUNT(*) FILTER (WHERE type_secretary = TRUE) FROM larcauth_aecuser WHERE is_active = TRUE
            """)
            t_rows = cur.fetchall()
            self._teacher_table.setRowCount(len(t_rows))
            for i, (statut, cnt) in enumerate(t_rows):
                for col, val in enumerate([statut, str(cnt)]):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    self._teacher_table.setItem(i, col, item)

            # Niveau chart
            cur.execute("""
                SELECT l.label, pr.sigle, COUNT(*) AS cnt
                FROM larcauth_student s
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                WHERE pr.sigle IN %s AND s.enabled = TRUE
                GROUP BY l.id, l.label, pr.sigle
                ORDER BY l.id
            """, (_SEC_PROGS,))
            self._populate_niveau_chart(cur.fetchall())

            # Alertes
            cur.execute("""
                SELECT COUNT(*)
                FROM larcauth_student s
                WHERE s.enabled = TRUE
                  AND s.s_classroom_id IN (
                      SELECT c.id FROM larcauth_classroom c
                      JOIN larcauth_level l ON l.id = c.fk_level_id
                      JOIN larcauth_program pr ON pr.id = l.fk_program_id
                      WHERE pr.sigle IN %s
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM larcauth_aecuser p
                      WHERE p.id = s.aecuser_ptr_id AND p.fk_parent_id IS NOT NULL
                  )
            """, (_SEC_PROGS,))
            no_parent = cur.fetchone()[0]
            self._alert_label.setText(
                f"⚠ {no_parent} élève(s) actif(s) sans parent/tuteur rattaché." if no_parent
                else "✓ Aucune alerte."
            )

            # Classes pour la sidebar
            cur.execute("""
                SELECT c.id, c.label, l.fk_program_id, pr.sigle
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                WHERE c.enabled = TRUE AND pr.sigle IN %s
                ORDER BY pr.sigle, c.label
            """, (_SEC_PROGS,))
            self._classes = cur.fetchall()
            self._build_sidebar()

            self._status_bar.setText("Données chargées.")

        except Exception as e:
            log(f"_load_initial_data: {e}")
            self._status_bar.setText(f"Erreur de chargement : {e}")

    def _on_class_clicked(self, class_id: int, btn=None):
        label = next((c[1] for c in self._classes if c[0] == class_id), str(class_id))
        self._select_btn(btn)
        self._content_stack.setCurrentIndex(1)
        self._supervisor_panel.load_class(class_id, label)
        self._status_bar.setText(f"Supervision — {label}")

    def _select_btn(self, btn):
        if self._selected_btn is not None:
            try:
                self._selected_btn.setChecked(False)
            except RuntimeError:
                pass
        self._selected_btn = btn
        if btn is not None:
            try:
                btn.setChecked(True)
            except RuntimeError:
                pass

    def _cycle_theme(self):
        themes = ['blue', 'dark', 'sobre', 'contrast']
        current = theme_manager._active
        idx = (themes.index(current) + 1) % len(themes) if current in themes else 0
        theme_manager.set_active(themes[idx])
        self._restyle_all()
        self._build_sidebar()
        self._supervisor_panel.reload()
        self._update_status_bar()
        self._update_datetime()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _launch_superviseur(self):
        import subprocess, os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sup_path = os.path.join(base, 'LarcSuperviseur', 'main.py')
        if os.path.exists(sup_path):
            subprocess.Popen(['python', sup_path])
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "LarcSuperviseur",
                "Le dossier LarcSuperviseur n'est pas trouvé à côté de LarcSecretaire.\n"
                f"Chemin attendu : {sup_path}")

    def _on_logout(self):
        from larccommon.database import db as _larc_db
        _larc_db.disconnect_all()
        QApplication.quit()

    def _restyle_all(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design

        # Main window
        self.setStyleSheet(self._style())

        # Top bar
        self._theme_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        self._date_label.setStyleSheet(
            f"font-size: {s(13)}px; color: {p.text_soft};")
        self._network_label.setStyleSheet(
            f"font-size: {s(12)}px; font-weight: bold;")
        self._title.setStyleSheet(
            f"color: {p.text_strong}; font-size: {s(13)}px; font-weight: bold;")
        self._profile_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"font-weight: bold; font-size: 13px; border: none; border-radius: 17px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}")

        # Dashboard
        for v in self._kpi_widgets.values():
            v.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.primary};")
        for l in self._kpi_labels.values():
            l.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft};")
        self._dashboard_title.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong};")
        self._teacher_title.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong};")
        self._gender_ratio_label.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; padding: 5px;")
        self._alert_title.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong};")
        self._alert_label.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; padding: 8px;")

        # Status bar
        self._status_bar.setStyleSheet(
            f"background: {p.surface_variant}; color: {p.text_soft}; "
            f"font-size: {s(10)}px; padding: 2px 13px;")

    def _update_datetime(self):
        from datetime import datetime
        now = datetime.now()
        self._date_label.setText(now.strftime("%A %d %B %Y %H:%M") + "  ")

    def _update_status_bar(self):
        net = detect_network()
        p = theme_manager.palette
        s = theme_manager.font_size
        if net == NetworkMode.INTRANET:
            txt, color = "Intranet ●", p.success
        elif net == NetworkMode.INTERNET:
            txt, color = "Cloud ●", p.primary
        else:
            txt, color = "Hors ligne", p.text_disabled
        self._network_label.setText(txt)
        self._network_label.setStyleSheet(
            f"font-size: {s(12)}px; font-weight: bold; color: {color};")
        self._network_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: {theme_manager.font_size(11)}px;")
        self._sidebar_status.setText(txt)
        self._sidebar_status.setStyleSheet(f"font-size: {theme_manager.font_size(9)}px; color: {color};")
