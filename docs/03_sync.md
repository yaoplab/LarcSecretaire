# LarcSecretaire — Synchronisation device ↔ serveur

## Principe

Reprend le pattern shadow-table de eLarcProfPy. Chaque table métier du device a une jumelle `_ref` au schéma identique.

## Tables concernées

| Table de travail | Table de référence | Contenu |
|---|---|---|
| `student_profile` | `student_profile_ref` | Snapshots élèves actifs + coordonnées |
| `student_event` | `student_event_ref` | Événements de présence (à connecter) |
| `student_parent` | `student_parent_ref` | Liens élèves↔parents (à connecter) |

## Pattern shadow-table

- **Table de travail** = état local courant, modifié par les saisies de la secrétaire.
- **Table `_ref`** = snapshot du dernier état serveur connu (acté à la dernière synchro réussie).
- Au seed, les deux tables sont peuplées avec les mêmes données serveur.

### Diff cellule

```sql
SELECT t.id, t.col1, r.col1 AS r_col1, t.col2, r.col2 AS r_col2, ...
FROM student_profile t
LEFT JOIN student_profile_ref r ON r.id = t.id
```

Comparaison colonne par colonne. Si `t.col != r.col` → diff.

### Matrice de décision (par cellule)

| local vs ref | serveur vs ref | Action |
|---|---|---|
| = | = | rien |
| = | ≠ | **pull** : local = serveur, ref = serveur |
| ≠ | = | **push** : serveur = local, ref = local |
| ≠ | ≠ | **conflit** → dernier gagne |

## Tables SQLite device

```sql
-- Session cache pour auth PIN
CREATE TABLE session_cache (
    user_id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    pin_hash TEXT,
    role TEXT NOT NULL DEFAULT 'SECR'
);

-- Configuration du module
CREATE TABLE module_config (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- État de synchro par table
CREATE TABLE sync_state (
    table_name TEXT PRIMARY KEY,
    last_sync TEXT,
    last_source TEXT
);

-- Profil élève (projection)
CREATE TABLE student_profile (
    id INTEGER PRIMARY KEY,
    last_name TEXT, first_name TEXT, firstname_2 TEXT,
    email TEXT, emailperso TEXT,
    tel_maison TEXT, tel_smartphone_1 TEXT, tel_smartphone_2 TEXT,
    fk_gender_id INTEGER, date_entree TEXT,
    s_classroom_id INTEGER, classroom_label TEXT,
    level_label TEXT, program_sigle TEXT,
    enabled INTEGER DEFAULT 0,
    fk_parent_id INTEGER,
    parent_last_name TEXT, parent_first_name TEXT,
    parent_tel TEXT, parent_nature TEXT,
    sync_version INTEGER DEFAULT 0
);

-- Référence shadow (même schéma)
CREATE TABLE student_profile_ref ( ... );
```

### Tables ajoutées en Phase 1

| Table SQLite | Source serveur | Statut |
|---|---|---|
| `student_event` | `public.student_event` | DDL créé, sync à connecter |
| `student_parent` | `public.student_parent` | DDL créé, sync à connecter |

### Curseur de sync incrémentale

```sql
CREATE TABLE sync_cursor (
    id INTEGER PRIMARY KEY,
    table_name TEXT NOT NULL,
    last_id INTEGER, last_version INTEGER, updated_at TEXT
);
```

## API SyncManager

```python
sync_manager.diff_table(table)          # → liste des diffs [{id, column, local, ref}]
sync_manager.pull(table, server_rows)   # écrit serveur → travail + _ref
sync_manager.push(table, diffs, push_fn)# push serveur + update _ref
sync_manager.pull_push(rows, push_fn)   # pull puis push
```

## Déclencheurs

- À la **création d'instance** : seed initial (local = ref = serveur)
- Sur **clic "Synchroniser"** depuis le tableau de bord (à faire)
- À la **sortie** (à faire)

## Notes

- Même mécanisme que eLarcProfPy : pas d'INSERT/DELETE, que des UPDATE (sauf événements)
- Les événements (`student_event`) sont en INSERT libre — la sync devra gérer l'append
- Pas de conflit entre profs (périmètre disjoint) ; possibles entre secrétaires
- La colonne `sync_revision` côté serveur est incrémentée par trigger PostgreSQL
- Daemon `LarcCloudSync` pour la sync Intranet ↔ Cloud (projet séparé)
