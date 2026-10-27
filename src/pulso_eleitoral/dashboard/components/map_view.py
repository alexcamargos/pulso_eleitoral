"""Componente do Mapa Geoespacial Dot-Density e Scrubber Temporal (Ato 3).

Exibe cada município com votação pós-17h no Brasil como um ponto luminoso
em Pydeck, com suporte a filtro de horário e busca por localidade.
"""

from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st


def render_map_view(df_map: pd.DataFrame) -> None:
    """Renderiza o mapa geoespacial e a barra de controle temporal (scrubber).

    Args:
        df_map: DataFrame contendo as coordenadas e métricas dos municípios.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    st.markdown(
        """
        <div class="section-tag">Onde</div>
        <h2 class="section-title">Cada círculo é um polo de votação</h2>
        <p class="section-desc">
            Você está visualizando os <strong>3.341 municípios</strong> onde eleitores
            votaram após as 17h. O raio e o brilho refletem o volume absoluto de votos.
            Utilize a barra temporal abaixo para rebobinar o encerramento pelo país.
        </p>
        """,
        unsafe_allow_html=True,
    )

    if df_map.empty:
        st.warning("Nenhum dado geográfico encontrado para os filtros selecionados.")
        return

    # Controles de Interatividade (Scrubber Temporal e Busca)
    col_ctrl1, col_ctrl2 = st.columns([3, 1])

    with col_ctrl1:
        horarios = [
            "19:06 (Janela Completa)",
            "18:45 (Últimos 20 min)",
            "18:30 (Extensão Avançada)",
            "18:00 (Entrada na 2ª Hora)",
            "17:30 (Fim da Absorção Inicial)",
            "17:15 (Primeiros 15 min)",
        ]
        sel_horario = st.select_slider(
            "Filtrar por Horário de Encerramento (BRT):",
            options=horarios,
            value="19:06 (Janela Completa)",
            help="Filtra os municípios com seções ativas até o horário selecionado.",
        )

    with col_ctrl2:
        search_mun = st.text_input(
            "Buscar Município:",
            placeholder="Ex: São Paulo, Lábrea...",
            help="Filtra a lista e destaca a localidade no mapa.",
        )

    df_filtered = df_map.copy()

    corte_map = {
        "19:06 (Janela Completa)": "19:06",
        "18:45 (Últimos 20 min)": "18:45",
        "18:30 (Extensão Avançada)": "18:30",
        "18:00 (Entrada na 2ª Hora)": "18:00",
        "17:30 (Fim da Absorção Inicial)": "17:30",
        "17:15 (Primeiros 15 min)": "17:15",
    }
    limite = corte_map.get(sel_horario, "19:06")
    df_filtered = df_filtered[df_filtered["ultimo_voto_str"] <= f"{limite}:59"]

    if search_mun:
        df_filtered = df_filtered[
            df_filtered["municipio_nome"].str.contains(search_mun.upper(), na=False)
        ]

    # Cálculo do raio visual proporcional
    df_filtered["raio_metros"] = df_filtered["votos_pos"].apply(
        lambda v: min(v * 12 + 3500, 75000)
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_filtered,
        get_position=["longitude", "latitude"],
        get_radius="raio_metros",
        get_fill_color=[255, 85, 0, 185],
        get_line_color=[255, 170, 0, 220],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=-14.235,
        longitude=-51.925,
        zoom=3.8,
        min_zoom=3,
        max_zoom=10,
        pitch=0,
    )

    tooltip_html = (
        "<div style='font-family: sans-serif;'>"
        "<b style='font-size: 14px; color: #FFFFFF;'>{municipio_nome} - {uf}</b>"
        "<hr style='border: 0; border-top: 1px solid #333; margin: 4px 0;'/>"
        "Votos pós-17h: <b style='color: #FF5500;'>{votos_pos}</b><br/>"
        "Fatia do município: <b>{pct_apos_17h}%</b><br/>"
        "Último voto: <b>{ultimo_voto_str} BRT</b>"
        "</div>"
    )

    tooltip = {
        "html": tooltip_html,
        "style": {
            "backgroundColor": "#13151C",
            "color": "#F1F3F5",
            "border": "1px solid #FF5500",
            "borderRadius": "8px",
            "padding": "10px",
            "boxShadow": "0 4px 20px rgba(0,0,0,0.6)",
        },
    }

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="dark",
        tooltip=tooltip,
    )

    st.pydeck_chart(deck, use_container_width=True)

    st.caption(
        f"Exibindo **{len(df_filtered):,}** de **{len(df_map):,}** municípios "
        f"com seções encerradas até **{limite} BRT**."
    )
