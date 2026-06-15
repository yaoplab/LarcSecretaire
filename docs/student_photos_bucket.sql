-- ============================================================
-- student_photos_bucket : Bucket Supabase Storage pour photos
-- ============================================================
-- À exécuter SUR LE CLOUD UNIQUEMENT (connexion directe,
-- PAS via PgBouncer, car le schema storage y est masqué).
--
-- Connexion directe :
--   psql -U postgres.crvyxfsuvwqxzlhsfbwq \
--         -d postgres \
--         -h aws-1-eu-north-1.pooler.supabase.com \
--         -p 5432
-- ============================================================

-- Créer le bucket public
INSERT INTO storage.buckets (id, name, public, avif_autodetection)
VALUES ('student-photos', 'student-photos', true, false)
ON CONFLICT (id) DO NOTHING;

-- Politique : lecture publique
DROP POLICY IF EXISTS "Public Read" ON storage.objects;
CREATE POLICY "Public Read"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'student-photos');
