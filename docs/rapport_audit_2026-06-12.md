# Rapport d'audit — LarcSecretaire ↔ LarcSuperviseur

**Date :** 12 juin 2026  
**Périmètre :** LarcSecretaire V4Pro + LarcSuperviseur  
**Méthode :** Analyse statique du code, DDLs, documentation et cohérence inter-applications

---

## Résumé

| Catégorie | Nombre |
|---|---|---|
| **Bugs code** | 6 |
| **Incohérences doc/code** | 7 |
| **Failles de sécurité / robustesse** | 8 |
| **Évolutions à faire** | 3 |
| **Nettoyages demandés** | 2 |
| **Total** | **26** |

---

## 1. Bugs de code

### 1.1 LarcSecretaire — Onglet 2 "Contact" : espace réservé (pas un bug)
- **Fichier :** `views/student_form.py:621-622`
- **Sévérité :** INFORMATION (intentionnel)
- **Détail :** L'onglet "Contact" est laissé volontairement vide. C'est un espace réservé pour y placer ultérieurement des informations destinées aux superviseurs (coordonnées des parents, etc.). Les champs `_inp_email`, `_inp_emailperso`, `_inp_tel`, `_inp_tel2` existent mais ne sont pas encore intégrés à l'UI dans l'attente de la décision sur le contenu exact de cet onglet.
- **À faire :** Définir le contenu exact de l'onglet Contact (coordonnées parents pour le superviseur, etc.) puis remplir le layout.

### 1.2 LarcSecretaire — QMessageBox de debug en production
- **Fichier :** `views/student_form.py:986-993, 1019-1020`
- **Sévérité :** MOYENNE (UX dégradée)
- **Détail :** 4 `QMessageBox.information()` de debug (`Debug 1/6` à `Debug 4/6`) affichent le contenu des requêtes SQL intermédiaires lors de `_save()`. L'utilisateur voit des popups avec des détails techniques.
- **Correction :** Supprimer ces 4 QMessageBox ou les remplacer par des `log()`.

### 1.3 LarcSecretaire — `autocommit = True` rend le `rollback()` inopérant
- **Fichiers :** `common/database.py:76,104` + `views/student_form.py:1043` + `views/supervisor_panel.py:483`
- **Sévérité :** HAUTE (intégrité données)
- **Détail :** Les connexions PostgreSQL sont en `autocommit = True`, donc chaque requête est commitée immédiatement. Le `conn.rollback()` dans les blocs `except` n'a aucun effet. Si la 2ème requête d'un bloc multi-requêtes échoue, la 1ère est déjà persistée — potentiel état incohérent.
- **Correction :** Soit gérer les transactions manuellement (`autocommit = False` + `conn.commit()` explicite), soit accepter le mode autocommit et supprimer les `rollback()` trompeurs.

### 1.4 LarcSecretaire — `SET LOCAL` exécuté APRÈS `conn.commit()`
- **Fichier :** `views/student_form.py:1024-1028`
- **Sévérité :** MOYENNE (triggers serveur non informés)
- **Détail :** `conn.commit()` ligne 1024, puis `SET LOCAL app.sync_source = 'intranet'` ligne 1027. `SET LOCAL` n'a d'effet que dans la transaction courante — or la transaction est déjà terminée. Le trigger serveur ne reçoit pas l'information.
- **Correction :** Déplacer les `SET LOCAL` avant le `conn.commit()`.

### 1.5 LarcSuperviseur — `event_type` CHECK constraint désynchronisé
- **Fichier :** `sql/student_event.sql:25-28` vs `views/main_window.py:734,767`
- **Sévérité :** CRITIQUE
- **Détail :** Le CHECK constraint n'autorise que 7 valeurs legacy : `'arrival', 'departure', 'exit', 'return', 'absence', 'justified', 'late'`. Mais `EventGenerator._on_niv3_clicked()` (ligne 734) construit des chemins hiérarchiques comme `"Sortie > Perturbation > Bavardage"`. Ces valeurs sont insérées telles quelles (ligne 290, 2034). Si le CHECK constraint existe encore sur le serveur, ces INSERTs échouent.
- **Correction :** Modifier ou supprimer le CHECK constraint dans le DDL (et sur le serveur) : `CHECK (event_type IS NOT NULL)` ou `CHECK (char_length(event_type) > 0)`.

