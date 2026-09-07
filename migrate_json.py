"""
migrate_json.py - Migration ponctuelle de l'ancien system_db.json vers SQLite.

Utilisation (une seule fois, si vous avez un ancien fichier system_db.json) :
    python migrate_json.py /chemin/vers/system_db.json

Ce script est séparé de l'application pour que vous puissiez vérifier son
résultat avant de lancer l'ERP (il affiche un résumé de ce qui a été importé).
"""

import sys
import json
import pandas as pd

import db


def migrate(json_path: str):
    db.init_db()

    with open(json_path, "r", encoding="utf-8") as f:
        old = json.load(f)

    # --- Factures ---
    old_factures = old.get("data", [])
    if old_factures:
        df = pd.DataFrame(old_factures)
        rename_map = {
            "Mois": "mois", "Marché / Chantier": "marche", "Fournisseurs": "fournisseur",
            "Nature": "nature", "Désignation": "designation", "Montant (MAD)": "montant",
            "Remarque": "remarque", "N° de Contrat": "contrat",
            "Facture_Originale_Recue": "facture_originale_recue",
            "Recu_Paiement_Original_Recu": "recu_paiement_original_recu",
        }
        df = df.rename(columns=rename_map)
        for col in db.FACTURE_COLUMNS:
            if col not in df.columns:
                df[col] = "" if col not in (
                    "facture_originale_recue", "recu_paiement_original_recu", "montant"
                ) else 0
        df["montant"] = pd.to_numeric(
            df["montant"].astype(str).str.replace(",", "."), errors="coerce"
        ).fillna(0)
        db.replace_all_factures(df[db.FACTURE_COLUMNS], username="migration")
        print(f"✅ {len(df)} factures importées.")

        # récupère aussi les listes de chantiers / fournisseurs / remarques rencontrées
        for nom in df["marche"].dropna().unique():
            db.add_chantier(str(nom))
        for nom in df["fournisseur"].dropna().unique():
            db.add_fournisseur(str(nom))
        for label in df["remarque"].dropna().unique():
            if label and label not in db.get_remarques_labels():
                db.add_remarque(str(label))
    else:
        print("ℹ️ Aucune facture trouvée dans l'ancien fichier.")

    # --- Prorata ---
    old_prorata = old.get("prorata_data", [])
    if old_prorata:
        dfp = pd.DataFrame(old_prorata)
        rename_map_p = {
            "Date": "date", "Chantier": "chantier", "Libellé Dépense": "libelle",
            "Fournisseur": "fournisseur", "Montant Total (MAD)": "montant_total",
            "Entreprise / Sous-Traitant": "entreprise",
            "Clé de Répartition (%)": "cle_repartition",
            "Montant Partagé (MAD)": "montant_partage", "Statut Règlement": "statut",
        }
        dfp = dfp.rename(columns=rename_map_p)
        for col in db.PRORATA_COLUMNS:
            if col not in dfp.columns:
                dfp[col] = 0 if "montant" in col or "cle" in col else ""
        db.replace_all_prorata(dfp[db.PRORATA_COLUMNS], username="migration")
        print(f"✅ {len(dfp)} lignes de compte prorata importées.")
    else:
        print("ℹ️ Aucune donnée de compte prorata trouvée.")

    print("\n🎉 Migration terminée. Vous pouvez maintenant lancer : streamlit run app.py")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python migrate_json.py /chemin/vers/system_db.json")
        sys.exit(1)
    migrate(sys.argv[1])
