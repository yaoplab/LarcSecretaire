-- Ajout de la colonne notes sur larcauth_student
ALTER TABLE larcauth_student ADD COLUMN IF NOT EXISTS notes TEXT;
