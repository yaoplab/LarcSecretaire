-- Ajout colonne notes_json JSONB sur larcauth_student
-- Remplace l'ancienne colonne notes TEXT par une structure JSONB
-- 7 sections : confidentielle, medicale, pedagogique, administrative,
--              communication, orientation, autre
-- Chaque section : { intro: "HTML text", entries: [{ no, date, titre, doc }] }
-- sync_version est automatiquement incrémenté par le trigger
-- handle_updated_at_and_sync() présent sur la table.

ALTER TABLE larcauth_student
  ADD COLUMN IF NOT EXISTS notes_json JSONB DEFAULT '{}'::jsonb;

-- Appliquer aussi sur le Cloud si la connexion Supabase est distincte.
-- Executer manuellement sur Supabase via la console SQL si nécessaire.
