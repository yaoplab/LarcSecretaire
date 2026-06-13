# Historique de construction — LarcSecretaire

## Itération 1 — 5 juin 2026 : Création du projet

### Spécifications
- Rédaction du document `docs/01_specifications.md` avec analyse des points forts/faibles
- Décision : Phase 1 = inscription/gestion élèves, Phase 2 = finance
- Principe gabarit confirmé : 40 slots par classe (IDs 121101–121140)
- Pas d'INSERT (sauf événements), pas de DELETE

### Architecture
- Création de l'arborescence `LarcSecretaire/` avec `common/` et `views/`
- Copie des modules communs depuis `eLarcProfPy` :
  - `network.py`, `session.py`, `database.py`, `auth.py`, `logger.py`, `grid_config.py`
- Copie du thème MD3 depuis `LarcSuperviseur` : `theme.py`
- Palette MD3 enrichie avec les champs manquants (`border`, `button_primary`, etc.)

### Modules spécifiques
- `common/sqlite_init.py` : DDL secrétaire avec `student_profile`, `student_profile_ref`, `session_cache`, `module_config`, `sync_state`, `sync_cursor`
- `common/sync.py` : SyncManager avec diff cellule via shadow-tables
- `views/login.py` : 2 onglets (Intranet/Cloud), vérifie `type_secretary`
- `views/main_window.py` : Sidebar + Dashboard KPIs (total élèves, collège, lycée, places, répartition par programme, alertes)
- `views/password.py` : ChangePasswordDialog
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

---

## Itération 2 — 7 juin 2026 : Supervision + Parents

### Supervision présence/événements
- Création de `student_event` (DDL + table serveur) — timeline d'événements, INSERT libre
- Création de `views/supervisor_panel.py` : grille de cartes élèves, présence du jour (✓/✕/—), historique événements, ajout événement
- Intégré comme page 1 du content stack (bascale sidebar → supervision)
- Rafraîchissement au changement de thème

### Gestion des parents
- Création de `student_parent` (DDL + table serveur, N-N élèves ↔ parents, avec nature)
- Création de `views/parent_manager.py` : liste parents filtrable, élèves liés, combo lier/délier
- Ajouté comme page 2 du content stack, bouton "👪 Gestion parents" dans la sidebar

### Filtrage PP/PYP
- Exclus PP/PYP de toutes les requêtes KPIs, alertes, sidebar, stats (LarcSecretaire + LarcSuperviseur)

### DDLs
- Copies vers `docs/student_event.sql` et `docs/student_parent.sql` (à exécuter sur Intranet + Supabase)

---

## Itération 3 — 8 juin 2026 : Corrections thème + sidebar

### Correction cycle de thème
- `_cycle_theme()` ne mettait à jour que le QSS global et la sidebar
- Les styles inline du dashboard (KPIs, titres, alertes), de la top bar et de la status bar gardaient les anciennes couleurs
- Ajout de `_restyle_all()` qui rafraîchit tous les styles inline
- Stockage des références manquantes (`self._kpi_labels`, `self._prog_title`, `self._alert_title`)

### Correction doublons sidebar
- `_build_sidebar()` utilisait `widget().deleteLater()` pour nettoyer — ne supprime pas les sous-layouts (QGridLayout)
- Ajout de `_clear_layout()` récursif qui supprime widgets ET sous-layouts
- Résultat : plus de doublons des en-têtes PEI/MYP/DP/DPEn lors du rechargement

### État actuel
- Cycle thème fonctionnel : tous les styles inline sont recalculés
- Sidebar sans doublons
- Supervision + parents intégrés et fonctionnels

---

## Itération 4 — 8 juin 2026 : Modèle foyer + larcauth_parent

### Modèle de données parents
Après discussion, décision de créer une architecture complète pour les parents :

**Tables créées :**
- `foyer` — adresse/household (address_line1, address_line2, postal_code, city, country, phone, email)
- `larcauth_parent` — 1-to-1 avec `larcauth_aecuser` (comme `teachadm`/`student`), avec `nature` (père, mère, tuteur) et `enabled`
- `fk_foyer_id` ajouté sur `larcauth_aecuser` — adresse de résidence pour TOUS (profs, élèves, parents, admin)

