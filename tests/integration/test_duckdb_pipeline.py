"""Testes de integração da consolidação DuckDB e pipeline (`REQ-ANA-01`..`02`).

Valida a consolidação idempotente, cálculo das 4 visões analíticas
(`summary_national`, `summary_by_uf`, `summary_by_municipio`, `flagged_sections`),
classificação dos 3 Tiers e execução via CLI.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from pulso_eleitoral.analytics.consolidator import DuckDbConsolidator
from pulso_eleitoral.analytics.orchestrator import PipelineOrchestrator
from pulso_eleitoral.analytics.parquet_writer import ParquetBatchWriter
from pulso_eleitoral.cli import app
from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings
from pulso_eleitoral.contracts.models import (
    CutoffMode,
    IngestionCheckpoint,
    MunicipalityTzInfo,
    ParsedSectionMetrics,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.ingestion.base import SectionArtifactProvider
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog

runner = CliRunner()


def _build_test_metric(
    *,
    uf: str = "PE",
    mun_cod: int = 30015,
    zona: int = 1,
    secao: int = 1,
    total_votos: int = 100,
    votos_ate_17h: int = 80,
    votos_apos_17h: int = 20,
    sem_bio_ate_17h: int = 8,
    sem_bio_apos_17h: int = 10,
    relogio_suspeito: bool = False,
    voto_apos_encerramento: bool = False,
    divergencia_bu_log: int = 0,
    status: str = "SUCCESS",
) -> ParsedSectionMetrics:
    """Gera uma instância de ParsedSectionMetrics para testes de consolidação.

    Args:
        uf: Sigla da UF.
        mun_cod: Código TSE do município.
        zona: Número da zona eleitoral.
        secao: Número da seção eleitoral.
        total_votos: Total de votos confirmados.
        votos_ate_17h: Votos antes das 17h.
        votos_apos_17h: Votos a partir das 17h.
        sem_bio_ate_17h: Votos manuais antes das 17h.
        sem_bio_apos_17h: Votos manuais a partir das 17h.
        relogio_suspeito: Indicador de anomalia de relógio.
        voto_apos_encerramento: Indicador de voto após fechamento.
        divergencia_bu_log: Diferença entre BU e log.
        status: Status de processamento (`SUCCESS` ou erro).

    Returns:
        Instância preenchida de ParsedSectionMetrics.

    Raises:
        Nenhum.
    """
    return ParsedSectionMetrics(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf=uf,
        municipio_cod=mun_cod,
        municipio_ibge=2605459,
        municipio_nome="FERNANDO DE NORONHA",
        zona=zona,
        secao=secao,
        fuso_horario_offset_brt=1,
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        qtd_arquivos_log=1,
        total_aptos=200,
        comparecimento_bu=total_votos,
        total_votos=total_votos,
        divergencia_bu_log=divergencia_bu_log,
        votos_antes_08h=0,
        votos_ate_17h=votos_ate_17h,
        votos_apos_17h=votos_apos_17h,
        sem_bio_ate_17h=sem_bio_ate_17h,
        sem_bio_apos_17h=sem_bio_apos_17h,
        bio_status_indefinido=0,
        tentativas_bio_falhas=0,
        votos_cancelados_suspensos=0,
        qtd_reinicializacoes=0,
        horario_abertura_brt=datetime(2022, 10, 2, 8, 0, 0),
        horario_primeiro_voto_brt=datetime(2022, 10, 2, 8, 10, 0),
        horario_ultimo_voto_brt=datetime(2022, 10, 2, 17, 30, 0),
        horario_encerramento_brt=datetime(2022, 10, 2, 17, 35, 0),
        relogio_suspeito=relogio_suspeito,
        voto_apos_encerramento=voto_apos_encerramento,
        status_processamento=status,
    )


def test_duckdb_idempotent_consolidation_and_views(tmp_path: Path) -> None:
    """Verifica consolidação idempotente e visões analíticas no DuckDB.

    Testa se a reexecução com partições duplicadas preserva idempotência exata
    e se a classificação em TIER_1, TIER_2 e TIER_3 opera perfeitamente.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "pulso_eleitoral.duckdb",
    )
    writer = ParquetBatchWriter(settings)

    # 1. Monta três seções com perfis distintos:
    # Seção 1: TIER_1 (normal com sem_bio_apos_17h >= 1)
    # Seção 2: TIER_2 (salto >= 15 p.p. sem_bio: ate_17h = 0%, pos_17h = 50%)
    # Seção 3: TIER_3 (relogio_suspeito = True)
    m1 = _build_test_metric(
        secao=1,
        total_votos=100,
        votos_ate_17h=80,
        votos_apos_17h=20,
        sem_bio_ate_17h=10,
        sem_bio_apos_17h=2,
    )
    m2 = _build_test_metric(
        secao=2,
        total_votos=100,
        votos_ate_17h=80,
        votos_apos_17h=20,
        sem_bio_ate_17h=0,
        sem_bio_apos_17h=15,  # 75% vs 0% -> salto de 75 pp (> 15 pp)
    )
    m3 = _build_test_metric(
        secao=3,
        total_votos=100,
        votos_ate_17h=80,
        votos_apos_17h=20,
        relogio_suspeito=True,
    )

    writer.write_metrics_batch([m1, m2, m3], chunk_id=1)

    # Erro de auditoria (seção 4)
    err = UnprocessedSectionError(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="PE",
        municipio_cod=30015,
        zona=1,
        secao=4,
        error_code="CORRUPT_ARCHIVE",
        error_message="CRC fail",
        recorded_at=datetime(2022, 10, 2, 10, 0, 0),
    )
    writer.write_audit_batch([err])

    consolidator = DuckDbConsolidator(settings)
    db_file = consolidator.consolidate()
    assert db_file.is_file()

    # Validação da tabela raw_section_metrics
    rows = consolidator.query("SELECT COUNT(*) AS total FROM raw_section_metrics;")
    assert rows[0]["total"] == 3

    # Idempotência: grava segundo arquivo com seções sobrepostas e re-consolida
    writer.write_metrics_batch([m1, m2], chunk_id=2)
    consolidator.consolidate()
    rows_after = consolidator.query(
        "SELECT COUNT(*) AS total FROM raw_section_metrics;"
    )
    assert rows_after[0]["total"] == 3  # Não duplicou!

    # Validação da visão summary_national
    nat_rows = consolidator.query("SELECT * FROM summary_national;")
    assert len(nat_rows) == 1
    nat = nat_rows[0]
    assert nat["total_secoes_analisadas"] == 3
    assert nat["total_votos_brasil"] == 300
    assert nat["votos_apos_17h_brasil"] == 60

    # Validação da visão summary_by_uf
    uf_rows = consolidator.query("SELECT * FROM summary_by_uf WHERE uf = 'PE';")
    assert len(uf_rows) == 1
    assert uf_rows[0]["total_votos_uf"] == 300

    # Validação da visão flagged_sections e seus Tiers
    flagged = consolidator.query(
        "SELECT secao, severidade_sinalizacao FROM flagged_sections ORDER BY secao;"
    )
    assert len(flagged) == 3
    tiers_by_sec = {r["secao"]: r["severidade_sinalizacao"] for r in flagged}
    assert tiers_by_sec[1] == "TIER_1_POST_17H_NO_BIO"
    assert tiers_by_sec[2] == "TIER_2_STATISTICAL_OUTLIER"
    assert tiers_by_sec[3] == "TIER_3_CRITICAL_ANOMALY"


