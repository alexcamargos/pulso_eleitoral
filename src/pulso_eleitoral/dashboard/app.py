"""Aplicação principal do dashboard interativo Streamlit do Pulso Eleitoral.

Implementa a narrativa de data journalism investigativo focada no comportamento
atípico dos votos registrados entre 17h00 e 19h06 no 2º turno de 2026.
"""

from __future__ import annotations

import streamlit as st

from pulso_eleitoral.dashboard.components.biometrics import render_biometrics
from pulso_eleitoral.dashboard.components.explorer import render_explorer
from pulso_eleitoral.dashboard.components.hero import render_hero
from pulso_eleitoral.dashboard.components.map_view import render_map_view
from pulso_eleitoral.dashboard.components.rankings import render_rankings
from pulso_eleitoral.dashboard.components.timeline import render_timeline
from pulso_eleitoral.dashboard.data import (
    get_biometrics_data,
    get_map_locations,
    get_national_kpis,
    get_rankings_data,
    get_timeline_data,
)
from pulso_eleitoral.dashboard.styles import apply_custom_styles


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
        page_title="Depois das 17h — Pulso Eleitoral (2026)",
        page_icon="🗳️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Aplica estilos CSS personalizados (Dark Mode + Electric Orange)
    apply_custom_styles()

    # Carrega dados consolidados do DuckDB
    kpis = get_national_kpis()
    df_timeline = get_timeline_data()
    df_map = get_map_locations()
    _df_ufs, df_capitais, df_proporcao = get_rankings_data()
    bio_data = get_biometrics_data()

    # Ato 1: Hero e KPIs Monumentais
    render_hero(kpis)

    st.html("<hr class='custom-divider'/>")

    # Ato 2: Curva de Vazão Minuto a Minuto (Física do Fluxo)
    render_timeline(df_timeline)

    st.html("<hr class='custom-divider'/>")

    # Ato 3: Onde Aconteceu (Mapa Interativo & Scrubber Temporal)
    render_map_view(df_map)

    st.html("<hr class='custom-divider'/>")

    # Ato 4: Rankings Regionais (Capitais vs Municípios de Maior Impacto)
    render_rankings(df_capitais, df_proporcao)

    st.html("<hr class='custom-divider'/>")

    # Ato 5: Integridade Biometria vs. Manual
    render_biometrics(bio_data)

    st.html("<hr class='custom-divider'/>")

    # Ato 6: Explorador de Seções e Cartões Metodológicos
    render_explorer()

    # Rodapé Institucional
    footer_html = (
        "<div style='text-align: center; color: #555C70; font-size: 0.8rem; "
        "margin-top: 4rem; padding-bottom: 2rem;'>"
        "Pulso Eleitoral — Auditoria Técnica e Reproduzível de Logs de Urna TSE.<br/>"
        "Dados abertos oficiais do Tribunal Superior Eleitoral (TSE). "
        "Horários normalizados para o Horário de Brasília (BRT / UTC-3).<br/>"
        "Desenvolvido em Python com DuckDB e Streamlit "
        "sob o protocolo SDD (Spec-Driven Development)."
        "</div>"
    )
    st.html(footer_html)


if __name__ == "__main__":
    main()
