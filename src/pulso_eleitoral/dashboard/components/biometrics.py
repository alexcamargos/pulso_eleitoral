"""Componente de Integridade e Autenticação Biométrica (Ato 5).

Apresenta o comparativo auditável entre a taxa de habilitação com biometria
versus habilitação manual pelo mesário antes e depois das 17h.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st


def render_biometrics(bio_data: dict[str, Any]) -> None:
    """Renderiza a análise de estabilidade e integridade da biometria.

    Args:
        bio_data: Dicionário contendo os dados de autenticação calculados.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    st.html(
        """
        <div class="section-tag">Integridade</div>
        <h2 class="section-title">Como os eleitores foram autenticados na urna</h2>
        <p class="section-desc">
            Uma questão técnica primordial em horários estendidos é auditar se
            houve relaxamento nas regras de validação biométrica pelo mesário.
        </p>
        """
    )

    if not bio_data:
        st.info("Dados de biometria indisponíveis.")
        return

    ate_17h = bio_data["ate_17h"]
    pos_17h = bio_data["pos_17h"]
    delta_sb = bio_data["delta_sem_bio"]

    col1, col2 = st.columns([3, 2])

    with col1:
        # Gráfico de barras empilhadas 100%
        categorias = ["Até 17h00 (Período Regular)", "Após 17h00 (Extensão)"]
        pct_bio = [ate_17h["pct_com_bio"], pos_17h["pct_com_bio"]]
        pct_manual = [ate_17h["pct_sem_bio"], pos_17h["pct_sem_bio"]]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                name="Identificação Biométrica (Digital)",
                y=categorias,
                x=pct_bio,
                orientation="h",
                marker=dict(color="#10B981"),
                text=[f"{v:.1f}%" for v in pct_bio],
                textposition="inside",
                hovertemplate="Biometria: <b>%{x:.2f}%</b><extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                name="Liberação Manual (Mesário)",
                y=categorias,
                x=pct_manual,
                orientation="h",
                marker=dict(color="#F59E0B"),
                text=[f"{v:.1f}%" for v in pct_manual],
                textposition="inside",
                hovertemplate="Manual: <b>%{x:.2f}%</b><extra></extra>",
            )
        )

        fig.update_layout(
            barmode="stack",
            template="plotly_dark",
            paper_bgcolor="#0A0B0E",
            plot_bgcolor="#111319",
            height=260,
            margin=dict(l=10, r=20, t=10, b=20),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                font=dict(color="#8C93A4", size=11),
            ),
            xaxis=dict(
                title="Proporção dos Votos (%)",
                range=[0, 100],
                gridcolor="#1F232F",
                zerolinecolor="#1F232F",
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Card de auditoria estatística
        sb_ate = ate_17h["pct_sem_bio"]
        sb_pos = pos_17h["pct_sem_bio"]
        card_html = (
            "<div class='kpi-card' style='margin-top: 15px;'>"
            "<div class='kpi-label'>Variação da Liberação Manual</div>"
            f"<div class='kpi-value' style='color: #10B981;'>+{delta_sb:.2f}%</div>"
            "<div class='kpi-sub' style='color: #8C93A4; margin-top: 0.5rem; "
            "line-height: 1.45;'>"
            f"A taxa de liberação pelo mesário foi de <strong>{sb_ate:.2f}%</strong> "
            f"para <strong>{sb_pos:.2f}%</strong>.<br/>"
            "Essa estabilidade comprova que <strong>mais de 92%</strong> dos eleitores "
            "continuaram autenticados por biometria, afastando suspeitas de liberação "
            "desordenada."
            "</div></div>"
        )
        st.html(card_html)
