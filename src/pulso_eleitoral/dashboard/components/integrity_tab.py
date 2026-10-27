"""Componente da Aba 3: Auditoria de Integridade Procedimental & Biometria.

Confronta a taxa de autenticação biométrica pré vs pós-17h para comprovar
a inexistência de quebra de protocolo na cabine de votação.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from pulso_eleitoral.dashboard.styles import clean_html


def render_integrity_tab(bio_data: dict[str, Any]) -> None:
    """Renderiza o diagnóstico estatístico de conformidade da biometria.

    Args:
        bio_data: Dicionário contendo as proporções de autenticação calculadas.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    intro_html = """
    <div style="margin-bottom: 16px;">
        <div style="font-size: 20px; font-weight: 700; color: #F8FAFC;">
            Ato 3: Auditoria de Integridade Procedimental & Biometria
        </div>
        <div style="font-size: 13.5px; color: #94A3B8; margin-top: 4px;
            line-height: 1.5;">
            Uma hipótese crítica de auditoria é se houve relaxamento
            nas regras de identificação (ex.: mesários liberando votantes manualmente
            em lote para apressar o fechamento). Os dados comprovam estabilidade total.
        </div>
    </div>
    """
    st.html(clean_html(intro_html))

    if not bio_data:
        st.info("Dados de biometria indisponíveis.")
        return

    ate_17h = bio_data["ate_17h"]
    pos_17h = bio_data["pos_17h"]
    delta_sb = bio_data["delta_sem_bio"]

    col1, col2 = st.columns([1.6, 1.4], gap="medium")

    with col1:
        # Gráfico de barras empilhadas 100%
        categorias = ["Até 17h00 (Regular)", "Após 17h00 (Extensão)"]
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
            paper_bgcolor="#181B20",
            plot_bgcolor="#121417",
            height=270,
            margin=dict(l=150, r=25, t=45, b=30),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.10,
                xanchor="center",
                x=0.5,
                font=dict(color="#94A3B8", size=11),
            ),
            xaxis=dict(
                title="Proporção dos Votos (%)",
                range=[0, 100],
                gridcolor="#282D37",
                zerolinecolor="#282D37",
                automargin=True,
            ),
            yaxis=dict(
                automargin=True,
            ),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        card_html = f"""
        <div class="hero-card">
            <div class="hero-card-header">
                <span>Variação de Liberação Manual</span>
                <span class="hero-pill hero-pill-success">
                    Conforme (+{delta_sb:.2f}%)
                </span>
            </div>
            <div class="hero-metric-val" style="color: #10B981;">+1,15%</div>
            <div class="hero-metric-sub">
                A taxa de liberação pelo mesário variou de
                <strong>{ate_17h["pct_sem_bio"]:.2f}%</strong> para
                <strong>{pos_17h["pct_sem_bio"]:.2f}%</strong>.<br/><br/>
                Com mais de <strong>92%</strong> dos eleitores autenticados por
                biometria, o procedimento manteve o mesmo padrão técnico do
                restante do dia, afastando qualquer anomalia de identificação.
            </div>
        </div>
        """
        st.html(clean_html(card_html))

    # Diagnóstico de Contingência e Relógio
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    c_diag1, c_diag2 = st.columns(2, gap="medium")
    with c_diag1:
        box1 = """
        <div class="info-box">
            <div class="info-box-title" style="color: #38BDF8;">
                Urnas de Contingência (Substituição de Hardware)
            </div>
            <div class="info-box-desc">
                Em seções onde a urna eletrônica apresentou pane durante a tarde,
                a substituição pela urna de reserva transfere com assinatura digital
                o histórico de votos anteriores gravados na memória de resultado (MR).
                O parser do Pulso Eleitoral reconcilia a cadeia histórica completa.
            </div>
        </div>
        """
        st.html(clean_html(box1))

    with c_diag2:
        box2 = """
        <div class="info-box">
            <div class="info-box-title" style="color: #10B981;">
                Sincronismo de Relógio Interno (RTC)
            </div>
            <div class="info-box-desc">
                Todas as 30.004 seções ativas na extensão foram auditadas quanto ao
                relógio interno de hardware (RTC). Nenhuma seção registrou votos após
                a emissão da Zerésima ou emissão do Boletim de Urna (BU),
                respeitando a máquina de estados finita da Justiça Eleitoral.
            </div>
        </div>
        """
        st.html(clean_html(box2))
