import os
import sys

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

_larc_common = os.path.normpath(os.path.join(_root, "LarcCommon"))
if os.path.isdir(_larc_common) and _larc_common not in sys.path:
    sys.path.insert(0, _larc_common)

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from larccommon.l10n import _


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("LarcSecretaire")
    app.setOrganizationName("LarcSpace")
    app.setFont(QFont("Roboto", 10))

    from larccommon.l10n import Translator
    lang = os.environ.get("LARC_LANG", "fr")
    Translator.instance(lang).load_dir(Translator.l10n_dir())

    from LarcSecretaire.common.database import db
    from LarcSecretaire.common.logger import log
    from LarcSecretaire.common.app_config import app_config
    from LarcSecretaire.common.sqlite_init import sqlite_init
    from LarcSecretaire.common.auth import AuthManager
    from LarcSecretaire.common.session import session, ConnMode, UserRole
    from LarcSecretaire.common.audit import audit

    db.connect_intranet()
    if not db.server_conn:
        db.connect_cloud()
    sqlite_init.init()
    app_config.load()
    log("LarcSecretaire démarré")

    def _check_secretary(email):
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute(
            "SELECT aec.id, aec.last_name, aec.first_name "
            "FROM larcauth_aecuser aec "
            "WHERE LOWER(aec.email) = %s AND aec.type_secretary = TRUE AND aec.is_active = TRUE "
            "LIMIT 1",
            (email.lower().strip(),),
        )
        return cur.fetchone()

    def on_intranet_login(email, password):
        result = AuthManager.auth_intranet(email, password)
        ok, res, err = result
        if not ok:
            return (False, None, err)
        row = _check_secretary(res.email)
        if not row:
            return (False, None, "Ce compte n'est pas une secrétaire active.")
        res.user_id = row[0]
        res.full_name = f"{row[1]} {row[2]}"
        if not sqlite_init.init():
            return (False, None, "Impossible d'initialiser la base locale.")
        sqlite_init.set_module_config('secretary_name', res.full_name)
        sqlite_init.set_module_config('secretary_email', res.email)
        sqlite_init.set_module_config('secretary_id', str(res.user_id))
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR
        session.conn_mode = ConnMode.INTRANET
        audit.login(session.user_id, session.full_name, ConnMode.INTRANET.value)
        return (True, res, "")

    def on_cloud_login():
        result = AuthManager.auth_cloud()
        ok, res, err = result
        if not ok:
            return (False, None, err)
        row = _check_secretary(res.email)
        if not row:
            return (False, None, "Ce compte n'est pas une secrétaire active.")
        res.user_id = row[0]
        res.full_name = f"{row[1]} {row[2]}"
        if not sqlite_init.init():
            return (False, None, "Impossible d'initialiser la base locale.")
        sqlite_init.set_module_config('secretary_name', res.full_name)
        sqlite_init.set_module_config('secretary_email', res.email)
        sqlite_init.set_module_config('secretary_id', str(res.user_id))
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR
        session.conn_mode = ConnMode.CLOUD
        audit.login(session.user_id, session.full_name, ConnMode.CLOUD.value)
        return (True, res, "")

    def on_success():
        from LarcSecretaire.views.main_window import MainWindow
        window = MainWindow()
        window.showMaximized()

    from larccommon.login import LoginWindow
    login = LoginWindow(
        on_success=on_success,
        title_prefix="LarcSecrétariat",
        on_intranet_login=on_intranet_login,
        on_cloud_login=on_cloud_login,
    )
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
