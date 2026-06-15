"""Audit trail — traçabilité centralisée PostgreSQL.

Usage :
    from common.audit import audit
    audit.log('update_student', 'student', 123101, 'Email modifié')
"""
from LarcSecretaire.common.database import db
from LarcSecretaire.common.session import session
from LarcSecretaire.common.logger import log


def _insert(action: str, target_type: str, target_id: int | None,
            detail: str, source: str | None = None) -> None:
    conn = db.server_conn
    if not conn:
        log("audit: pas de connexion serveur, log ignoré")
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_trail
                (secretary_id, secretary_name, action, target_type,
                 target_id, detail, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            getattr(session, 'user_id', None),
            getattr(session, 'full_name', None),
            action, target_type, target_id,
            (detail or '')[:500],
            source or getattr(session, 'conn_mode', None) or 'intranet',
        ))
    except Exception as e:
        log(f"audit: echec INSERT audit_trail: {e}")


class AuditLogger:
    """Points d'entrée métier pour l'audit."""

    @staticmethod
    def login(secretary_id: int, secretary_name: str, mode: str) -> None:
        _insert('login', 'session', secretary_id,
                f"Connexion {mode} — {secretary_name}",
                source=mode)

    @staticmethod
    def logout(secretary_id: int, secretary_name: str) -> None:
        _insert('logout', 'session', secretary_id,
                f"Déconnexion — {secretary_name}")

    @staticmethod
    def create_student(student_id: int, detail: str) -> None:
        _insert('create_student', 'student', student_id, detail)

    @staticmethod
    def update_student(student_id: int, detail: str) -> None:
        _insert('update_student', 'student', student_id, detail)

    @staticmethod
    def update_foyer(foyer_id: int, detail: str) -> None:
        _insert('update_foyer', 'foyer', foyer_id, detail)

    @staticmethod
    def update_parent(parent_id: int, detail: str) -> None:
        _insert('update_parent', 'parent', parent_id, detail)

    @staticmethod
    def add_event(student_id: int, event_type: str, note: str = '') -> None:
        detail = f"Événement {event_type}"
        if note:
            detail += f" : {note[:200]}"
        _insert('add_event', 'event', student_id, detail)

    @staticmethod
    def delete_event(event_id: int, detail: str) -> None:
        _insert('delete_event', 'event', event_id, detail)

    @staticmethod
    def validate_event(event_id: int, detail: str) -> None:
        _insert('validate_event', 'event', event_id, detail)


audit = AuditLogger()
