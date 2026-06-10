# Processus d'enregistrement de LarcSecretaire

## Vue d'ensemble

LarcSecretaire connecte l'utilisateur à PostgreSQL (Intranet ou Cloud Supabase)
via psycopg2, lit/écrit les données élève/foyer/parent/événements, et maintient
une base SQLite locale (`larcsecretaire.db`) pour le mode hors-ligne et la sync.

---

## 1. Connexion à la base de données

### Au démarrage de LoginWindow

```python
# login.py — __init__
db.connect_intranet()           # Tente Intranet d'abord
if db.server_conn is None:      # Si échec
    db.connect_cloud()          # Tente Cloud Supabase
sqlite_init.init()              # Toujours : crée/ouvre larcsecretaire.db
```

### DBMode & server_conn

```
DBMode.INTRANET → db._intranet (PostgreSQL 192.168.2.90:5432/NewLarcDB)
DBMode.CLOUD    → db._cloud    (PostgreSQL via Supabase PgBouncer 6543)
DBMode.NONE     → None
```

**Propriété `server_conn`** (common/database.py:162) :
```python
@property
def server_conn(self):
    if self._server_mode == DBMode.INTRANET:
        return self._intranet
    if self._server_mode == DBMode.CLOUD:
        return self._cloud
    return None
```

**Les deux connexions PostgreSQL ont `autocommit = True`** :
Chaque `cur.execute()` est immédiatement commité. `conn.commit()` est sans
effet. `conn.rollback()` en cas d'erreur est également sans effet sur les
requêtes déjà exécutées.

---

## 2. Authentification

### Intranet

1. Saisie : email + mot de passe
2. Calcul SHA-256 du mot de passe saisi
3. Requête PostgreSQL :
   ```sql
   SELECT id, email, last_name, first_name, password
   FROM larcauth_aecuser
   WHERE email = %s
   ```
4. Comparaison du hash stocké avec le hash calculé
5. Vérification du rôle :
   ```sql
   SELECT is_adm, is_coordonator, is_secretary
   FROM larcauth_teachadm
   WHERE aecuser_id = %s
   ```
6. Si `is_secretary = TRUE` → autorisé

### Cloud (OAuth2 Google)

1. PKCE : génération verifier + challenge
2. Ouverture du navigateur → Google OAuth2 (`hd=arc-en-ciel.org`)
3. Callback HTTP sur `localhost:8765`
4. Échange du code contre des tokens
5. Décodage du JWT (payload seulement)
6. Vérification `hd == 'arc-en-ciel.org'`
7. Cross-check : `module_config.email_professeur` en SQLite
8. Re-quête du rôle dans PostgreSQL

### PIN (Hors-ligne)

1. SHA-256 du PIN
2. Requête SQLite :
   ```sql
   SELECT user_id, email, full_name, role, pin_hash
   FROM session_cache
   WHERE email = ? AND pin_hash = ?
   ```

### Post-auth — `_on_auth_done()` (login.py:355)

```python
# 1. Vérification secrétaire
_check_secretary_exists(res.email)
# → "SELECT id, last_name, first_name, email FROM larcauth_aecuser
#     WHERE email = %s AND type_secretary = TRUE AND is_active = TRUE"

# 2. Init SQLite
sqlite_init.init()

# 3. Sauvegarde en module_config
set_module_config("secretary_name", res.full_name)
set_module_config("secretary_email", res.email)
set_module_config("secretary_id", str(res.user_id))

# 4. Session globale
session.user_id = res.user_id
session.email = res.email
session.full_name = res.full_name
session.role = UserRole.SECR

# 5. Lancement MainWindow
main_window = MainWindow()
main_window.showMaximized()
```

---

## 3. Flux de consultation — Dashboard

### Queries KPIs (main_window.py)

Toutes les requêtes utilisent `db.server_conn` (PostgreSQL, Intranet ou Cloud).

**Total élèves actifs :**
```sql
SELECT COUNT(*) FILTER (WHERE enabled = TRUE) AS total_actifs
FROM larcauth_student
WHERE s_classroom_id IN (
    SELECT c.id FROM larcauth_classroom c
    JOIN larcauth_level l ON l.id = c.fk_level_id
    JOIN larcauth_program pr ON pr.id = l.fk_program_id
    WHERE pr.sigle IN ('PEI', 'MYP', 'DPEn', 'DPFr')
)
```

