ALTER TABLE larcauth_aecuser ADD COLUMN IF NOT EXISTS date_of_birth DATE;

COMMENT ON COLUMN larcauth_aecuser.date_of_birth IS 'Date de naissance de l''utilisateur';
COMMENT ON COLUMN larcauth_aecuser.date_entree IS 'Date d''entree pour l''annee en cours';
COMMENT ON COLUMN larcauth_aecuser.date_joined IS 'Date de premiere entree a Arc-en-Ciel';
