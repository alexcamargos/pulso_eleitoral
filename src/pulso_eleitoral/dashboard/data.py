"""Camada de acesso a dados analíticos e consultas otimizadas no DuckDB.

Fornece funções cacheadas para alimentar os componentes do dashboard
Streamlit, conectando-se diretamente ao banco de dados `data/pulso_eleitoral.duckdb`.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd
import streamlit as st

from pulso_eleitoral.analytics.electoral_impact import (
    calculate_manski_sensitivity_bounds,
    run_parametric_bias_model,
)
from pulso_eleitoral.config import OFFICIAL_2026_TURNO2_MARGIN
from pulso_eleitoral.contracts.models import (
    ParametricRegressionResult,
    SensitivityBoundsResult,
)


@st.cache_resource
def get_duckdb_connection(
    db_path: str = "data/pulso_eleitoral.duckdb",
) -> duckdb.DuckDBPyConnection:
    """Obtém uma conexão somente-leitura persistente com o banco DuckDB.

    Args:
        db_path: Caminho no sistema de arquivos para o banco DuckDB.

    Returns:
        Conexão ativa do DuckDB configurada em modo read-only.

    Raises:
        duckdb.Error: Se o arquivo não existir ou estiver corrompido.
    """
    return duckdb.connect(db_path, read_only=True)


@st.cache_data(ttl=3600)
def get_national_kpis(db_path: str = "data/pulso_eleitoral.duckdb") -> dict[str, Any]:
    """Calcula os indicadores nacionais consolidados do 2º turno de 2026.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Dicionário com os valores dos KPIs nacionais agregados.

    Raises:
        duckdb.Error: Se a consulta falhar.
    """
    con = get_duckdb_connection(db_path)
    q = """
    SELECT
        SUM(total_votos) as total_votos_brasil,
        SUM(votos_ate_17h) as total_ate_17h,
        SUM(votos_apos_17h) as votos_pos_17h,
        COUNT(*) as total_secoes_analisadas,
        COUNT(CASE WHEN votos_apos_17h > 0 THEN 1 END) as secoes_pos_17h,
        COUNT(DISTINCT uf) as total_ufs_ativas,
        MAX(horario_ultimo_voto_brt) as horario_ultimo_voto,
        SUM(CASE WHEN horario_ultimo_voto_brt < '2026-10-25 18:00:00'
                 THEN votos_apos_17h ELSE 0 END) as votos_h1,
        SUM(CASE WHEN horario_ultimo_voto_brt >= '2026-10-25 18:00:00'
                 THEN votos_apos_17h ELSE 0 END) as votos_h2,
        SUM(CASE WHEN horario_ultimo_voto_brt < '2026-10-25 17:15:00'
                 THEN votos_apos_17h ELSE 0 END) as votos_fila,
        SUM(CASE WHEN horario_ultimo_voto_brt >= '2026-10-25 17:45:00'
                 AND horario_ultimo_voto_brt < '2026-10-25 18:30:00'
                 THEN votos_apos_17h ELSE 0 END) as votos_plato
    FROM raw_section_metrics
    """
    row = con.execute(q).fetchone()
    if not row:
        return {}

    (
        total_votos,
        _ate_17h,
        pos_17h,
        total_secoes,
        secoes_pos,
        ufs_ativas,
        ultimo_voto,
        votos_h1,
        votos_h2,
        votos_fila,
        votos_plato,
    ) = row

    total_votos_val = int(total_votos or 0)
    pos_17h_val = int(pos_17h or 0)
    pct_pos = (pos_17h_val / total_votos_val * 100.0) if total_votos_val > 0 else 0.0
    votos_h1_val = int(votos_h1 or 0)
    votos_h2_val = int(votos_h2 or 0)
    votos_fila_val = int(votos_fila or 0)
    votos_plato_val = int(votos_plato or 0)
    pct_h1 = (votos_h1_val / pos_17h_val * 100.0) if pos_17h_val > 0 else 0.0
    pct_h2 = (votos_h2_val / pos_17h_val * 100.0) if pos_17h_val > 0 else 0.0
    pct_fila = (votos_fila_val / pos_17h_val * 100.0) if pos_17h_val > 0 else 0.0
    pct_plato = (votos_plato_val / pos_17h_val * 100.0) if pos_17h_val > 0 else 0.0

    return {
        "total_votos_brasil": total_votos_val,
        "votos_pos_17h": pos_17h_val,
        "pct_pos_17h": pct_pos,
        "total_secoes_analisadas": int(total_secoes or 0),
        "secoes_pos_17h": int(secoes_pos or 0),
        "total_ufs_ativas": int(ufs_ativas or 0),
        "horario_ultimo_voto": (
            ultimo_voto.strftime("%H:%M:%S") if ultimo_voto else "19:06:21"
        ),
        "local_ultimo_voto": "São Paulo / SP",
        "votos_h1": votos_h1_val,
        "pct_h1": pct_h1,
        "votos_h2": votos_h2_val,
        "pct_h2": pct_h2,
        "votos_fila": votos_fila_val,
        "pct_fila": pct_fila,
        "votos_plato": votos_plato_val,
        "pct_plato": pct_plato,
    }


@st.cache_data(ttl=3600)
def get_timeline_data(db_path: str = "data/pulso_eleitoral.duckdb") -> pd.DataFrame:
    """Extrai a série temporal minuto a minuto da vazão de votos pós-17h.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        DataFrame indexado por minuto (17:00 até 19:06) contendo contagem de
        seções, votos acumulados, ritmo e fase do fenômeno.

    Raises:
        duckdb.Error: Se a consulta falhar.
    """
    con = get_duckdb_connection(db_path)
    q = """
    SELECT
        strftime(horario_ultimo_voto_brt, '%H:%M') as minuto,
        COUNT(*) as secoes,
        SUM(votos_apos_17h) as votos,
        SUM(sem_bio_apos_17h) as sem_bio
    FROM raw_section_metrics
    WHERE votos_apos_17h > 0
    GROUP BY strftime(horario_ultimo_voto_brt, '%H:%M')
    ORDER BY minuto
    """
    df = con.execute(q).df()
    if df.empty:
        return df

    df["votos_acumulados"] = df["votos"].cumsum()
    df["pct_acumulado"] = (df["votos_acumulados"] / df["votos"].sum()) * 100.0

    def categorizar_fase(minuto: str) -> str:
        if minuto <= "17:14":
            return "1. Fila Inicial (Absorção Rápida)"
        if minuto <= "17:44":
            return "2. Desaceleração / Transição"
        if minuto <= "18:30":
            return "3. Platô Atípico da Extensão"
        return "4. Esgotamento Final"

    df["fase"] = df["minuto"].apply(categorizar_fase)
    return df


@st.cache_data(ttl=3600)
def get_map_locations(
    db_path: str = "data/pulso_eleitoral.duckdb",
    max_minuto: str | None = None,
) -> pd.DataFrame:
    """Carrega as coordenadas geográficas dos municípios com votos pós-17h.

    Permite filtragem opcional pelo horário máximo de encerramento para
    permitir o controle do scrubber temporal interativo.

    Args:
        db_path: Caminho do banco DuckDB.
        max_minuto: Horário de corte no formato 'HH:MM' (ex: '18:15').

    Returns:
        DataFrame com colunas latitude, longitude, municipio_nome, uf,
        votos_pos, pct_apos_17h e ultimo_voto_str.

    Raises:
        duckdb.Error: Se a consulta falhar.
    """
    con = get_duckdb_connection(db_path)
    filtro_tempo = ""
    if max_minuto:
        filtro_tempo = (
            f"AND strftime(r.horario_ultimo_voto_brt, '%H:%M') <= '{max_minuto}'"
        )

    q = f"""
    SELECT
        m.uf,
        m.municipio_nome,
        SUM(r.votos_apos_17h) as votos_pos,
        ROUND(
            SUM(r.votos_apos_17h) * 100.0 / NULLIF(m.total_votos_municipio, 0),
            3
        ) as pct_apos_17h,
        c.latitude,
        c.longitude,
        strftime(MAX(r.horario_ultimo_voto_brt), '%H:%M:%S') as ultimo_voto_str
    FROM raw_section_metrics r
    JOIN summary_by_municipio m ON r.municipio_ibge = m.municipio_ibge
    JOIN 'resources/municipios_coordenadas.csv' c ON r.municipio_ibge = c.codigo_ibge
    WHERE r.votos_apos_17h > 0 {filtro_tempo}
    GROUP BY m.uf, m.municipio_nome, m.total_votos_municipio, c.latitude, c.longitude
    HAVING SUM(r.votos_apos_17h) > 0
    ORDER BY votos_pos DESC
    """
    return con.execute(q).df()


@st.cache_data(ttl=3600)
def get_rankings_data(
    db_path: str = "data/pulso_eleitoral.duckdb",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Retorna os rankings consolidados por estado, capitais e impacto percentual.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Tupla com três DataFrames: (df_ufs, df_capitais, df_proporcao).

    Raises:
        duckdb.Error: Se as consultas falharem.
    """
    con = get_duckdb_connection(db_path)

    q_ufs = """
    SELECT
        uf,
        SUM(votos_apos_17h) as votos_pos,
        ROUND(SUM(votos_apos_17h) * 100.0 / SUM(total_votos), 4) as pct_pos,
        COUNT(CASE WHEN votos_apos_17h > 0 THEN 1 END) as secoes_pos,
        strftime(MAX(horario_ultimo_voto_brt), '%H:%M:%S') as ultimo_voto
    FROM raw_section_metrics
    GROUP BY uf
    ORDER BY votos_pos DESC
    """
    df_ufs = con.execute(q_ufs).df()

    capitais = (
        "'SAO PAULO', 'RIO DE JANEIRO', 'SALVADOR', 'BRASILIA', 'MANAUS', "
        "'BELO HORIZONTE', 'FORTALEZA', 'RECIFE', 'CURITIBA', 'PORTO ALEGRE', "
        "'GOIANIA', 'BELEM', 'SAO LUIS', 'MACEIO', 'NATAL', 'CAMPO GRANDE', "
        "'TERESINA', 'JOAO PESSOA', 'ARACAJU', 'CUIABA', 'PORTO VELHO', "
        "'FLORIANOPOLIS', 'MACAPA', 'RIO BRANCO', 'VITORIA', 'BOA VISTA', 'PALMAS'"
    )
    q_capitais = f"""
    SELECT
        uf,
        municipio_nome,
        SUM(votos_apos_17h) as votos_pos,
        ROUND(SUM(votos_apos_17h) * 100.0 / SUM(total_votos), 3) as pct_pos,
        strftime(MAX(horario_ultimo_voto_brt), '%H:%M:%S') as ultimo_voto
    FROM raw_section_metrics
    WHERE municipio_nome IN ({capitais})
    GROUP BY uf, municipio_nome
    ORDER BY votos_pos DESC
    LIMIT 10
    """
    df_capitais = con.execute(q_capitais).df()

    q_proporcao = """
    SELECT
        uf,
        municipio_nome,
        SUM(votos_apos_17h) as votos_pos,
        ROUND(SUM(votos_apos_17h) * 100.0 / SUM(total_votos), 2) as pct_pos,
        strftime(MAX(horario_ultimo_voto_brt), '%H:%M:%S') as ultimo_voto
    FROM raw_section_metrics
    GROUP BY uf, municipio_nome
    HAVING SUM(votos_apos_17h) >= 20
    ORDER BY pct_pos DESC
    LIMIT 10
    """
    df_proporcao = con.execute(q_proporcao).df()

    return df_ufs, df_capitais, df_proporcao


