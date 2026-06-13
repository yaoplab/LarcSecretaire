from typing import Optional, Tuple

import time

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

from LarcSecretaire.common.session import AuthResult, ConnMode, UserRole, session
from LarcSecretaire.common.network import NetworkMode, detect_network
from LarcSecretaire.common.database import db
from LarcSecretaire.common.auth import AuthManager
from LarcSecretaire.common.sqlite_init import sqlite_init
from LarcSecretaire.common.theme import theme_manager
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.audit import audit


class _Worker(QThread):
    done = Signal(object)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self.finished.connect(self.deleteLater)

    def run(self):
        try:
            self.done.emit(self._fn(*self._args))
        except Exception as exc:
            self.done.emit((False, None, str(exc)))


class LoginWindow(QMainWindow):

    _login_attempts: dict[str, dict] = {}

    @classmethod
    def _check_rate_limit(cls, key: str) -> bool:
        now = time.time()
        entry = cls._login_attempts.get(key)
        if entry and entry['until'] > now:
            remaining = int(entry['until'] - now)
            raise RuntimeError(f"Trop de tentatives. Réessayez dans {remaining}s.")
        if entry and entry['until'] <= now:
            cls._login_attempts.pop(key, None)
        return True

    @classmethod
    def _record_failure(cls, key: str):
        entry = cls._login_attempts.setdefault(key, {'count': 0, 'until': 0})
        entry['count'] += 1
        if entry['count'] >= 5:
            entry['until'] = time.time() + 30

    def _style(self) -> str:
        p = theme_manager.palette
        d = theme_manager.design
        return f"""
            QMainWindow  {{ background: {p.background}; }}
            QWidget#root {{ background: {p.background}; }}
            QTabWidget::pane {{
                border: 1px solid {p.border}; background: {p.surface}; border-radius: {d.radius}px;
            }}
            QTabBar::tab          {{ padding: {d.btn_pad_v}px {d.btn_pad_h}px; font-size: 11px; }}
            QTabBar::tab:selected {{
                background: {p.surface}; border-bottom: 2px solid {p.primary};
                color: {p.text_strong}; font-weight: bold;
            }}
            QTabBar::tab:!selected {{ background: {p.border_light}; color: {p.text_soft}; }}
            QLineEdit {{
                padding: 7px 10px; border: 1px solid {p.border};
                border-radius: {d.radius}px; font-size: 12px; background: {p.surface};
            }}
            QLineEdit:focus {{ border-color: {p.primary}; }}
            QPushButton {{
                padding: 9px 20px; border: none; border-radius: {d.radius}px;
                font-size: 12px; font-weight: bold; color: white;
            }}
            QPushButton#btnIntra  {{ background: {p.button_primary}; }}
            QPushButton#btnIntra:hover  {{ background: {p.primary}; }}
            QPushButton#btnIntra:disabled  {{ background: {p.inactive}; }}
            QPushButton#btnGoogle {{ background: {p.button_danger}; }}
            QPushButton#btnGoogle:hover {{ background: {p.danger}; }}
            QPushButton#btnGoogle:disabled {{ background: {p.inactive}; }}
            QLabel#errLabel {{ color: {p.danger}; font-size: 11px; }}
            QLabel#hdrTitle {{ color: {p.text_strong}; font-size: 22px; font-weight: bold; }}
            QLabel#hdrSub   {{ color: {p.text_soft}; font-size: 11px; }}
            QLabel#infoLbl  {{ color: {p.text_secondary}; font-size: 11px; }}
        """

    def __init__(self):
        super().__init__()
        self._worker: Optional[_Worker] = None
        self._net_mode: Optional[NetworkMode] = None

        # Initialiser la base de données serveur
        db.connect_intranet()
        # Tenter Cloud si Intranet indisponible
        if not db.server_conn:
            db.connect_cloud()
        # Initialiser la base SQLite locale
        sqlite_init.init()

        self._setup_ui()
        self._start_net_detection()

        self._network_timer = QTimer(self)
        self._network_timer.setInterval(30000)
        self._network_timer.timeout.connect(self._update_network_status)
        self._network_timer.start()

        self.setWindowTitle("LarcSecrétariat — Connexion")
        self.setMinimumSize(520, 480)
        self.setMaximumSize(580, 620)

    def _setup_ui(self):
        self.setStyleSheet(self._style())
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(40, 30, 40, 20)

        # En-tête
        hdr = QLabel("LarcSecrétariat")
        hdr.setObjectName("hdrTitle")
        hdr.setAlignment(Qt.AlignCenter)
        outer.addWidget(hdr)

        sub = QLabel("Module de gestion administrative — Secrétariat")
        sub.setObjectName("hdrSub")
        sub.setAlignment(Qt.AlignCenter)
        outer.addWidget(sub)
        outer.addSpacing(10)

        # Indicateur réseau
        self._net_label = QLabel()
        self._net_label.setAlignment(Qt.AlignCenter)
        self._net_label.setObjectName("infoLbl")
        outer.addWidget(self._net_label)
        outer.addSpacing(10)

        # Onglets
        tabs = QTabWidget()
        tabs.addTab(self._tab_intranet(), "Intranet")
        tabs.addTab(self._tab_cloud(), "Cloud")
        outer.addWidget(tabs, 1)

        # Message d'erreur
        self._err_label = QLabel()
        self._err_label.setObjectName("errLabel")
        self._err_label.setAlignment(Qt.AlignCenter)
        self._err_label.setWordWrap(True)
        outer.addWidget(self._err_label)

        # Barre d'état
        self._status_label = QLabel()
        self._status_label.setObjectName("infoLbl")
        self._status_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._status_label)

    # ---- Intranet ----
    def _tab_intranet(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)
        form = QFormLayout()
        form.setSpacing(8)

        email = QLineEdit()
        email.setPlaceholderText("prenom.nom@votreedu.com")
        self._edt_i_email = email
        pwd = QLineEdit()
        pwd.setEchoMode(QLineEdit.Password)
        pwd.setPlaceholderText("Mot de passe")
        pwd.returnPressed.connect(self._on_intranet)
        self._edt_i_pwd = pwd

        form.addRow("Email :", email)
        form.addRow("Mot de passe :", pwd)
        layout.addLayout(form)

        btn = QPushButton("Connexion Intranet")
        btn.setObjectName("btnIntra")
        btn.setMinimumHeight(44)
        btn.clicked.connect(self._on_intranet)
        layout.addWidget(btn)

        layout.addSpacing(8)
        info = QLabel("Authentification via le serveur interne.")
        info.setObjectName("infoLbl")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        return w

    # ---- Cloud ----
    def _tab_cloud(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        info = QLabel("Connectez-vous avec votre compte\nGoogle @arc-en-ciel.org")
        info.setObjectName("infoLbl")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        layout.addSpacing(10)

        btn = QPushButton("Connexion Google")
        btn.setObjectName("btnGoogle")
        btn.setMinimumHeight(44)
        btn.clicked.connect(self._on_cloud)
        layout.addWidget(btn)

        layout.addSpacing(8)
        info2 = QLabel("Utilise le protocole OAuth2 PKCE.")
        info2.setObjectName("infoLbl")
        info2.setAlignment(Qt.AlignCenter)
        layout.addWidget(info2)
        return w

    def _on_intranet(self):
        email = self._edt_i_email.text().strip()
        pwd = self._edt_i_pwd.text()
        if not email or not pwd:
            self._show_error("Veuillez saisir votre email et mot de passe.")
            return
        try:
            self._check_rate_limit(email.lower())
        except RuntimeError as e:
            self._show_error(str(e))
            return
        self._hide_error()
        self._set_busy(True)
        email_key = email.lower()
        self._worker = _Worker(AuthManager.auth_intranet, email, pwd, parent=self)
        self._worker.done.connect(lambda r, ek=email_key: self._on_auth_done(r, ConnMode.INTRANET, ek))
        self._worker.start()

    def _on_cloud(self):
        try:
            self._check_rate_limit('cloud')
        except RuntimeError as e:
            self._show_error(str(e))
            return
        self._hide_error()
        self._set_busy(True)
        self._worker = _Worker(AuthManager.auth_cloud, parent=self)
        self._worker.done.connect(lambda r: self._on_auth_done(r, ConnMode.CLOUD, 'cloud'))
        self._worker.start()

    def _check_secretary_exists(self, email: str) -> Tuple[bool, dict]:
        """Vérifie que l'utilisateur est une secrétaire active (type_secretary = TRUE)."""
        conn = db.server_conn
        if not conn:
            return False, {}
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT aec.id, aec.last_name, aec.first_name, aec.email
                FROM larcauth_aecuser aec
                WHERE LOWER(aec.email) = %s AND aec.type_secretary = TRUE AND aec.is_active = TRUE
                LIMIT 1
            """, (email.lower().strip(),))
            row = cur.fetchone()
            if not row:
                return False, {}
            return True, {
                'user_id': row[0],
                'last_name': row[1],
                'first_name': row[2],
                'email': row[3],
            }
        except Exception as e:
            log(f"_check_secretary_exists: {e}")
            return False, {}

    def _on_auth_done(self, result, mode: ConnMode, rate_key: str):
        self._set_busy(False)
        ok, res, err = result
        if not ok:
            self._record_failure(rate_key)
            self._show_error(err or "Authentification échouée.")
            return

        # Vérifier que l'utilisateur est une secrétaire
        if mode in (ConnMode.INTRANET, ConnMode.CLOUD):
            exists, infos = self._check_secretary_exists(res.email)
            if not exists:
                self._show_error("Ce compte n'est pas une secrétaire active.")
                return
            res.user_id = infos['user_id']
            res.full_name = f"{infos['first_name']} {infos['last_name']}"

            if not sqlite_init.init():
                self._show_error("Impossible d'initialiser la base locale.")
                return

            sqlite_init.set_module_config('secretary_name', res.full_name)
            sqlite_init.set_module_config('secretary_email', res.email)
            sqlite_init.set_module_config('secretary_id', str(res.user_id))

            self._apply_session(res, mode)

    def _apply_session(self, res: AuthResult, mode: ConnMode):
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR
        session.conn_mode = mode

        audit.login(session.user_id, session.full_name, mode.value)

        from LarcSecretaire.views.main_window import MainWindow
        self._main_window = MainWindow()
        self._main_window.showMaximized()
        self.close()

    # ---- UI helpers ----
    def _show_error(self, msg: str):
        self._err_label.setText(msg)

    def _hide_error(self):
        self._err_label.setText("")

    def _set_busy(self, busy: bool):
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(not busy)
        if busy:
            self._status_label.setText("Connexion en cours...")
        else:
            self._status_label.setText("")

    def _update_network_status(self):
        mode = detect_network()
        p = theme_manager.palette
        if mode == NetworkMode.INTRANET:
            txt, color = "Intranet ●", p.success
        elif mode == NetworkMode.INTERNET:
            txt, color = "Cloud ●", p.primary
        else:
            txt, color = "Hors ligne", p.text_disabled
        self._net_label.setText(txt)
        self._net_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px;")

    def _start_net_detection(self):
        self._update_network_status()