**Effectifs par programme :**
```sql
SELECT pr.sigle,
       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE) AS actifs,
       COUNT(s.aecuser_ptr_id) AS slots,
       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE AND g.sigle IN ('M','Mr')) AS garcons,
       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE AND g.sigle IN ('F','Mme')) AS filles
FROM larcauth_classroom c
JOIN larcauth_level l ON l.id = c.fk_level_id
JOIN larcauth_program pr ON pr.id = l.fk_program_id
LEFT JOIN larcauth_student s ON s.s_classroom_id = c.id
LEFT JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
LEFT JOIN larcauth_gender g ON g.id = aec.fk_gender_id
WHERE pr.sigle IN ('PEI', 'MYP', 'DPEn', 'DPFr')
GROUP BY pr.id, pr.sigle
ORDER BY pr.sigle
```

**Répartition par niveau (graphique) :**
```sql
SELECT l.label, pr.sigle, COUNT(*) AS cnt
FROM larcauth_student s
JOIN larcauth_classroom c ON c.id = s.s_classroom_id
JOIN larcauth_level l ON l.id = c.fk_level_id
JOIN larcauth_program pr ON pr.id = l.fk_program_id
WHERE pr.sigle IN ('PEI', 'MYP', 'DPEn', 'DPFr') AND s.enabled = TRUE
GROUP BY l.id, l.label, pr.sigle
ORDER BY l.id
```

---

## 4. Flux de recherche

### StudentForm.search() (student_form.py:240)

```python
def search(self, query: str):
    like = f"%{query}%"
    cur.execute("""
        SELECT s.aecuser_ptr_id AS id,
               aec.last_name, aec.first_name,
               aec.email, aec.emailperso,
               aec.tel_smartphone_1, aec.tel_maison,
               c.label AS classroom,
               aec.date_entree, aec.fk_foyer_id,
               aec.fk_gender_id, s.s_classroom_id,
               s.notes,
               f.address_line1, f.address_line2, f.postal_code,
               f.city, f.country,
               f.phone AS foyer_phone, f.email AS foyer_email
        FROM larcauth_student s
        JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
        JOIN larcauth_classroom c ON c.id = s.s_classroom_id
        LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
        WHERE s.enabled = TRUE
          AND (aec.last_name ILIKE %s OR aec.first_name ILIKE %s
            OR aec.email ILIKE %s OR c.label ILIKE %s)
        ORDER BY aec.last_name, aec.first_name
        LIMIT 200
    """, (like, like, like, like))
    cols = [desc[0] for desc in cur.description]
    self._results = [dict(zip(cols, row)) for row in cur.fetchall()]
```

### Sélection d'un résultat

```python
_on_result_selected()
  └─ _open_student_dialog(student_id)
       ├─ Re-quête DB (mêmes colonnes + foyer JOIN)
       │   WHERE s.aecuser_ptr_id = %s
       ├─ self._current_student = data  # dict avec 20+ clés
       ├─ _update_info_card(data)
       │   ├─ Photo : LarcSuperviseur/photos/{id}.png
       │   ├─ Nom, classe, ID
       └─ Affiche panneau détail + bouton "Ouvrir la fiche"
```

---

## 5. Flux d'édition — StudentEditDialog

### Ouverture du dialogue

```python
_open_edit_dialog()
  └─ dlg = StudentEditDialog(self._current_student, self)
       ├─ __init__ :
       │   ├─ self._data = data          # dict de l'élève
       │   ├─ self._sid = data['id']     # ID PostgreSQL
       │   ├─ _init_ui()                 # Construit les 6 onglets
       │   │   └─ _load_genders()        # Initial : tous les genres
       │   └─ _load_data()               # Remplit tous les champs
       │       ├─ _inp_nom.setText(...)
       │       ├─ _inp_prenom.setText(...)
       │       ├─ _inp_date.setDate(...) # QDateEdit avec calendrier popup
       │       ├─ _load_genders(lang_id, include_gid=current_gid)
       │       │   # Filtre par langue de la classe + conserve genre existant
       │       ├─ _inp_addr1.setText(...)
       │       ├─ _inp_notes.setHtml(...) # Notes HTML
       │       ├─ _load_parents()         # Requête student_parent
       │       └─ _load_events()          # Requête student_event
       └─ dlg.exec()                      # Modal — bloque jusqu'à fermeture
```

### Sauvegarde — `_save()` (student_form.py:887)

