"""Componente do Explorador de Seções e Cartões Metodológicos (Ato 6).

Permite a auditoria direta das seções eleitorais que registraram votos tardios
e explica o rigor técnico da decodificação dos logs da urna eletrônica.
"""

from __future__ import annotations

import streamlit as st

from pulso_eleitoral.dashboard.data import get_latest_sections


def render_explorer(db_path: str = "data/pulso_eleitoral.duckdb") -> None:
    """Renderiza a tabela de seções auditáveis e os 4 cartões de metodologia.

    Args:
        db_path: Caminho do banco de dados DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    st.html(
        """
        <div class="section-tag">Auditoria Direta</div>
        <h2 class="section-title">Explorador de seções eleitorais</h2>
        <p class="section-desc">
            Inspecione as seções com encerramento tardio no país.
            Filtre por estado ou pesquise o município para auditar a zona e seção.
        </p>
        """
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
            placeholder="Ex: São Paulo, Campinas, Salvador...",
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

    st.html("<hr class='custom-divider'/>")

    st.html(
        """
        <div class="section-tag">Transparência Radical</div>
        <h2 class="section-title">Contamos linha por linha: como calculamos</h2>
        <p class="section-desc">
            O pipeline Pulso Eleitoral decodifica diretamente os artefatos binários
            oficiais disponibilizados pelo Tribunal Superior Eleitoral (TSE).
        </p>
        """
    )

    m1, m2 = st.columns(2)
    with m1:
        st.html(
            """
            <div class="method-card">
                <span class="method-tag">1. O Log da Urna (logd.dat)</span>
                <div class="method-title">Eventos VOTA Decodificados</div>
                <p class="method-text">
                    Cada linha do arquivo <code>logd.dat</code> descompactado em
                    memória (7z/LZMA) registra eventos operacionais da urna. Extraímos
                    unicamente as transições de habilitação e emissão do voto com
                    carimbo temporal auditável UTC/BRT.
                </p>
            </div>
            <div style="height: 12px;"></div>
            <div class="method-card">
                <span class="method-tag">2. Urnas Substituídas</span>
                <div class="method-title">Cadeia Histórica Preservada</div>
                <p class="method-text">
                    Quando uma urna sofre falha técnica de hardware e é substituída
                    por contingência, a memória de resultado transfere os votos.
                    Nosso parser analisa todos os logs da seção para consolidar uma
                    única linha temporal contínua e sem duplicações.
                </p>
            </div>
            """
        )

    with m2:
        st.html(
            """
            <div class="method-card">
                <span class="method-tag">3. Reconciliação com o BU</span>
                <div class="method-title">Confronto Boletim de Urna (ASN.1)</div>
                <p class="method-text">
                    O total de votos computados a partir dos logs de votação é
                    reconciliado com o comparecimento gravado no Boletim de Urna
                    assinado digitalmente pelo TSE. Se houver divergência, a seção
                    recebe um alerta imediato.
                </p>
            </div>
            <div style="height: 12px;"></div>
            <div class="method-card">
                <span class="method-tag">4. Fuso Horário Normalizado</span>
                <div class="method-title">Hora de Brasília (BRT / UTC-3)</div>
                <p class="method-text">
                    O TSE unificou o encerramento da votação em todo o país às 17h BRT.
                    Municípios do Acre e do Amazonas (UTC-5) encerram suas atividades
                    às 15h locais, sendo rigorosamente convertidos para a mesma escala
                    de tempo nacional.
                </p>
            </div>
            """
        )
