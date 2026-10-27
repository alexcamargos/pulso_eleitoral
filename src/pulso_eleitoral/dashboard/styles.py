"""Definição de estilos CSS customizados e identidade visual do dashboard.

Configura a paleta de cores *Investigative Dark Mode* com detalhes em
laranja eleitoral (#FF5500), tipografia moderna e cartões com acabamento
glassmorphism escuro para data journalism.
"""

from __future__ import annotations

import streamlit as st

DASHBOARD_CSS = """
<style>
/* Reset de espaçamentos superiores padrão do Streamlit */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1280px !important;
}

/* Tipografia global e fundo */
body {
    background-color: #0A0B0E !important;
    color: #F1F3F5 !important;
}

/* Badge de topo */
.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(255, 85, 0, 0.12);
    border: 1px solid rgba(255, 85, 0, 0.35);
    color: #FF7A29;
    padding: 0.35rem 0.85rem;
    border-radius: 9999px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 0.75rem;
}

/* Título Monumental */
.hero-title {
    font-size: clamp(2.2rem, 5vw, 3.8rem);
    font-weight: 900;
    line-height: 1.08;
    color: #FFFFFF;
    margin: 0;
    letter-spacing: -0.03em;
}

.hero-highlight {
    color: #FF5500;
    text-shadow: 0 0 25px rgba(255, 85, 0, 0.4);
}

.hero-subtext {
    font-size: 1.1rem;
    color: #9DA3AE;
    line-height: 1.55;
    margin-top: 0.85rem;
    margin-bottom: 2rem;
    max-width: 820px;
}

/* Cartões de KPI Monumentais */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 2.5rem;
}

.kpi-card {
    background: #13151C;
    border: 1px solid #1F222E;
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    position: relative;
    overflow: hidden;
    transition: transform 0.15s ease, border-color 0.15s ease;
}

.kpi-card:hover {
    border-color: rgba(255, 85, 0, 0.4);
    transform: translateY(-2px);
}

.kpi-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #FF5500 0%, #FF9E00 100%);
    opacity: 0.8;
}

.kpi-value {
    font-size: 2.1rem;
    font-weight: 800;
    color: #FFFFFF;
    line-height: 1.1;
    letter-spacing: -0.02em;
}

.kpi-label {
    font-size: 0.8rem;
    color: #8C93A4;
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.06em;
    margin-top: 0.4rem;
}

.kpi-sub {
    font-size: 0.82rem;
    color: #FF7A29;
    font-weight: 500;
    margin-top: 0.35rem;
}

/* Títulos de Seções Narrativas */
.section-tag {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #FF5500;
    margin-bottom: 0.25rem;
}

.section-title {
    font-size: 1.8rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.02em;
    margin-top: 0;
    margin-bottom: 0.4rem;
}

.section-desc {
    font-size: 0.95rem;
    color: #9DA3AE;
    line-height: 1.5;
    margin-bottom: 1.25rem;
}

/* Card Metodológico Didático */
.method-card {
    background: #111319;
    border: 1px solid #1E212B;
    border-radius: 12px;
    padding: 1.25rem;
    height: 100%;
}

.method-tag {
    font-size: 0.7rem;
    font-weight: 700;
    color: #FF5500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.method-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #FFFFFF;
    margin: 0.3rem 0 0.5rem 0;
}

.method-text {
    font-size: 0.85rem;
    color: #8C93A4;
    line-height: 1.5;
    margin: 0;
}

/* Customização dos widgets do Streamlit */
div[data-baseweb="select"] > div {
    background-color: #13151C !important;
    border-color: #1F222E !important;
    color: #FFFFFF !important;
}

/* Linha divisória suave */
.custom-divider {
    height: 1px;
    background: #1A1D26;
    margin: 2.5rem 0;
    border: none;
}
</style>
"""


def apply_custom_styles() -> None:
    """Aplica os estilos CSS da identidade visual no aplicativo Streamlit.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    st.html(DASHBOARD_CSS)
