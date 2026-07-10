import hashlib

from larccommon.l10n import _
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from phibuilder.widgets import M3Button, M3Label, M3TextField
from phibuilder.widgets.button import ButtonVariant
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QVBoxLayout


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        phi = theme_manager.phi_theme
        self.setWindowTitle(_("password.title"))
        self.setFixedSize(360, 260)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        info = M3Label(
            _("password.info"),
            theme=phi,
            style="body_small",
        )
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        self._old_pwd = M3TextField(placeholder=_("password.old_placeholder"), theme=phi)
        self._old_pwd.setEchoMode(M3TextField().EchoMode.Password)
        self._old_pwd.setStyleSheet("background: transparent; border: 1px solid " + phi.colors.outline + "; border-radius: 4px;")
        layout.addWidget(self._old_pwd)

        self._new_pwd = M3TextField(placeholder=_("password.new_placeholder"), theme=phi)
        self._new_pwd.setEchoMode(M3TextField().EchoMode.Password)
        self._new_pwd.setStyleSheet("background: transparent; border: 1px solid " + phi.colors.outline + "; border-radius: 4px;")
        layout.addWidget(self._new_pwd)

        self._confirm_pwd = M3TextField(placeholder=_("password.confirm_placeholder"), theme=phi)
        self._confirm_pwd.setEchoMode(M3TextField().EchoMode.Password)
        self._confirm_pwd.setStyleSheet("background: transparent; border: 1px solid " + phi.colors.outline + "; border-radius: 4px;")
        layout.addWidget(self._confirm_pwd)

        btn_row = QHBoxLayout()
        save_btn = M3Button(_("password.save_button"), theme=phi, variant=ButtonVariant.FILLED)
        save_btn.clicked.connect(self._save)
        cancel_btn = M3Button(_("password.cancel_button"), theme=phi, variant=ButtonVariant.OUTLINED)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _save(self):
        old = self._old_pwd.text()
        new = self._new_pwd.text()
        confirm = self._confirm_pwd.text()

        if not new or len(new) < 4:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("password.error.too_short"))
            return
        if new != confirm:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("password.error.not_matching"))
            return

        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("password.error.no_connection"))
            return

        try:
            cur = conn.cursor()
            cur.execute("SELECT password FROM larcauth_aecuser WHERE id = %s", (session.user_id,))
            row = cur.fetchone()
            if not row:
                QMessageBox.warning(self, _("common.dialog.error_title"), _("password.error.user_not_found"))
                return
            if _sha256_hex(old) != row[0]:
                QMessageBox.warning(self, _("common.dialog.error_title"), _("password.error.wrong_old"))
                return

            new_hash = _sha256_hex(new)
            cur.execute("UPDATE larcauth_aecuser SET password = %s WHERE id = %s", (new_hash, session.user_id))
            conn.commit()
            QMessageBox.information(self, _("password.success"), _("password.success_msg"))
            self.accept()
        except Exception as e:
            log(f"ChangePasswordDialog: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), _("password.error.update").format(e=e))
