import os
from datetime import datetime

import pandas as pd
import streamlit as st

import db
import auth
import style
import excel_export
import pdf_invoice

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="SOCIÉTÉ ROUANDI - ERP BTP", page_icon="🏗️", layout="wide")

db.init_db()

# --- GATE : rien ne s'affiche tant que la personne n'est pas connectée ---
auth.require_login()
user = auth.current_user()

settings = db.get_all_settings()
style.apply_style(
    settings.get("theme_primary_color", "#1E3A8A"),
    settings.get("theme_secondary_color", "#F5A623"),
)


# =============================================================
# HEADER
# =============================================================
def render_header():
    col_logo, col_title, col_info = st.columns([1.5, 3, 1.5])
    with col_logo:
        logo_path = settings.get("logo_path", "")
        if logo_path and os.path.exists(logo_path):
            st.image(logo_path, width=150)
        else:
            st.markdown("## 🏗️ **" + settings.get("company_name", "SOCIÉTÉ ROUANDI") + "**")
            st.caption(settings.get("company_subtitle", "Travaux Divers & BTP"))
    with col_title:
        st.markdown(
            f"<h2 style='text-align:center;'>{settings.get('company_name', 'SOCIÉTÉ ROUANDI')} - ERP GESTION BTP</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center; color:#555;'>Suivi Des Factures, Contrats & Compte Prorata Chantier</p>",
            unsafe_allow_html=True,
        )
    with col_info:
        st.markdown(f"<span class='user-badge'>👤 {user['username']} ({user['role']})</span>", unsafe_allow_html=True)
        st.markdown(f"**Date :** {datetime.now().strftime('%d/%m/%Y')}")
        if st.button("🚪 Déconnexion", use_container_width=True):
            auth.logout()
    st.markdown("---")


render_header()

# =============================================================
# SIDEBAR NAVIGATION
# =============================================================
MENU_ITEMS = [
    "📊 Dashboard 1: Factures & Contrats",
    "📊 Dashboard 2: Compte Prorata",
    "🧾 Suivi Factures & Règlements (Saisie & Modif)",
    "🧠 Importer une Facture (PDF intelligent)",
    "🤝 Suivi Compte Prorata (Saisie & Modif)",
    "🔴 Suivi des Impayés & RAP/AR",
    "⚠️ Factures Manquantes",
    "📁 Transmis à la Comptabilité",
    "📄 Bordereaux d'Envoi",
    "🚰 Contrats & Compteurs",
    "📋 Éditeur Global (Copy/Paste/Saisie)",
    "📥 Import / Export Data",
    "🗒️ Journal d'Activité (Logs)",
]
if user["role"] == "admin":
    MENU_ITEMS.append("⚙️ Paramètres & Administration")

with st.sidebar:
    st.title("📌 Navigation ERP")
    menu = st.radio("Services & Modules :", MENU_ITEMS)
    st.markdown("---")

df_raw = db.get_factures_df()
df_prorata = db.get_prorata_df()
REMARQUES = db.get_remarques_labels()
CHANTIERS = db.get_chantiers()
FOURNISSEURS = db.get_fournisseurs()


def montant_numeric(df, col):
    if df.empty or col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce").fillna(0)


# =============================================================
# MODULE 1 : DASHBOARD FACTURES
# =============================================================
if menu == "📊 Dashboard 1: Factures & Contrats":
    st.subheader("📊 Tableau de Bord 1 : Synthèse Générale")
    if not df_raw.empty:
        montants = montant_numeric(df_raw, "montant")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Lignes / Factures", len(df_raw))
        c2.metric("Montant Total Engagé", f"{montants.sum():,.2f} MAD")
        mask_impaye = df_raw["remarque"].isin(["IMPAYÉ", "RAP/AR"])
        c3.metric("🔴 Factures Impayées", int(mask_impaye.sum()))
        c4.metric("📁 Transmis à Compta", int((df_raw["remarque"] == "TRANSMIS A LA COMPTA").sum()))
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Répartition par Remarque**")
            st.bar_chart(df_raw["remarque"].value_counts())
        with col2:
            st.write("**Répartition par Fournisseur**")
            st.bar_chart(df_raw["fournisseur"].value_counts())
    else:
        st.info("Aucune donnée disponible. Ajoutez des données manuellement ou importez un fichier.")

