"""
style.py - Habillage visuel de l'ERP, thème sombre "bordeaux/or" piloté par
les Paramètres (aucune couleur n'est figée dans le code : tout vient de
la table `settings`, modifiable depuis ⚙️ Paramètres > Général & Apparence).
"""

import streamlit as st


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        hex_color = "5B1B2D"
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def apply_style(primary_color: str, secondary_color: str):
    primary_glow = _hex_to_rgba(primary_color, 0.35)
    primary_soft = _hex_to_rgba(primary_color, 0.12)

    st.markdown(
        f"""
        <style>
        :root {{
            --primary-color: {primary_color};
            --secondary-color: {secondary_color};
        }}

        /* ---------- Fond général : dégradé bordeaux sombre ---------- */
        .stApp {{
            background: radial-gradient(circle at 15% 0%, {primary_soft} 0%, transparent 45%),
                        linear-gradient(160deg, #1a0d12 0%, #120a0e 60%, #0d080b 100%);
        }}
        .main .block-container {{
            padding-top: 1.2rem;
        }}

        /* ---------- Titres ---------- */
        h1, h2, h3 {{
            color: #F4E9D8;
            font-weight: 700;
        }}
        p, span, label, .stMarkdown {{
            color: #E6DCE0;
        }}

        /* ---------- Sidebar sombre avec accent doré ---------- */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #24121a 0%, #170c11 100%);
            border-right: 1px solid {_hex_to_rgba(secondary_color, 0.25)};
        }}
        section[data-testid="stSidebar"] * {{
            color: #F4E9D8 !important;
        }}
        section[data-testid="stSidebar"] .stRadio > div {{
            gap: 4px;
        }}
        section[data-testid="stSidebar"] .stRadio label {{
            background: transparent;
            border-radius: 8px;
            padding: 6px 10px;
            transition: 0.15s ease-in-out;
        }}
        section[data-testid="stSidebar"] .stRadio label:hover {{
            background: {primary_soft};
        }}

        /* ---------- Cartes KPI façon "tableau de bord" ---------- */
        div[data-testid="stMetric"] {{
            background: linear-gradient(155deg, {primary_color} 0%, {_hex_to_rgba(primary_color, 0.75)} 100%);
            border: 1px solid {_hex_to_rgba(secondary_color, 0.35)};
            border-radius: 14px;
            padding: 16px 18px;
            box-shadow: 0 6px 18px {primary_glow};
        }}
        div[data-testid="stMetric"] label,
        div[data-testid="stMetricLabel"] p {{
            color: {secondary_color} !important;
            font-weight: 600;
            letter-spacing: 0.02em;
        }}
        div[data-testid="stMetricValue"] {{
            color: #FBF3E4 !important;
            font-size: 1.7rem;
        }}

        /* ---------- Conteneurs / expanders comme des cartes ---------- */
        div[data-testid="stExpander"], div[data-testid="stForm"] {{
            background: rgba(42, 22, 32, 0.65);
            border: 1px solid {_hex_to_rgba(secondary_color, 0.2)};
            border-radius: 14px;
            padding: 4px 10px;
        }}

        /* ---------- Tableaux (data_editor / dataframe) ---------- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {{
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid {_hex_to_rgba(secondary_color, 0.25)};
        }}

        /* ---------- Boutons ---------- */
        .stButton > button {{
            background: linear-gradient(135deg, {primary_color}, {_hex_to_rgba(primary_color, 0.85)});
            color: #FBF3E4;
            border: 1px solid {_hex_to_rgba(secondary_color, 0.4)};
            border-radius: 8px;
            font-weight: 600;
            transition: 0.15s ease-in-out;
        }}
        .stButton > button:hover {{
            background: {secondary_color};
            color: #241019;
            border-color: {secondary_color};
        }}
        div[data-testid="stFormSubmitButton"] > button {{
            background: {secondary_color};
            color: #241019;
            font-weight: 700;
            border: none;
        }}
        div[data-testid="stFormSubmitButton"] > button:hover {{
            filter: brightness(1.08);
        }}
        .stDownloadButton > button {{
            background: transparent;
            color: {secondary_color};
            border: 1px solid {secondary_color};
            border-radius: 8px;
            font-weight: 600;
        }}
        .stDownloadButton > button:hover {{
            background: {secondary_color};
            color: #241019;
        }}

        /* ---------- Onglets ---------- */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
            border-bottom: 1px solid {_hex_to_rgba(secondary_color, 0.2)};
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: rgba(0,0,0,0.15);
            color: #E6DCE0;
            border-radius: 8px 8px 0 0;
            padding: 8px 18px;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: {primary_color} !important;
            color: #FBF3E4 !important;
        }}

        /* ---------- Champs de saisie ---------- */
        input, textarea, .stSelectbox div[data-baseweb="select"] > div {{
            background-color: rgba(255,255,255,0.06) !important;
            color: #F4E9D8 !important;
            border-color: {_hex_to_rgba(secondary_color, 0.3)} !important;
        }}

        /* ---------- Bandeau utilisateur connecté ---------- */
        .user-badge {{
            background: linear-gradient(135deg, {primary_color}, {_hex_to_rgba(primary_color, 0.8)});
            color: #FBF3E4;
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 0.82rem;
            font-weight: 600;
            border: 1px solid {_hex_to_rgba(secondary_color, 0.4)};
            display: inline-block;
        }}

        div[data-testid="stAlert"] {{
            border-radius: 10px;
        }}

        footer {{visibility: hidden;}}
        #MainMenu {{visibility: hidden;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def remarque_badge(label: str, couleur: str) -> str:
    """Retourne un badge HTML coloré pour une valeur de Remarque, utile
    pour un rendu plus lisible que du texte brut dans les tableaux/résumés."""
    return (
        f"<span style='background-color:{couleur}33; color:{couleur}; "
        f"border:1px solid {couleur}; padding:2px 10px; border-radius:12px; "
        f"font-size:0.8rem; font-weight:600;'>{label}</span>"
    )


def kpi_card_html(title: str, value: str, accent: str = "#C9A227") -> str:
    """Carte KPI HTML autonome (façon tableau de bord), utilisable partout où
    st.metric ne convient pas (ex: cartes avec barre de progression)."""
    return f"""
    <div style="background:linear-gradient(155deg, #2A1620, #1c0f16);
                border:1px solid {accent}55; border-radius:14px; padding:16px 18px;
                box-shadow:0 6px 16px rgba(0,0,0,0.35);">
        <div style="color:{accent}; font-weight:600; font-size:0.85rem; margin-bottom:6px;">{title}</div>
        <div style="color:#FBF3E4; font-size:1.6rem; font-weight:700;">{value}</div>
    </div>
    """