```
_save()
│
├── [1] Vérification connexion
│     db.server_conn → None ? → alerte + return
│
├── [2] Collecte des valeurs UI → dict aec
│     ┌────────────────────────────┬────────────────────────────┐
│     │ last_name                  │ QLineEdit.text().strip()   │
│     │ first_name                 │ QLineEdit.text().strip()   │
│     │ email                      │ QLineEdit.text().strip()   │
│     │ emailperso                 │ QLineEdit → str or None    │
│     │ tel_smartphone_1           │ QLineEdit → str or None    │
│     │ tel_maison                 │ QLineEdit → str or None    │
│     │ date_entree                │ QDateEdit → yyyy-MM-dd     │
│     │                            │   ou None si non définie   │
│     │ fk_gender_id               │ QComboBox.currentData()    │
│     │                            │   ou None                  │
│     │ updated                    │ datetime.now().isoformat() │
│     └────────────────────────────┴────────────────────────────┘
│
├── [3] UPDATE larcauth_aecuser
│     SQL : "UPDATE larcauth_aecuser SET col1=%s, col2=%s, ...
│            WHERE id=%s"
│     Param : list(aec.values()) + [self._sid]
│     Vérification : if rowcount == 0 → ValueError
│
├── [4] UPSERT foyer
│     Détermine foyer_id :
│       fid = self._data.get('fk_foyer_id') or self._sid
│     Collecte adresse :
│       address_line1, address_line2, postal_code, city, country
│     SQL :
│       "INSERT INTO foyer (id, col1, col2, ...)
│        VALUES (%s, %s, %s, ...)
│        ON CONFLICT (id) DO UPDATE SET
│        col1=EXCLUDED.col1, col2=EXCLUDED.col2, ..."
│
├── [5] Traitement notes HTML
│     notes = _inp_notes.toHtml().strip()
│     Si non vide :
│       Remplacement regex des chemins absolus → relatifs
│       "file:///base/notes_img/xxx" → "notes_img/xxx"
│
├── [6] UPDATE larcauth_student SET notes
│     SQL : "UPDATE larcauth_student SET notes = %s
│            WHERE aecuser_ptr_id = %s"
│     Vérification : if rowcount == 0 → ValueError
│
├── [7] conn.commit()  # Sans effet car autocommit=True
│
├── [8] Vérification : re-lecture DB
│     SELECT last_name, first_name, email, date_entree, fk_gender_id
│     FROM larcauth_aecuser WHERE id = %s
│
├── [9] QMessageBox "Élève mis à jour."
│
└── [10] self.accept() → fermeture du dialogue (QDialog.Accepted)
```

### Gestion d'erreur

```python
except Exception as e:
    conn.rollback()                  # sans effet (autocommit=True)
    log(f"StudentEditDialog._save: {e}")
    QMessageBox.critical(self, "Erreur", str(e))
    # Dialogue reste ouvert
```

---

## 6. Rafraîchissement après édition

### StudentForm._open_edit_dialog()

```python
if dlg.exec():  # True si Accepté
    self.search(self._search_input.text().strip())
    # → Re-quête PostgreSQL → self._results mis à jour

    self._open_student_dialog(self._current_student['id'], force_refresh=True)
    # → Re-quête DB → self._current_student actualisé
    # → _update_info_card() rafraîchie
```

### SupervisorPanel._on_student_clicked()

```python
if dlg.exec():
    self._load_students()    # Re-quête des élèves de la classe
    self._load_presence()    # Re-quête des événements du jour
```

---

## 7. Flux de création — StudentCreateDialog

### Détection du slot libre

```python
# _on_class_changed(class_id)
cur.execute("""
    SELECT s.aecuser_ptr_id, aec.last_name, s.enabled
    FROM larcauth_student s
    JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
    WHERE s.s_classroom_id = %s
    ORDER BY s.aecuser_ptr_id
""", (class_id,))

# Parcourt les 40 slots (01-40), cherche :
#   - enabled = FALSE
#   - last_name LIKE '%Name of%'  (placeholder)
# premier slot libre → student_id = class_id * 100 + slot
```

### Création — `_create_student()` (student_form.py:1880)

