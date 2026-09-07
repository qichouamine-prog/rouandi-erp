"""
pdf_invoice.py - Extraction heuristique des champs clés d'une facture PDF
(N° de Facture, N° de Contrat, Montant) pour préparer un import automatique.

IMPORTANT (honnêteté technique) : les factures PDF n'ont pas de format
standard — chaque fournisseur met ses champs à un endroit différent. Cette
extraction utilise des expressions régulières sur le texte brut du PDF et
fait de son mieux, mais n'est jamais garantie à 100%. C'est pourquoi
l'application affiche toujours les valeurs extraites dans un formulaire
modifiable avant d'enregistrer quoi que ce soit — jamais d'écriture
automatique en base sans confirmation visuelle de l'utilisateur.
"""

import re

import pdfplumber


def extract_text_from_pdf(file) -> str:
    """file : objet fichier (ex. UploadedFile de Streamlit)."""
    file.seek(0)
    text_parts = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


# Chaque motif capture la valeur qui suit le libellé (N° facture, contrat...).
# Les motifs sont volontairement tolérants aux variantes d'écriture
# (accents, °, espaces, ":" ou "-").
_FACTURE_NUM_PATTERNS = [
    r"n[°ºo]?\s*(?:de\s*)?facture\s*[:\-]?\s*([A-Za-z0-9\/\.\-]{3,})",
    r"facture\s*n[°ºo]?\s*[:\-]?\s*([A-Za-z0-9\/\.\-]{3,})",
    r"invoice\s*(?:n[°ºo]?)?\s*[:\-]?\s*([A-Za-z0-9\/\.\-]{3,})",
]

_CONTRAT_NUM_PATTERNS = [
    r"n[°ºo]?\s*(?:de\s*)?contrat\s*[:\-]?\s*([A-Za-z0-9\/\.\-]{3,})",
    r"contrat\s*n[°ºo]?\s*[:\-]?\s*([A-Za-z0-9\/\.\-]{3,})",
    r"r[ée]f(?:[ée]rence)?\.?\s*contrat\s*[:\-]?\s*([A-Za-z0-9\/\.\-]{3,})",
]

_MONTANT_PATTERNS = [
    r"net\s*[àa]\s*payer\s*[:\-]?\s*([\d\s]+[.,]\d{2})",
    r"total\s*ttc\s*[:\-]?\s*([\d\s]+[.,]\d{2})",
    r"montant\s*(?:ttc)?\s*[:\-]?\s*([\d\s]+[.,]\d{2})",
    r"total\s*[:\-]?\s*([\d\s]+[.,]\d{2})\s*(?:mad|dh)?",
]


def _first_match(patterns, text):
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_invoice_fields(text: str) -> dict:
    """Retourne un dict avec num_facture, contrat, montant (les valeurs non
    trouvées restent à None). L'appelant doit toujours laisser l'utilisateur
    vérifier/corriger ces valeurs avant tout enregistrement."""
    num_facture = _first_match(_FACTURE_NUM_PATTERNS, text)
    contrat = _first_match(_CONTRAT_NUM_PATTERNS, text)
    montant_raw = _first_match(_MONTANT_PATTERNS, text)

    montant = None
    if montant_raw:
        cleaned = montant_raw.replace(" ", "").replace(",", ".")
        try:
            montant = float(cleaned)
        except ValueError:
            montant = None

    return {
        "num_facture": num_facture,
        "contrat": contrat,
        "montant": montant,
        "texte_brut": text,
    }
