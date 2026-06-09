# LarcSecretaire — Spécifications fonctionnelles et techniques

> Module desktop pour les secrétaires : supervision présence/événements + gestion des parents (Phase 1) + inscriptions élèves (Phase 1 suite) + gestion financière (Phase 2).

---

## 1. Contexte

Le système existant (eLarcProfPy, LarcSuperviseur) repose sur une base PostgreSQL Intranet partagée et une philosophie **gabarit** : les slots sont pré-alloués en base, l'activation se fait par booléen. Le module secrétaire s'inscrit dans la même architecture.

### Principes communs
- **PySide6** (Qt6) — pas PyQt, pas Flet
- Connexion directe **psycopg2** au PostgreSQL Intranet (127.0.0.1:5432/NewLarcDB)
- Auth : Intranet (SHA-256, colonne `password`), Cloud (OAuth2 PKCE Google @arc-en-ciel.org), PIN (SQLite `session_cache`)
- Rôle SECR authentifié par `type_secretary = TRUE` dans `larcauth_aecuser`
- Base SQLite device locale (`larcsecretaire.db`) avec tables shadow (`_ref`)
- Sync via diff cellule → pull/push (identique à eLarcProfPy)
- Fichiers communs réutilisables : `common/network.py`, `common/session.py`, `common/database.py`, `common/auth.py`, `common/theme.py`, `common/logger.py`, `common/sync.py`, `common/sqlite_init.py`
- `config.ini` partagé (jamais commité — voir `.gitignore`)
- Daemon `LarcCloudSync` pour la sync Intranet ↔ Cloud

### Identifiants élèves (gabarit)
Les IDs élèves suivent le schéma `XXYYZZ` :
- Exemple : `121101` = élève n°01 de la classe `1211`
  - `1` = langue anglais
  - `2` = collège (PEI)
  - `1` = 1er niveau
  - `1` = 1re classe de ce niveau
  - `01` = numéro d'élève dans la classe
- **40 slots par classe** (XXYY01 à XXYY40), pré-alloués avec `enabled = FALSE`
- Staff (professeurs, administration) : IDs 1–1000
- Primaire : IDs 100–2000
- Maternelle : IDs 2000–3000

---

## 2. Rôle SECR — Périmètre

Le rôle SECR correspond à `type_secretary = TRUE` dans `larcauth_aecuser` (colonne ajoutée le 05/06/2026).

| Fonction | Phase |
|---|---|
| Supervision présence / événements (importé de LarcSuperviseur) | 1 |
| Gestion des parents/tuteurs (lien N-N élèves ↔ parents) | 1 |
| Inscription des élèves (remplir un slot vide) | 1 (suite) |
| Mise à jour des coordonnées élève | 1 (suite) |
| Affectation / changement de classe | 1 (suite) |
| Activation / désactivation d'un élève | 1 (suite) |
| Paiements de scolarité (échéancier, encaissements, reçus) | 2 |
| Reporting financier | 2 |

**Principe :** `UPDATE` uniquement, jamais `INSERT` ni `DELETE` pour les entités stables (élèves, classes, places). Les événements (`student_event`) sont en INSERT libre — une timeline d'événements est imprévisible par nature.

---

## 3. Architecture applicative