### 1.6 LarcSuperviseur — Colonnes `lieu_label` et `subject_label` absentes du DDL
- **Fichier :** `sql/student_event.sql:19-36` vs `views/main_window.py:290,2034`
- **Sévérité :** MOYENNE (DDL obsolète)
- **Détail :** Les INSERT utilisent les colonnes `lieu_label` et `subject_label` mais le DDL dans le fichier ne les déclare pas. Elles ont probablement été ajoutées manuellement sur le serveur. Le fichier SQL ne reflète pas l'état réel de la base.
- **Correction :** Ajouter les `ALTER TABLE` manquants dans le fichier `student_event.sql` et le synchroniser avec le `sql/run_ddl.py`.

### 1.7 LarcSecretaire — `application_name = 'eLarcProf'` hardcodé
- **Fichier :** `common/database.py:58`
- **Sévérité :** FAIBLE (traçabilité)
- **Détail :** Toutes les connexions PostgreSQL s'annoncent comme `'eLarcProf'` au lieu de `'LarcSecretaire'`. Incohérent et gênant pour le monitoring PostgreSQL (`pg_stat_activity`).
- **Correction :** Remplacer par `'LarcSecretaire'`.

### 1.8 LarcSecretaire — Config fallback pointe vers `eLarcProf` au lieu de `eLarcProfPy`
- **Fichier :** `common/database.py:20`
- **Sévérité :** FAIBLE
- **Détail :** Le chemin de fallback est `'../../eLarcProf/config.ini'` mais le projet s'appelle `eLarcProfPy` (comme mentionné dans CONTEXT.md et main.py de LarcSuperviseur).
- **Correction :** Remplacer par `'../../eLarcProfPy/config.ini'`.

---

## 2. Incohérences Documentation / Code

### 2.1 Fichiers `class_view.py` et `search.py` inexistants
- **Doc :** `01_specifications.md:86-87`, `historique_construction.md:133-134,298-299`
- **Statut :** Listés comme "à faire" depuis l'itération 4 (8 juin). N'ont jamais été créés.
- **Impact :** Les fonctionnalités "Vue classe" (grille élèves avec slots vides, toggle Actif/Inactif) et "Recherche globale" sont documentées mais non implémentées.

### 2.2 Sync non branchée (5 mentions dans la doc, jamais faite)
- **Doc :** `01_specifications.md:223-225`, `historique_construction.md:198,267,303`, `CONTEXT.md:228`
- **Détail :** `common/sync.py` existe avec `SyncManager` mais ne couvre que `student_profile`. Les tables `student_event`, `student_parent` et `foyer` ne sont pas dans `SYNC_TABLES`. Pas de bouton Synchroniser dans le dashboard.
- **Impact :** Les modifications faites hors ligne ne sont jamais synchronisées.

### 2.3 Tab 2 "Contact" documenté mais vide
- **Doc :** `01_specifications.md:179` dit "Contact — email, email perso, tél. portable, tél. fixe"
- **Code :** `views/student_form.py:621-622` — l'onglet est un commentaire vide
- **Impact :** Cf. bug 1.1

### 2.4 Notes : Le code actuel stocke en JSONB, mais la doc mentionne encore HTML
- **Doc :** `historique_construction.md:166-167` (itération 6) parle de "QTextEdit + barre d'outils" et stockage HTML, or l'itération 7 a tout remplacé par JSONB. La doc de l'itération 6 n'a pas été rétractée.
- **Impact :** Confusion pour un nouveau développeur.

### 2.5 `views/notes_panel.py` non listé dans le spé initial
- **Doc :** `01_specifications.md:58-88` (arborescence) ne liste pas `notes_panel.py`, alors qu'il existe et est critique.
- **Impact :** Documentation incomplète.

### 2.6 Nombre d'onglets divergent : doc dit "6 onglets", CreateDialog a "Fichiers & Parents"
- **Doc :** `01_specifications.md:177` et `CONTEXT.md` décrivent 6 onglets.
- **Code :** `StudentCreateDialog` (ligne 1702) : `tabs.addTab(tab5, "Fichiers & Parents")` — contient un placeholder (pas de parents séparés ici). Cohérent vu que l'élève n'a pas encore d'ID, mais le label est trompeur vs EditDialog qui a "Fichiers" uniquement.
- **Impact :** Mineur, confusion utilisateur.

---

## 3. Failles de sécurité et robustesse

### 3.1 Pas de gestion de concurrence entre secrétaires
- **Fichier :** `views/student_form.py:_save()`
- **Sévérité :** MOYENNE
- **Détail :** Deux secrétaires peuvent ouvrir le même élève, modifier des champs différents, et le dernier à sauver écrase l'autre. Pas de lock optimiste (version_number) ni de `SELECT FOR UPDATE`.
- **Correction :** Ajouter une colonne `sync_version` (ou `updated_at`) et vérifier avant UPDATE.

