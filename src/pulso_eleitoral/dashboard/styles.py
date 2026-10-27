"""Definição de estilos CSS customizados e identidade visual do dashboard.

Configura a paleta de cores institucional do dashboard: fundo dark slate
(#0E1117 / #121417), cartões em dark charcoal (#181B20), bordas refinadas
(#282D37), destaque primário em Sky Blue (#38BDF8) e acentos de integridade
(#10B981, #F59E0B, #EF4444).
"""

from __future__ import annotations

import re

import streamlit as st

DASHBOARD_CSS = """
<style>
/* Fundo geral e tipografia limpa */
.stApp {
    background-color: #121417 !important;
    color: #E2E8F0 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
        sans-serif !important;
}

/* Redução de espaçamentos superiores nativos do Streamlit */
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 3.5rem !important;
    max-width: 1280px !important;
}

/* Breadcrumbs e Cabeçalho Superior */
.breadcrumb-text {
    color: #94A3B8;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 4px;
}

.main-header-title {
    font-size: 27px;
    font-weight: 800;
    color: #F8FAFC;
    margin-bottom: 6px;
    letter-spacing: -0.5px;
    line-height: 1.2;
}

.main-header-subtitle {
    font-size: 14px;
    color: #94A3B8;
    line-height: 1.5;
    margin-bottom: 18px;
    max-width: 900px;
}

/* Banner de Contexto da Totalização Oficial */
.tse-summary-card {
    background-color: #181B20;
    border: 1px solid #282D37;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 20px;
}

.tse-summary-title {
    font-size: 14px;
    font-weight: 700;
    color: #F1F5F9;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.tse-summary-stats {
    color: #94A3B8;
    font-size: 13px;
    line-height: 1.5;
}

/* Hero Executive Story Cards */
.hero-card {
    background-color: #181B20;
    border: 1px solid #282D37;
    border-radius: 10px;
    padding: 18px 20px;
    height: 100%;
    min-height: 140px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: visible;
}

.hero-card:hover {
    border-color: #38BDF8;
    transition: border-color 0.2s ease;
}

.hero-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11.5px;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 10px;
}

.hero-pill {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 9999px;
    letter-spacing: 0.3px;
}

.hero-pill-info {
    background: rgba(56, 189, 248, 0.15);
    color: #38BDF8;
    border: 1px solid rgba(56, 189, 248, 0.3);
}

.hero-pill-success {
    background: rgba(16, 185, 129, 0.15);
    color: #10B981;
    border: 1px solid rgba(16, 185, 129, 0.3);
}

.hero-pill-warning {
    background: rgba(245, 158, 11, 0.15);
    color: #F59E0B;
    border: 1px solid rgba(245, 158, 11, 0.3);
}

.hero-metric-val {
    font-size: 32px;
    font-weight: 800;
    color: #F8FAFC;
    line-height: 1.1;
    letter-spacing: -0.5px;
}

.hero-metric-sub {
    font-size: 13px;
    color: #94A3B8;
    margin-top: 6px;
    line-height: 1.4;
}

/* Customização refinada das Abas (stTabs) */
.stTabs [data-baseweb="tab-list"],
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 6px !important;
    border-bottom: 1px solid #282D37 !important;
    margin-bottom: 18px !important;
}

.stTabs [data-baseweb="tab"],
button[data-baseweb="tab"] {
    background-color: #181B20 !important;
    border: 1px solid #282D37 !important;
    border-radius: 6px 6px 0 0 !important;
    color: #CBD5E1 !important;
    padding: 8px 16px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
}

.stTabs [aria-selected="true"],
button[data-baseweb="tab"][aria-selected="true"] {
    background-color: #242933 !important;
    color: #38BDF8 !important;
    border-bottom: 2px solid #38BDF8 !important;
}

.stTabs [aria-selected="true"] p,
button[data-baseweb="tab"][aria-selected="true"] p {
    color: #38BDF8 !important;
    font-weight: 700 !important;
}

/* Cards informativos e didáticos internos */
.info-box {
    background-color: #181B20;
    border: 1px solid #282D37;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 14px;
    overflow: visible;
}

.info-box-title {
    font-size: 14px;
    font-weight: 700;
    color: #F8FAFC;
    margin-bottom: 6px;
}

.info-box-desc {
    font-size: 13px;
    color: #94A3B8;
    line-height: 1.5;
    margin: 0;
}

/* Linha divisória sutil */
.custom-divider {
    height: 1px;
    background: #282D37;
    margin: 20px 0;
    border: none;
}
</style>
"""


def clean_html(html_str: str) -> str:
    """Higieniza e compacta strings HTML para renderização nativa segura no Streamlit.

    Remove comentários HTML, recuos e quebras de linha preservando o espaçamento
    correto entre palavras e tags textuais para evitar aglutinação indevida.

    Args:
        html_str: String de markup HTML com potenciais quebras de linha e recuos.

    Returns:
        String HTML compactada e contínua em linha única.

    Raises:
        Nenhum.
    """
    cleaned = re.sub(r"<!--.*?-->", "", html_str, flags=re.DOTALL)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return ""

    result: list[str] = [lines[0]]
    for line in lines[1:]:
        prev = result[-1]
        if not prev.endswith(">") or not line.startswith("<"):
            result.append(" ")
        result.append(line)

    return "".join(result)


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
