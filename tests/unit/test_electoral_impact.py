"""Testes unitários do motor de testes paramétricos e limites de Manski (`REQ-ANA-03`).

Valida os cálculos de limites extremos de causalidade (Bounds de Manski),
o estimador Within de efeitos fixos municipais com erros-padrão clusterizados (CRVE),
e a geração do relatório consolidado de impacto eleitoral.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from pulso_eleitoral.analytics.electoral_impact import (
    calculate_manski_sensitivity_bounds,
    generate_electoral_impact_report,
    run_parametric_bias_model,
)


@pytest.fixture
def memory_db() -> duckdb.DuckDBPyConnection:
    """Fixture que cria uma conexão DuckDB em memória com dados sintéticos.

    Args:
        Nenhum.

    Returns:
        Conexão DuckDB configurada com tabela `raw_section_metrics`.

    Raises:
        Nenhum.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
    CREATE TABLE raw_section_metrics (
        ano_eleicao SMALLINT,
        turno TINYINT,
        municipio_cod INTEGER,
        zona SMALLINT,
        secao SMALLINT,
        total_votos INTEGER,
        votos_apos_17h INTEGER,
        status_processamento VARCHAR
    );
    """)

    # 100 seções em 5 municípios: 20 seções por município
    # Total de 40.000 votos, com 2.000 votos após 17h
    rows: list[tuple[int, int, int, int, int, int, int, str]] = []
    for m in range(1, 6):
        for s in range(1, 21):
            tot = 400
            pos = 20 if s % 2 == 0 else 0
            rows.append((2026, 2, m, 1, s, tot, pos, "SUCCESS"))

    con.executemany(
        "INSERT INTO raw_section_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return con


def test_manski_bounds_invariance_with_large_margin(
    memory_db: duckdb.DuckDBPyConnection,
) -> None:
    """Valida que uma margem superior ao volume pós-17h garante risco zero de inversão.

    Args:
        memory_db: Conexão DuckDB em memória com dados sintéticos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    bounds = calculate_manski_sensitivity_bounds(memory_db, margin=50_000)

    assert bounds.total_votos_analisados == 40_000
    assert bounds.votos_pos_17h == 1_000  # 5 mun * 10 secoes * 20 votos
    assert bounds.pct_pos_17h == 2.5
    assert bounds.margem_eleitoral_referencia == 50_000
    assert bounds.impacto_maximo_possivel_votos == 1_000
    assert bounds.impacto_maximo_pct_margem == 2.0
    assert bounds.risco_inversao_resultado is False
    assert "INVERSÃO IMPOSSÍVEL" in bounds.veredito_deterministico


def test_manski_bounds_invariance_with_tiny_margin(
    memory_db: duckdb.DuckDBPyConnection,
) -> None:
    """Valida detecção de zona crítica quando a margem for menor que os votos pós-17h.

    Args:
        memory_db: Conexão DuckDB em memória com dados sintéticos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    bounds = calculate_manski_sensitivity_bounds(memory_db, margin=500)

    assert bounds.risco_inversao_resultado is True
    assert "ZONA CRÍTICA" in bounds.veredito_deterministico
    assert bounds.impacto_maximo_pct_margem == 200.0


def test_empirical_neutrality_benchmark(
    memory_db: duckdb.DuckDBPyConnection,
) -> None:
    """Valida execução da hipótese nula de neutralidade sobre variabilidade empírica.

    Args:
        memory_db: Conexão DuckDB em memória com dados sintéticos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    result = run_parametric_bias_model(memory_db)

    assert result.beta_pos_17h == 0.0
    assert result.p_value == 1.0
    assert result.t_statistic == 0.0
    assert result.candidato_favorecido == "NEUTRO"
    assert result.n_secoes == 100
    assert result.n_municipios == 5
    assert result.ci_95_lower < 0.0 < result.ci_95_upper
    assert "TESTE DE NEUTRALIDADE EMPÍRICA" in result.conclusao_estatistica


