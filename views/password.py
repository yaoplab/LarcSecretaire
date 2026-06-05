import hashlib
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt

from LarcSecretaire.common.database import db
from LarcSecretaire.common.sqlite_init import sqlite_init
from LarcSecretaire.common.session import session
from LarcSecretaire.common.logger import log


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


class ChangePinDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Changer le code PIN")
        self.setFixedSize(360, 220)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        info = QLabel("Le PIN permet la connexion hors ligne.\n4 à 8 chiffres.")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("font-size: 11px; color: #555;")
        layout.addWidget(info)

        self._old_pin = QLineEdit()
        self._old_pin.setEchoMode(QLineEdit.Password)
        self._old_pin.setPlaceholderText("Ancien PIN (laisser vide si nouveau)")
        self._old_pin.setMaxLength(8)
        layout.addWidget(self._old_pin)

        self._new_pin = QLineEdit()
        self._new_pin.setEchoMode(QLineEdit.Password)
        self._new_pin.setPlaceholderText("Nouveau PIN (4-8 chiffres)")
        self._new_pin.setMaxLength(8)
        layout.addWidget(self._new_pin)

        self._confirm_pin = QLineEdit()
        self._confirm_pin.setEchoMode(QLineEdit.Password)
        self._confirm_pin.setPlaceholderText("Confirmer le nouveau PIN")
        self._confirm_pin.setMaxLength(8)
        layout.addWidget(self._confirm_pin)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Enregistrer")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _save(self):
        old = self._old_pin.text().strip()
        new = self._new_pin.text().strip()
        confirm = self._confirm_pin.text().strip()

        if not new or not new.isdigit() or len(new) > 8:
            QMessageBox.warning(self, "Erreur", "Le PIN doit contenir 4 à 8 chiffres.")
            return
        if new != confirm:
            QMessageBox.warning(self, "Erreur", "Les PIN ne correspondent pas.")
            return

        user_id = session.user_id
        if old:
            stored_hash = sqlite_init.get_pin_hash(user_id)
            if stored_hash and _sha256_hex(old) != stored_hash:
                QMessageBox.warning(self, "Erreur", "Ancien PIN incorrect.")
                return

        new_hash = _sha256_hex(new)
        sqlite_init.set_pin_hash(user_id, new_hash)
        QMessageBox.information(self, "Succès", "Code PIN mis à jour.")
        self.accept()


class ChangePasswordDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Changer le mot de passe Intranet")
        self.setFixedSize(360, 260)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        info = QLabel("Le mot de passe est stocké en base SHA-256\net utilisé pour la connexion Intranet.")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("font-size: 11px; color: #555;")
        layout.addWidget(info)

        self._old_pwd = QLineEdit()
        self._old_pwd.setEchoMode(QLineEdit.Password)
        self._old_pwd.setPlaceholderText("Ancien mot de passe")
        layout.addWidget(self._old_pwd)

        self._new_pwd = QLineEdit()
        self._new_pwd.setEchoMode(QLineEdit.Password)
        self._new_pwd.setPlaceholderText("Nouveau mot de passe")
        layout.addWidget(self._new_pwd)

        self._confirm_pwd = QLineEdit()
        self._confirm_pwd.setEchoMode(QLineEdit.Password)
        self._confirm_pwd.setPlaceholderText("Confirmer le nouveau mot de passe")
        layout.addWidget(self._confirm_pwd)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Enregistrer")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _save(self):
        old = self._old_pwd.text()
        new = self._new_pwd.text()
        confirm = self._confirm_pwd.text()

        if not new or len(new) < 4:
            QMessageBox.warning(self, "Erreur", "Le mot de passe doit contenir au moins 4 caractères.")
            return
        if new != confirm:
            QMessageBox.warning(self, "Erreur", "Les mots de passe ne correspondent pas.")
            return

        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, "Erreur", "Non connecté au serveur Intranet.")
            return

        try:
            cur = conn.cursor()
            # Vérifier ancien mot de passe
            cur.execute(
                "SELECT password FROM larcauth_aecuser WHERE id = %s",
                (session.user_id,)
            )
            row = cur.fetchone()
            if not row:
                QMessageBox.warning(self, "Erreur", "Utilisateur introuvable.")
                return
            if _sha256_hex(old) != row[0]:
                QMessageBox.warning(self, "Erreur", "Ancien mot de passe incorrect.")
                return

            # Mettre à jour
            new_hash = _sha256_hex(new)
            cur.execute(
                "UPDATE larcauth_aecuser SET password = %s WHERE id = %s",
                (new_hash, session.user_id)
            )
            conn.commit()
            QMessageBox.information(self, "Succès", "Mot de passe mis à jour.")
            self.accept()
        except Exception as e:
            log(f"ChangePasswordDialog: {e}")
            QMessageBox.critical(self, "Erreur", f"Échec de la mise à jour : {e}")