class _MockSectionProvider(SectionArtifactProvider):
    """Provedor mock que emite uma seção e um erro de auditoria para testes."""

    def __init__(self, bundle: SectionArtifactBundle) -> None:
        self._bundle = bundle

    async def stream_uf(
        self,
        uf: str,
        checkpoint: IngestionCheckpoint | None = None,
    ) -> AsyncIterator[SectionArtifactBundle | UnprocessedSectionError]:
        yield self._bundle
        yield UnprocessedSectionError(
            ano_eleicao=self._bundle.ano_eleicao,
            turno=self._bundle.turno,
            pleito_id=self._bundle.pleito_id,
            uf=self._bundle.uf,
            municipio_cod=self._bundle.municipio_cod,
            zona=self._bundle.zona,
            secao=self._bundle.secao + 1,
            error_code="MISSING_LOG",
            error_message="Log inexistente na seção",
            recorded_at=datetime.now(),
        )


@pytest.mark.asyncio
async def test_pipeline_orchestrator_execution(tmp_path: Path) -> None:
    """Verifica execução completa do PipelineOrchestrator com escrita de Parquet.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(
        data_dir=tmp_path / "data",
        workers=1,  # In-process execution para teste
        batch_size=10,
    )
    run_cfg = ElectionRunConfig(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        ufs=("PE",),
    )
    tz_info = MunicipalityTzInfo(
        municipio_cod_tse=30015,
        municipio_cod_ibge=2605459,
        uf="PE",
        municipio_nome="FERNANDO DE NORONHA",
        iana_timezone="America/Noronha",
        fuso_horario_offset_brt=1,
    )
    catalog = TimezoneCatalog({30015: tz_info})

    # Cria bundle sintético usando a fixture FX-01
    from tests.fixtures.builder import build_fx01_sp_standard

    fx01_bundle = build_fx01_sp_standard()

    provider = _MockSectionProvider(fx01_bundle)
    orchestrator = PipelineOrchestrator(
        run_cfg=run_cfg,
        settings=settings,
        tz_catalog=catalog,
        provider=provider,
    )

    summary = await orchestrator.run_uf("PE")
    assert summary.uf == "PE"
    assert summary.total_sections == 2
    assert summary.success_sections == 1
    assert summary.error_sections == 1
    assert len(summary.parquet_files) == 2  # 1 métricas + 1 auditoria


def test_cli_consolidate_command(tmp_path: Path) -> None:
    """Verifica o comando 'pulso consolidate' através do Typer CliRunner.

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
    metric = _build_test_metric()
    writer.write_metrics_batch([metric], chunk_id=1)

    result = runner.invoke(
        app,
        ["consolidate", "--db-path", str(settings.db_path)],
    )
    assert result.exit_code == 0
    assert "Consolidação DuckDB concluída com sucesso" in result.stdout