```
LarcSecretaire/
├── main.py                  # QApplication + LoginWindow
├── config.ini               # (gitignoré)
├── requirements.txt         # PySide6 + psycopg2-binary
├── larcsecretaire.db        # SQLite locale (généré)
│
├── common/                  # Partagé depuis eLarcProfPy/LarcSuperviseur
│   ├── __init__.py
│   ├── network.py           # detect_network() → INTRANET/INTERNET/OFFLINE
│   ├── session.py           # UserRole (SECR), Session, session (global)
│   ├── database.py          # Database (psycopg2 Intranet + Cloud), db
│   ├── auth.py              # AuthManager (SHA-256) + OAuth2Manager (PKCE Google)
│   ├── theme.py             # ThemeManager MD3 (Material Light/Dark/Contrast)
│   ├── logger.py            # log() vers fichier
│   ├── sqlite_init.py       # SQLiteInit (DDL secrétaire), sqlite_init
│   ├── sync.py              # SyncManager (shadow-table), sync_manager
│   └── grid_config.py       # (réserve, inutilisé)
│
├── views/
│   ├── __init__.py
│   ├── login.py             # LoginWindow — 4 onglets auth
│   ├── main_window.py       # MainWindow — sidebar + dashboard KPIs + bascule supervision/parents + lanceur LarcSuperviseur
│   ├── password.py          # ChangePinDialog + ChangePasswordDialog
│   ├── supervisor_panel.py  # Grille de cartes élèves, clic → EditDialog modal, présence/événements
│   ├── parent_manager.py    # Liste parents, lien N-N élèves ↔ parents
│   ├── student_form.py      # Recherche + vignette + StudentEditDialog/StudentCreateDialog à 6 onglets
│   ├── class_view.py        # (à faire) grille classe
│   └── search.py            # (à faire) recherche
│
├── docs/
│   ├── 01_specifications.md  # Ce document
│   ├── 02_authentification.md
│   ├── 03_sync.md
│   ├── historique_construction.md
│   ├── student_event.sql     # DDL déployé Intranet + Supabase le 07/06/2026
│   └── student_parent.sql    # DDL déployé Intranet + Supabase le 07/06/2026
```

---

## 4. Navigation — Sidebar (gauche)

```
┌──────────────────────┐
│  Navigation          │
│  [📊 Tableau de bord]│
│                      │
│  INSCRIPTIONS        │
│  [🔍 Rechercher]     │
│  [➕ Nouvelle fiche] │
│  [👪 Gestion parents]│
│                      │
│  ── Collège ──       │
│  ┌──────┬──────┐     │
│  │ PEI  │ MYP  │     │
│  ├──────┼──────┤     │
│  │ 6111 │ 7111 │     │
│  │ 6112 │ 7121 │     │
│  │ 6121 │      │     │
│  └──────┴──────┘     │
│                      │
│  ── Lycée ──         │
│  ┌──────┬──────┐     │
│  │ DP   │ DPEn │     │
│  ├──────┼──────┤     │
│  │ 1011 │ 2001 │     │
│  │ 1021 │ 2011 │     │
│  └──────┴──────┘     │
│                      │
│  ● Intranet          │
└──────────────────────┘
```

Clic sur une classe → bascule en page Supervision (présence/événements pour cette classe).
Clic sur "Gestion parents" → page de gestion des liens élèves↔parents.

---

## 5. Phase 1 — Réalisé

### 5.1 Connexion (views/login.py)
- 4 onglets : Intranet (SHA-256), Cloud (OAuth2 Google), Hors connexion (PIN), Nouvelle instance
- Vérifie `type_secretary = TRUE` pour autoriser l'accès
- Boutons "Changer le mot de passe" (onglet Intranet) et "Changer le code PIN" (onglet Hors connexion)
- Détection réseau avec indicateur coloré en haut

### 5.2 Tableau de bord (views/main_window.py)
- **KPIs** : Total élèves actifs, Collège, Lycée, Places libres
- **Tableau répartition** par programme (PEI/MYP/DP/DPEn) avec taux de remplissage
- **Alertes** : élèves actifs sans parent/tuteur rattaché
- **Sidebar** : Navigation + Inscriptions + classes par programme (style LarcSuperviseur)
- **3 thèmes MD3** : Material Light, Dark, Contrast (cycle via bouton 🎨) — rafraîchit tous les styles inline
- **Barre d'état** : indicateur réseau Intranet/Cloud/Hors ligne

### 5.3 Supervision présence/événements (views/supervisor_panel.py)
- Importé et adapté depuis LarcSuperviseur
- Grille de cartes élèves avec présence du jour (✓/✕/—)
- Clic sur une vignette élève → ouvre `StudentEditDialog` en popup modal (grille reste visible)
- Historique des événements par élève dans le popup (onglet Événements, lecture seule)
- Bouton d'ajout d'événement (arrival, departure, exit, return, absence, justified, late)
- Bascule depuis un clic sur une classe dans la sidebar