### 3.2 `subprocess.Popen` avec `shell=True`
- **Fichier :** `views/student_form.py:1098`
- **Sévérité :** MOYENNE (injection de commande si le chemin est contrôlable)
- **Détail :** `subprocess.Popen(['explorer', path], shell=True)` — le `shell=True` est inutile avec une liste d'arguments et représente un risque si `path` pouvait être injecté.
- **Correction :** Remplacer par `subprocess.Popen(['explorer', path])` (supprimer `shell=True`) ou utiliser `os.startfile(path)`.

### 3.3 Pas de sanitisation des noms de fichiers joints
- **Fichier :** `views/student_form.py:1072-1075`
- **Sévérité :** FAIBLE
- **Détail :** Le nom de fichier original (`os.path.basename(p)`) est utilisé tel quel pour `shutil.copy2`. Si un fichier malveillant a un nom avec `..` ou des caractères spéciaux, risque de path traversal (mitigé par `os.path.join` + `os.path.basename`).
- **Correction :** Ajouter une validation : refuser les noms contenant `..`, `/`, `\`, ou les caractères non imprimables.

### 3.4 LarcSuperviseur — SHA-256 sans sel pour les mots de passe
- **Fichier :** `views/login.py:101`
- **Sévérité :** MOYENNE
- **Détail :** `hashlib.sha256(password.encode('utf-8')).hexdigest()` — pas de sel (salt). Vulnérable aux rainbow tables si la DB fuit. LarcSecretaire utilise la même méthode dans `auth.py:19`.
- **Correction :** Utiliser `hashlib.pbkdf2_hmac` avec un sel par utilisateur, ou passer à bcrypt/argon2.

### 3.5 Pas de rate limiting sur les tentatives de connexion
- **Fichiers :** `views/login.py` (les deux apps)
- **Sévérité :** MOYENNE
- **Détail :** Aucune limitation du nombre de tentatives de connexion. Un attaquant peut brute-forcer indéfiniment.
- **Correction :** Ajouter un compteur de tentatives (avec délai exponentiel) ou un verrouillage temporaire après N échecs.

### 3.6 LarcSuperviseur — Pas de timer d'inactivité
- **Fichier :** `views/main_window.py` (LarcSuperviseur)
- **Sévérité :** FAIBLE
- **Détail :** LarcSecretaire a un timer d'inactivité de 10 minutes (`_idle_timer`, ligne 46-49 de main_window.py) qui déclenche une fermeture. LarcSuperviseur n'en a pas.
- **Correction :** Ajouter un mécanisme similaire.

### 3.7 LarcSuperviseur — Pas d'audit trail pour les connexions
- **Fichier :** `views/login.py` (LarcSuperviseur)
- **Sévérité :** FAIBLE
- **Détail :** `common/audit.py` existe avec `audit.login()` mais n'est jamais appelé dans LoginWindow. Les connexions/déconnexions ne sont pas tracées.
- **Correction :** Appeler `audit.login()` après authentification réussie.

### 3.8 Chemins photos hardcodés
- **Fichier :** `views/supervisor_panel.py:17-19` (LarcSecretaire)
- **Sévérité :** FAIBLE
- **Détail :** `PHOTOS_DIR` est calculé en relatif depuis le fichier source avec `'..', '..', 'LarcSuperviseur', 'photos'`. Si l'arborescence change, ça casse.
- **Correction :** Mettre dans `config.ini`.

---

## 4. Divergences inter-applications (LarcSecretaire ↔ LarcSuperviseur)

### 4.1 Affichage des événements hiérarchiques — LarcSecretaire doit suivre LarcSuperviseur
- **Fichier :** `views/supervisor_panel.py:21-29, 430-455`
- **Sévérité :** HAUTE (défaut d'affichage)
- **Détail :** LarcSuperviseur a évolué vers des types d'événements hiérarchiques (ex : `"Sortie > Perturbation > Bavardage"`) stockés dans `student_event.event_type`, chargés depuis `larcauth_type_event`. LarcSecretaire, lui, utilise encore des constantes legacy (`EVENT_TYPES` et `EVENT_COLORS`) qui ne reconnaissent que 7 mots-clés (`arrival`, `departure`, `exit`, `return`, `absence`, `justified`, `late`).
- **Impact :** Quand LarcSecretaire lit un événement créé par LarcSuperviseur, `EVENT_COLORS.get(etype, '#000')` retourne noir (fallback) et `dict(EVENT_TYPES).get(etype, etype)` affiche le chemin brut sans icône. L'affichage est inexploitable pour le secrétaire.
- **Correction :** Remplacer `EVENT_TYPES`/`EVENT_COLORS` par une logique de parsing hiérarchique (catégorie → icône + couleur), comme fait dans LarcSuperviseur (`_event_icon()`, `_event_color()`), ou charger depuis `larcauth_type_event`.

### 4.2 Pas de module commun partagé
- `_event_icon()` et `_event_color()` sont dupliqués dans les deux apps (`supervisor_panel.py` vs `main_window.py`).
- `StudentCard` est dupliqué.
- Aucun package `common/` partagé entre les deux projets.

### 4.3 Formats d'événements INSERT différents
- **LarcSecretaire :** `(student_id, event_type, event_at, note, source, created_by)` — 6 colonnes
- **LarcSuperviseur :** `(student_id, event_type, event_at, lieu_label, subject_label, note, source, created_by)` — 8 colonnes

### 4.4 Auth asymétrique
| Feature | LarcSecretaire | LarcSuperviseur |
|---|---|---|
| Intranet SHA-256 | Oui (via AuthManager) | Oui (direct) |
| Cloud OAuth2 | Oui (PKCE Google) | **À ajouter** (objectif confirmé) |
| PIN hors ligne | **Supprimé** (code clean, docs à mettre à jour) | Non |
| Vérification rôle | `type_secretary` | `type_supervisor` / `type_coordonator` / `type_director` |

### 4.5 Documentation PIN obsolète
- **Fichiers :** `CONTEXT.md`, `docs/01_specifications.md`, `docs/02_authentification.md`, `docs/03_sync.md`, `docs/historique_construction.md`, `docs/processus_enregistrement.md`
- **Sévérité :** MOYENNE (docs trompeuses)
- **Détail :** Le code ne contient plus aucune trace de login PIN (pas d'onglet Hors connexion, pas de `session_cache` DDL, pas de `ChangePinDialog`). Mais 9 endroits dans 6 documents le décrivent encore comme fonctionnel.
- **Correction :** Mettre à jour tous ces documents pour refléter que seul Intranet + Cloud sont actifs. Supprimer les sections PIN et Nouvelle instance.

### 4.6 LarcSuperviseur — Absence de Cloud auth
- **Fichier :** `views/login.py`, `common/auth.py` (absent)
- **Sévérité :** OBJECTIF (évolution demandée)
- **Détail :** LarcSuperviseur n'a que l'auth Intranet. Le superviseur doit pouvoir se connecter via Cloud (OAuth2 Google @arc-en-ciel.org). LarcSecretaire a déjà `OAuth2Manager` (PKCE complet) dans `common/auth.py` — ce module peut être repris ou partagé.
- **Dépendances :** `config.ini` avec `[OAuth2]` ClientID + ClientSecret. Actuellement LarcSuperviseur lit la config de `eLarcProfPy`. Solution possible : copier `auth.py` ou mutualiser via un `common/` partagé.

---

## 5. Plan de correction priorisé

### Priorité CRITIQUE (bloquant fonctionnel)
1. **Corriger le CHECK constraint event_type** — LarcSuperviseur DDL + serveur
2. **Mettre à jour le DDL student_event** — Ajouter `lieu_label`, `subject_label` dans le fichier SQL

### Priorité HAUTE (intégrité / cohérence)
3. **Régler autocommit/rollback** — Choisir un mode et s'y tenir
4. **Supprimer les QMessageBox de debug** (`Debug 1/6` à `4/6`)
5. **Déplacer SET LOCAL avant commit** — Triggers serveur
6. **Adapter l'affichage événements LarcSecretaire** — Aligner sur les types hiérarchiques de LarcSuperviseur
7. **Ajouter gestion de concurrence** — Lock optimiste sur UPDATE élève

### Priorité MOYENNE
8. **Ajouter Cloud auth à LarcSuperviseur** — Reprendre/partager `OAuth2Manager`
9. **Nettoyer la documentation du PIN** — 6 fichiers à mettre à jour
10. **Connecter sync.py** aux tables manquantes
11. **Créer `class_view.py` et `search.py`**
12. **Ajouter un sel aux hashs de mot de passe**
13. **Ajouter rate limiting** sur login
14. **Ajouter audit connexions LarcSuperviseur**
15. **Supprimer `shell=True`** dans `subprocess.Popen`
16. **Définir le contenu de l'onglet Contact** — Coordonnées parents pour superviseur

### Priorité BASSE
17. **Corriger `application_name`** (`'eLarcProf'` → `'LarcSecretaire'`)
18. **Corriger chemin fallback** (`eLarcProf` → `eLarcProfPy`)
19. **Sanitizer noms de fichiers** joints
20. **Ajouter timer inactivité LarcSuperviseur**
21. **Rendre le chemin des photos configurable**
22. **Mettre à jour les incohérences de documentation**

---

*Rapport généré automatiquement par analyse statique — 12 juin 2026*