# =============================================================
# MODULE 2 : DASHBOARD PRORATA
# =============================================================
elif menu == "📊 Dashboard 2: Compte Prorata":
    st.subheader("📊 Tableau de Bord 2 : Compte Prorata Chantiers")
    if not df_prorata.empty:
        montants = montant_numeric(df_prorata, "montant_partage")
        p1, p2 = st.columns(2)
        p1.metric("Nombre de Dépenses", len(df_prorata))
        p2.metric("Total Dépenses Communes", f"{montants.sum():,.2f} MAD")
        st.bar_chart(df_prorata.groupby("chantier")["montant_partage"].sum() if "chantier" in df_prorata.columns else None)
    else:
        st.info("Aucune donnée dans le Compte Prorata.")

# =============================================================
# MODULE 3 : SUIVI FACTURES (SAISIE + MODIFICATION)
# =============================================================
elif menu == "🧾 Suivi Factures & Règlements (Saisie & Modif)":
    st.subheader("🧾 Suivi & Saisie des Factures / Contrats")

    with st.expander("➕ Ajouter une nouvelle facture / contrat (Saisie Manuelle)", expanded=False):
        with st.form("add_facture_form"):
            f_col1, f_col2, f_col3 = st.columns(3)
            mois = f_col1.text_input("Mois")
            marche = f_col2.selectbox("Marché / Chantier", [""] + CHANTIERS)
            marche_libre = f_col2.text_input("... ou nouveau chantier (facultatif)")
            fournisseur = f_col3.selectbox("Fournisseur", [""] + FOURNISSEURS)
            fournisseur_libre = f_col3.text_input("... ou nouveau fournisseur (facultatif)")

            f_col4, f_col5, f_col6 = st.columns(3)
            nature = f_col4.text_input("Nature")
            designation = f_col5.text_input("Désignation")
            montant = f_col6.text_input("Montant (MAD)")

            f_col7, f_col8 = st.columns(2)
            remarque = f_col7.selectbox("Remarque / Statut", REMARQUES)
            contrat = f_col8.text_input("N° Contrat / Compteur")

            f_col8b, f_col8c = st.columns(2)
            num_facture = f_col8b.text_input("N° de Facture")
            date_reglement = f_col8c.text_input("Date de Règlement (facultatif)")

            f_col8d, f_col8e = st.columns(2)
            mode_reglement = f_col8d.text_input("Mode de Règlement (facultatif)")
            date_cheque = f_col8e.text_input("Date de Chèque (facultatif)")

            f_col9, f_col10 = st.columns(2)
            facture_recue = f_col9.checkbox("Facture originale reçue ?")
            recu_recue = f_col10.checkbox("Reçu de paiement original reçu ?")

            submit = st.form_submit_button("➕ Ajouter à la Base")
            if submit:
                marche_final = marche_libre.strip() if marche_libre.strip() else marche
                fournisseur_final = fournisseur_libre.strip() if fournisseur_libre.strip() else fournisseur
                if marche_libre.strip():
                    db.add_chantier(marche_libre.strip())
                if fournisseur_libre.strip():
                    db.add_fournisseur(fournisseur_libre.strip())

                new_row = {
                    "mois": mois, "marche": marche_final, "fournisseur": fournisseur_final,
                    "nature": nature, "designation": designation,
                    "montant": pd.to_numeric(str(montant).replace(",", "."), errors="coerce") or 0,
                    "remarque": remarque, "contrat": contrat, "num_facture": num_facture,
                    "facture_originale_recue": facture_recue,
                    "recu_paiement_original_recu": recu_recue,
                    "date_reglement": date_reglement, "mode_reglement": mode_reglement,
                    "date_cheque": date_cheque,
                }
                db.insert_facture(new_row, username=user["username"])
                st.success("Nouvelle ligne ajoutée avec succès !")
                st.rerun()

    st.write("📋 **Tableau Interactif (Modifiez, supprimez ou ajoutez directement dans le tableau) :**")
    if df_raw.empty:
        df_raw = pd.DataFrame(columns=db.FACTURE_COLUMNS)

    mois_disponibles = sorted(
        [m for m in df_raw["mois"].dropna().unique() if str(m).strip() != ""],
        key=db.mois_sort_key, reverse=True,
    ) if "mois" in df_raw.columns else []
    mois_filtre = st.selectbox("🔎 Filtrer par Mois (le plus récent en haut)", ["Tous les mois"] + mois_disponibles)

    df_pour_edition = df_raw if mois_filtre == "Tous les mois" else df_raw[df_raw["mois"] == mois_filtre]

    edited_df = st.data_editor(
        df_pour_edition.drop(columns=["id", "created_at", "updated_at"], errors="ignore"),
        num_rows="dynamic",
        use_container_width=True,
        key="editor_factures",
        column_config={
            "facture_originale_recue": st.column_config.CheckboxColumn("F. Originale ?"),
            "recu_paiement_original_recu": st.column_config.CheckboxColumn("Reçu Original ?"),
            "remarque": st.column_config.SelectboxColumn("Remarque", options=REMARQUES),
            "montant": st.column_config.NumberColumn("Montant (MAD)", format="%.2f"),
            "num_facture": st.column_config.TextColumn("N° de Facture"),
            "date_reglement": st.column_config.TextColumn("Date de Règlement"),
            "mode_reglement": st.column_config.TextColumn("Mode de Règlement"),
            "date_cheque": st.column_config.TextColumn("Date de Chèque"),
        },
    )

    if st.button("💾 Enregistrer les Modifications", use_container_width=True):
        if mois_filtre == "Tous les mois":
            db.replace_all_factures(edited_df, username=user["username"])
        else:
            # Un filtre est actif : on ne réécrit QUE le mois filtré, et on
            # conserve intact tout le reste de la base (sinon les autres
            # mois seraient effacés par le remplacement complet).
            df_autres_mois = df_raw[df_raw["mois"] != mois_filtre].drop(
                columns=["id", "created_at", "updated_at"], errors="ignore"
            )
            combined = pd.concat([df_autres_mois, edited_df], ignore_index=True)
            db.replace_all_factures(combined, username=user["username"])
        st.success("Base de données sauvegardée avec succès !")
        st.rerun()

