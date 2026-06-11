from typing import Optional, List, Tuple, Dict
from datetime import datetime
import sqlite3

from .logger import log
from .sqlite_init import sqlite_init, _resolve_db_path


class SyncManager:
    """Synchronisation shadow-table pour LarcSecretaire.

    Tables concernées :
      - student_profile / student_profile_ref
    """

    SYNC_TABLES = ["student_profile"]

    def _ref_name(self, table: str) -> str:
        return f"{table}_ref"

    def diff_table(self, table: str) -> List[Dict]:
        """Compare working table vs _ref, retourne la liste des diffs."""
        ref = self._ref_name(table)
        path = _resolve_db_path()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            # Récupérer les colonnes (sans id, sync_version)
            cur.execute(f"PRAGMA table_info({table})")
            all_cols = [r[1] for r in cur.fetchall() if r[1] not in ("id", "sync_version")]
            cols_sql = ", ".join(f"t.{c}, r.{c} AS r_{c}" for c in all_cols)

            cur.execute(f"""
                SELECT t.id {', '.join(f', t.{c}' for c in all_cols)}
                       {', '.join(f', r.{c} AS r_{c}' for c in all_cols)}
                FROM {table} t
                LEFT JOIN {ref} r ON r.id = t.id
                WHERE t.id IS NOT NULL
            """)
            rows = cur.fetchall()
        finally:
            conn.close()

        diffs = []
        for row in rows:
            row_id = row["id"]
            for c in all_cols:
                local_val = row[c]
                ref_key = f"r_{c}"
                ref_val = row[ref_key] if ref_key in row.keys() else None
                if str(local_val) != str(ref_val):
                    diffs.append({
                        "id": row_id,
                        "column": c,
                        "local": local_val,
                        "ref": ref_val,
                    })
        return diffs

    def pull(self, table: str, server_rows: List[Dict]) -> int:
        """Écrit les données serveur dans la table de travail et _ref."""
        path = _resolve_db_path()
        ref = self._ref_name(table)
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            count = 0
            for row in server_rows:
                row_id = row.get("id")
                if not row_id:
                    continue
                # Mettre à jour la table de travail
                set_clause = ", ".join(f"{k} = ?" for k in row if k != "id")
                values = [row[k] for k in row if k != "id"] + [row_id]
                cur.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
                if cur.rowcount == 0:
                    # INSERT si pas encore présent
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join("?" for _ in row)
                    cur.execute(f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})",
                                list(row.values()))
                # Même chose pour _ref
                cur.execute(f"UPDATE {ref} SET {set_clause} WHERE id = ?", values)
                if cur.rowcount == 0:
                    cur.execute(f"INSERT OR IGNORE INTO {ref} ({cols}) VALUES ({placeholders})",
                                list(row.values()))
                count += 1
            conn.commit()
            self._update_sync_state(table, "intranet")
            log(f"Sync pull: {table} -> {count} lignes")
            return count
        except Exception as e:
            conn.rollback()
            log(f"Sync pull error: {e}")
            raise
        finally:
            conn.close()

    def push(self, table: str, diffs: List[Dict], push_fn) -> int:
        """Push les diffs vers le serveur via push_fn(id, updates)."""
        grouped = {}
        for d in diffs:
            grouped.setdefault(d["id"], {})[d["column"]] = d["local"]

        path = _resolve_db_path()
        ref = self._ref_name(table)
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            for row_id, updates in grouped.items():
                success = push_fn(row_id, updates)
                if success:
                    # Mettre à jour _ref pour refléter le push
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    values = list(updates.values()) + [row_id]
                    cur.execute(f"UPDATE {ref} SET {set_clause} WHERE id = ?", values)
            conn.commit()
            log(f"Sync push: {table} -> {len(grouped)} lignes")
            return len(grouped)
        except Exception as e:
            conn.rollback()
            log(f"Sync push error: {e}")
            raise
        finally:
            conn.close()

    def pull_push(self, server_rows: List[Dict], push_fn) -> Tuple[int, int]:
        """Pull d'abord, puis push les diffs résiduels."""
        pulled = 0
        pushed = 0
        for table in self.SYNC_TABLES:
            pulled += self.pull(table, server_rows)
            diffs = self.diff_table(table)
            if diffs:
                pushed += self.push(table, diffs, push_fn)
        return pulled, pushed

    def _update_sync_state(self, table: str, source: str) -> None:
        path = _resolve_db_path()
        conn = sqlite3.connect(path)
        try:
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO sync_state (table_name, last_sync, last_source)
                VALUES (?, ?, ?)
            """, (table, now, source))
            conn.commit()
        finally:
            conn.close()


sync_manager = SyncManager()
