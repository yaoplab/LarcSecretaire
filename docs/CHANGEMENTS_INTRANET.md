# Changements appliqués — Bases de données

_8 juin 2026 — Mise à jour_  
_Dernier ajout : 9 juin 2026 — 18h_

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

La liaison N-N dans `student_parent` n'est PAS une exception : elle associe deux entités existantes (élève + parent déjà en base).

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