# =============================================================
# MODULE 3bis : IMPORT INTELLIGENT DE FACTURE PDF
# =============================================================
elif menu == "🧠 Importer une Facture (PDF intelligent)":
    st.subheader("🧠 Importer une Facture PDF")
    st.caption(
        "Dépose le PDF d'une facture reçue : l'application vérifie si elle est déjà "
        "enregistrée (par N° de Facture), et sinon retrouve automatiquement le "
        "Marché, le Fournisseur, la Nature et la Désignation à partir du N° de "
        "Contrat détecté dans le PDF (à condition qu'un contrat identique existe déjà)."
    )

    pdf_file = st.file_uploader("Charger la facture (PDF)", type=["pdf"], key="pdf_invoice_uploader")

    if pdf_file:
        with st.spinner("🔎 Lecture du PDF en cours..."):
            try:
                texte = pdf_invoice.extract_text_from_pdf(pdf_file)
                extrait = pdf_invoice.extract_invoice_fields(texte)
            except Exception as e:
                st.error(f"Impossible de lire ce PDF : {e}")
                extrait = None

        if extrait:
            num_facture_detecte = extrait.get("num_facture")
            contrat_detecte = extrait.get("contrat")
            montant_detecte = extrait.get("montant")

            st.markdown("##### 🔍 Champs détectés dans le PDF (vérifiez avant d'enregistrer)")

            # --- Étape 1 : doublon EXACT = même N° de Contrat + même N° de Facture ---
            existante = db.get_facture_by_num(num_facture_detecte, contrat_detecte) if num_facture_detecte else None
            if existante:
                st.warning(
                    f"⚠️ Cette facture (N° {num_facture_detecte}, Contrat {contrat_detecte}) est "
                    f"**déjà enregistrée** dans le système — Marché : {existante.get('marche')}, "
                    f"Fournisseur : {existante.get('fournisseur')}, Montant : {existante.get('montant'):,.2f} MAD, "
                    f"Remarque actuelle : {existante.get('remarque')}. Rien n'a été ajouté pour éviter un doublon."
                )
            else:
                # --- Remarque de cohérence : même N° de Facture mais sous un
                # autre N° de Contrat -> pas forcément un doublon, mais
                # suspect -> on le signale sans bloquer la saisie.
                if num_facture_detecte:
                    autres_contrats = {
                        r.get("contrat") for r in db.get_factures_by_num_only(num_facture_detecte)
                        if r.get("contrat") and r.get("contrat") != contrat_detecte
                    }
                    if autres_contrats:
                        st.warning(
                            f"🔎 Remarque : le N° de Facture **{num_facture_detecte}** existe déjà mais "
                            f"associé à un autre N° de Contrat ({', '.join(autres_contrats)}). "
                            "Vérifiez qu'il ne s'agit pas d'une erreur de saisie avant de continuer."
                        )
                if not num_facture_detecte:
                    st.warning("🔎 Remarque : aucun N° de Facture n'a pu être détecté dans ce PDF — vérifiez le texte brut ci-dessous et complétez-le manuellement.")
                if not contrat_detecte:
                    st.warning("🔎 Remarque : aucun N° de Contrat n'a pu être détecté dans ce PDF.")

                # --- Étape 2 : recherche des infos liées au N° de Contrat ---
                reference = db.get_reference_by_contrat(contrat_detecte) if contrat_detecte else None
                if reference:
                    st.info(
                        f"✅ N° de Contrat **{contrat_detecte}** reconnu — Marché, Fournisseur, Nature et "
                        f"Désignation ont été pré-remplis à partir d'une facture précédente sur ce contrat."
                    )
                elif contrat_detecte:
                    st.warning(
                        "ℹ️ Ce N° de Contrat n'a pas été retrouvé dans les factures existantes — "
                        "complétez les champs manuellement ci-dessous."
                    )

                with st.form("confirm_pdf_import"):
                    f1, f2 = st.columns(2)
                    marche_val = f1.text_input("Marché / Chantier", reference.get("marche") if reference else "")
                    fournisseur_val = f2.text_input("Fournisseur", reference.get("fournisseur") if reference else "")
                    f3, f4 = st.columns(2)
                    nature_val = f3.text_input("Nature", reference.get("nature") if reference else "")
                    designation_val = f4.text_input("Désignation", reference.get("designation") if reference else "")
                    f5, f6 = st.columns(2)
                    contrat_val = f5.text_input("N° de Contrat", contrat_detecte or "")
                    num_facture_val = f6.text_input("N° de Facture", num_facture_detecte or "")
                    f7, f8 = st.columns(2)
                    montant_val = f7.number_input("Montant (MAD)", value=float(montant_detecte or 0.0), format="%.2f")
                    mois_val = f8.text_input("Mois", pd.Timestamp.now().strftime("%m/%Y"))

                    st.caption(
                        "La Remarque sera automatiquement mise à **RAP/AR** (en attente de règlement). "
                        "Vous complèterez vous-même Date de Règlement, Mode de Règlement et Date de Chèque "
                        "une fois le paiement effectué (depuis « Suivi Factures & Règlements »)."
                    )

                    confirmer = st.form_submit_button("✅ Enregistrer cette facture")
                    if confirmer:
                        if not num_facture_val.strip():
                            st.error("Le N° de Facture est requis pour éviter les doublons futurs.")
                        else:
                            nouvelle_ligne = {
                                "mois": mois_val,
                                "marche": marche_val,
                                "fournisseur": fournisseur_val,
                                "nature": nature_val,
                                "designation": designation_val,
                                "montant": montant_val,
                                "remarque": "RAP/AR",
                                "contrat": contrat_val,
                                "num_facture": num_facture_val,
                                "facture_originale_recue": True,
                                "recu_paiement_original_recu": False,
                                "date_reglement": "",
                                "mode_reglement": "",
                                "date_cheque": "",
                            }
                            db.insert_facture(nouvelle_ligne, username=user["username"])
                            st.success(f"✅ Facture {num_facture_val} enregistrée avec la remarque RAP/AR.")
                            st.rerun()

            with st.expander("📄 Voir le texte brut extrait du PDF (pour vérification)"):
                st.text(extrait.get("texte_brut", ""))