```
_create_student()
│
├── [1] ID = self._class_id * 100 + slot
│
├── [2] UPDATE larcauth_aecuser
│     SQL :
│       "UPDATE larcauth_aecuser SET
│          first_name=%s, last_name=%s, email=%s,
│          username=%s, is_active=TRUE, updated=%s,
│          emailperso=%s, tel_smartphone_1=%s, tel_maison=%s,
│          date_entree=%s, fk_gender_id=%s
│        WHERE id=%s"
│
├── [3] UPDATE larcauth_student
│     SQL :
│       "UPDATE larcauth_student SET
│          enabled=TRUE, updated_s=%s, notes=%s
│        WHERE aecuser_ptr_id=%s"
│
├── [4] UPSERT foyer
│     INSERT INTO foyer (id, enabled, address_line1, ...)
│     VALUES (%s, TRUE, %s, ...)
│     ON CONFLICT (id) DO UPDATE SET ...
│
├── [5] UPDATE aecuser SET fk_foyer_id = student_id
│
├── [6] conn.commit()  # Sans effet (autocommit)
│
├── [7] Reset du formulaire pour saisie suivante
│       (champs vidés, pays="Togo", nouveau slot libre)
│
└── [8] Le dialogue reste ouvert (création batch)
```

---

## 8. Flux Supervision — Présence

### Chargement des élèves

```python
# supervisor_panel.py — _load_students()
cur.execute("""
    SELECT s.aecuser_ptr_id AS id,
           aec.last_name, aec.first_name
    FROM larcauth_student s
    JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
    WHERE s.s_classroom_id = %s AND s.enabled = TRUE
    ORDER BY aec.last_name, aec.first_name
""", (class_id,))
```

### Chargement de la présence

```python
# supervisor_panel.py — _load_presence()
# Détermine pour chaque élève :
#   - ABSENT  → event_type='absence' ET validated_by IS NULL
#   - PRESENT → event_type != 'absence'
#   - UNKNOWN → aucun événement aujourd'hui
```

### Ajout d'événement

```python
# _on_add_event()
dialog = EventDialog()  # Type + note optionnelle
if dialog.exec():
    data = dialog.get_data()
    cur.execute("""
        INSERT INTO student_event
            (student_id, event_type, event_at, note, source, created_by)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (data['student_id'], data['event_type'],
          data['event_at'], data['note'][:200],
          'intranet', session.user_id))
    conn.commit()
```

---

## 9. Base SQLite locale — `larcsecretaire.db`

### Tables

| Table | Usage |
|---|---|
| `session_cache` | Auth hors-ligne (email, pin_hash, role) |
| `module_config` | Config clé-valeur (secretary_name, etc.) |
| `sync_state` | Timestamp dernière sync par table |
| `student_profile` | Shadow local données élève |
| `student_profile_ref` | Snapshot référence pour diff sync |
| `foyer` | Shadow local adresses |
| `student_parent` | Shadow local liens parent-élève |

### Initialisation

```python
# common/sqlite_init.py
def init():
    conn = sqlite3.connect("larcsecretaire.db")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(DDL)  # CREATE TABLE IF NOT EXISTS
    return conn
```

---

## 10. Synchronisation device ↔ serveur

### Pattern shadow-table (common/sync.py)

```
Table travail     → student_profile
Table référence   → student_profile_ref

Au seed (1e connexion) :
  student_profile = student_profile_ref = données serveur

À chaque sync :
  1. Diff : JOIN student_profile / student_profile_ref
     → cellules modifiées localement
  2. Pull : serveur → student_profile + student_profile_ref
  3. Push : student_profile → serveur + student_profile_ref
```

**Note :** Le sync n'est pas encore branché sur le flux d'édition.
`StudentEditDialog._save()` écrit directement sur PostgreSQL sans
transiter par le système de shadow-tables. L'intégration sync est
prévue pour une phase ultérieure.

---

## 11. Points critiques à retenir

1. **`autocommit = True`** sur les deux connexions PostgreSQL.
   `conn.rollback()` en cas d'erreur n'annule PAS les requêtes déjà exécutées.
   Une erreur sur la foyer après la mise à jour aecuser → aecuser modifié,
   foyer pas modifié, pas de rollback.

2. **Pas de `before_update()`** dans `_save()` — les variables session
   PostgreSQL (app.sync_source, app.modified_by) ne sont pas positionnées.
   Les triggers de sync ne sont pas informés.

3. **Le genre existant de l'élève** (`include_gid`) est conservé même s'il
   n'appartient pas à la langue de la classe — évite la perte silencieuse
   de la valeur.

4. **La date utilise `QDateEdit`** avec calendrier popup — format ISO garanti
   `yyyy-MM-dd` côté base.

5. **Principe gabarit** : les élèves existent déjà en base (slots pré-alloués).
   Création = `UPDATE enabled=TRUE` + mise à jour des champs. Pas d'INSERT.

6. **Vérification post-sauvegarde** : re-lecture DB avec `SELECT` après le
   `commit()` pour confirmer la persistance des données.
