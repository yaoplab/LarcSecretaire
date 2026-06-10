CREATE TABLE IF NOT EXISTS audit_trail (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    secretary_id INTEGER,
    secretary_name TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    detail TEXT,
    source TEXT DEFAULT 'intranet',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_trail_action ON audit_trail (action);
CREATE INDEX IF NOT EXISTS idx_audit_trail_secretary ON audit_trail (secretary_id);
CREATE INDEX IF NOT EXISTS idx_audit_trail_created ON audit_trail (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_trail_target ON audit_trail (target_type, target_id);

COMMENT ON TABLE audit_trail IS 'Traçabilité des actions secrétaires et superviseurs';
COMMENT ON COLUMN audit_trail.secretary_id IS 'ID de l''utilisateur ayant effectué l''action';
COMMENT ON COLUMN audit_trail.action IS 'login, logout, create_student, update_student, update_foyer, update_parent, add_event, delete_event, validate_event';
COMMENT ON COLUMN audit_trail.target_type IS 'session, student, foyer, parent, event';
COMMENT ON COLUMN audit_trail.source IS 'intranet, cloud';