# =============================================================
# MODULE 4 : SUIVI COMPTE PRORATA
# =============================================================
elif menu == "🤝 Suivi Compte Prorata (Saisie & Modif)":
    st.subheader("🤝 Gestion & Saisie du Compte Prorata Chantier")

    if df_prorata.empty:
        df_prorata = pd.DataFrame(columns=db.PRORATA_COLUMNS)

    edited_prorata = st.data_editor(
        df_prorata.drop(columns=["id", "created_at", "updated_at"], errors="ignore"),
        num_rows="dynamic",
        use_container_width=True,
        key="editor_prorata",
        column_config={
            "montant_total": st.column_config.NumberColumn("Montant Total (MAD)", format="%.2f"),
            "montant_partage": st.column_config.NumberColumn("Montant Partagé (MAD)", format="%.2f"),
            "cle_repartition": st.column_config.NumberColumn("Clé de Répartition (%)", format="%.2f"),
        },
    )

    if st.button("💾 Enregistrer le Compte Prorata", use_container_width=True):
        db.replace_all_prorata(edited_prorata, username=user["username"])
        st.success("Compte Prorata sauvegardé !")
        st.rerun()

# =============================================================
# MODULE 5 : IMPAYÉS
# =============================================================
elif menu == "🔴 Suivi des Impayés & RAP/AR":
    st.subheader("🔴 Factures Impayées & RAP/AR")
    if not df_raw.empty:
        st.dataframe(df_raw[df_raw["remarque"].isin(["IMPAYÉ", "RAP/AR"])], use_container_width=True)
    else:
        st.info("Aucune donnée.")

