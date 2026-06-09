-- ============================================================
-- student_parent : Liaison N-N élèves ↔ parents/tuteurs
-- ============================================================
-- À exécuter SUR LES 3 BASES :
--   1) Intranet école (PostgreSQL 127.0.0.1:5432/NewLarcDB)
--   2) Cloud Supabase (via PgBouncer port 6543)
--   3) Copie locale Intranet (PC maison)
--
-- Usage :
--   psql -U postgres -d NewLarcDB -h 127.0.0.1 -f student_parent.sql
-- ============================================================

-- 1. Table de jonction élèves ↔ parents
CREATE TABLE IF NOT EXISTS student_parent (
    id                INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    student_id        INTEGER NOT NULL REFERENCES larcauth_student(aecuser_ptr_id)
                                 ON DELETE CASCADE,
    parent_id         INTEGER NOT NULL REFERENCES larcauth_aecuser(id)
                                 ON DELETE CASCADE,
    nature            TEXT,                     -- 'père', 'mère', 'tuteur', 'grand-parent', etc.
    is_emergency      BOOLEAN NOT NULL DEFAULT FALSE,
    is_authorized     BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    synced            BOOLEAN DEFAULT FALSE,
    source            TEXT DEFAULT 'intranet' CHECK (source IN ('intranet', 'cloud')),
    last_modified_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sync_revision     BIGINT DEFAULT 0,
    UNIQUE (student_id, parent_id)
);

-- 2. Index
CREATE INDEX IF NOT EXISTS idx_student_parent_student ON student_parent(student_id);
CREATE INDEX IF NOT EXISTS idx_student_parent_parent  ON student_parent(parent_id);

-- 3. Trigger updated_at
CREATE OR REPLACE FUNCTION update_student_parent_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    NEW.last_modified_at = CURRENT_TIMESTAMP;
    NEW.sync_revision = COALESCE(OLD.sync_revision, 0) + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_student_parent_updated ON student_parent;
CREATE TRIGGER trg_student_parent_updated
    BEFORE UPDATE ON student_parent
    FOR EACH ROW EXECUTE FUNCTION update_student_parent_timestamp();
