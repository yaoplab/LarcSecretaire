# LarcSecretaire — Spécifications fonctionnelles et techniques

> Module desktop pour les secrétaires : inscription des élèves (Phase 1) + gestion financière (Phase 2).

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
| Inscription des élèves (remplir un slot vide) | 1 |
| Mise à jour des coordonnées élève | 1 |
| Affectation / changement de classe | 1 |
| Gestion des parents/tuteurs | 1 |
| Activation / désactivation d'un élève | 1 |
| Paiements de scolarité (échéancier, encaissements, reçus) | 2 |
| Reporting financier | 2 |

**Principe :** `UPDATE` uniquement, jamais `INSERT` ni `DELETE`. Confirmé par le schéma d'IDs : les 40 slots par classe existent en base.

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
│   ├── main_window.py       # MainWindow — sidebar + dashboard KPIs
│   ├── password.py          # ChangePinDialog + ChangePasswordDialog
│   ├── student_form.py      # (à faire) fiche élève
│   ├── class_view.py        # (à faire) grille classe
│   ├── search.py            # (à faire) recherche
│   └── parent_manager.py    # (à faire) gestion parents
│
└── docs/
    ├── 01_specifications.md  # Ce document
    ├── 02_authentification.md
    ├── 03_sync.md
    └── historiques_construction.md
```

---

## 4. Navigation — Sidebar (gauche)

```
┌──────────────────────┐
│  Navigation          │
│                      │
│  [📊 Tableau de bord]│
│                      │
│  INSCRIPTIONS        │
│  [🔍 Rechercher]     │
│  [➕ Nouvelle fiche] │
│                      │
│  CLASSES             │
│    PEI               │
│      PEI-5A          │
│      PEI-5B          │
│    MYP               │
│      MYP-1A          │
│    DP                │
│    DPEn              │
│                      │
│  ● Intranet          │
└──────────────────────┘
```

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
- **Sidebar** : Navigation avec liste des classes par programme
- **3 thèmes MD3** : Material Light, Dark, Contrast (cycle via bouton 🎨)
- **Barre d'état** : indicateur réseau Intranet/Cloud/Hors ligne

---

## 6. Phase 1 — À faire

### 6.1 Fiche élève (student_form.py)
Champs à éditer :
- `larcauth_aecuser` : `first_name`, `last_name`, `firstname_2`, `email`, `emailperso`, `tel_maison`, `tel_smartphone_1`, `tel_smartphone_2`, `fk_gender_id`, `date_entree`
- `larcauth_student` : `s_classroom_id`, `enabled`
- Adresse : à vérifier (table `larcauth_address` ou colonnes à ajouter)

### 6.2 Vue classe (class_view.py)
Grille des élèves d'une classe avec :
- Statut toggle Actif/Inactif
- Double-clic → fiche élève
- Lignes inactives grisées
- Slots vides affichés

### 6.3 Recherche (search.py)
Barre de recherche globale avec résultats en temps réel.

### 6.4 Gestion des parents (parent_manager.py)
Lier un parent (`type_parentutor = TRUE`) à un élève via `fk_parent_id`.

---

## 7. Phase 2 — Gestion financière (esquisse)

Tables à créer côté serveur : `tuition_fee_structure`, `student_invoice`, `payment_transaction`, `payment_plan`, `receipt`.

Workflow : `Grille tarifaire → Facture → Échéancier → Encaissement → Reçu`

---

## 8. Points forts

1. **Architecture éprouvée** — Auth, sync, thèmes, logger déjà rodés
2. **Philosophie gabarit** — Pas d'INSERT, sync simplifiée, pas de conflit d'ID
3. **Slots pré-alloués** confirmés (IDs 121101–121140 par classe)
4. **Mêmes connexions** — config.ini déjà en place
5. **Sync déjà opérationnelle** — triggers sync_version existent
6. **Module financier isolé en Phase 2**

## 9. Points faibles / Risques

1. **Adresse élève** — colonnes manquantes dans `larcauth_aecuser` (rue, CP, ville)
2. **Photos** — import à implémenter (upload PNG + redimensionnement)
3. **Conflits entre secrétaires** — deux modifications simultanées possibles
4. **Sécurité financière** (Phase 2)
5. **Pas de `gitignore`** — config.ini et *.db doivent être exclus

---

## 10. Questions résolues

- [x] **Slots pré-alloués** confirmés : IDs 121101..121140 par classe
- [x] **type_secretary** : colonne ajoutée sur Intranet et Cloud (05/06/2026)
- [x] **Compte secrétaire** : patrlabo@arc-en-ciel.org (id=1021, Patrice LABONNE)
- [ ] Adresse : colonnes à vérifier/ajouter
- [ ] Photo : import à définir
