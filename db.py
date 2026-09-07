"""
db.py - Couche d'accès à la base de données SQLite pour l'ERP Rouandi.

Pourquoi SQLite au lieu du JSON ?
- Le JSON était rechargé et réécrit EN ENTIER à chaque sauvegarde -> lent
  et risqué dès que le fichier grossit ou que 2 personnes écrivent en même temps.
- SQLite gère les écritures via des transactions (tout ou rien), indexe les
  données, et reste rapide même avec des dizaines de milliers de lignes.
- Un seul fichier .db, aucun serveur à installer, donc aussi simple à déployer
  que le JSON mais infiniment plus robuste.
"""

import sqlite3
import hashlib
import os
import secrets
import re
import unicodedata
from datetime import datetime
from contextlib import contextmanager

import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rouandi_erp.db")

DEFAULT_REMARQUES = [
    ("IMPAYÉ", "#e74c3c"), ("RAP/AR", "#e67e22"), ("RAP", "#e67e22"),
    ("RAS", "#2ecc71"), ("ENVOYÉ AU CHANTIER", "#3498db"),
    ("TRANSMIS A LA COMPTA", "#9b59b6"), ("MQ DE JUSTIF", "#f39c12"),
    ("MQ de reçu Original", "#f39c12"), ("MQ de F originale", "#f39c12"),
    ("A RESILIER", "#c0392b"), ("RESILIE", "#7f8c8d"),
    ("A RESILIER/RAP", "#c0392b"), ("RESILIER/RAS", "#7f8c8d"),
    ("SS JUSTIF", "#f39c12"), ("A REMBOURSER", "#e74c3c"),
    ("REMBOURSE", "#2ecc71"), ("RESTE A REMBOURSER", "#e67e22"),
    ("AVOIR", "#3498db"), ("Réglement par avoir", "#3498db"),
    ("RESTITUER", "#2ecc71"), ("A RESTITUER", "#e67e22"),
    ("RENOUVELER", "#f1c40f"), ("A TRANSERER", "#f1c40f"),
    ("A VERIFIER", "#e67e22"), ("FNP", "#95a5a6"),
]

FACTURE_COLUMNS = [
    "mois", "marche", "fournisseur", "nature", "designation", "montant",
    "remarque", "contrat", "num_facture", "facture_originale_recue",
    "recu_paiement_original_recu", "date_reglement", "mode_reglement", "date_cheque",
]

PRORATA_COLUMNS = [
    "date", "chantier", "libelle", "fournisseur", "montant_total",
    "entreprise", "cle_repartition", "montant_partage", "statut",
]

# Alias des noms de colonnes tels qu'on les rencontre couramment dans les
# fichiers Excel/CSV existants (accents, espaces, "(MAD)", "N°"...), vers les
# noms internes utilisés par la base. Sans cette table, un fichier avec la
# colonne "Montant (MAD)" ne serait jamais reconnu comme "montant" et
# resterait à 0 après import — c'est exactement ce qui causait le bug.
_FACTURE_COLUMN_ALIASES = {
    "mois": "mois",
    "marche": "marche", "marche chantier": "marche", "chantier": "marche",
    "marche/chantier": "marche",
    "fournisseur": "fournisseur", "fournisseurs": "fournisseur",
    "nature": "nature",
    "designation": "designation", "designations": "designation",
    "montant": "montant", "montant mad": "montant", "montant dh": "montant",
    "montant (mad)": "montant",
    "remarque": "remarque", "remarques": "remarque", "statut": "remarque",
    "n contrat": "contrat", "n de contrat": "contrat",
    "n contrat compteur": "contrat", "n° de contrat": "contrat",
    "contrat": "contrat_statut",
    "facture originale recue": "facture_originale_recue",
    "facture originale recue ?": "facture_originale_recue",
    "recu paiement original recu": "recu_paiement_original_recu",
    "recu paiement original recu ?": "recu_paiement_original_recu",
    "n de facture": "num_facture", "n facture": "num_facture",
    "date de reglement": "date_reglement", "date reglement": "date_reglement",
    "mode de reglement": "mode_reglement", "mode reglement": "mode_reglement",
    "date de cheque": "date_cheque", "date cheque": "date_cheque",
}

