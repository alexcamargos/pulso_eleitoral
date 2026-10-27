"""Componente da Aba 2: Geografia da Anomalia (Megalópoles vs Sudoeste Amazônico).

Apresenta o mapa geoespacial Pydeck estilizado,
além do confronto dos dois eixos de impacto: volume absoluto vs impacto relativo.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from pulso_eleitoral.dashboard.styles import clean_html


def render_geography_tab(
    df_map: pd.DataFrame,
    df_capitais: pd.DataFrame,
    df_proporcao: pd.DataFrame,
) -> None:
    """Renderiza a narrativa geoespacial, o mapa e os rankings dos dois eixos.

    Args:
        df_map: DataFrame contendo as coordenadas geográficas dos municípios.
        df_capitais: DataFrame das capitais com maior volume absoluto.
        df_proporcao: DataFrame dos municípios com maior peso percentual relativo.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    intro_html = """
    <div style="margin-bottom: 16px;">
        <div style="font-size: 20px; font-weight: 700; color: #F8FAFC;">
            Ato 2: Geografia da Anomalia: Os Dois Eixos Discrepantes
        </div>
        <div style="font-size: 13.5px; color: #94A3B8; margin-top: 4px;
            line-height: 1.5;">
            A extensão de horário não se distribuiu homogeneamente.
            A análise espacial revela uma cisão entre dois polos:
            <strong>grandes megalópoles urbanas</strong> (concentrando o volume
            absoluto de votos) e <strong>municípios remotos do Sudoeste
            Amazônico</strong> (onde o fuso unificado das 17h BRT encerrou as urnas
            às 15h locais em áreas ribeirinhas de logística complexa).
        </div>
    </div>
    """
    st.html(clean_html(intro_html))

    if df_map.empty:
        st.warning("Dados geoespaciais não disponíveis.")
        return

    # Controles do Mapa (Scrubber Temporal e Busca)
    c_time, c_search = st.columns([2.5, 1.0])
    with c_time:
        horarios = [
            "19:06 (Janela Completa)",
            "18:45 (Últimos 20 min)",
            "18:30 (Extensão Avançada)",
            "18:00 (Entrada na 2ª Hora)",
            "17:30 (Fim da Absorção Inicial)",
            "17:15 (Primeiros 15 min)",
        ]
        sel_horario = st.select_slider(
            "Filtrar por Horário Limite de Encerramento (BRT):",
            options=horarios,
            value="19:06 (Janela Completa)",
            help="Filtra os municípios cuja última seção fechou até o horário.",
        )

    with c_search:
        search_mun = st.text_input(
            "Pesquisar Município:",
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

    # Raio visual proporcional calibrado para evitar saturação e cortes
    df_filtered["raio_metros"] = df_filtered["votos_pos"].apply(
        lambda v: min(v * 10 + 3500, 48000)
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_filtered,
        get_position=["longitude", "latitude"],
        get_radius="raio_metros",
        get_fill_color=[56, 189, 248, 175],
        get_line_color=[14, 165, 233, 230],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )

    # Enquadramento territorial completo para evitar corte de pontos nos extremos
    view_state = pdk.ViewState(
        latitude=-15.0,
        longitude=-53.5,
        zoom=3.3,
        min_zoom=2.5,
        max_zoom=10,
        pitch=0,
    )

    tooltip_html = (
        "<div style='font-family: -apple-system, sans-serif; font-size: 12.5px;'>"
        "<b style='color: #F8FAFC;'>{municipio_nome} - {uf}</b>"
        "<hr style='border: 0; border-top: 1px solid #282D37; margin: 4px 0;'/>"
        "Votos pós-17h: <b style='color: #38BDF8;'>{votos_pos}</b><br/>"
        "Fatia do município: <b>{pct_apos_17h}%</b><br/>"
        "Último voto: <b>{ultimo_voto_str} BRT</b>"
        "</div>"
    )

    tooltip = {
        "html": tooltip_html,
        "style": {
            "backgroundColor": "#181B20",
            "color": "#E2E8F0",
            "border": "1px solid #282D37",
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

    st.pydeck_chart(deck)

    st.caption(
        f"Exibindo **{len(df_filtered):,}** de **{len(df_map):,}** municípios "
        f"com seções encerradas até **{limite} BRT**."
    )

    # Confronto dos Dois Eixos (Rankings Lado a Lado)
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    c_rank1, c_rank2 = st.columns(2, gap="medium")

    with c_rank1:
        st.markdown(
            """
            <div class="info-box-title" style="color: #38BDF8;">
                Eixo 1: Megalópoles &bull; Volume Absoluto
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not df_capitais.empty:
            df_cap = df_capitais.sort_values(by="votos_pos", ascending=True)
            labels = [
                f"{mun} ({uf})"
                for mun, uf in zip(df_cap["municipio_nome"], df_cap["uf"], strict=False)
            ]
            fig_cap = go.Figure(
                go.Bar(
                    x=df_cap["votos_pos"],
                    y=labels,
                    orientation="h",
                    marker=dict(
                        color="#38BDF8",
                        line=dict(color="#0284C7", width=1),
                    ),
                    text=[f"{v:,.0f}" for v in df_cap["votos_pos"]],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b>: %{x:,.0f} votos<extra></extra>",
                )
            )
            max_cap = float(df_cap["votos_pos"].max()) if not df_cap.empty else 5000.0
            fig_cap.update_layout(
                template="plotly_dark",
                paper_bgcolor="#181B20",
                plot_bgcolor="#121417",
                height=350,
                margin=dict(l=150, r=50, t=15, b=25),
                xaxis=dict(
                    title="Votos Pós-17h",
                    range=[0, max_cap * 1.18],
                    gridcolor="#282D37",
                    zerolinecolor="#282D37",
                    automargin=True,
                ),
                yaxis=dict(
                    automargin=True,
                ),
            )
            st.plotly_chart(fig_cap)

    with c_rank2:
        st.markdown(
            """
            <div class="info-box-title" style="color: #F59E0B;">
                Eixo 2: Sudoeste Amazônico &bull; Impacto Relativo Local
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not df_proporcao.empty:
            df_prop = df_proporcao.sort_values(by="pct_pos", ascending=True)
            labels_prop = [
                f"{mun} ({uf})"
                for mun, uf in zip(
                    df_prop["municipio_nome"], df_prop["uf"], strict=False
                )
            ]
            fig_prop = go.Figure(
                go.Bar(
                    x=df_prop["pct_pos"],
                    y=labels_prop,
                    orientation="h",
                    marker=dict(
                        color="#F59E0B",
                        line=dict(color="#D97706", width=1),
                    ),
                    text=[f"{p:.2f}%" for p in df_prop["pct_pos"]],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b>: %{x:.2f}% dos votos<extra></extra>",
                )
            )
            max_prop = float(df_prop["pct_pos"].max()) if not df_prop.empty else 10.0
            fig_prop.update_layout(
                template="plotly_dark",
                paper_bgcolor="#181B20",
                plot_bgcolor="#121417",
                height=350,
                margin=dict(l=165, r=50, t=15, b=25),
                xaxis=dict(
                    title="% em Relação ao Total de Votos do Município",
                    range=[0, max_prop * 1.18],
                    gridcolor="#282D37",
                    zerolinecolor="#282D37",
                    automargin=True,
                ),
                yaxis=dict(
                    automargin=True,
                ),
            )
            st.plotly_chart(fig_prop)
