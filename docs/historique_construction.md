# Historique de construction — LarcSecretaire

## Itération 1 — 5 juin 2026 : Création du projet

### Spécifications
- Rédaction du document `docs/01_specifications.md` avec analyse des points forts/faibles
- Décision : Phase 1 = inscription/gestion élèves, Phase 2 = finance
- Principe gabarit confirmé : 40 slots par classe (IDs 121101–121140)
- Pas d'INSERT, pas de DELETE

### Architecture
- Création de l'arborescence `LarcSecretaire/` avec `common/` et `views/`
- Copie des modules communs depuis `eLarcProfPy` :
  - `network.py`, `session.py`, `database.py`, `auth.py`, `logger.py`, `grid_config.py`
- Copie du thème MD3 depuis `LarcSuperviseur` : `theme.py`
- Palette MD3 enrichie avec les champs manquants (`border`, `button_primary`, etc.)

### Modules spécifiques
- `common/sqlite_init.py` : DDL secrétaire avec `student_profile`, `student_profile_ref`, `session_cache`, `module_config`, `sync_state`, `sync_cursor`
- `common/sync.py` : SyncManager avec diff cellule via shadow-tables
- `views/login.py` : 4 onglets (Intranet/Cloud/PIN/Nouvelle instance), vérifie `type_secretary`
- `views/main_window.py` : Sidebar + Dashboard KPIs (total élèves, collège, lycée, places, répartition par programme, alertes)
- `views/password.py` : ChangePinDialog + ChangePasswordDialog
- `main.py` : point d'entrée
- `requirements.txt` : PySide6 + psycopg2-binary

### Base de données
- **Ajout colonne `type_secretary`** sur Intranet et Cloud (Supabase)
  ```sql
  ALTER TABLE larcauth_aecuser ADD COLUMN type_secretary BOOLEAN DEFAULT FALSE;
  ```
- **Activation du compte** patrlabo@arc-en-ciel.org (id=1021, Patrice LABONNE)
- **Vérification :** les 40 slots par classe confirmés via le schéma d'IDs

### Corrections post-création
- `db.init()` inexistant → remplacé par `db.connect_intranet()` / `db.connect_cloud()`
- `theme_manager.theme_name` → `theme_manager._active`
- `theme_manager.set_theme()` → `theme_manager.set_active()`
- Palette MD3 enrichie des champs attendus par login.py

### État
- Import de tous les modules vérifié
- Application démarre (fenêtre de connexion)
- Dashboard fonctionnel (KPIs, répartition, alertes)
- Sidebar avec classes par programme
- 3 thèmes MD3 cyclables

### Prochaines étapes
1. Fiche élève (student_form.py) — édition coordonnées
2. Vue classe (class_view.py) — grille élèves
3. Recherche (search.py)
4. Gestion des parents (parent_manager.py)
5. Phase 2 : gestion financière
