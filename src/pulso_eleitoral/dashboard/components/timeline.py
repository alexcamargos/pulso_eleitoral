"""Componente da Curva Temporal de Vazão Minuto a Minuto (Ato 2).

Gera o gráfico de alta densidade informativa utilizando Plotly, evidenciando
a física de entrada dos votos entre 17h00 e 19h06.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_timeline(df_timeline: pd.DataFrame) -> None:
    """Renderiza a curva de vazão e o histograma temporal minuto a minuto.

    Args:
        df_timeline: DataFrame com a série temporal por minuto.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    st.markdown(
        """
        <div class="section-tag">Quando</div>
        <h2 class="section-title">A física do fluxo: como os votos entraram</h2>
        <p class="section-desc">
            Em eleições típicas, a fila esgota-se nos primeiros 15 minutos.
            No 2º turno de 2026, observe o duplo comportamento: a queda abrupta da
            fila inicial (82,7% até as 17h14) seguida por um <strong>platô sustentado
            de extensão</strong> entre 17h45 e 18h30 (com picos de até 170 votos/min),
            esgotando-se gradualmente até as 19h06.
        </p>
        """,
        unsafe_allow_html=True,
    )

    if df_timeline.empty:
        st.warning("Dados temporais não disponíveis para o pleito selecionado.")
        return

    cores_map = {
        "1. Fila Inicial (Absorção Rápida)": "#FF5500",
        "2. Desaceleração / Transição": "#FF7A29",
        "3. Platô Atípico da Extensão": "#FFB703",
        "4. Esgotamento Final": "#64748B",
    }
    bar_colors = [cores_map.get(fase, "#FF5500") for fase in df_timeline["fase"]]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df_timeline["minuto"],
            y=df_timeline["votos"],
            marker_color=bar_colors,
            name="Votos por Minuto",
            hovertemplate=(
                "<b>Horário: %{x} BRT</b><br>"
                + "Votos no minuto: <b>%{y:,.0f}</b><br>"
                + "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_timeline["minuto"],
            y=df_timeline["pct_acumulado"],
            mode="lines",
            line=dict(color="#00E5FF", width=2.5, dash="dot"),
            yaxis="y2",
            name="% Acumulado da Janela",
            hovertemplate=("Progresso acumulado: <b>%{y:.1f}%</b><br><extra></extra>"),
        )
    )

    fig.add_annotation(
        x="17:00",
        y=df_timeline.loc[df_timeline["minuto"] == "17:00", "votos"].values[0],
        text="Fechamento oficial das 17h<br>(12.607 votos)",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#FF5500",
        arrowsize=1,
        arrowwidth=1.5,
        ax=40,
        ay=-30,
        font=dict(color="#FFFFFF", size=11),
        bgcolor="#1E212B",
        bordercolor="#FF5500",
    )

    fig.add_annotation(
        x="18:00",
        y=170,
        text="Platô da 2ª hora<br>(170 votos/min)",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#FFB703",
        arrowsize=1,
        arrowwidth=1.5,
        ax=40,
        ay=-40,
        font=dict(color="#FFFFFF", size=11),
        bgcolor="#1E212B",
        bordercolor="#FFB703",
    )

    fig.add_annotation(
        x="19:06",
        y=10,
        text="Último voto nacional (19:06:21)",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#64748B",
        arrowsize=1,
        arrowwidth=1.5,
        ax=-50,
        ay=-35,
        font=dict(color="#FFFFFF", size=11),
        bgcolor="#1E212B",
        bordercolor="#64748B",
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0B0E",
        plot_bgcolor="#111319",
        height=420,
        margin=dict(l=20, r=20, t=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#8C93A4"),
        ),
        xaxis=dict(
            title="Horário do Último Voto Registrado na Seção (Horário de Brasília)",
            title_font=dict(size=12, color="#8C93A4"),
            tickangle=-45,
            nticks=25,
            gridcolor="#1F232F",
            zerolinecolor="#1F232F",
        ),
        yaxis=dict(
            title="Votos por Minuto",
            title_font=dict(size=12, color="#FF5500"),
            gridcolor="#1F232F",
            zerolinecolor="#1F232F",
        ),
        yaxis2=dict(
            title="% Acumulado da Janela",
            title_font=dict(size=12, color="#00E5FF"),
            overlaying="y",
            side="right",
            range=[0, 105],
            showgrid=False,
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="method-card">
                <span class="method-tag">17h00 às 17h14</span>
                <div class="method-title">Absorção da Fila Legal</div>
                <p class="method-text">
                    <strong>29.738 votos (82,7%)</strong> foram processados nos
                    primeiros 15 minutos. Corresponde ao esvaziamento padrão dos
                    eleitores que já estavam no recinto antes do fechamento.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="method-card">
                <span class="method-tag">17h45 às 18h30</span>
                <div class="method-title">O Platô Atípico da 2ª Hora</div>
                <p class="method-text">
                    <strong>3.020 votos</strong> entraram em fluxo sustentado
                    (50 a 170 votos/min). Identifica seções onde a votação foi
                    estendida ou enfrentou lentidão extraordinária.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="method-card">
                <span class="method-tag">Cadência da Cabine</span>
                <div class="method-title">~38 Segundos por Eleitor</div>
                <p class="method-text">
                    A taxa média de digitação manteve-se idêntica ao período diurno,
                    comprovando votação humana contínua e sem injeção anormal em lote.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