# Colonnes qu'on reconnaît dans un en-tête mais qui ne font pas partie du
# modèle "factures" actuel (dates/modes de règlement...) : on les garde
# le temps de détecter la ligne d'en-tête, mais elles ne bloquent pas
# l'import si FACTURE_COLUMNS ne les contient pas.
_HEADER_DETECTION_KEYWORDS = {
    "mois", "marche", "chantier", "fournisseur", "fournisseurs", "nature",
    "designation", "montant", "remarque", "contrat", "facture",
}


def _normalize_header(text: str) -> str:
    """'Montant (MAD)' -> 'montant mad' ; 'N° de Contrat' -> 'n de contrat'."""
    text = str(text).strip().lower()
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    text = text.replace("°", "").replace("(", " ").replace(")", " ")
    text = re.sub(r"[\/_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def list_excel_sheets(file) -> list:
    """Retourne les noms des feuilles d'un classeur Excel (le fichier uploadé
    peut contenir plusieurs feuilles : BDD, Bordereaux, TCD...)."""
    file.seek(0)
    xls = pd.ExcelFile(file)
    return xls.sheet_names


def _detect_header_row(raw: pd.DataFrame, max_scan: int = 20) -> int:
    """Beaucoup de fichiers réels ont un bandeau logo/titre sur les premières
    lignes avant la vraie ligne d'en-têtes (Mois, Marché/Chantier...). Cette
    fonction cherche, parmi les 20 premières lignes, celle qui contient le
    plus de mots-clés reconnus, au lieu de supposer bêtement que c'est la
    ligne 1 — c'est ce qui causait le bug du Montant à 0 après import."""
    best_row, best_score = 0, -1
    for i in range(min(max_scan, len(raw))):
        row_vals = [_normalize_header(v) for v in raw.iloc[i].tolist() if pd.notna(v)]
        score = sum(1 for v in row_vals if v in _HEADER_DETECTION_KEYWORDS)
        if score > best_score:
            best_score, best_row = score, i
    return best_row if best_score >= 2 else 0


def smart_read_excel(file, sheet_name=0) -> pd.DataFrame:
    """Lit une feuille Excel en détectant automatiquement la ligne d'en-têtes,
    même si elle est précédée d'un bandeau logo/titre sur plusieurs lignes."""
    file.seek(0)
    raw = pd.read_excel(file, sheet_name=sheet_name, header=None)
    header_row = _detect_header_row(raw)
    file.seek(0)
    return pd.read_excel(file, sheet_name=sheet_name, header=header_row)


def map_import_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes d'un DataFrame importé vers les noms internes
    des factures (mois, marche, fournisseur, montant, ...), en reconnaissant
    les variantes usuelles (accents, espaces, unités). Les colonnes non
    reconnues sont conservées sous une forme normalisée (elles seront
    simplement ignorées si elles ne font pas partie de FACTURE_COLUMNS).

    Si deux colonnes source différentes (ex: 'Remarque' et 'Statut') se
    retrouvent mappées vers le même nom interne, elles sont fusionnées
    (on garde la première valeur non vide, ligne par ligne) au lieu de
    laisser un DOUBLON — un doublon de colonne casse silencieusement tout
    le reste (comparaisons, filtres, export) plus loin dans l'application."""
    rename_map = {}
    for col in df.columns:
        norm = _normalize_header(col)
        rename_map[col] = _FACTURE_COLUMN_ALIASES.get(norm, norm.replace(" ", "_"))
    df = df.rename(columns=rename_map)

    if df.columns.duplicated().any():
        deduped = {}
        for name in pd.unique(df.columns):
            same_name_cols = df.loc[:, df.columns == name]
            if same_name_cols.shape[1] > 1:
                merged = same_name_cols.bfill(axis=1).iloc[:, 0]
                deduped[name] = merged
            else:
                deduped[name] = same_name_cols.iloc[:, 0]
        df = pd.DataFrame(deduped)

    return df


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Crée les tables si elles n'existent pas, et ajoute des valeurs par défaut."""
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            actif INTEGER NOT NULL DEFAULT 1,
            created_at TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS factures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mois TEXT, marche TEXT, fournisseur TEXT, nature TEXT,
            designation TEXT, montant REAL DEFAULT 0, remarque TEXT,
            contrat TEXT,
            facture_originale_recue INTEGER DEFAULT 0,
            recu_paiement_original_recu INTEGER DEFAULT 0,
            created_at TEXT, updated_at TEXT
        )""")

        # --- Migration douce : ajoute les colonnes manquantes sans jamais
        # supprimer ou réécrire les données existantes (utile quand on met à
        # jour l'application sur une base déjà en service). ---
        existing_cols = {row["name"] for row in c.execute("PRAGMA table_info(factures)").fetchall()}
        for col_name, col_def in [
            ("num_facture", "TEXT"),
            ("date_reglement", "TEXT"),
            ("mode_reglement", "TEXT"),
            ("date_cheque", "TEXT"),
        ]:
            if col_name not in existing_cols:
                c.execute(f"ALTER TABLE factures ADD COLUMN {col_name} {col_def}")

        c.execute("CREATE INDEX IF NOT EXISTS idx_factures_num_facture ON factures(num_facture)")

        c.execute("""CREATE TABLE IF NOT EXISTS prorata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, chantier TEXT, libelle TEXT, fournisseur TEXT,
            montant_total REAL DEFAULT 0, entreprise TEXT,
            cle_repartition REAL DEFAULT 0, montant_partage REAL DEFAULT 0,
            statut TEXT, created_at TEXT, updated_at TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS remarques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT UNIQUE NOT NULL,
            couleur TEXT DEFAULT '#3498db',
            ordre INTEGER DEFAULT 0
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS chantiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS fournisseurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, action TEXT, details TEXT, timestamp TEXT
        )""")

        c.execute("CREATE INDEX IF NOT EXISTS idx_factures_remarque ON factures(remarque)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_factures_marche ON factures(marche)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_prorata_chantier ON prorata(chantier)")

        # --- Seed remarques par défaut ---
        c.execute("SELECT COUNT(*) FROM remarques")
        if c.fetchone()[0] == 0:
            for i, (label, couleur) in enumerate(DEFAULT_REMARQUES):
                c.execute(
                    "INSERT OR IGNORE INTO remarques (label, couleur, ordre) VALUES (?,?,?)",
                    (label, couleur, i),
                )

        # --- Seed paramètres par défaut ---
        c.execute("SELECT COUNT(*) FROM settings")
        if c.fetchone()[0] == 0:
            defaults = {
                "company_name": "SOCIÉTÉ ROUANDI",
                "company_subtitle": "Travaux Divers & BTP",
                "theme_primary_color": "#5B1B2D",
                "theme_secondary_color": "#C9A227",
                "logo_path": "",
            }
            for k, v in defaults.items():
                c.execute("INSERT INTO settings (key, value) VALUES (?,?)", (k, v))

        # --- Seed premier compte admin si aucun utilisateur ---
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            salt = secrets.token_hex(16)
            pwd_hash = hash_password("admin123", salt)
            c.execute(
                "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?,?,?,?,?)",
                ("admin", pwd_hash, salt, "admin", datetime.now().isoformat()),
            )


# ---------------- AUTH HELPERS (utilisés aussi par auth.py) ----------------

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


# ---------------- SETTINGS ----------------

def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_all_settings():
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# ---------------- REMARQUES (paramétrage) ----------------

def get_remarques():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM remarques ORDER BY ordre, label").fetchall()
        return [dict(r) for r in rows]


def get_remarques_labels():
    return [r["label"] for r in get_remarques()]


def get_remarques_colors():
    return {r["label"]: r["couleur"] for r in get_remarques()}


def add_remarque(label, couleur="#3498db"):
    with get_conn() as conn:
        maxo = conn.execute("SELECT COALESCE(MAX(ordre),0) FROM remarques").fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO remarques (label, couleur, ordre) VALUES (?,?,?)",
            (label.strip(), couleur, maxo + 1),
        )


def update_remarque(old_label, new_label, couleur):
    with get_conn() as conn:
        conn.execute(
            "UPDATE remarques SET label=?, couleur=? WHERE label=?",
            (new_label.strip(), couleur, old_label),
        )
        conn.execute("UPDATE factures SET remarque=? WHERE remarque=?", (new_label.strip(), old_label))


def delete_remarque(label):
    with get_conn() as conn:
        conn.execute("DELETE FROM remarques WHERE label=?", (label,))


# ---------------- CHANTIERS ----------------

def get_chantiers():
    with get_conn() as conn:
        return [r["nom"] for r in conn.execute("SELECT nom FROM chantiers ORDER BY nom").fetchall()]


def add_chantier(nom):
    if not nom or not nom.strip():
        return
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO chantiers (nom) VALUES (?)", (nom.strip(),))


def delete_chantier(nom):
    with get_conn() as conn:
        conn.execute("DELETE FROM chantiers WHERE nom=?", (nom,))


# ---------------- FOURNISSEURS ----------------

def get_fournisseurs():
    with get_conn() as conn:
        return [r["nom"] for r in conn.execute("SELECT nom FROM fournisseurs ORDER BY nom").fetchall()]


def add_fournisseur(nom):
    if not nom or not nom.strip():
        return
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO fournisseurs (nom) VALUES (?)", (nom.strip(),))


def delete_fournisseur(nom):
    with get_conn() as conn:
        conn.execute("DELETE FROM fournisseurs WHERE nom=?", (nom,))


# ---------------- FACTURES ----------------

def _mois_sort_key(mois):
    """Convertit une valeur de Mois ('04/2026', '2017', 'Avril 2026'...) en
    clé triable (année, mois). Les valeurs non reconnues renvoient (0, 0),
    ce qui les place tout en bas — comme les données anciennes/non datées."""
    if not mois:
        return (0, 0)
    text = str(mois).strip()
    m = re.match(r"^(\d{1,2})[\/\-](\d{4})$", text)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m2 = re.match(r"^(\d{4})[\/\-](\d{1,2})$", text)
    if m2:
        return (int(m2.group(1)), int(m2.group(2)))
    m3 = re.match(r"^(\d{4})$", text)
    if m3:
        return (int(m3.group(1)), 0)
    return (0, 0)


# Alias public (sans underscore) pour usage hors de ce module.
mois_sort_key = _mois_sort_key


def sort_factures_recent_first(df: pd.DataFrame) -> pd.DataFrame:
    """Trie un DataFrame de factures pour que le mois le plus récent soit en
    haut et le plus ancien en bas (au lieu de l'ordre d'insertion en base)."""
    if df.empty or "mois" not in df.columns:
        return df
    df = df.copy()
    df["_sort_key"] = df["mois"].apply(_mois_sort_key)
    df = df.sort_values("_sort_key", ascending=False).drop(columns=["_sort_key"])
    return df.reset_index(drop=True)


def get_factures_df():
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM factures ORDER BY id", conn)
    if not df.empty:
        df["facture_originale_recue"] = df["facture_originale_recue"].astype(bool)
        df["recu_paiement_original_recu"] = df["recu_paiement_original_recu"].astype(bool)
        df = sort_factures_recent_first(df)
    return df


def insert_facture(row: dict, username="system"):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            f"""INSERT INTO factures
            ({", ".join(FACTURE_COLUMNS)}, created_at, updated_at)
            VALUES ({", ".join(["?"] * len(FACTURE_COLUMNS))}, ?, ?)""",
            [row.get(col) for col in FACTURE_COLUMNS] + [now, now],
        )
    log_action(username, "AJOUT_FACTURE", f"{row.get('marche')} / {row.get('fournisseur')}")


def get_facture_by_num(num_facture: str, contrat: str = None):
    """Cherche un doublon EXACT : même N° de Facture ET même N° de Contrat.
    (Un même N° de Facture réutilisé sous un autre contrat n'est PAS
    considéré comme un doublon ici — voir get_factures_by_num_only pour
    signaler ce cas comme une simple anomalie à vérifier.)"""
    if not num_facture:
        return None
    with get_conn() as conn:
        if contrat:
            row = conn.execute(
                """SELECT * FROM factures
                   WHERE TRIM(num_facture) = TRIM(?) AND TRIM(contrat) = TRIM(?)
                   ORDER BY id DESC LIMIT 1""",
                (num_facture, contrat),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM factures WHERE TRIM(num_facture) = TRIM(?) ORDER BY id DESC LIMIT 1",
                (num_facture,),
            ).fetchone()
        return dict(row) if row else None


def get_factures_by_num_only(num_facture: str):
    """Retourne toutes les factures partageant ce N° de Facture, quel que
    soit le N° de Contrat — sert à détecter une anomalie (même numéro de
    facture réutilisé sous un contrat différent, ce qui est suspect sans
    être forcément un doublon)."""
    if not num_facture:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM factures WHERE TRIM(num_facture) = TRIM(?) ORDER BY id DESC",
            (num_facture,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_reference_by_contrat(contrat: str):
    """Retrouve, à partir d'un N° de Contrat déjà connu dans la base, les
    informations qui se répètent pour ce contrat (Marché/Chantier,
    Fournisseur, Nature, Désignation) — utilisé pour pré-remplir
    automatiquement une nouvelle facture importée depuis un PDF."""
    if not contrat:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """SELECT marche, fournisseur, nature, designation, contrat
               FROM factures
               WHERE TRIM(contrat) = TRIM(?) AND marche IS NOT NULL AND marche != ''
               ORDER BY id DESC LIMIT 1""",
            (contrat,),
        ).fetchone()
        return dict(row) if row else None


def replace_all_factures(df: pd.DataFrame, username="system"):
    """Remplace tout le contenu de la table factures dans UNE SEULE transaction.
    Beaucoup plus rapide et sûr que de réécrire un fichier JSON entier."""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM factures")
        for _, row in df.iterrows():
            values = []
            for col in FACTURE_COLUMNS:
                val = row.get(col, None)
                if col in ("facture_originale_recue", "recu_paiement_original_recu"):
                    val = 1 if bool(val) else 0
                values.append(val)
            conn.execute(
                f"""INSERT INTO factures ({", ".join(FACTURE_COLUMNS)}, created_at, updated_at)
                VALUES ({", ".join(["?"] * len(FACTURE_COLUMNS))}, ?, ?)""",
                values + [now, now],
            )
    log_action(username, "SAUVEGARDE_FACTURES", f"{len(df)} lignes")


def delete_facture(facture_id, username="system"):
    with get_conn() as conn:
        conn.execute("DELETE FROM factures WHERE id=?", (facture_id,))
    log_action(username, "SUPPRESSION_FACTURE", f"id={facture_id}")


# ---------------- PRORATA ----------------

def get_prorata_df():
    with get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM prorata ORDER BY id", conn)


def replace_all_prorata(df: pd.DataFrame, username="system"):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM prorata")
        for _, row in df.iterrows():
            values = [row.get(col, None) for col in PRORATA_COLUMNS]
            conn.execute(
                f"""INSERT INTO prorata ({", ".join(PRORATA_COLUMNS)}, created_at, updated_at)
                VALUES ({", ".join(["?"] * len(PRORATA_COLUMNS))}, ?, ?)""",
                values + [now, now],
            )
    log_action(username, "SAUVEGARDE_PRORATA", f"{len(df)} lignes")


# ---------------- USERS ----------------

def get_users():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, username, role, actif, created_at FROM users ORDER BY username").fetchall()
        return [dict(r) for r in rows]


def get_user_by_username(username):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None


def create_user(username, password, role="user"):
    salt = secrets.token_hex(16)
    pwd_hash = hash_password(password, salt)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?,?,?,?,?)",
            (username.strip(), pwd_hash, salt, role, datetime.now().isoformat()),
        )


def set_user_active(username, actif: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET actif=? WHERE username=?", (1 if actif else 0, username))


def reset_user_password(username, new_password):
    salt = secrets.token_hex(16)
    pwd_hash = hash_password(new_password, salt)
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash=?, salt=? WHERE username=?", (pwd_hash, salt, username))


def delete_user(username):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE username=?", (username,))


# ---------------- LOGS ----------------

def log_action(username, action, details=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO logs (username, action, details, timestamp) VALUES (?,?,?,?)",
            (username, action, details, datetime.now().isoformat()),
        )


def get_logs_df(limit=500):
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", conn, params=(limit,)
        )
