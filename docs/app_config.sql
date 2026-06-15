-- ============================================================
-- app_config : Configuration centralisee (clef/valeur)
-- ============================================================
-- Remplace les chemins en dur et les constantes dupliquees.
-- Les parametres de connexion DB restent dans config.ini
-- ============================================================

CREATE TABLE IF NOT EXISTS larcauth_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT,
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE larcauth_config IS
    'Configuration centralisee de l''application (chemins, defaults, feature flags)';

-- Seed valeurs par defaut
INSERT INTO larcauth_config (key, value, description) VALUES
    ('photos_dir', 'C:\Projets\LarcSuperviseur\photos',
     'Repertoire des photos des eleves (PNG 500x500)'),
    ('photos_cache_dir', 'C:\Projets\LarcSecretaire\photos\cache',
     'Cache local des photos telechargees depuis le cloud')
ON CONFLICT (key) DO NOTHING;
