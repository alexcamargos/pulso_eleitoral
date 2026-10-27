"""Componente de Rankings Regionais (Ato 4).

Compara os maiores polos de volume absoluto (Capitais) com os municípios
de maior impacto relativo no eleitorado local (Sudoeste do Amazonas).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_rankings(
    df_capitais: pd.DataFrame,
    df_proporcao: pd.DataFrame,
) -> None:
    """Renderiza os gráficos comparativos de rankings regionais.

    Args:
        df_capitais: DataFrame das capitais com maior volume absoluto.
        df_proporcao: DataFrame dos municípios com maior peso percentual.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    st.html(
        """
        <div class="section-tag">Estados e Municípios</div>
        <h2 class="section-title">Onde mais pessoas votaram depois das 17h</h2>
        <p class="section-desc">
            O fenômeno dividiu-se entre dois perfis: <strong>grandes metrópoles</strong>
            concentrando volume e <strong>municípios ribeirinhos</strong>
            (Amazonas e Acre) onde fuso horário e logística local resultaram em maior
            proporção relativa no comparecimento final.
        </p>
        """
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 10 Capitais por Volume Absoluto")
        if df_capitais.empty:
            st.info("Sem dados de capitais.")
        else:
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
                        color="#FF5500",
                        line=dict(color="#FF7A29", width=1),
                    ),
                    text=[f"{v:,.0f}" for v in df_cap["votos_pos"]],
                    textposition="outside",
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        + "Votos pós-17h: <b>%{x:,.0f}</b><br>"
                        + "<extra></extra>"
                    ),
                )
            )
            fig_cap.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0A0B0E",
                plot_bgcolor="#111319",
                height=380,
                margin=dict(l=10, r=40, t=10, b=20),
                xaxis=dict(
                    title="Votos Pós-17h",
                    gridcolor="#1F232F",
                    zerolinecolor="#1F232F",
                ),
            )
            st.plotly_chart(fig_cap, use_container_width=True)

    with col2:
        st.subheader("Top 10 Municípios por Impacto no Total Local")
        if df_proporcao.empty:
            st.info("Sem dados de proporção.")
        else:
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
                        color="#00E5FF",
                        line=dict(color="#38BDF8", width=1),
                    ),
                    text=[f"{p:.2f}%" for p in df_prop["pct_pos"]],
                    textposition="outside",
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        + "Fatia dos votos locais: <b>%{x:.2f}%</b><br>"
                        + "<extra></extra>"
                    ),
                )
            )
            fig_prop.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0A0B0E",
                plot_bgcolor="#111319",
                height=380,
                margin=dict(l=10, r=40, t=10, b=20),
                xaxis=dict(
                    title="% dos Votos do Município",
                    gridcolor="#1F232F",
                    zerolinecolor="#1F232F",
                ),
            )
            st.plotly_chart(fig_prop, use_container_width=True)