def test_regression_with_candidate_data_h0_retention(
    memory_db: duckdb.DuckDBPyConnection,
    tmp_path: Path,
) -> None:
    """Valida retenção de H0 quando os votos de candidatos são neutros frente a pós-17h.

    Args:
        memory_db: Conexão DuckDB em memória.
        tmp_path: Diretório temporário para gravação do CSV de candidatos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    csv_file = tmp_path / "cand_neutral.csv"
    lines = ["municipio_cod,zona,secao,votos_a,votos_b"]
    for m in range(1, 6):
        for s in range(1, 21):
            # Proporção 50/50 constante em todas as seções
            lines.append(f"{m},1,{s},200,200")
    csv_file.write_text("\n".join(lines), encoding="utf-8")

    result = run_parametric_bias_model(
        con=memory_db,
        candidate_csv_path=csv_file,
        candidate_a_name="Candidato Alpha",
        candidate_b_name="Candidato Beta",
    )

    assert result.candidato_favorecido == "NEUTRO"
    assert result.p_value >= 0.05
    assert abs(result.beta_pos_17h) < 1e-4
    assert "HIPÓTESE NULA RETIDA" in result.conclusao_estatistica


def test_regression_with_candidate_data_h1_detection(
    memory_db: duckdb.DuckDBPyConnection,
    tmp_path: Path,
) -> None:
    """Valida detecção de viés partidário positivo (rejeição de H0) com efeito induzido.

    Args:
        memory_db: Conexão DuckDB em memória.
        tmp_path: Diretório temporário para gravação do CSV de candidatos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    csv_file = tmp_path / "cand_biased.csv"
    lines = ["municipio_cod,zona,secao,votos_a,votos_b"]
    for m in range(1, 6):
        for s in range(1, 21):
            # Se s par, teve votos pós-17h (pos=20) -> Cand A forte (350 votos)
            # Se s ímpar, sem votos pós-17h (pos=0) -> Cand A fraco (50 votos)
            if s % 2 == 0:
                lines.append(f"{m},1,{s},350,50")
            else:
                lines.append(f"{m},1,{s},50,350")
    csv_file.write_text("\n".join(lines), encoding="utf-8")

    result = run_parametric_bias_model(
        con=memory_db,
        candidate_csv_path=csv_file,
        candidate_a_name="Candidato Alpha",
        candidate_b_name="Candidato Beta",
    )

    assert result.candidato_favorecido == "Candidato Alpha"
    assert result.p_value < 0.01
    assert result.beta_pos_17h > 0.0
    assert result.t_statistic > 3.0
    assert "EFEITO SIGNIFICATIVO" in result.conclusao_estatistica


def test_generate_electoral_impact_report_integration(
    tmp_path: Path,
) -> None:
    """Valida geração ponta a ponta do relatório estruturado em banco temporário.

    Args:
        tmp_path: Diretório temporário para o banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    test_db = tmp_path / "test_pulso.duckdb"
    con = duckdb.connect(str(test_db))
    con.execute("""
    CREATE TABLE raw_section_metrics (
        ano_eleicao SMALLINT,
        turno TINYINT,
        municipio_cod INTEGER,
        zona SMALLINT,
        secao SMALLINT,
        total_votos INTEGER,
        votos_apos_17h INTEGER,
        status_processamento VARCHAR
    );
    INSERT INTO raw_section_metrics VALUES (2026, 2, 100, 1, 1, 300, 10, 'SUCCESS');
    """)
    con.close()

    report = generate_electoral_impact_report(db_path=test_db, margin=1_000_000)

    assert report.ano_eleicao == 2026
    assert report.turno == 2
    assert report.bounds.total_votos_analisados == 300
    assert report.bounds.votos_pos_17h == 10
    assert report.bounds.risco_inversao_resultado is False
    assert report.parametric is not None
    assert report.parametric.candidato_favorecido == "NEUTRO"
