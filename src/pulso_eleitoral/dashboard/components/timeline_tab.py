"""Componente da Aba 1: Anatomia do Fluxo Temporal e Física de Vazão.

Apresenta a série temporal minuto a minuto utilizando Plotly estilizado,
destacando a absorção inicial e o platô anômalo das 18h.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pulso_eleitoral.dashboard.styles import clean_html


def render_timeline_tab(df_timeline: pd.DataFrame) -> None:
    """Renderiza a narrativa e os gráficos interativos da série temporal.

    Args:
        df_timeline: DataFrame com a série temporal por minuto (17h00 às 19h06).

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    intro_html = """
    <div style="margin-bottom: 16px;">
        <div style="font-size: 20px; font-weight: 700; color: #F8FAFC;">
            Ato 1: Anatomia do Fluxo Temporal e Física de Vazão
        </div>
        <div style="font-size: 13.5px; color: #94A3B8; margin-top: 4px;
            line-height: 1.5;">
            Em eleições ordinárias, a fila residual esgota-se nos primeiros 15 minutos.
            No 2º turno de 2026, observe o duplo comportamento: a queda abrupta da
            fila inicial (82,7% até 17h14) seguida por um
            <strong>platô anômalo sustentado de extensão</strong> entre 17h45 e 18h30
            (com picos de 170 votos/minuto), esgotando-se às 19h06.
        </div>
    </div>
    """
    st.html(clean_html(intro_html))

    if df_timeline.empty:
        st.warning("Dados temporais não disponíveis para o pleito selecionado.")
        return

    cores_map = {
        "1. Fila Inicial (Absorção Rápida)": "#38BDF8",
        "2. Desaceleração / Transição": "#0284C7",
        "3. Platô Atípico da Extensão": "#F59E0B",
        "4. Esgotamento Final": "#64748B",
    }
    bar_colors = [cores_map.get(fase, "#38BDF8") for fase in df_timeline["fase"]]

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
            mode="lines+markers",
            marker=dict(color="#10B981", size=4),
            line=dict(color="#10B981", width=2.5, dash="dot"),
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
        arrowcolor="#38BDF8",
        arrowsize=1,
        arrowwidth=1.5,
        ax=45,
        ay=-30,
        font=dict(color="#F8FAFC", size=11),
        bgcolor="#1E242C",
        bordercolor="#38BDF8",
    )

    fig.add_annotation(
        x="18:00",
        y=170,
        text="Platô Anômalo das 18h<br>(170 votos/min)",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#F59E0B",
        arrowsize=1,
        arrowwidth=1.5,
        ax=45,
        ay=-40,
        font=dict(color="#F8FAFC", size=11),
        bgcolor="#1E242C",
        bordercolor="#F59E0B",
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
        ax=-55,
        ay=-35,
        font=dict(color="#F8FAFC", size=11),
        bgcolor="#1E242C",
        bordercolor="#64748B",
    )

    max_votos = float(df_timeline["votos"].max()) if not df_timeline.empty else 13000.0
    y_max = max(max_votos * 1.15, 14500.0)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#181B20",
        plot_bgcolor="#121417",
        height=440,
        margin=dict(l=55, r=55, t=65, b=65),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#94A3B8"),
        ),
        xaxis=dict(
            title="Horário do Último Voto Registrado na Seção (Horário de Brasília)",
            title_font=dict(size=12, color="#94A3B8"),
            tickangle=-45,
            nticks=25,
            gridcolor="#282D37",
            zerolinecolor="#282D37",
            automargin=True,
        ),
        yaxis=dict(
            title="Votos por Minuto",
            title_font=dict(size=12, color="#38BDF8"),
            range=[0, y_max],
            gridcolor="#282D37",
            zerolinecolor="#282D37",
            automargin=True,
        ),
        yaxis2=dict(
            title="% Acumulado da Janela",
            title_font=dict(size=12, color="#10B981"),
            overlaying="y",
            side="right",
            range=[0, 105],
            showgrid=False,
            automargin=True,
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        card1 = """
        <div class="info-box">
            <div class="info-box-title" style="color: #38BDF8;">
                17h00 às 17h14 &bull; Fila Inicial
            </div>
            <div class="info-box-desc">
                <strong>29.738 votos (82,7%)</strong> absorvidos nos primeiros 15 min.
                Corresponde à dispersão natural dos eleitores com senha legal.
            </div>
        </div>
        """
        st.html(clean_html(card1))

    with c2:
        card2 = """
        <div class="info-box">
            <div class="info-box-title" style="color: #F59E0B;">
                17h45 às 18h30 &bull; Platô da 2ª Hora
            </div>
            <div class="info-box-desc">
                <strong>3.670 votos</strong> em fluxo sustentado (50 a 170 votos/min).
                Identifica seções onde a votação foi formalmente estendida.
            </div>
        </div>
        """
        st.html(clean_html(card2))

    with c3:
        card3 = """
        <div class="info-box">
            <div class="info-box-title" style="color: #10B981;">
                Cadência de Cabine &bull; ~38s/voto
            </div>
            <div class="info-box-desc">
                O tempo de digitação manteve-se idêntico ao período regular,
                comprovando fluxo humano normal e ausência de injeção em lote.
            </div>
        </div>
        """
        st.html(clean_html(card3))
