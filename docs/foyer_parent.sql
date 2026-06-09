-- ============================================================
-- foyer_parent.sql : Foyer + larcauth_parent + fk_foyer_id
-- ============================================================
-- À exécuter SUR LES 3 BASES :
--   1) Intranet école (PostgreSQL 127.0.0.1:5432/NewLarcDB)
--   2) Cloud Supabase (via PgBouncer port 6543)
--   3) Copie locale Intranet (PC maison)
--
-- Usage :
--   psql -U postgres -d NewLarcDB -h 127.0.0.1 -f foyer_parent.sql
-- ============================================================

-- 1. Foyer (adresse/household)
-- IDs identiques aecuser.id (gabarit : 1 row par aecuser)
CREATE TABLE IF NOT EXISTS foyer (
    id              INTEGER PRIMARY KEY,
    address_line1   TEXT,
    address_line2   TEXT,
    postal_code     TEXT,
    city            TEXT,
    country         TEXT DEFAULT 'France',
    phone           TEXT,
    email           TEXT,
    notes           TEXT,
    enabled         BOOLEAN DEFAULT FALSE
);

-- 2. larcauth_parent (1-to-1 avec aecuser, comme teachadm/student)
CREATE TABLE IF NOT EXISTS larcauth_parent (
    aecuser_ptr_id  INTEGER PRIMARY KEY REFERENCES larcauth_aecuser(id) ON DELETE CASCADE,
    enabled         BOOLEAN DEFAULT TRUE,
    nature          TEXT   -- 'père', 'mère', 'tuteur légal', 'grand-parent', 'autre'
);

-- 3. fk_foyer_id sur aecuser (adresse pour tout le monde)
ALTER TABLE larcauth_aecuser ADD COLUMN IF NOT EXISTS fk_foyer_id INTEGER REFERENCES foyer(id);

-- 4. Index pour les recherches par foyer
CREATE INDEX IF NOT EXISTS idx_aecuser_foyer ON larcauth_aecuser(fk_foyer_id);

-- 5. Index pour les parents actifs
CREATE INDEX IF NOT EXISTS idx_larcauth_parent_enabled ON larcauth_parent(enabled);

-- 6. Contrainte d'unicité partielle : pas deux foyers avec la même adresse
CREATE UNIQUE INDEX IF NOT EXISTS idx_foyer_unique_address
    ON foyer(address_line1, postal_code, city)
    WHERE enabled = TRUE AND address_line1 IS NOT NULL;

-- 7. Seed : pour chaque aecuser existant, créer son foyer
INSERT INTO foyer (id, enabled)
SELECT id, TRUE FROM larcauth_aecuser
ON CONFLICT DO NOTHING;

-- 8. Chaque aecuser a son propre foyer par défaut
UPDATE larcauth_aecuser SET fk_foyer_id = id WHERE fk_foyer_id IS NULL;

-- ============================================================
-- Notes
-- ============================================================
-- IDs parents dans aecuser : 10001–10400 (réservés)
-- Convention : un aecuser avec type_parentutor = TRUE
--   DOIT avoir une ligne correspondante dans larcauth_parent
-- student_parent (table existante) référence larcauth_aecuser(id)
--   pour parent_id — la FK reste valide car l'aecuser existe
-- Foyer : chaque aecuser a son propre foyer (same id).
--   Partager une adresse = UPDATE aecuser.fk_foyer_id vers le foyer
--   de l'autre personne. L'adresse n'est écrite qu'une fois.