**Modèle final :**
```
larcauth_aecuser (tous)
  ├── fk_foyer_id → foyer.id (adresse universelle)

larcauth_parent (1-to-1 avec aecuser)
  ├── nature (père, mère, tuteur légal)
  └── enabled

student_parent (N-N élèves ↔ parents, déjà existant)
  ├── student_id → aecuser.id
  ├── parent_id → aecuser.id (type_parentutor)
  └── nature (override optionnel)
```

- IDs parents dans aecuser : 10001–10400 (potentiel < 100000)
- SQL : `docs/foyer_parent.sql`

### Modèle foyer (gabarit)
- Foyer.ID = aecuser.ID (identiques) — chaque utilisateur a son propre foyer par défaut
- Pré-remplissage : `INSERT INTO foyer (id, enabled) SELECT id, TRUE FROM larcauth_aecuser`
- Partager une adresse : `UPDATE aecuser SET fk_foyer_id = foyer_id_cible` — plusieurs personnes pointent vers le même foyer
- Contrainte d'unicité partielle : pas deux foyers actifs avec la même adresse
- Colonne `enabled` ajoutée, `fk_foyer_id` auto-initialisé à `id`

### Corrections
- `supervisor_panel.py` : `validated = FALSE` → `validated_by IS NULL` dans `_load_presence` et `_load_events`
- `parent_manager.py` : requêtes JOIN `larcauth_parent` + `foyer`, affichage nature/ville dans la table
- `sqlite_init.py` : tables `foyer` et `student_parent` ajoutées au DDL SQLite
- Cloud : PK ajoutée sur `aecuser(id)`, FKs sur `larcauth_parent` et `fk_foyer_id` (Intranet avait déjà les vraies FKs)

### Prochaines étapes
1. Fiche élève (student_form.py) — édition coordonnées
2. Vue classe (class_view.py) — grille élèves avec slots vides
3. Recherche globale (search.py)
4. Connecter `sync.py` aux nouvelles tables (student_event, student_parent, foyer)
5. Phase 2 : gestion financière (frais par foyer)

---

## Itération 6 — 9 juin 2026 : Tabbed dialogs, éditeur enrichi, événements, intégration Superviseur

### Refonte complète des dialogues
Les deux popups (édition et création) ont été unifiés et repensés :

**Mise en page onglets (6 tabs, photo toujours visible) :**
1. **Identité** — nom, prénom, date d'entrée
2. **Contact** — email, email perso, tél. portable, tél. fixe
3. **Adresse** — ligne1, complément, CP, ville, pays
4. **Notes** — éditeur QTextEdit riche avec barre d'outils (B/I/listes/tableau)
5. **Fichiers & Parents** — explorateur fichiers + tableau parents
6. **Événements** (lecture seule) — tableau des événements de l'élève

**Design tokens :**
- Centralisation de toutes les valeurs de design (radius, padding, spacing, margin) dans `DesignTokens` (3 jeux de valeurs par thème)
- Plus de valeurs hardcodées dans les feuilles de style
- Labels protégés contre l'étirement vertical (`Maximum` size policy)

