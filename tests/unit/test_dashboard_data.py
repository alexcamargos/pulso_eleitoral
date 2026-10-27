"""Testes unitários para a camada de dados do dashboard Streamlit.

Valida as funções de consulta e agregação analítica do banco DuckDB.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pulso_eleitoral.cli import app
from pulso_eleitoral.dashboard.data import (
    get_biometrics_data,
    get_latest_sections,
    get_map_locations,
    get_national_kpis,
    get_rankings_data,
    get_timeline_data,
)

runner = CliRunner()


@pytest.fixture
def db_path() -> str:
    """Retorna o caminho do banco DuckDB consolidado para testes.

    Args:
        Nenhum.

    Returns:
        String com o caminho do banco.

    Raises:
        Nenhum.
    """
    path = "data/pulso_eleitoral.duckdb"
    if not Path(path).exists():
        pytest.skip(f"Banco analítico {path} não encontrado no workspace.")
    return path


def test_national_kpis_aggregation(db_path: str) -> None:
    """Valida o cálculo dos KPIs nacionais da janela atípica.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    kpis = get_national_kpis(db_path)
    assert isinstance(kpis, dict)
    assert kpis["total_votos_brasil"] > 100_000_000
    assert kpis["votos_pos_17h"] in (35972, 36141)
    assert 0.02 < kpis["pct_pos_17h"] < 0.04
    assert kpis["total_ufs_ativas"] in (27, 28)
    assert kpis["horario_ultimo_voto"] == "19:06:21"
    assert kpis["votos_h1"] > 25000


def test_timeline_data_flow(db_path: str) -> None:
    """Valida a extração da série temporal minuto a minuto.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    df = get_timeline_data(db_path)
    assert not df.empty
    assert "minuto" in df.columns
    assert "votos" in df.columns
    assert "votos_acumulados" in df.columns
    assert "fase" in df.columns
    assert df["minuto"].min() == "17:00"
    assert df["minuto"].max() == "19:06"
    assert df["votos"].sum() in (35972, 36141)


def test_map_locations_with_coordinates(db_path: str) -> None:
    """Valida a junção das métricas municipais com as coordenadas geográficas.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    df_map = get_map_locations(db_path)
    assert not df_map.empty
    assert "latitude" in df_map.columns
    assert "longitude" in df_map.columns
    assert "votos_pos" in df_map.columns
    assert len(df_map) >= 3000
    # Valida que São Paulo é o município com maior volume
    top_mun = df_map.iloc[0]
    assert top_mun["municipio_nome"] == "SAO PAULO"
    assert top_mun["votos_pos"] > 4000


def test_rankings_aggregation(db_path: str) -> None:
    """Valida os rankings regionais de capitais e proporção local.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    df_ufs, df_capitais, df_proporcao = get_rankings_data(db_path)
    assert len(df_ufs) in (27, 28)
    assert df_ufs.iloc[0]["uf"] == "SP"
    assert not df_capitais.empty
    assert len(df_capitais) <= 10
    assert not df_proporcao.empty
    # Valida que os líderes em proporção são do Amazonas (Lábrea, Boca do Acre, Pauini)
    assert df_proporcao.iloc[0]["uf"] == "AM"


def test_biometrics_stability(db_path: str) -> None:
    """Valida o comparativo biométrico antes e depois das 17h.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    bio = get_biometrics_data(db_path)
    assert "ate_17h" in bio
    assert "pos_17h" in bio
    assert bio["ate_17h"]["pct_com_bio"] > 90.0
    assert bio["pos_17h"]["pct_com_bio"] > 90.0
    # O delta de liberação manual deve ser inferior a 2%
    assert abs(bio["delta_sem_bio"]) < 2.0


def test_latest_sections_filter(db_path: str) -> None:
    """Valida a consulta filtrada do explorador de seções.

    Args:
        db_path: Caminho do banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    df_sec = get_latest_sections(db_path, uf="SP", limit=10)
    assert not df_sec.empty
    assert len(df_sec) <= 10
    assert (df_sec["UF"] == "SP").all()


def test_cli_dashboard_help() -> None:
    """Valida que o comando `pulso dashboard --help` exibe as opções corretamente.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    result = runner.invoke(app, ["dashboard", "--help"])
    assert result.exit_code == 0
    assert "Inicia o dashboard analítico" in result.output
    assert "--port" in result.output