@st.cache_data(ttl=3600)
def get_biometrics_data(db_path: str = "data/pulso_eleitoral.duckdb") -> dict[str, Any]:
    """Extrai as proporções de autenticação biométrica pré vs pós-17h.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Dicionário com contagens absolutas e percentuais de identificação
        biométrica e liberação manual pelo mesário.

    Raises:
        duckdb.Error: Se a consulta falhar.
    """
    con = get_duckdb_connection(db_path)
    q = """
    SELECT
        SUM(votos_ate_17h) as votos_ate_17h,
        SUM(sem_bio_ate_17h) as sem_bio_ate_17h,
        SUM(votos_apos_17h) as votos_apos_17h,
        SUM(sem_bio_apos_17h) as sem_bio_apos_17h
    FROM raw_section_metrics
    """
    row = con.execute(q).fetchone()
    if not row:
        return {}

    v_ate_17h, sb_ate_17h, v_pos_17h, sb_pos_17h = row

    v_ate = int(v_ate_17h or 0)
    sb_ate = int(sb_ate_17h or 0)
    cb_ate = v_ate - sb_ate
    pct_sb_ate = (sb_ate / v_ate * 100.0) if v_ate > 0 else 0.0
    pct_cb_ate = 100.0 - pct_sb_ate

    v_pos = int(v_pos_17h or 0)
    sb_pos = int(sb_pos_17h or 0)
    cb_pos = v_pos - sb_pos
    pct_sb_pos = (sb_pos / v_pos * 100.0) if v_pos > 0 else 0.0
    pct_cb_pos = 100.0 - pct_sb_pos

    q_faixas = """
    SELECT
        CASE
            WHEN horario_ultimo_voto_brt < '2026-10-25 17:15:00'
                THEN '17:00-17:14 (Fila)'
            WHEN horario_ultimo_voto_brt < '2026-10-25 18:00:00'
                THEN '17:15-17:59 (Transição)'
            ELSE '18:00-19:06 (Extensão)'
        END as faixa,
        SUM(votos_apos_17h) as total,
        SUM(sem_bio_apos_17h) as sem_bio
    FROM raw_section_metrics
    WHERE votos_apos_17h > 0
    GROUP BY 1
    ORDER BY MIN(horario_ultimo_voto_brt)
    """
    df_faixas = con.execute(q_faixas).df()
    df_faixas["pct_sem_bio"] = (df_faixas["sem_bio"] / df_faixas["total"]) * 100.0
    df_faixas["pct_com_bio"] = 100.0 - df_faixas["pct_sem_bio"]

    return {
        "ate_17h": {
            "total": v_ate,
            "com_bio": cb_ate,
            "sem_bio": sb_ate,
            "pct_com_bio": pct_cb_ate,
            "pct_sem_bio": pct_sb_ate,
        },
        "pos_17h": {
            "total": v_pos,
            "com_bio": cb_pos,
            "sem_bio": sb_pos,
            "pct_com_bio": pct_cb_pos,
            "pct_sem_bio": pct_sb_pos,
        },
        "delta_sem_bio": pct_sb_pos - pct_sb_ate,
        "faixas": df_faixas,
    }