**Police unifiée :**
- `fs = 10` dans les deux dialogues (match avec l'écran principal)
- Plus de `s(fs - 2)` pour les boutons — tout en `s(fs)`
- Dialogues élargis : `setMinimumSize(900, 860)`

### Éditeur de notes
- **Suppression du Markdown** : fonctions `_md_to_html`, `_md_inline`, `_update_md_preview` retirées
- **Remplacement par QTextEdit** + barre d'outils (Gras, Italique, Liste puces, Liste numérotée, Tableau 3×3)
- Stockage en HTML dans la colonne `notes`
- Fonctionnel en création et édition

### Événements dans la fiche élève
- Nouvel onglet "Événements" (lecture seule) avec tableau des événements
- Requête `student_event` triée par date DESC
- Aucun bouton d'ajout/modification — consultation uniquement
- Création : placeholder "visible après création"

### Intégration des vignettes → fiche élève
- **Supervision (page 1)** : clic sur une vignette élève → `StudentEditDialog` modal (grille reste visible)
- **Recherche (page 3)** : photo cliquable (curseur main + eventFilter) → `StudentEditDialog`
- Plus de panneau détail intermédiaire dans Supervision

### Lancement LarcSuperviseur
- Bouton "Lancer LarcSuperviseur" dans le dashboard (sous les alertes)
- `subprocess.Popen(['python', 'LarcSuperviseur/main.py'])` si le chemin existe

### Corrections
- `AttributeError: 'Palette' object has no attribute 'on_primary_container'` — remplacé par `on_primary`
- `QFont::setPointSize` error — retiré `setMinimumHeight` dans les labels
- Bug padding notes : `padding: {d.spacing+2}px {p.border}` → `padding: {d.field_pad_v}px {d.field_pad_h}px`
- Nettoyage imports inutilisés : `re`, `html.escape`, `QSplitter`, `QTextBrowser`

### État actuel
- Les deux dialogues (édition et création) partagent la même structure à 6 onglets
- Notes en HTML avec éditeur enrichi (pas de syntaxe Markdown)
- Événements visibles depuis la fiche élève (lecture seule)
- Vignette Supervision → popup modal

### Prochaines étapes
1. Connecter `sync.py` aux nouvelles tables (`student_event`, `student_parent`, `foyer`)
2. Bouton Synchroniser dans le dashboard
3. Vue classe complète (class_view.py) — slots vides, inactifs grisés
4. Recherche globale (search.py)
5. Phase 2 : gestion financière

---

## Itération 7 — 10 juin 2026 : Notes JSONB, adresse & parents fusionnés, export PDF/Word

### Notes structurées JSONB
- Remplacement de l'ancien système notes (TEXT HTML, éditeur QTextEdit avec barre d'outils) par une structure **JSONB** à 7 sections prédéfinies :
  - **Confidentielle** — réservé direction/secrétariat
  - **Médicale** — allergies, PAI, traitements
  - **Pédagogique** — PPRE, suivi, bilans
  - **Administrative** — bourses, assurances
  - **Communication** — historique contacts parents
  - **Orientation** — vœux, stages, PsyEN
  - **Autre** — divers
- Création de `views/notes_panel.py` :
  - `NotesPanel` : widget principal avec QTabWidget (7 onglets)
  - `_SectionTab` : chaque onglet = introduction contextuelle statique (QLabel coloré) + tableau entries (N°, Date, Titre, Document/Note)
  - `_MultilineDelegate` : éditeur QPlainTextEdit pour la colonne Document/Note (redimensionnable, multi-lignes)
  - Boutons d'export PDF/Word dans la ligne des boutons de section (exportent toutes les sections)
- Fallback : anciennes notes TEXT importées automatiquement dans la section `autre` à la première ouverture de la fiche
- `docs/migrate_notes_json.sql` : `ALTER TABLE larcauth_student ADD COLUMN notes_json JSONB DEFAULT '{}'::jsonb`

### Refonte onglet 3 "Adresse & Parents"
- Fusion des sections Adresse et Parents dans un seul onglet
- **Gestion parent inline** :
  - Bouton **+ Ajouter un parent** : ouvre une boîte de dialogue de recherche (filtre type_parentutor, LIKE nom/email, exclut ceux déjà liés) → INSERT INTO student_parent
  - Bouton **✎ Nature** : QInputDialog pour modifier la nature du lien
  - Bouton **− Retirer** : DELETE avec confirmation
  - Bouton **Copier l'adresse du parent sélectionné** : requête foyer du parent → remplit les champs adresse
  - `_load_parents()` extrait en méthode séparée pour rechargement après modification
  - `_parent_ids` stocké pour les opérations