def test_orchestrator_default_providers_instantiation(tmp_path: Path) -> None:
    """Verifica instanciação automática dos provedores CDN e ZIP no Orchestrator.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(data_dir=tmp_path / "data")
    tz_info = MunicipalityTzInfo(
        municipio_cod_tse=30015,
        municipio_cod_ibge=2605459,
        uf="PE",
        municipio_nome="FERNANDO DE NORONHA",
        iana_timezone="America/Noronha",
        fuso_horario_offset_brt=1,
    )
    catalog = TimezoneCatalog({30015: tz_info})

    from pulso_eleitoral.config import SourceMode

    cfg_zip = ElectionRunConfig(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        source_mode=SourceMode.ZIP,
    )
    orch_zip = PipelineOrchestrator(cfg_zip, settings, catalog)
    assert orch_zip._provider is not None

    cfg_cdn = ElectionRunConfig(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        source_mode=SourceMode.CDN,
    )
    orch_cdn = PipelineOrchestrator(cfg_cdn, settings, catalog)
    assert orch_cdn._provider is not None


def test_cli_ingest_parse_command_with_mock(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Verifica comando 'pulso ingest-parse' via CliRunner.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.
        mocker: Fixture oficial do pytest-mock.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    from pulso_eleitoral.analytics.orchestrator import UfExecutionSummary

    async def mock_run_uf(uf: str) -> UfExecutionSummary:
        return UfExecutionSummary(
            uf=uf,
            total_sections=1,
            success_sections=1,
            error_sections=0,
            parquet_files=(),
        )

    mocker.patch.object(PipelineOrchestrator, "run_uf", side_effect=mock_run_uf)
    result = runner.invoke(
        app,
        [
            "ingest-parse",
            "--ano",
            "2022",
            "--turno",
            "1",
            "--pleito",
            "406",
            "--uf",
            "PE",
            "--municipio",
            "30015",
            "--workers",
            "1",
        ],
    )
    assert result.exit_code == 0
    assert "Concluído PE" in result.stdout
