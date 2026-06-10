# LarcSecretaire — Contexte projet

_Dernière mise à jour : 10 juin 2026_

## Règle importante — Décisions avant actions
Quand je demande "qu'est-ce que tu pens ?" à propos d'une approche ou d'une solution,
**ne rien modifier ni implémenter** avant d'avoir donné mon avis et confirmé la décision.
D'abord répondre avec l'analyse/avis, puis attendre mon accord avant d'exécuter.

## Décision technique
Version **Python/PySide6** retenue pour le desktop. Même stack que eLarcProfPy et LarcSuperviseur.
**Pas PyQt5, pas PyQt6, pas Flet** — PySide6 uniquement.
Mobile/tablette = phase ultérieure (FastAPI + Flutter ou PWA).

## Environnement
- Python 3.x + PySide6 (Qt6)
- Pas de `.venv` sur ce PC — Python 3.11.5 système
- Dépendances : `pip install -r requirements.txt`
- Lancement : `python main.py`
- OS cible : Windows desktop

## Bases de données
| Source | Technologie | Usage |
|---|---|---|
| Intranet | PostgreSQL `127.0.0.1:5432/NewLarcDB` | Données en ligne réseau local |
| Cloud | Supabase PostgreSQL (PgBouncer port 6543) | Données en ligne internet |
| Device | SQLite `larcsecretaire.db` | Cache local + auth PIN + sync |

Config dans `config.ini` (jamais commité).
Même structure que les autres projets Larc.

## Architecture fichiers
```
LarcSecretaire/
├── main.py                 # QApplication + LoginWindow
├── common/
│   ├── network.py          # detect_network() → NetworkMode
│   ├── session.py          # UserRole, session (global)
│   ├── database.py         # Database class, db (global singleton)
│   ├── auth.py             # AuthManager (Intranet SHA-256) + OAuth2 (PKCE Google)
│   ├── sqlite_init.py      # SQLiteInit, DDL secrétaire
│   ├── sync.py             # SyncManager (shadow-table diff cellule)
│   ├── theme.py            # ThemeManager MD3 (Light/Dark/Contrast) + DesignTokens
│   ├── logger.py           # log() vers fichier
│   └── grid_config.py      # (réserve)
├── data/
│   └── students/           # Fichiers joints par élève (créé automatiquement)
├── views/
│   ├── login.py            # LoginWindow — 4 onglets auth
│   ├── password.py         # ChangePinDialog + ChangePasswordDialog
│   ├── main_window.py      # MainWindow — sidebar + dashboard + stack pages
│   ├── supervisor_panel.py # Grille élèves, présence, événements (page 1)
│   ├── parent_manager.py   # Gestion parents, foyer, lien élèves↔parents (page 2)
│   ├── student_form.py     # Fiche élève — recherche + popup édition (page 3)
│   └── notes_panel.py      # NotesPanel — 7 sections JSONB avec export PDF/Word
├── docs/
│   ├── 01_specifications.md
│   ├── 02_authentification.md
│   ├── 03_sync.md
│   ├── historique_construction.md
│   ├── student_event.sql
│   ├── student_parent.sql
│   ├── foyer_parent.sql
│   └── migrate_notes_json.sql
├── sql/
│   └── 02_date_columns.sql
```

Photos des élèves partagées avec LarcSuperviseur : `C:\Projets\LarcSuperviseur\photos\{id}.png`.
Source FB : `C:\Projets\LarcSuperviseur\photos\FB\*.jpg` → redim 500×500 + fond blanc supprimé → PNG.

## Rôles utilisateurs
| Rôle | Accès |
|---|---|
| SECR | Supervision présence, gestion parents, inscriptions ; pas de modification notes/profs |
| PROF | (hors périmètre) |
| COORD | (hors périmètre) |
| ADMIN | (hors périmètre) |

## Phase 1 — EN COURS

### Fonctionnel
- Connexion Intranet (SHA-256) → vérifie `type_secretary = TRUE`
- Connexion Cloud (OAuth2 PKCE Google @arc-en-ciel.org)
- Connexion PIN (hors ligne, hash SHA-256 en SQLite)
- Nouvelle instance (copie du projet)
- Dashboard avec KPIs (total élèves, collège, lycée, enseignants)
- Tableau fusionné : Programme \| Actifs \| Places \| Taux \| ♂ \| ♀ \| Total (colonnes stretch largeur égale, centré)
- Tableau enseignants : Enseignants / Admins / Coordinateurs / Secrétaires
- Graphique barres groupées : Effectifs par niveau (coloré par programme PEI/MYP/DP/DPEn)
- Ratio filles/garçons élèves centré sous les graphiques
- Alertes (élèves sans parent rattaché)
- Sidebar navigation + classes par programme + sections Enseignants / Staff non enseignant (placeholders)
- Bouton "Lancer LarcSuperviseur" dans la sidebar (MD3, couleur tertiary)
- 3 thèmes MD3 cyclables (Light/Dark/Contrast) avec DesignTokens centralisés
- Supervision présence/événements (page 1)
- Gestion des parents (page 2) — liste, création, édition, lien élèves
- **Fiche élève (page 3)** — recherche, sélection → popup édition grand format

