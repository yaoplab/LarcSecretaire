import os
import sys

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

_prof_root = os.path.normpath(os.path.join(_root, "eLarcProfPy"))
if os.path.isdir(_prof_root) and _prof_root not in sys.path:
    sys.path.insert(0, _prof_root)

_larc_common = os.path.normpath(os.path.join(_root, "LarcCommon"))
if os.path.isdir(_larc_common) and _larc_common not in sys.path:
    sys.path.insert(0, _larc_common)

from LarcSecretaire.views.login import LoginWindow
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("LarcSecretaire")
    app.setOrganizationName("LarcSpace")

    font = QFont("Roboto", 10)
    app.setFont(font)

    from LarcSecretaire.common.theme import theme_manager

    theme_manager.bind(app)

    from LarcSecretaire.common.logger import log

    log("LarcSecretaire démarré")

    window = LoginWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
