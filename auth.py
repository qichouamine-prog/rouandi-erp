"""
auth.py - Authentification par session pour l'ERP Rouandi.

Sécurité mise en place :
- Mots de passe jamais stockés en clair : hachés avec PBKDF2-HMAC-SHA256
  + un "sel" (salt) aléatoire différent pour chaque utilisateur (protège
  contre les tables arc-en-ciel / rainbow tables).
- Session Streamlit : tant que l'utilisateur n'est pas authentifié, aucune
  page de l'application n'est accessible (voir require_login()).
- Rôles : "admin" (accès total, y compris gestion des utilisateurs et
  paramétrage) et "user" (accès aux données, pas à la gestion des comptes).
- Chaque connexion, déconnexion et action de sauvegarde est journalisée
  dans la table `logs` (qui a fait quoi, et quand).

Limites à connaître (honnêteté technique) :
- Ceci protège l'accès à l'application elle-même, pas le fichier .db sur
  le disque : toute personne ayant accès physique/SSH au serveur peut lire
  rouandi_erp.db. Pour un usage interne sur un PC/serveur de bureau fermé,
  c'est un niveau de sécurité raisonnable. Pour un vrai déploiement multi-
  utilisateurs sur Internet, il faudrait en plus : HTTPS, un vrai serveur
  d'authentification, et des sauvegardes chiffrées.
"""

import streamlit as st
import db


def authenticate(username: str, password: str):
    user = db.get_user_by_username(username)
    if not user:
        return None
    if not user["actif"]:
        return None
    expected_hash = db.hash_password(password, user["salt"])
    if expected_hash == user["password_hash"]:
        return user
    return None


def login_form():
    st.markdown(
        "<h2 style='text-align:center;'>🔒 Connexion - ERP Société Rouandi</h2>",
        unsafe_allow_html=True,
    )
    col_a, col_b, col_c = st.columns([1, 1.2, 1])
    with col_b:
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter", use_container_width=True)
            if submitted:
                user = authenticate(username, password)
                if user:
                    st.session_state["auth_user"] = {
                        "username": user["username"],
                        "role": user["role"],
                    }
                    db.log_action(user["username"], "CONNEXION", "")
                    st.rerun()
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect, ou compte désactivé.")
        st.caption(
            "Compte par défaut à la première utilisation : **admin / admin123** "
            "— changez ce mot de passe immédiatement dans ⚙️ Paramètres > Utilisateurs."
        )


def is_logged_in() -> bool:
    return "auth_user" in st.session_state


def current_user():
    return st.session_state.get("auth_user")


def require_login():
    """Bloque l'accès à tout le reste de l'app tant qu'on n'est pas connecté."""
    if not is_logged_in():
        login_form()
        st.stop()


def require_admin():
    """À appeler au début des sections réservées aux administrateurs."""
    user = current_user()
    if not user or user.get("role") != "admin":
        st.error("⛔ Accès réservé aux administrateurs.")
        st.stop()


def logout():
    user = current_user()
    if user:
        db.log_action(user["username"], "DECONNEXION", "")
    st.session_state.pop("auth_user", None)
    st.rerun()