@st.cache_data(ttl=3600)
def get_latest_sections(
    db_path: str = "data/pulso_eleitoral.duckdb",
    uf: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    """Busca as seções eleitorais que encerraram mais tarde na eleição.

    Args:
        db_path: Caminho do banco DuckDB.
        uf: Sigla da UF opcional para filtro.
        search: Termo de busca opcional para nome de município.
        limit: Quantidade máxima de registros retornados.

    Returns:
        DataFrame com colunas formatadas para auditoria cidadã.

    Raises:
        duckdb.Error: Se a consulta falhar.
    """
    con = get_duckdb_connection(db_path)
    filtros = ["votos_apos_17h > 0"]
    if uf and uf != "Todas":
        filtros.append(f"uf = '{uf}'")
    if search:
        search_escaped = search.replace("'", "''").upper()
        filtros.append(f"municipio_nome LIKE '%{search_escaped}%'")

    where_clause = " AND ".join(filtros)
    q = f"""
    SELECT
        uf as UF,
        municipio_nome as "Município",
        zona as Zona,
        secao as "Seção",
        votos_apos_17h as "Votos Pós-17h",
        sem_bio_apos_17h as "Sem Biometria",
        total_votos as "Total Votos Urna",
        strftime(horario_ultimo_voto_brt, '%H:%M:%S') as "Último Voto (BRT)",
        relogio_suspeito as "Alerta RTC"
    FROM raw_section_metrics
    WHERE {where_clause}
    ORDER BY horario_ultimo_voto_brt DESC
    LIMIT {limit}
    """
    return con.execute(q).df()


@st.cache_data(ttl=3600)
def get_electoral_impact_data(
    margin: int = OFFICIAL_2026_TURNO2_MARGIN,
    db_path: str = "data/pulso_eleitoral.duckdb",
) -> tuple[SensitivityBoundsResult, ParametricRegressionResult]:
    """Obtém as métricas do teste paramétrico e bounds de Manski para o dashboard.

    Args:
        margin: Margem absoluta oficial de vitória no pleito.
        db_path: Caminho do banco DuckDB.

    Returns:
        Tupla com `(SensitivityBoundsResult, ParametricRegressionResult)`.

    Raises:
        duckdb.Error: Se a consulta ao banco falhar.
    """
    con = get_duckdb_connection(db_path)
    bounds = calculate_manski_sensitivity_bounds(con, margin=margin)
    param = run_parametric_bias_model(con)
    return bounds, param