# =============================================================
# MODULE 6 : MANQUANTS
# =============================================================
elif menu == "⚠️ Factures Manquantes":
    st.subheader("⚠️ Factures / Reçus Originaux Manquants")
    if not df_raw.empty:
        keywords = ["MQ", "MANQUE", "JUSTIF", "SANS"]
        remarque_col = df_raw["remarque"]
        if isinstance(remarque_col, pd.DataFrame):  # doublon de colonne résiduel
            remarque_col = remarque_col.iloc[:, 0]
        remarque_upper = remarque_col.fillna("").astype(str).str.upper()
        mask = remarque_upper.apply(lambda x: any(k in x for k in keywords))
        st.dataframe(df_raw[mask], use_container_width=True)
    else:
        st.info("Aucune donnée.")

# =============================================================
# MODULE 7 : TRANSMIS COMPTA
# =============================================================
elif menu == "📁 Transmis à la Comptabilité":
    st.subheader("📁 Dossiers Transmis à la Comptabilité")
    if not df_raw.empty:
        st.dataframe(df_raw[df_raw["remarque"] == "TRANSMIS A LA COMPTA"], use_container_width=True)
    else:
        st.info("Aucune donnée.")

# =============================================================
# MODULE 8 : BORDEREAUX D'ENVOI
# =============================================================
elif menu == "📄 Bordereaux d'Envoi":
    st.subheader("📄 Génération de Bordereau d'Envoi")
    if not df_raw.empty:
        chantier_filter = st.selectbox("Filtrer par chantier (facultatif)", ["Tous"] + CHANTIERS)
        df_show = df_raw if chantier_filter == "Tous" else df_raw[df_raw["marche"] == chantier_filter]
        st.dataframe(df_show, use_container_width=True)
        excel_buf = excel_export.export_factures_to_excel(
            df_show, settings.get("company_name", "SOCIÉTÉ ROUANDI"),
            settings.get("company_subtitle", ""),
            settings.get("theme_primary_color", "#5B1B2D"),
            settings.get("theme_secondary_color", "#C9A227"),
        )
        st.download_button(
            "⬇️ Télécharger ce Bordereau (Excel, mis en forme)",
            excel_buf, "bordereau_envoi.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("Aucune donnée.")

# =============================================================
# MODULE 9 : CONTRATS & COMPTEURS
# =============================================================
elif menu == "🚰 Contrats & Compteurs":
    st.subheader("🚰 Contrats & Compteurs Eau/Électricité")
    df_contrats = df_raw[df_raw["contrat"].astype(str).str.strip() != ""] if not df_raw.empty else df_raw
    st.dataframe(df_contrats, use_container_width=True)
    st.caption("Cette vue est en lecture seule ici — modifiez ces lignes depuis « Suivi Factures & Règlements ».")

# =============================================================
# MODULE 10 : ÉDITEUR GLOBAL
# =============================================================
elif menu == "📋 Éditeur Global (Copy/Paste/Saisie)":
    st.subheader("📋 Édition Globale (Copier/Coller direct depuis Excel)")
    if df_raw.empty:
        df_raw = pd.DataFrame(columns=db.FACTURE_COLUMNS)

    edited_global = st.data_editor(
        df_raw.drop(columns=["id", "created_at", "updated_at"], errors="ignore"),
        num_rows="dynamic",
        use_container_width=True,
        key="global_edit",
    )
    if st.button("💾 Sauvegarder Toute la Base", use_container_width=True):
        db.replace_all_factures(edited_global, username=user["username"])
        st.success("Base de données mise à jour !")
        st.rerun()

# =============================================================
# MODULE 11 : IMPORT / EXPORT
# =============================================================
elif menu == "📥 Import / Export Data":
    st.subheader("📥 Importer / Exporter des Fichiers Excel")

    tab_import, tab_export = st.tabs(["📤 Importer", "📥 Exporter"])

    with tab_import:
        if "import_flash" in st.session_state:
            st.success(st.session_state.pop("import_flash"))

        uploaded_file = st.file_uploader("Charger un Fichier Excel/CSV", type=["xlsx", "xls", "csv"])

        sheet_name = 0
        is_excel = uploaded_file is not None and uploaded_file.name.endswith((".xlsx", ".xls"))
        if is_excel:
            try:
                sheets = db.list_excel_sheets(uploaded_file)
            except Exception:
                sheets = []
            if len(sheets) > 1:
                sheet_name = st.selectbox(
                    "Ce classeur contient plusieurs feuilles — laquelle contient les factures à importer ?",
                    sheets,
                )
            elif sheets:
                sheet_name = sheets[0]

        mode = st.radio("Mode d'import", ["Ajouter aux données existantes", "Remplacer toutes les données"])

        if uploaded_file and st.button("Importer"):
            with st.spinner("⏳ Importation en cours, patientez quelques secondes..."):
                try:
                    if is_excel:
                        # Détecte automatiquement la ligne d'en-têtes, même
                        # précédée d'un bandeau logo/titre sur plusieurs lignes.
                        df_imp = db.smart_read_excel(uploaded_file, sheet_name=sheet_name)
                    else:
                        df_imp = pd.read_csv(uploaded_file)

                    df_imp = db.map_import_columns(df_imp)

                    if "montant" not in df_imp.columns:
                        st.error(
                            "⚠️ Aucune colonne « Montant » n'a été reconnue dans cette feuille. "
                            "Vérifiez que vous avez choisi la bonne feuille ci-dessus, ou que le "
                            "fichier contient bien une colonne Montant / Montant (MAD)."
                        )
                        st.write("Colonnes détectées :", list(df_imp.columns))
                        st.stop()

                    for col in db.FACTURE_COLUMNS:
                        if col not in df_imp.columns:
                            df_imp[col] = 0 if col == "montant" else False if "recue" in col else ""
                    df_imp["montant"] = pd.to_numeric(
                        df_imp["montant"].astype(str).str.replace(",", "."), errors="coerce"
                    ).fillna(0)
                    df_imp = df_imp.dropna(how="all", subset=["marche", "fournisseur", "montant"])

                    if mode == "Remplacer toutes les données":
                        db.replace_all_factures(df_imp[db.FACTURE_COLUMNS], username=user["username"])
                        total_final = len(df_imp)
                    else:
                        combined = pd.concat([df_raw.drop(columns=["id", "created_at", "updated_at"], errors="ignore"),
                                               df_imp[db.FACTURE_COLUMNS]], ignore_index=True)
                        db.replace_all_factures(combined, username=user["username"])
                        total_final = len(combined)

                    for nom in df_imp["marche"].dropna().unique():
                        db.add_chantier(str(nom))
                    for nom in df_imp["fournisseur"].dropna().unique():
                        db.add_fournisseur(str(nom))

                    montant_total = df_imp["montant"].sum()
                    st.session_state["import_flash"] = (
                        f"✅ Fichier importé avec succès ({sheet_name if is_excel else 'CSV'}) : "
                        f"{len(df_imp)} lignes lues, montant total du fichier = {montant_total:,.2f} MAD. "
                        f"La base contient maintenant {total_final} lignes au total."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'importation : {e}")

    with tab_export:
        primary = settings.get("theme_primary_color", "#5B1B2D")
        secondary = settings.get("theme_secondary_color", "#C9A227")
        company = settings.get("company_name", "SOCIÉTÉ ROUANDI")
        subtitle = settings.get("company_subtitle", "")

        if not df_raw.empty:
            excel_buf = excel_export.export_factures_to_excel(df_raw, company, subtitle, primary, secondary)
            st.download_button(
                "⬇️ Exporter Factures (Excel, mis en forme)", excel_buf, "factures_export.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            csv = df_raw.to_csv(index=False).encode("utf-8-sig")
            st.download_button("⬇️ Exporter Factures (CSV brut)", csv, "factures_export.csv", "text/csv")
        if not df_prorata.empty:
            excel_buf2 = excel_export.export_prorata_to_excel(df_prorata, company, subtitle, primary, secondary)
            st.download_button(
                "⬇️ Exporter Compte Prorata (Excel, mis en forme)", excel_buf2, "prorata_export.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            csv2 = df_prorata.to_csv(index=False).encode("utf-8-sig")
            st.download_button("⬇️ Exporter Compte Prorata (CSV brut)", csv2, "prorata_export.csv", "text/csv")

# =============================================================
# MODULE 12 : LOGS
# =============================================================
elif menu == "🗒️ Journal d'Activité (Logs)":
    st.subheader("🗒️ Journal d'Activité")
    st.caption("Historique des connexions, sauvegardes et modifications — qui a fait quoi, et quand.")
    st.dataframe(db.get_logs_df(), use_container_width=True)

# =============================================================
# MODULE 13 : PARAMÈTRES & ADMINISTRATION (admin uniquement)
# =============================================================
elif menu == "⚙️ Paramètres & Administration":
    auth.require_admin()
    st.subheader("⚙️ Paramètres & Administration")

    tab_general, tab_remarques, tab_listes, tab_users = st.tabs(
        ["🎨 Général & Apparence", "🏷️ Remarques (Statuts)", "📋 Chantiers & Fournisseurs", "👥 Utilisateurs"]
    )

    # --- Général ---
    with tab_general:
        st.write("Modifiez le nom de la société, le logo et les couleurs du thème — tout se répercute immédiatement, sans toucher au code.")
        new_name = st.text_input("Nom de la société", settings.get("company_name", ""))
        new_subtitle = st.text_input("Sous-titre", settings.get("company_subtitle", ""))
        colc1, colc2 = st.columns(2)
        new_primary = colc1.color_picker("Couleur principale", settings.get("theme_primary_color", "#1E3A8A"))
        new_secondary = colc2.color_picker("Couleur secondaire (accent)", settings.get("theme_secondary_color", "#F5A623"))
        uploaded_logo = st.file_uploader("Changer le logo (PNG/JPG)", type=["png", "jpg", "jpeg"])

        if st.button("💾 Enregistrer les Paramètres Généraux"):
            db.set_setting("company_name", new_name)
            db.set_setting("company_subtitle", new_subtitle)
            db.set_setting("theme_primary_color", new_primary)
            db.set_setting("theme_secondary_color", new_secondary)
            if uploaded_logo:
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploaded_logo.png")
                with open(logo_path, "wb") as f:
                    f.write(uploaded_logo.getbuffer())
                db.set_setting("logo_path", logo_path)
            db.log_action(user["username"], "MODIF_PARAMETRES_GENERAUX", "")
            st.success("Paramètres enregistrés !")
            st.rerun()

    # --- Remarques (parametrage dynamique des statuts) ---
    with tab_remarques:
        st.write(
            "Ajoutez, renommez, recolorez ou supprimez les statuts (« Remarques ») utilisés dans "
            "les listes déroulantes — sans jamais modifier le code."
        )
        remarques = db.get_remarques()
        for r in remarques:
            rc1, rc2, rc3, rc4 = st.columns([3, 1, 1, 1])
            rc1.markdown(style.remarque_badge(r["label"], r["couleur"]), unsafe_allow_html=True)
            new_label = rc2.text_input("Label", r["label"], key=f"lbl_{r['id']}", label_visibility="collapsed")
            new_color = rc3.color_picker("Couleur", r["couleur"], key=f"col_{r['id']}", label_visibility="collapsed")
            if rc4.button("💾", key=f"save_{r['id']}", help="Enregistrer"):
                db.update_remarque(r["label"], new_label, new_color)
                st.rerun()
            if rc4.button("🗑️", key=f"del_{r['id']}", help="Supprimer"):
                db.delete_remarque(r["label"])
                st.rerun()

        st.markdown("---")
        with st.form("add_remarque_form"):
            ac1, ac2, ac3 = st.columns([3, 1, 1])
            new_r_label = ac1.text_input("Nouvelle Remarque / Statut")
            new_r_color = ac2.color_picker("Couleur", "#3498db")
            add_r = ac3.form_submit_button("➕ Ajouter")
            if add_r and new_r_label.strip():
                db.add_remarque(new_r_label, new_r_color)
                st.success("Remarque ajoutée !")
                st.rerun()

    # --- Chantiers & Fournisseurs ---
    with tab_listes:
        col_ch, col_fo = st.columns(2)
        with col_ch:
            st.write("**Chantiers**")
            for nom in CHANTIERS:
                cc1, cc2 = st.columns([4, 1])
                cc1.write(nom)
                if cc2.button("🗑️", key=f"delch_{nom}"):
                    db.delete_chantier(nom)
                    st.rerun()
            with st.form("add_chantier_form"):
                nc = st.text_input("Nouveau chantier")
                if st.form_submit_button("➕ Ajouter") and nc.strip():
                    db.add_chantier(nc)
                    st.rerun()
        with col_fo:
            st.write("**Fournisseurs**")
            for nom in FOURNISSEURS:
                fc1, fc2 = st.columns([4, 1])
                fc1.write(nom)
                if fc2.button("🗑️", key=f"delfo_{nom}"):
                    db.delete_fournisseur(nom)
                    st.rerun()
            with st.form("add_fournisseur_form"):
                nf = st.text_input("Nouveau fournisseur")
                if st.form_submit_button("➕ Ajouter") and nf.strip():
                    db.add_fournisseur(nf)
                    st.rerun()

    # --- Utilisateurs ---
    with tab_users:
        st.write("Gestion des comptes ayant accès à l'ERP.")
        users_list = db.get_users()
        for u in users_list:
            uc1, uc2, uc3, uc4, uc5 = st.columns([2, 1, 1, 1, 1])
            uc1.write(f"**{u['username']}** ({u['role']})")
            uc2.write("🟢 Actif" if u["actif"] else "🔴 Désactivé")
            if uc3.button("Désactiver" if u["actif"] else "Activer", key=f"tog_{u['username']}"):
                db.set_user_active(u["username"], not u["actif"])
                st.rerun()
            new_pwd = uc4.text_input("Nouveau mdp", key=f"pwd_{u['username']}", label_visibility="collapsed", placeholder="Nouveau mdp")
            if uc4.button("🔑 Réinitialiser", key=f"resetpwd_{u['username']}") and new_pwd:
                db.reset_user_password(u["username"], new_pwd)
                st.success(f"Mot de passe changé pour {u['username']}")
            if u["username"] != user["username"] and uc5.button("🗑️ Supprimer", key=f"deluser_{u['username']}"):
                db.delete_user(u["username"])
                st.rerun()

        st.markdown("---")
        with st.form("add_user_form"):
            st.write("**➕ Créer un nouveau compte**")
            nu1, nu2, nu3 = st.columns(3)
            new_username = nu1.text_input("Nom d'utilisateur")
            new_password = nu2.text_input("Mot de passe", type="password")
            new_role = nu3.selectbox("Rôle", ["user", "admin"])
            if st.form_submit_button("Créer le compte"):
                if new_username.strip() and new_password.strip():
                    if db.get_user_by_username(new_username):
                        st.error("Ce nom d'utilisateur existe déjà.")
                    else:
                        db.create_user(new_username.strip(), new_password, new_role)
                        st.success(f"Compte {new_username} créé !")
                        st.rerun()
                else:
                    st.error("Veuillez remplir le nom d'utilisateur et le mot de passe.")
