"""Aplicação principal do dashboard interativo Streamlit do Pulso Eleitoral.

Implementa a narrativa científica de auditoria eleitoral no padrão de UI/UX
e storytelling do projeto Margem Eleitoral (Alexsander Camargos).
"""

from __future__ import annotations

import streamlit as st

from pulso_eleitoral.dashboard.components.executive_story_cards import (
    render_executive_story_cards,
)
from pulso_eleitoral.dashboard.components.geography_tab import (
    render_geography_tab,
)
from pulso_eleitoral.dashboard.components.integrity_tab import (
    render_integrity_tab,
)
from pulso_eleitoral.dashboard.components.timeline_tab import (
    render_timeline_tab,
)
from pulso_eleitoral.dashboard.components.verdict_tab import render_verdict_tab
from pulso_eleitoral.dashboard.data import (
    get_biometrics_data,
    get_map_locations,
    get_national_kpis,
    get_rankings_data,
    get_timeline_data,
)
from pulso_eleitoral.dashboard.styles import apply_custom_styles, clean_html


def main() -> None:
    """Ponto de entrada principal da aplicação Streamlit.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    st.set_page_config(
        page_title="Pulso Eleitoral: Auditoria da Janela de Extensão (2026/2T)",
        page_icon="🗳️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Aplica identidade visual e estilos customizados (Padrão Margem Eleitoral)
    apply_custom_styles()

    # Carrega métricas consolidadas do banco analítico DuckDB
    kpis = get_national_kpis()
    df_timeline = get_timeline_data()
    df_map = get_map_locations()
    _df_ufs, df_capitais, df_proporcao = get_rankings_data()
    bio_data = get_biometrics_data()

    # 1. Hero Executive Story Cards no topo da interface
    render_executive_story_cards(kpis)

    st.html("<div style='height: 18px;'></div>")

    # 2. Navegação em Abas Narrativas Científicas (st.tabs)
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Anatomia do Fluxo Temporal",
            "Geografia da Anomalia",
            "Integridade & Biometria",
            "Veredito Científico & Seções",
        ]
    )

    with tab1:
        render_timeline_tab(df_timeline)

    with tab2:
        render_geography_tab(df_map, df_capitais, df_proporcao)

    with tab3:
        render_integrity_tab(bio_data)

    with tab4:
        render_verdict_tab()

    # Rodapé Institucional
    footer_html = """
    <div style='text-align: center; color: #64748B; font-size: 0.8rem;
                margin-top: 3.5rem; padding-bottom: 2rem;
                border-top: 1px solid #1E242C; padding-top: 1.5rem;'>
        <strong>Pulso Eleitoral</strong> &bull; Auditoria de Logs de Urna TSE.<br/>
        Dados abertos oficiais do Tribunal Superior Eleitoral (TSE).
        Horários normalizados para o Horário de Brasília (BRT / UTC-3).<br/>
        Storytelling Científico inspirado no projeto
        <a href='https://github.com/alexcamargos/margem_eleitoral'
           target='_blank' style='color: #38BDF8; text-decoration: none;'>
            Margem Eleitoral
        </a> (Alexsander Camargos).
    </div>
    """
    st.html(clean_html(footer_html))


if __name__ == "__main__":
    main()