### Refonte onglet 5 "Fichiers"
- La partie parents déplacée dans l'onglet 3
- Onglet 5 : uniquement la liste des fichiers joints (`data/students/{id}/`)

### Boutons dialog en haut
- Enregistrer, PDF, Word, Annuler déplacés à côté de la photo (sous le nom)
- Plus de scroll nécessaire pour accéder aux boutons

### Export complet fiche élève
- `_build_full_html()` : génère HTML complet (en-tête + contact + adresse + parents + notes + événements)
- Export PDF : `QPrinter` avec `QTextDocument.print_()`
- Export Word : fichier HTML (ouvrable dans Word)

### Colonnes événements harmonisées
- Date/Heure : 150px, Type : 110px, Note : Stretch, Par : 140px, Validé : ResizeToContents

### Nettoyage
- Import inutiles retirés : `QColorDialog`, `QInputDialog`, `QTextListFormat`, `QTextCharFormat`, `QTextBlockFormat`, `QPlainTextEdit`, `QTextEdit`
- Anciennes méthodes toolbar notes supprimées
- `QTextDocument` ajouté aux imports (export PDF)

### DDL exécutés
- `docs/migrate_notes_json.sql` : ajout `notes_json JSONB` sur Intranet et Cloud
- `sql/02_date_columns.sql` : ajout `date_of_birth DATE` + COMMENT sur `larcauth_aecuser`

### État actuel
- 7 sections de notes structurées en JSONB
- Gestion parents inline dans la fiche élève (Ajouter, Nature, Retirer, Copier adresse)
- Export PDF/Word complet et par section
- Tab 3 = Adresse & Parents, Tab 4 = Notes, Tab 5 = Fichiers
- Boutons d'action en haut du dialog

### Prochaines étapes
1. Connecter `sync.py` aux nouvelles tables (`student_event`, `student_parent`, `foyer`)
2. Bouton Synchroniser dans le dashboard
3. Vue classe complète (class_view.py)
4. Phase 2 : gestion financière

---

## Itération 8 — 11 juin 2026 : Cloud OAuth2 fix, parent management harmonisé, ClassListDialog

### Cloud OAuth2 (LarcSecretaire)
- Ajout de `AuthManager.auth_cloud()` qui délègue à `OAuth2Manager.authenticate()`
- Suppression du bloc `module_config.email_professeur` (contrôle eLarcProfPy, inadapté aux secrétaires)
- Fix import du module database dans OAuth2

### Parent management dans les deux dialogues
- `StudentEditDialog` : onglet 3 passe de "Adresse" à "Adresse & Parents" avec tableau parents + 4 boutons de gestion
- `StudentCreateDialog` : ajout des 4 méthodes parents manquantes (`_add_parent_link`, `_edit_parent_nature`, `_remove_parent_link`, `_copy_parent_address`)
- `self._sid` stocké après création pour permettre la liaison parents immédiate

### ClassListDialog
- Nouveau bouton "📋 Liste" dans l'en-tête Supervision (à côté du "+")
- Ouvre `ClassListDialog` : table stylée avec checkbox par élève (colonnes N°, Nom, Prénom)
- Espacement ajouté autour des deux boutons

### Corrections Cloud/PgBouncer
- `UPDATE larcauth_aecuser` sans `enabled = TRUE` (table aecuser utilise `is_active`)
- `json.dumps(notes_json)` pour contourner l'absence d'adaptateur JSON via PgBouncer
- Erreur `can't adapt type 'dict'` résolue

### État actuel
- Cloud OAuth2 fonctionnel pour les secrétaires
- Gestion parents inline dans les deux dialogues (édition et création)
- ClassListDialog avec checkboxes disponible en Supervision
- Compatibilité Cloud Supabase via PgBouncer assurée

### Prochaines étapes
1. Connecter `sync.py` aux nouvelles tables (`student_event`, `student_parent`, `foyer`)
2. Bouton Synchroniser dans le dashboard
3. Ajuster les thèmes (Dark trop clair, Contraste pas assez marqué)
4. Phase 2 : gestion financière
