# ERP Société Rouandi — v2 (SQLite + Authentification + Paramétrage)

## Ce qui a changé par rapport à la version JSON

| Sujet | Avant (JSON) | Maintenant (SQLite) |
|---|---|---|
| Stockage | 1 fichier réécrit en entier à chaque sauvegarde | Base SQLite, écritures en transaction, indexée |
| Vitesse à grande échelle | Se dégrade avec le volume | Reste rapide (milliers de lignes) |
| Sécurité d'accès | Aucune | Connexion obligatoire, mots de passe hachés (PBKDF2+sel) |
| Rôles | Aucun | `admin` (tout) / `user` (saisie, pas de gestion des comptes) |
| Traçabilité | Aucune | Journal d'activité (`logs`) : qui a fait quoi, quand |
| Statuts « Remarque » | Codés en dur dans le code | Table `remarques` modifiable dans l'app (label + couleur) |
| Listes Chantiers/Fournisseurs | Texte libre uniquement | Listes gérées dans Paramètres, réutilisables en dropdown |
| Couleurs / Logo / Nom société | Codés en dur | Modifiables dans ⚙️ Paramètres, sans toucher au code |

## Installation

```bash
pip install -r requirements.txt
```

## Si vous avez un ancien fichier `system_db.json`

```bash
python migrate_json.py /chemin/vers/votre/system_db.json
```

Ça importe automatiquement vos factures, votre compte prorata, et reconstruit
les listes de chantiers/fournisseurs/remarques à partir de vos données existantes.

## Lancer l'application

```bash
streamlit run app.py
```

**Première connexion :** `admin` / `admin123`
➡️ Changez ce mot de passe immédiatement dans **⚙️ Paramètres > Utilisateurs**.

## Ce qui est maintenant paramétrable SANS toucher au code

Tout se trouve dans **⚙️ Paramètres & Administration** (visible seulement pour les admins) :

- **Général & Apparence** : nom de la société, sous-titre, logo, couleur principale, couleur d'accent.
- **Remarques (Statuts)** : ajoutez/renommez/recolorez/supprimez n'importe quel statut
  (IMPAYÉ, RAS, etc.) — les listes déroulantes se mettent à jour partout automatiquement.
- **Chantiers & Fournisseurs** : gérez vos listes de référence, réutilisées dans les
  formulaires de saisie (avec possibilité d'en taper un nouveau à la volée aussi).
- **Utilisateurs** : créer des comptes, changer les mots de passe, activer/désactiver,
  attribuer le rôle admin ou utilisateur simple.

## Limites honnêtes à connaître

- Ceci sécurise l'**accès à l'application**, pas le fichier `rouandi_erp.db` sur le
  disque : toute personne ayant un accès direct au serveur/PC peut le lire. Pour un
  usage interne (bureau, réseau local), c'est un niveau raisonnable. Pour un vrai
  déploiement public sur Internet, il faudrait ajouter HTTPS et des sauvegardes chiffrées.
- `st.data_editor` remplace toute la table à chaque sauvegarde (comme avant), mais
  maintenant dans une transaction SQLite atomique — donc rapide et sûr même si
  l'opération est interrompue en cours de route.
- Pensez à faire des sauvegardes régulières du fichier `rouandi_erp.db` (copier ce
  seul fichier suffit).

## Structure des fichiers

```
rouandi_erp/
├── app.py            → Application principale (toutes les pages)
├── db.py             → Accès base de données SQLite (CRUD, paramétrage)
├── auth.py           → Authentification et rôles
├── style.py          → Thème visuel piloté par les Paramètres
├── migrate_json.py   → Script de migration ponctuelle depuis l'ancien JSON
├── requirements.txt
└── rouandi_erp.db    → Créé automatiquement au premier lancement
```
