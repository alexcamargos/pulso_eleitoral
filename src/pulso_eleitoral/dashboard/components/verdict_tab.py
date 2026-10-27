"""Componente da Aba 4: Veredito Científico & Explorador de Seções.

Apresenta o teste de estresse de impacto no resultado eleitoral e a tabela
interativa de busca para auditoria pública de seções eleitorais.
"""

from __future__ import annotations

import streamlit as st

from pulso_eleitoral.dashboard.data import get_latest_sections
from pulso_eleitoral.dashboard.styles import clean_html


def render_verdict_tab(db_path: str = "data/pulso_eleitoral.duckdb") -> None:
    """Renderiza o veredito científico conclusivo e o explorador de seções.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    intro_html = """
    <div style="margin-bottom: 16px;">
        <div style="font-size: 20px; font-weight: 700; color: #F8FAFC;">
            Ato 4: Veredito Científico & Explorador de Seções
        </div>
        <div style="font-size: 13.5px; color: #94A3B8; margin-top: 4px;
            line-height: 1.5;">
            A pergunta definitiva de qualquer auditoria independente é:
            <strong>os votos computados na extensão poderiam alterar o resultado
            da eleição?</strong>
            Confrontamos a física dos dados com a margem matemática do pleito.
        </div>
    </div>
    """
    st.html(clean_html(intro_html))

    # Teste de Estresse Eleitoral (Confronto da Margem)
    c_ver1, c_ver2 = st.columns([1.2, 0.8], gap="medium")

    with c_ver1:
        st.markdown("#### Teste de Sensibilidade de Resultado")
        st.markdown(
            "Mesmo no cenário teórico mais extremo e estatisticamente implausível "
            "(onde **100% dos 35.972 votos** da janela tivessem sido "
            "atribuídos a um único concorrente), o impacto máximo sobre o total "
            "de 127,6 milhões de votos auditados seria de apenas:"
        )
        st.latex(r"\text{Impacto Máximo} = \frac{35.972}{127.635.809} = 0{,}0282\%")
        st.markdown(
            "Em eleições presidenciais brasileiras de segundo turno, a menor "
            "diferença de votos já registrada na história moderna foi superior "
            "a **2,1 milhões de votos** (2014 e 2022). Portanto, o volume da "
            "janela atípica equivale a **menos de 1,7%** da menor margem "
            "histórica de vitória."
        )

    with c_ver2:
        card_veredito = """
        <div class="hero-card" style="border-color: #10B981; background: #131B17;">
            <div class="hero-card-header">
                <span style="color: #10B981;">Conclusão da Auditoria</span>
                <span class="hero-pill hero-pill-success">Aprovado</span>
            </div>
            <div class="hero-metric-val" style="color: #10B981; font-size: 26px;">
                Sem Risco de Inversão
            </div>
            <div class="hero-metric-sub" style="color: #CBD5E1; margin-top: 8px;
                line-height: 1.5;">
                O atraso operacional verificado no 2º turno de 2026 configurou uma
                <strong>anomalia de vazão logística</strong>, mas foi
                <strong>matematicamente incapaz</strong> de afetar a legitimidade
                ou inverter o resultado da eleição presidencial.
            </div>
        </div>
        """
        st.html(clean_html(card_veredito))

    st.markdown("<hr class='custom-divider'/>", unsafe_allow_html=True)

    # Explorador Interativo de Seções
    st.markdown("#### Explorador de Seções Eleitorais Auditáveis")
    st.markdown(
        """
        <div style="font-size: 13px; color: #94A3B8; margin-bottom: 12px;">
            Inspecione as seções que encerraram suas atividades mais tarde no país.
            Filtre por estado ou busque por município para auditar a zona e seção.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_filtro1, col_filtro2 = st.columns([1, 3])
    with col_filtro1:
        ufs = [
            "Todas",
            "SP",
            "RJ",
            "BA",
            "MG",
            "PE",
            "CE",
            "AM",
            "PA",
            "PR",
            "RS",
            "SC",
            "DF",
            "GO",
            "MA",
            "ES",
            "PB",
            "RN",
            "PI",
            "AL",
            "MT",
            "MS",
            "SE",
            "RO",
            "TO",
            "AC",
            "AP",
            "RR",
        ]
        sel_uf = st.selectbox("Filtrar por UF:", options=ufs, index=0)

    with col_filtro2:
        busca = st.text_input(
            "Pesquisar Município:",
            placeholder="Ex: São Paulo, Lábrea, Salvador...",
        )

    df_secoes = get_latest_sections(
        db_path,
        uf=sel_uf if sel_uf != "Todas" else None,
        search=busca if busca else None,
        limit=50,
    )

    if not df_secoes.empty:
        st.dataframe(
            df_secoes,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma seção encontrada com os filtros informados.")

    # Notas Metodológicas Finais
    st.markdown("<hr class='custom-divider'/>", unsafe_allow_html=True)
    st.markdown("#### Notas Metodológicas e Cadeia de Custódia")

    m1, m2 = st.columns(2, gap="medium")
    with m1:
        box_m1 = """
        <div class="info-box">
            <div class="info-box-title" style="color: #38BDF8;">
                Extração Linha a Linha (logd.dat)
            </div>
            <div class="info-box-desc">
                Os logs foram descompactados a partir dos pacotes oficiais
                <code>.logjez</code> (LZMA). Apenas os eventos de habilitação e
                confirmação de voto (linhas <code>VOTA</code>) foram processados
                para reconstruir o carimbo cronológico de cada eleitor, sem violar
                o sigilo constitucional do voto.
            </div>
        </div>
        """
        st.html(clean_html(box_m1))

    with m2:
        box_m2 = """
        <div class="info-box">
            <div class="info-box-title" style="color: #10B981;">
                Reconciliação com o Boletim de Urna (ASN.1)
            </div>
            <div class="info-box-desc">
                O somatório dos eventos de log foi confrontado com o total de
                votos registrados no Boletim de Urna (BU) assinado digitalmente
                com certificado da autoridade certificadora da Justiça Eleitoral.
                100% das seções demonstraram convergência estrita entre BU e logs.
            </div>
        </div>
        """
        st.html(clean_html(box_m2))
