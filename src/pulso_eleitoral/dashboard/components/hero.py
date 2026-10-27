"""Componente da Seção Hero e Indicadores Monumentais (Ato 1).

Apresenta a manchete de impacto inspirada em data journalism e os 4
indicadores-chave da extensão atípica do 2º turno de 2026.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_hero(kpis: dict[str, Any]) -> None:
    """Renderiza a manchete principal e os 4 cartões de KPI monumentais.

    Args:
        kpis: Dicionário contendo os indicadores agregados do 2º turno.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    total_pos = kpis.get("votos_pos_17h", 35972)
    pct_pos = kpis.get("pct_pos_17h", 0.028)
    ultimo_voto = kpis.get("horario_ultimo_voto", "19:06:21")
    local_ultimo = kpis.get("local_ultimo_voto", "São Paulo / SP")
    votos_h1 = kpis.get("votos_h1", 32927)
    pct_h1 = kpis.get("pct_h1", 91.5)
    ufs_ativas = kpis.get("total_ufs_ativas", 27)

    # Formatação com separador de milhar brasileiro
    total_pos_fmt = f"{total_pos:,}".replace(",", ".")
    votos_h1_fmt = f"{votos_h1:,}".replace(",", ".")

    html = f"""
    <div>
        <div class="hero-badge">
            <span>●</span> ELEIÇÕES 2026 • 2º TURNO • AUDITORIA DE URNAS
        </div>
        <h1 class="hero-title">
            <span class="hero-highlight">{total_pos_fmt}</span> votos depois das 17h
        </h1>
        <p class="hero-subtext">
            A votação encerra oficialmente às 17h de Brasília, mas quem já estava
            na fila tem direito legal de votar. No 2º turno de 2026, com o caso
            atípico de extensão e lentidão em seções pontuais, cerca de 36 mil eleitores
            continuaram votando até as 19h06. Veja a física da curva de vazão minuto a
            minuto e onde cada voto ocorreu no país.
        </p>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-value">{votos_h1_fmt}</div>
                <div class="kpi-label">Votaram na 1ª Hora (17h-18h)</div>
                <div class="kpi-sub">{pct_h1:.1f}% absorvidos na fila inicial</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{pct_pos:.3f}%</div>
                <div class="kpi-label">Fatia do Total Nacional</div>
                <div class="kpi-sub">de 127,6 milhões de votos auditados</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{ultimo_voto}</div>
                <div class="kpi-label">Último Voto no Brasil</div>
                <div class="kpi-sub">{local_ultimo}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-value">{ufs_ativas} / 27</div>
                <div class="kpi-label">Estados com Votos Pós-17h</div>
                <div class="kpi-sub">presente em todas as 27 UFs</div>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
