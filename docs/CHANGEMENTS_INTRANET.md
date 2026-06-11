# Changements appliqués — Bases de données

_8 juin 2026 — Mise à jour_  
_Dernier ajout : 11 juin 2026_

## État final (Intranet maison + Cloud Supabase)

| Table/Colonne | Intranet maison | Cloud Supabase |
|---|---|---|
| `student_event` | ✓ | ✓ (sans FK) |
| `student_parent` | ✓ | ✓ (sans FK) |
| `student_daily_summary` (vue) | ✓ | ✓ |
| `student_alerts` (vue) | ✓ | ✓ |
| `foyer` | ✓ | ✓ |
| `larcauth_parent` | ✓ | ✓ |
| `fk_foyer_id` sur `aecuser` | ✓ | ✓ |
| `day_notice` sur `agenda` | ✓ | ✓ |

## Scripts exécutés

1. **Intranet maison** : `docs/foyer_parent.sql` (8 juin 2026)
2. **Cloud Supabase** : `docs/student_parent.sql` + `docs/student_event.sql` adaptés (sans FK) (8 juin 2026)

## Notes complémentaires

### Colonne notes

`ALTER TABLE larcauth_student ADD COLUMN notes TEXT;` déployé sur Intranet et Supabase le 08/06/2026.

Stocke les notes Markdown (santé, confidentiel, etc.). Les fichiers joints sont dans `data/students/{id}/` (pas syncés).

### Exceptions au principe « UPDATE uniquement »

| Exception | Raison |
|---|---|
| `student_event` | Timeline d'événements imprévisible — INSERT libre |
| Fichiers joints (`data/students/{id}/`) | Création de fichiers sur disque — pas de sync cloud |

La liaison N-N dans `student_parent` n'est PAS une exception : elle associe deux entités existantes (élève + parent déjà en base, les deux en gabarit UPDATE).

`larcauth_parent` n'est PAS une exception depuis le 10/06/2026 : les 800 gabarits (10001–10800) sont pré-remplis avec `enabled = FALSE` et la création se fait par UPDATE, comme pour `larcauth_student`.

### Note technique Supabase

Tables créées **sans contraintes FOREIGN KEY** car Supabase utilise Row-Level Security (RLS) plutôt que des FK traditionnelles (pattern constaté sur les tables existantes comme `larcauth_student` qui n'a ni PK ni index). Les triggers et vues sont identiques à l'Intranet.

---

## 9 juin 2026 — Nettoyage genres

### Contexte
La table `larcauth_gender` contenait des doublons pour la langue française :
- ID 3 (sigle `M`, label `Monsieur`) et ID 21 (sigle `M.`, label `Monsieur`) — tous deux `fk_language_id = 2`
- ID 4 (sigle `Mme`, label `Madame`) et ID 22 (sigle `Mme`, label `Madame`) — tous deux `fk_language_id = 2`

### Action
```sql
-- 1. Migrer les élèves référençant les IDs à garder
UPDATE larcauth_aecuser SET fk_gender_id = 21 WHERE fk_gender_id = 3;  -- 89 élèves
UPDATE larcauth_aecuser SET fk_gender_id = 22 WHERE fk_gender_id = 4;  -- 114 élèves

-- 2. Supprimer les doublons
DELETE FROM larcauth_gender WHERE id IN (3, 4);
```

### Résultat
| Langue | Genres disponibles |
|---|---|
| Français (lang 2) | 21 (M., Monsieur), 22 (Mme, Madame), 20 (Sans) |
| Anglais (lang 1) | 10 (None), 11 (Mr., Mister), 12 (Ms., Miss) |

### ALTER TABLE notes (re-exécution)
```sql
ALTER TABLE larcauth_student ADD COLUMN IF NOT EXISTS notes TEXT;
```
Exécuté le 09/06/2026 sur Intranet. La colonne existait déjà (créée le 08/06), le `IF NOT EXISTS` est sans effet.

---

## 10 juin 2026 — Notes structurées JSON

### Ajout colonne notes_json

```sql
ALTER TABLE larcauth_student ADD COLUMN IF NOT EXISTS notes_json JSONB DEFAULT '{}'::jsonb;
```

Remplace l'ancienne colonne `notes` (TEXT, HTML libre) par une structure JSONB avec 7 sections prédéfinies :
- `confidentielle` — Réservé direction/secrétariat
- `medicale` — Allergies, PAI, traitements
- `pedagogique` — Suivi éducatif, PPRE
- `administrative` — Bourses, assurances
- `communication` — Historique contacts parents
- `orientation` — Vœux, stages, PsyEN
- `autre` — Divers

Chaque section : `{ intro: "HTML", entries: [{ no, date, titre, doc }] }`

### Migration données
Les anciennes notes (colonne `notes` TEXT) sont importées automatiquement dans la section `autre` à la première ouverture de la fiche (fallback dans `_load_data()`). Aucune perte de données.

### sync_version
Automatique via le trigger `handle_updated_at_and_sync()` (BEFORE UPDATE sur `larcauth_student`). Toute mise à jour de `notes_json` incrémente `sync_version`.

### Date de naissance (`date_of_birth`)
```sql
ALTER TABLE larcauth_aecuser ADD COLUMN IF NOT EXISTS date_of_birth DATE;
```
Ajoutée le 10/06/2026 sur Intranet et Cloud via `sql/02_date_columns.sql`.
COMMENT ON COLUMN ajoutés pour `date_of_birth`, `date_entree`, `date_joined`.

### Statut déploiement
- `docs/migrate_notes_json.sql` : exécuté Intranet + Cloud le 10/06/2026
- `sql/02_date_columns.sql` : exécuté Intranet + Cloud le 10/06/2026

---

## 10 juin 2026 — Gabarit parents (UPDATE uniquement)

### Contexte
La table `larcauth_parent` était vide et les créations de parents utilisaient INSERT + recherche MAX(id)+1 dans `larcauth_aecuser`, ce qui sautait les IDs non utilisés dans la plage réservée.

### Action
`docs/parent_gabarit.sql` exécuté sur Intranet et Supabase le 10/06/2026 :
```sql
INSERT INTO larcauth_aecuser (id, password, ..., type_parentutor, ...)
SELECT s, '', ..., TRUE, ...
FROM generate_series(10001, 10800) AS s
WHERE NOT EXISTS (SELECT 1 FROM larcauth_aecuser WHERE id = s);

INSERT INTO larcauth_parent (aecuser_ptr_id, enabled, nature)
SELECT s, FALSE, NULL
FROM generate_series(10001, 10800) AS s;
```

### Résultat
- 800 gabarits parents (IDs 10001–10800) dans `larcauth_aecuser` + `larcauth_parent` avec `enabled = FALSE`
- `_create_new` dans `parent_manager.py` : UPDATE des deux tables au lieu d'INSERT
- La recherche du slot libre interroge désormais `larcauth_parent` (pas `larcauth_aecuser`)