### Fiche élève — StudentEditDialog (popup modale)
- Recherche par nom/prénom/email/classe dans le panneau gauche
- Sélection d'un résultat → vignette info à droite (photo cliquable, nom, classe)
- Photo `{id}.png` depuis `C:\Projets\LarcSuperviseur\photos\` (fallback avatar initiales) — clic photo ou bouton "Ouvrir la fiche" → popup
- Photos redimensionnées au QLabel (KeepAspectRatio, SmoothTransformation)
- **Boutons d'action en haut** (sous la photo) : Enregistrer, PDF, Word, Annuler
- **6 onglets avec photo toujours visible** :
  - **Identité** — nom, prénom, date de naissance, date d'entrée, genre
  - **Contact** — email, email perso, tél. portable, tél. fixe
  - **Adresse & Parents** — adresse (ligne1, complément, CP, ville, pays) + liste parents avec boutons de gestion parent (Ajouter, ✎ Nature, − Retirer, Copier l'adresse)
  - **Notes** — **NotesPanel** 7 sections JSONB : Confidentielle, Médicale, Pédagogique, Administrative, Communication, Orientation, Autre. Chaque section : introduction contextuelle statique + tableau (N°, Date, Titre, Document/Note) avec édition multi-lignes. Export PDF/Word par section.
  - **Fichiers** — explorateur fichiers joints `data/students/{id}/` (ajout, suppression, ouverture)
  - **Événements** (lecture seule) — tableau des événements de l'élève (date, type, note, auteur, validation)
- Export complet fiche élève : PDF (QPrinter) ou Word (HTML) depuis les boutons en haut ou par section depuis chaque onglet notes

### Recherche élèves
- Requête inclut `aec.fk_gender_id` et `s.s_classroom_id` (ajoutés le 9 juin)
- Fallback `pg_errors.UndefinedColumn` si colonne `notes` absente
- Rechargement après édition : `search()` → `_open_student_dialog()` (ordre corrigé)

### Création d'élève — StudentCreateDialog (même structure)
- Bouton "+" vert dans le titre de la page Fiche élève
- Bouton "+" vert dans le bandeau du panneau Supervision (visible quand une classe est chargée)
- Sélecteur de classe filtré (`enabled = TRUE`)
- Même présentation à 6 onglets que l'édition (Identité, Contact, Adresse, Notes, Fichiers & Parents placeholder, Événements placeholder)
- Champs : nom, prénom, email(s), téléphone(s), date entrée, adresse complète, notes
- Slot libre auto-détecté (premier 01-40 avec nom placeholder `'Name of ...'`)
- Création par **UPDATE** du gabarit (l'INSERT n'est plus utilisé)
- Foyer créé avec l'adresse en même temps
- Notes sauvegardées en HTML
- Dialogue réinitialisé après création pour saisie batch
- Pré-sélection de classe fonctionnelle via `preselected_class`

### Modèle parents / foyers
- `foyer` — chaque `aecuser` a son propre foyer (same ID, pré-rempli). Partager une adresse = `UPDATE aecuser.fk_foyer_id`
- `larcauth_parent` (1-to-1 avec `aecuser`) — nature, enabled
- `fk_foyer_id` sur `larcauth_aecuser` — adresse universelle
- `student_parent` (N-N) — liaison élève ↔ parent avec nature override
- Contrainte d'unicité partielle : deux foyers actifs ne peuvent pas avoir la même adresse
- IDs parents réservés : 10001–10400

### Principes gabarit
- Tous les slots 01-40 pré-existants (INSERT avec noms placeholders `'Name of XXXX'`)
- Toujours des UPDATE sauf exceptions ci-dessous
- Un slot occupé par un élève parti (enabled = FALSE) n'est jamais réutilisé
- Le premier slot libre est détecté par `enabled = FALSE AND last_name LIKE 'Name of %'`

### Exceptions au principe UPDATE uniquement
| Exception | Raison |
|---|---|
| `student_event` | Timeline d'événements imprévisible — INSERT libre |
| Fichiers joints `data/students/{id}/` | Création fichiers disque — pas de sync |
| `larcauth_student.notes` | colonne TEXT — UPDATE classique (pas une exception) |

`student_parent` n'est PAS une exception : associe deux entités existantes.

## Changements récents (10 juin 2026)

### 1. Notes structurées JSONB (remplace notes TEXT HTML)
- Nouveau widget `views/notes_panel.py` : `NotesPanel` + `_SectionTab` + `_MultilineDelegate`
- 7 sections prédéfinies : Confidentielle, Médicale, Pédagogique, Administrative, Communication, Orientation, Autre
- Stockage : colonne `notes_json JSONB` dans `larcauth_student`
- Chaque section : introduction contextuelle statique (QLabel) + tableau éditable (N°, Date, Titre, Document/Note)
- Édition multi-lignes dans la colonne Document/Note via `_MultilineDelegate` (QPlainTextEdit)
- Export PDF/Word par section (boutons dans la ligne des boutons de chaque onglet, exportent toutes les sections)
- Export complet fiche élève depuis les boutons en haut du dialog (Enregistrer, PDF, Word, Annuler)
- Fallback : anciennes notes TEXT importées dans section `autre` à la première ouverture

### 2. Onglet 3 "Adresse & Parents" fusionné
- Adresse (ligne1, complément, CP, ville, pays) + liste parents/tuteurs dans le même onglet
- Boutons de gestion parent : **+ Ajouter un parent** (recherche dialogue), **✎ Nature** (édition), **− Retirer** (confirmation)
- Bouton **Copier l'adresse** du parent sélectionné (requête foyer du parent et remplit les champs)
- Méthode `_load_parents()` extraite pour rechargement après chaque modification
- `_parent_ids` stocké pour le copy address

### 3. Onglet 5 devient "Fichiers" uniquement
- La partie parents déplacée dans l'onglet 3 Adresse & Parents
- Onglet 5 contient seulement la liste des fichiers joints

### 4. Boutons d'action déplacés en haut
- Enregistrer, PDF, Word, Annuler déplacés à côté de la photo (plus en bas du dialog)
- Visibles en permanence, pas besoin de scroller

### 5. Export PDF/Word par section notes
- Boutons PDF et Word dans la ligne de boutons de chaque onglet `_SectionTab`
- Exportent toutes les sections (pas seulement l'onglet courant)
- PDF : QPrinter (PdfFormat) avec QTextDocument
- Word : HTML (ouvrable dans Word)

### 6. Colonnes événements harmonisées
- Date/Heure : 150px, Type : 110px, Note : Stretch, Par : 140px, Validé : autosize

### 7. Nettoyage code mort
- Anciennes méthodes toolbar notes (B/I/U, H1/H2/H3, couleurs, listes, tableaux, source toggle) supprimées
- Imports inutilisés retirés : `QColorDialog`, `QInputDialog`, `QTextListFormat`, `QTextCharFormat`, `QTextBlockFormat`, `QPlainTextEdit`
- `QTextEdit` retiré de notes_panel.py (remplacé par QLabel statique)

### 8. DDL déployé
- `docs/migrate_notes_json.sql` : `ALTER TABLE larcauth_student ADD COLUMN notes_json JSONB DEFAULT '{}'::jsonb`
- `sql/02_date_columns.sql` : `ALTER TABLE larcauth_aecuser ADD COLUMN date_of_birth DATE` + COMMENT

### À faire
1. Connecter `sync.py` aux nouvelles tables (`student_event`, `student_parent`, `foyer`)
2. Bouton Synchroniser dans le dashboard
3. Phase 2 : gestion financière

## Phase 2 — À VENIR
Gestion financière : paiements de scolarité, échéancier, reçus.

## Architecture de synchronisation
Same as eLarcProfPy : shadow-table `_ref`, diff cellule, pull/push. Voir `docs/03_sync.md`.
Nouvelles tables à connecter : `student_event`, `student_parent`.

## Identifiants élèves (gabarit)
Format `XXYYZZ` : ex. `121101` = élève n°01, classe 1211. 40 slots par classe (XXYY01 à XXYY40).
IDs parents : 10001–10400.

## Compte secrétaire
- Email : `patrlabo@arc-en-ciel.org`
- ID : 1021 (Patrice LABONNE)
- Rôle : `type_secretary = TRUE`

## DDL déployé
- `docs/student_event.sql` — exécuté Intranet + Supabase
- `docs/student_parent.sql` — exécuté Intranet + Supabase
- `docs/foyer_parent.sql` — exécuté Intranet + Supabase le 08/06/2026
- `ALTER TABLE larcauth_student ADD COLUMN notes TEXT` — Intranet + Supabase le 08/06/2026

### Nettoyage genres (09/06/2026)
- Doublons supprimés : IDs **3 (M, Monsieur)** et **4 (Mme, Madame)** → supprimés
- Gardés : **21 (M., Monsieur)** et **22 (Mme, Madame)** — sigles avec point `M.`
- **199 élèves** migrés : 88 de 21→3, 111 de 22→4 (puis reverse 3→21, 4→22)
- Résultat : combo genre Français = {Monsieur, Madame, Sans} / Anglais = {None, Mister, Miss}

### Traitement photos FB (09/06/2026)
- 45 photos JPG dans `C:\Projets\LarcSuperviseur\photos\FB\` → redimensionnées 500×500 + fond blanc supprimé (seuil 240) → PNG dans `C:\Projets\LarcSuperviseur\photos\`
