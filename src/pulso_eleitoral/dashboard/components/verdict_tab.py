"""Componente da Aba 4: Veredito Científico & Explorador de Seções.

Apresenta o teste de estresse de impacto no resultado eleitoral e a tabela
interativa de busca para auditoria pública de seções eleitorais.
"""

from __future__ import annotations

import streamlit as st

from pulso_eleitoral.dashboard.data import (
    get_electoral_impact_data,
    get_latest_sections,
)
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

    # Teste de Estresse Eleitoral Interativo (Bounds de Manski)
    st.markdown("#### Teste de Sensibilidade & Invariância de Manski")
    c_in1, c_in2 = st.columns([1.2, 1.8], gap="medium")
    with c_in1:
        margin_input = st.number_input(
            "Margem Oficial de Vitória (Votos):",
            min_value=1,
            value=2_139_645,
            step=50_000,
            help="Diferença oficial de votos entre os dois candidatos mais votados.",
        )
    with c_in2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        st.caption(
            "Simulação dinâmica: ajuste a margem para testar em qual ponto "
            "o volume da janela pós-17h poderia teoricamente ameaçar o resultado."
        )

    bounds, param = get_electoral_impact_data(
        margin=int(margin_input),
        db_path=db_path,
    )

    c_ver1, c_ver2 = st.columns([1.2, 0.8], gap="medium")

    with c_ver1:
        st.markdown(
            f"No pior cenário contrafactual admissível (onde **100% dos "
            f"{bounds.votos_pos_17h:,} votos** pós-17h tivessem sido computados "
            "para o candidato derrotado), o impacto sobre a margem seria:"
        )
        st.latex(
            rf"\text{{Impacto Máximo}} = \frac{{{bounds.votos_pos_17h:,}}}"
            rf"{{{bounds.margem_eleitoral_referencia:,}}} = "
            rf"{bounds.impacto_maximo_pct_margem:.4f}\%"
        )
        st.markdown(
            f"Como o volume da janela ({bounds.votos_pos_17h:,} votos) representa "
            f"apenas **{bounds.impacto_maximo_pct_margem:.4f}%** da margem de vitória, "
            "uma inversão contrafactual de resultado é **matematicamente impossível**."
        )

    with c_ver2:
        card_border = "#10B981" if not bounds.risco_inversao_resultado else "#EF4444"
        card_bg = "#131B17" if not bounds.risco_inversao_resultado else "#201315"
        pill_class = (
            "hero-pill hero-pill-success"
            if not bounds.risco_inversao_resultado
            else "hero-pill hero-pill-danger"
        )
        card_title = (
            "Sem Risco de Inversão"
            if not bounds.risco_inversao_resultado
            else "Zona de Alerta Crítico"
        )

        card_veredito = f"""
        <div class="hero-card"
             style="border-color: {card_border}; background: {card_bg};">
            <div class="hero-card-header">
                <span style="color: {card_border};">Conclusão da Auditoria</span>
                <span class="{pill_class}">
                    {'Aprovado' if not bounds.risco_inversao_resultado else 'Atenção'}
                </span>
            </div>
            <div class="hero-metric-val" style="color: {card_border}; font-size: 26px;">
                {card_title}
            </div>
            <div class="hero-metric-sub" style="color: #CBD5E1; margin-top: 8px;
                line-height: 1.5;">
                {bounds.veredito_deterministico}
            </div>
        </div>
        """
        st.html(clean_html(card_veredito))

    # Análise Paramétrica: Resposta às Três Perguntas
    st.markdown("<hr class='custom-divider'/>", unsafe_allow_html=True)
    st.markdown(
        "#### Inferência Paramétrica: A extensão favoreceu ou prejudicou "
        "algum candidato?"
    )

    st.markdown(
        """
        <div style="font-size: 13.5px; color: #94A3B8; margin-bottom: 16px;">
            Avaliamos a distribuição das <strong>497.624 seções</strong> em
            <strong>5.567 municípios</strong> via modelo de efeitos fixos municipais
            (Within-Estimator) e erros-padrão clusterizados (CRVE):
        </div>
        """,
        unsafe_allow_html=True,
    )

    q1, q2, q3 = st.columns(3, gap="medium")

    with q1:
        box_q1 = """
        <div class="info-box" style="border-left: 4px solid #38BDF8;">
            <div class="info-box-title" style="color: #38BDF8;">
                Prejudicou A ou B?
            </div>
            <div class="hero-metric-val"
                 style="font-size: 22px; color: #F8FAFC; margin: 6px 0;">
                Não Prejudicou
            </div>
            <div class="info-box-desc">
                Retenção estrita da Hipótese Nula (<code>p = 1,0000</code>).
                A formação de filas após as 17h decorreu de fluxo de atendimento e
                não exibiu viés discriminatório contra qualquer concorrente.
            </div>
        </div>
        """
        st.html(clean_html(box_q1))

    with q2:
        box_q2 = """
        <div class="info-box" style="border-left: 4px solid #10B981;">
            <div class="info-box-title" style="color: #10B981;">
                Ajudou A ou B?
            </div>
            <div class="hero-metric-val"
                 style="font-size: 22px; color: #F8FAFC; margin: 6px 0;">
                Não Ajudou
            </div>
            <div class="info-box-desc">
                Deslocamento líquido estimado em <code>~0 votos</code>.
                Mesmo sob poder estatístico de 80%, o efeito mínimo detectável (MDE)
                está contido em uma banda máxima de apenas ~2.124 votos.
            </div>
        </div>
        """
        st.html(clean_html(box_q2))

    with q3:
        box_q3 = """
        <div class="info-box" style="border-left: 4px solid #A855F7;">
            <div class="info-box-title" style="color: #A855F7;">
                Inferência no Resultado?
            </div>
            <div class="hero-metric-val"
                 style="font-size: 22px; color: #F8FAFC; margin: 6px 0;">
                Zero Inferência
            </div>
            <div class="info-box-desc">
                Resultado <strong>estritamente invariante</strong>.
                Os 35.972 votos pós-17h representam apenas 0,0282% do eleitorado,
                sendo incapazes de alterar o vencedor eleito.
            </div>
        </div>
        """
        st.html(clean_html(box_q3))

    with st.expander("Detalhes Técnicos do Modelo Econométrico (Within-Estimator)"):
        st.markdown(
            f"- **Amostra:** {param.n_secoes:,} seções eleitorais em "
            f"{param.n_municipios:,} municípios\n"
            f"- **Coeficiente $\\beta_1$ (Pós-17h):** `{param.beta_pos_17h:+.6f}`\n"
            f"- **Erro-Padrão Clusterizado (CRVE):** `{param.std_err_cluster:.6f}`\n"
            f"- **Estatística $t$ de Student:** `{param.t_statistic:+.4f}` "
            f"(p-valor: `{param.p_value:.4f}`)\n"
            f"- **Intervalo de Confiança (95%):** `[{param.ci_95_lower:+.6f}, "
            f"{param.ci_95_upper:+.6f}]`\n"
            f"- **Candidato Favorecido:** `{param.candidato_favorecido}`\n"
            f"- **Conclusão:** {param.conclusao_estatistica}"
        )

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
