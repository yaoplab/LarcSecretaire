# LarcSecretaire — Contexte projet

_Dernière mise à jour : 5 juin 2026_

## Règle importante — Décisions avant actions
Quand je demande "qu'est-ce que tu penses ?" à propos d'une approche ou d'une solution,
**ne rien modifier ni implémenter** avant d'avoir donné mon avis et confirmé la décision.
D'abord répondre avec l'analyse/avis, puis attendre mon accord avant d'exécuter.

## Décision technique
Version **Python/PySide6** retenue pour le desktop. Même stack que eLarcProfPy et LarcSuperviseur.
**Pas PyQt5, pas PyQt6, pas Flet** — PySide6 uniquement.
Mobile/tablette = phase ultérieure (FastAPI + Flutter ou PWA).

## Environnement
- Python 3.x + PySide6 (Qt6)
- Venv : `.venv/` dans le répertoire du projet
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
│   ├── network.py          # detect_network() → INTRANET/INTERNET/OFFLINE
│   ├── session.py          # UserRole (SECR, PROF, COORD, ADMIN), session (global)
│   ├── database.py         # Database class, db (global singleton)
│   ├── auth.py             # AuthManager (Intranet SHA-256) + OAuth2Manager (PKCE Google)
│   ├── sqlite_init.py      # SQLiteInit, DDL secrétaire, save_session
│   ├── sync.py             # SyncManager (shadow-table diff cellule)
│   ├── theme.py            # ThemeManager MD3 (Material Light/Dark/Contrast)
│   ├── logger.py           # log() vers fichier
│   └── grid_config.py      # (réserve)
├── views/
│   ├── login.py            # LoginWindow — 4 onglets auth
│   ├── password.py         # ChangePinDialog + ChangePasswordDialog
│   └── main_window.py      # MainWindow — sidebar + dashboard
├── docs/
│   ├── 01_specifications.md
│   ├── 02_authentification.md
│   ├── 03_sync.md
│   └── historique_construction.md
```

## Rôles utilisateurs
| Rôle | Accès |
|---|---|
| SECR | Gestion des élèves, inscriptions, parents ; pas de modification des notes/profs |
| PROF | (hors périmètre) |
| COORD | (hors périmètre) |
| ADMIN | (hors périmètre) |

## Phase 1 — EN COURS (connexion + dashboard terminés)
- Connexion Intranet (SHA-256 password) → vérifie `type_secretary = TRUE`
- Connexion Cloud (OAuth2 PKCE Google @arc-en-ciel.org)
- Connexion PIN (hors ligne, hash SHA-256 en SQLite)
- Nouvelle instance (copie du projet)
- Dashboard avec KPIs (total élèves, collège, lycée, places libres)
- Tableau répartition par programme (PEI/MYP/DP/DPEn)
- Alertes (élèves sans parent rattaché)
- Sidebar avec classes par programme
- 3 thèmes MD3 cyclables (Light/Dark/Contrast)

Prochaines étapes :
1. Fiche élève (édition coordonnées)
2. Vue classe (grille élèves par classe)
3. Recherche globale
4. Gestion des parents/tuteurs

## Phase 2 — À VENIR
Gestion financière : paiements de scolarité, échéancier, reçus.

## Architecture de synchronisation
Same as eLarcProfPy : shadow-table `_ref`, diff cellule, pull/push. Voir `docs/03_sync.md`.

## Identifiants élèves (gabarit)
Format `XXYYZZ` : ex. `121101` = élève n°01, classe 1211 (anglais, collège PEI, niveau 1, classe 1). 40 slots par classe (XXYY01 à XXYY40).

## Compte secrétaire
- Email : `patrlabo@arc-en-ciel.org`
- ID : 1021 (Patrice LABONNE)
- Rôle : `type_secretary = TRUE` (colonne ajoutée le 05/06/2026 sur Intranet et Cloud)
