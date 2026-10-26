"""Testes de integração ponta a ponta da CLI e verificação pós-execução (`REQ-QA-01`).

Valida a cadeia completa de comandos: `export-json`, `verify` e `run-all`,
comprovando integridade das somas cruzadas, cumprimento dos SLAs e tratamento de erro.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from pulso_eleitoral import cli as cli_module
from pulso_eleitoral.analytics.consolidator import DuckDbConsolidator
from pulso_eleitoral.analytics.parquet_writer import ParquetBatchWriter
from pulso_eleitoral.cli import app
from pulso_eleitoral.config import PipelineSettings
from pulso_eleitoral.contracts.models import CutoffMode, ParsedSectionMetrics

runner = CliRunner()


def _make_metric(secao: int = 1) -> ParsedSectionMetrics:
    """Gera uma métrica de seção consistente para testes de integração.

    Args:
        secao: Número da seção eleitoral.

    Returns:
        Instância válida de ParsedSectionMetrics.

    Raises:
        Nenhum.
    """
    return ParsedSectionMetrics(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="PE",
        municipio_cod=30015,
        municipio_ibge=2605459,
        municipio_nome="FERNANDO DE NORONHA",
        zona=1,
        secao=secao,
        fuso_horario_offset_brt=1,
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        qtd_arquivos_log=1,
        total_aptos=200,
        comparecimento_bu=100,
        total_votos=100,
        divergencia_bu_log=0,
        votos_antes_08h=0,
        votos_ate_17h=80,
        votos_apos_17h=20,
        sem_bio_ate_17h=8,
        sem_bio_apos_17h=2,
        bio_status_indefinido=0,
        tentativas_bio_falhas=0,
        votos_cancelados_suspensos=0,
        qtd_reinicializacoes=0,
        horario_abertura_brt=datetime(2022, 10, 2, 8, 0, 0),
        horario_primeiro_voto_brt=datetime(2022, 10, 2, 8, 10, 0),
        horario_ultimo_voto_brt=datetime(2022, 10, 2, 17, 30, 0),
        horario_encerramento_brt=datetime(2022, 10, 2, 17, 35, 0),
        relogio_suspeito=False,
        voto_apos_encerramento=False,
    )


def test_cli_export_json_and_verify_flow(tmp_path: Path) -> None:
    """Verifica a sequência 'export-json' e 'verify' via CliRunner.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "pulso.duckdb",
    )
    writer = ParquetBatchWriter(settings)
    writer.write_metrics_batch([_make_metric(1), _make_metric(2)], chunk_id=1)

    consolidator = DuckDbConsolidator(settings)
    consolidator.consolidate()

    out_dir = tmp_path / "public" / "api" / "v1"

    # 1. export-json
    res_export = runner.invoke(
        app,
        [
            "export-json",
            "--ano",
            "2022",
            "--turno",
            "1",
            "--pleito",
            "406",
            "--db-path",
            str(settings.db_path),
            "--out-dir",
            str(out_dir),
        ],
    )
    assert res_export.exit_code == 0
    assert "Exportação concluída com sucesso" in res_export.stdout

    # 2. verify
    target_json_dir = out_dir / "ele2022" / "turno1"
    res_verify = runner.invoke(
        app,
        [
            "verify",
            "--db-path",
            str(settings.db_path),
            "--json-dir",
            str(target_json_dir),
        ],
    )
    assert res_verify.exit_code == 0
    assert "SUCESSO: 2 seções válidas" in res_verify.stdout
    assert "Invariantes 1..6 e somas cruzadas 100% conformes" in res_verify.stdout


def test_cli_run_all_command(tmp_path: Path, mocker: MockerFixture) -> None:
    """Verifica comando 'pulso run-all' encadeando todas as etapas com sucesso.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.
        mocker: Fixture oficial do pytest-mock.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "pulso.duckdb",
    )
    writer = ParquetBatchWriter(settings)
    writer.write_metrics_batch([_make_metric(1)], chunk_id=1)

    # Mock apenas de ingest_parse para evitar download real de rede no teste E2E
    mocker.patch.object(cli_module, "ingest_parse")

    out_dir = tmp_path / "public" / "api" / "v1"
    result = runner.invoke(
        app,
        [
            "run-all",
            "--ano",
            "2022",
            "--turno",
            "1",
            "--pleito",
            "406",
            "--uf",
            "PE",
            "--source",
            "zip",
            "--db-path",
            str(settings.db_path),
            "--out-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0
    assert "Execução concluída e auditada com sucesso" in result.stdout


def test_pipeline_verifier_missing_db_error(tmp_path: Path) -> None:
    """Verifica erro quando o arquivo DuckDB não existe para verificação.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "non_existent.duckdb",
    )
    result = runner.invoke(
        app,
        ["verify", "--db-path", str(settings.db_path)],
    )
    assert result.exit_code == 1
    assert "Auditoria reprovada" in result.output
