# LarcSecretaire — Authentification

## Modes de connexion

### 1. Intranet (SHA-256)

Connexion directe au PostgreSQL Intranet (127.0.0.1:5432/NewLarcDB).

```python
# Requête auth
SELECT id, email, last_name, first_name, password
FROM larcauth_aecuser
WHERE LOWER(email) = %s AND type_secretary = TRUE AND is_active = TRUE

# Vérification hash
stored_hash == sha256(password)
```

Étapes :
1. L'utilisateur saisit email + mot de passe
2. `_Worker` exécute `AuthManager.auth_intranet(email, pwd)` dans un QThread
3. Le thread vérifie le hash SHA-256 côté serveur
4. `_on_auth_done` vérifie que `type_secretary = TRUE` via `_check_secretary_exists()`
5. Si OK → initialise SQLite, sauvegarde `module_config`, ouvre `MainWindow`

### 2. Cloud (OAuth2 PKCE Google)

Authentification via Google OAuth2 avec PKCE, réservée aux comptes `@arc-en-ciel.org`.

```python
# OAuth2Manager gère :
# 1. Code Verifier (S256) + Challenge
# 2. Ouverture navigateur → auth Google
# 3. Serveur HTTP local (port 8765) pour le callback
# 4. Échange code → token → profile Google
# 5. Vérification email @arc-en-ciel.org
```

Étapes :
1. L'utilisateur clique "Connexion Google"
2. OAuth2Manager génère un code verifier PKCE
3. Le navigateur s'ouvre sur l'écran de connexion Google
4. Après auth, Google redirige vers `http://localhost:8765/callback`
5. Le serveur HTTP local capture le code d'autorisation
6. Échange du code contre un token d'accès
7. Récupération du profil (email, nom)
8. Vérification du domaine `@arc-en-ciel.org` et `type_secretary = TRUE`

*Les sections PIN (Hors ligne) et Nouvelle instance ont été supprimées — non retenues pour le périmètre secrétariat.*

---

## Rôle SECR

Colonne `type_secretary BOOLEAN DEFAULT FALSE` dans `larcauth_aecuser`.

```sql
-- Ajoutée le 05/06/2026
ALTER TABLE larcauth_aecuser ADD COLUMN type_secretary BOOLEAN DEFAULT FALSE;

-- Activation compte
UPDATE larcauth_aecuser SET type_secretary = TRUE WHERE id = 1021;
-- (patrlabo@arc-en-ciel.org, Patrice LABONNE)
```

La vérification se fait dans `_check_secretary_exists()` côté client après l'auth :

```python
cur.execute("""
    SELECT aec.id, aec.last_name, aec.first_name, aec.email
    FROM larcauth_aecuser aec
    WHERE LOWER(aec.email) = %s AND aec.type_secretary = TRUE AND aec.is_active = TRUE
    LIMIT 1
""", (email,))
```

---

## Changement de credentials

| Dialog | Déclencheur | Cible |
|---|---|---|
| `ChangePasswordDialog` | Bouton onglet Intranet | `larcauth_aecuser.password` (SHA-256) |
| ~~`ChangePinDialog`~~ | ~~Bouton onglet Hors connexion~~ | ~~`session_cache.pin_hash` (SQLite)~~ |
