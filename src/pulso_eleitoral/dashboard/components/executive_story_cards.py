"""Componente visual de Storytelling Executivo (Hero Executive Story Cards).

Renderiza a síntese executiva no topo da aplicação:
1. Breadcrumbs de auditoria oficial TSE.
2. Título principal analítico e subtítulo contextual.
3. Banner de contexto oficial do comparecimento do 2º turno de 2026.
4. Três Hero Executive Story Cards com tipografia monumental e síntese do veredito.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from pulso_eleitoral.dashboard.styles import clean_html


def render_executive_story_cards(kpis: dict[str, Any]) -> None:
    """Renderiza a Hero Section Executiva com breadcrumbs, banner e 3 cards de síntese.

    Args:
        kpis: Dicionário contendo os indicadores agregados do 2º turno de 2026.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    total_brasil = kpis.get("total_votos_brasil", 127635809)
    total_pos = kpis.get("votos_pos_17h", 35972)
    ultimo_voto = kpis.get("horario_ultimo_voto", "19:06:21")
    local_ultimo = kpis.get("local_ultimo_voto", "São Paulo / SP")
    votos_h2 = kpis.get("votos_h2", 3045)
    pct_h2 = kpis.get("pct_h2", 8.5)
    pct_fila = kpis.get("pct_fila", 82.7)
    votos_fila = kpis.get("votos_fila", 29738)
    secoes_pos = kpis.get("secoes_pos_17h", 30004)
    total_secoes = kpis.get("total_secoes_analisadas", 497640)

    total_brasil_fmt = f"{total_brasil:,}".replace(",", ".")
    total_pos_fmt = f"{total_pos:,}".replace(",", ".")
    votos_fila_fmt = f"{votos_fila:,}".replace(",", ".")
    votos_h2_fmt = f"{votos_h2:,}".replace(",", ".")
    secoes_pos_fmt = f"{secoes_pos:,}".replace(",", ".")
    total_secoes_fmt = f"{total_secoes:,}".replace(",", ".")

    # 1. Breadcrumbs e Cabeçalho Principal
    header_html = """
    <div style="margin-bottom: 8px;">
        <div class="breadcrumb-text">
            Auditoria Eleitoral TSE &bull; Eleições 2026 &bull; 2º Turno Presidencial
        </div>
        <div class="main-header-title">
            Pulso Eleitoral: Auditoria da Janela de Extensão de Votação (17h-19h06)
        </div>
        <div class="main-header-subtitle">
            Análise da física de vazão dos votos computados após o horário oficial
            de encerramento, diagnóstico de integridade biométrica e teste de estresse.
        </div>
    </div>
    """
    st.html(clean_html(header_html))

    # 2. Banner de Contexto da Totalização Oficial
    banner_html = f"""
    <div class="tse-summary-card">
        <div class="tse-summary-title">
            <span>🗳️</span> Painel Consolidado de Totalização Oficial (TSE)
        </div>
        <div class="tse-summary-stats">
            <strong>{total_secoes_fmt}</strong> seções auditadas no Brasil &bull;
            <strong>{total_brasil_fmt}</strong> votos computados &bull;
            Horários normalizados para
            <strong>Horário de Brasília (BRT / UTC-3)</strong>.
            Apenas <strong>{secoes_pos_fmt}</strong> seções (6,03%) registraram
            votos após as 17h00.
        </div>
    </div>
    """
    st.html(clean_html(banner_html))

    # 3. Grade dos 3 Hero Executive Story Cards
    c1, c2, c3 = st.columns(3, gap="medium")

    with c1:
        card1_html = f"""
        <div class="hero-card">
            <div class="hero-card-header">
                <span>Volume da Extensão</span>
                <span class="hero-pill hero-pill-info">0,028% do Brasil</span>
            </div>
            <div class="hero-metric-val">{total_pos_fmt}</div>
            <div class="hero-metric-sub">
                votos registrados na janela de 2h06.<br/>
                <strong>{votos_fila_fmt} ({pct_fila:.1f}%)</strong> foram absorvidos
                nos primeiros 15 minutos (esvaziamento da fila com senha legal).
            </div>
        </div>
        """
        st.html(clean_html(card1_html))

    with c2:
        card2_html = f"""
        <div class="hero-card">
            <div class="hero-card-header">
                <span>A Física da 2ª Hora</span>
                <span class="hero-pill hero-pill-warning">Platô Anômalo</span>
            </div>
            <div class="hero-metric-val">{votos_h2_fmt}</div>
            <div class="hero-metric-sub">
                votos computados entre 18h e 19h06 ({pct_h2:.1f}% da janela).<br/>
                Pico de <strong>170 votos/minuto</strong> às 18h00.
                Última urna encerrou às <strong>{ultimo_voto}</strong>
                em {local_ultimo}.
            </div>
        </div>
        """
        st.html(clean_html(card2_html))

    with c3:
        card3_html = """
        <div class="hero-card">
            <div class="hero-card-header">
                <span>Veredito de Integridade</span>
                <span class="hero-pill hero-pill-success">Impacto Nulo</span>
            </div>
            <div class="hero-metric-val" style="color: #10B981;">92,2%</div>
            <div class="hero-metric-sub">
                de validação biométrica mantida pós-17h (+1,15% manual).<br/>
                Volume total equivale a <strong>menos de 1,7%</strong> da menor margem
                presidencial histórica. <strong>Risco de inversão: zero</strong>.
            </div>
        </div>
        """
        st.html(clean_html(card3_html))