### 5.4 Gestion des parents (views/parent_manager.py)
- Liste des parents/tuteurs (`type_parentutor = TRUE`)
- Filtre par texte (nom, email)
- Sélection d'un parent → affiche ses élèves liés
- Combo pour lier un nouvel élève (avec nature : père, mère, tuteur, etc.)
- Bouton Délier
- Table `student_parent` créée (DDL dans `docs/student_parent.sql`)

---

## 6. Phase 1 — Réalisé (suite)

### 6.1 Fiche élève (student_form.py)
Popup modale `StudentEditDialog` avec **6 onglets** + photo toujours visible :
1. **Identité** — nom, prénom, date d'entrée
2. **Contact** — email, email perso, tél. portable, tél. fixe
3. **Adresse** — ligne1, complément, CP, ville, pays
4. **Notes** — éditeur QTextEdit riche avec barre d'outils (gras, italique, listes, tableau 3×3), stockage HTML
5. **Fichiers & Parents** — explorateur `data/students/{id}/` + tableau parents/tuteurs liés
6. **Événements** — tableau lecture seule des événements de l'élève

Popup `StudentCreateDialog` avec la même structure à 6 onglets :
- Sélecteur de classe + champs identiques à l'édition
- Notes actives (sauvegardées en HTML dès la création)
- Onglets Fichiers & Parents et Événements en placeholder
- Détection auto slot libre, réinitialisation pour saisie batch

### 6.2 Superviseur → Fiche élève
- Clic sur vignette élève dans la grille Supervision → `StudentEditDialog` modal
- Photo dans le panneau détail (page 3) cliquable → `StudentEditDialog`

### 6.3 Lancement LarcSuperviseur
Bouton dans le dashboard (sous les alertes) : `subprocess.Popen(['python', 'LarcSuperviseur/main.py'])`.

## 7. Phase 1 — À faire

### 7.1 Vue classe (class_view.py)
Grille des élèves d'une classe avec :
- Statut toggle Actif/Inactif
- Double-clic → fiche élève
- Lignes inactives grisées
- Slots vides affichés

### 7.2 Recherche globale (search.py)
Barre de recherche multi-entités (élèves, parents, classes).

### 7.3 Sync
- Connecter `sync.py` aux nouvelles tables (`student_event`, `student_parent`)
- Bouton Synchroniser dans le dashboard

---

## 9. Phase 2 — Gestion financière (esquisse)

Tables à créer côté serveur : `tuition_fee_structure`, `student_invoice`, `payment_transaction`, `payment_plan`, `receipt`.

Workflow : `Grille tarifaire → Facture → Échéancier → Encaissement → Reçu`

---

## 10. Points forts

1. **Architecture éprouvée** — Auth, sync, thèmes, logger déjà rodés
2. **Philosophie gabarit** — Pas d'INSERT (sauf événements), sync simplifiée, pas de conflit d'ID
3. **Slots pré-alloués** confirmés (IDs 121101–121140 par classe)
4. **Mêmes connexions** — config.ini déjà en place
5. **Sync déjà opérationnelle** — triggers sync_version existent
6. **Module financier isolé en Phase 2**

## 11. Points faibles / Risques

1. **Adresse élève** — colonnes manquantes dans `larcauth_aecuser` (rue, CP, ville)
2. **Photos** — import à implémenter (upload PNG + redimensionnement)
3. **Conflits entre secrétaires** — deux modifications simultanées possibles
4. **Sécurité financière** (Phase 2)
5. **Pas de `gitignore`** — config.ini et *.db doivent être exclus
6. **DDLs non déployés** — `student_event.sql` et `student_parent.sql` doivent être exécutés sur Intranet et Supabase

---

## 12. Questions résolues

- [x] **Slots pré-alloués** confirmés : IDs 121101..121140 par classe
- [x] **type_secretary** : colonne ajoutée sur Intranet et Cloud (05/06/2026)
- [x] **Compte secrétaire** : patrlabo@arc-en-ciel.org (id=1021, Patrice LABONNE)
- [x] **Filtrage PP/PYP** exclu de toutes les vues (Collège/Lycée seulement)
- [x] **SupervisorPanel** intégré depuis LarcSuperviseur
- [x] **ParentManager** créé (vue + table student_parent)
- [ ] Adresse : colonnes à vérifier/ajouter
- [ ] Photo : import à définir
- [ ] DDLs à déployer sur serveur
