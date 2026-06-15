# LarcSecretaire V4Pro — AGENTS.md

## Stack
- Python/PySide6 (Qt6) — pas PyQt5/PyQt6/Flet
- `.venv` activé : `python .venv\Scripts\python.exe` (Python 3.14.5, PySide6 6.11)
- Lancement : `python main.py`
- Dépendances : `pip install -r requirements.txt`

## Imports
Tous les imports internes utilisent le chemin absolu depuis le package `LarcSecretaire` :
```python
from LarcSecretaire.common.database import db
from LarcSecretaire.views.login import LoginWindow
```
`main.py` ajoute le parent (`C:\Projets`) au `sys.path` pour que ça marche.

## Bases de données
- **Intranet** : PostgreSQL `127.0.0.1:5432/NewLarcDB` (SHA-256)
- **Cloud** : Supabase PostgreSQL via PgBouncer port 6543 (OAuth2 PKCE Google @arc-en-ciel.org)
- **Local** : SQLite `larcsecretaire.db` (cache + sync)
- Connexion auto-détectée via `detect_network()`
- `config.ini` requis dans la racine (gitignoré)

## Conventions critiques

### Gabarit (template) — UPDATE uniquement
- Tous les élèves pré-existent avec des noms placeholders `'Name of XXXX'`
- **Ne jamais faire d'INSERT** sur `larcauth_student` ou `larcauth_parent` — toujours UPDATE
- Slot libre = `enabled = FALSE AND last_name LIKE 'Name of %'`
- IDs parents : 10001–10800 (pré-remplis `larcauth_parent.enabled = FALSE`)
- Format ID élève : `XXYYZZ` (classe + n°, ex. `121101`)
- Exceptions autorisées à l'INSERT : `student_event`, fichiers disque `data/students/{id}/`

### JSONB / PgBouncer
- `notes_json` (JSONB) nécessite `json.dumps()` avant `cur.execute()` sur Cloud (PgBouncer ne type pas correctement)
- Toujours : `cur.execute(..., (json.dumps(data),))`

### Photos
- Photos élèves : `C:\Projets\LarcSuperviseur\photos\{id}.png`
- Cloud : télécharge depuis Supabase Storage dans `data/photos/cache/`

### GUI
- 3 thèmes MD3 cyclables (Light/Dark/Contrast) via `ThemeManager`
- Boutons d'action en haut du StudentEditDialog (Enregistrer, PDF, Word, Annuler)
- 7 sections Notes JSONB : Confidentielle, Médicale, Pédagogique, Administrative, Communication, Orientation, Autre

### Compte secrétaire de test
- Email : `patrlabo@arc-en-ciel.org`, ID 1021, `type_secretary = TRUE`

## Pas de tests / lint / CI
Aucune config pytest, ruff, mypy, pre-commit ou CI. Tout se vérifie en lançant l'app.

## Projets siblings
- `C:\Projets\eLarcProfPy\` — partage `common/` et `config.ini` (fallback)
- `C:\Projets\LarcSuperviseur\` — partage le dossier `photos/`
