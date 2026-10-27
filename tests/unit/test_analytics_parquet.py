"""Testes dos schemas, invariantes vetorizadas e ParquetBatchWriter (`REQ-ANA-01`).

Valida `validate_dataframe_invariants` (Invariantes 1 a 5),
`validate_denominator_completeness` (Invariante 6) e escrita atômica com ZSTD.

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

import polars as pl
import pytest

from pulso_eleitoral.analytics.invariants import (
    validate_dataframe_invariants,
    validate_denominator_completeness,
)
from pulso_eleitoral.analytics.parquet_writer import ParquetBatchWriter
from pulso_eleitoral.analytics.schemas import (
    RAW_SECTION_METRICS_SCHEMA,
    UNPROCESSED_SECTIONS_SCHEMA,
)
from pulso_eleitoral.config import PipelineSettings
from pulso_eleitoral.contracts.exceptions import InvariantViolationError
from pulso_eleitoral.contracts.models import (
    CutoffMode,
    ParsedSectionMetrics,
    UnprocessedSectionError,
)


def _make_metric(
    total_votos: int = 100,
    votos_ate_17h: int = 80,
    votos_apos_17h: int = 20,
    sem_bio_ate_17h: int = 10,
    sem_bio_apos_17h: int = 5,
    ts_primeiro: datetime | None = datetime(2022, 10, 2, 8, 5, 0),
    ts_ultimo: datetime | None = datetime(2022, 10, 2, 17, 30, 0),
    secao: int = 1,
) -> ParsedSectionMetrics:
    """Helper para criar uma instância de ParsedSectionMetrics para testes.

    Args:
        total_votos: Total de votos confirmados.
        votos_ate_17h: Votos antes das 17h.
        votos_apos_17h: Votos a partir das 17h.
        sem_bio_ate_17h: Votos manuais antes das 17h.
        sem_bio_apos_17h: Votos manuais a partir das 17h.
        ts_primeiro: Timestamp do primeiro voto.
        ts_ultimo: Timestamp do último voto.
        secao: Número da seção.

    Returns:
        Instância preenchida de ParsedSectionMetrics.

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
        comparecimento_bu=total_votos,
        total_votos=total_votos,
        divergencia_bu_log=0,
        votos_antes_08h=0,
        votos_ate_17h=votos_ate_17h,
        votos_apos_17h=votos_apos_17h,
        sem_bio_ate_17h=sem_bio_ate_17h,
        sem_bio_apos_17h=sem_bio_apos_17h,
        bio_status_indefinido=0,
        tentativas_bio_falhas=2,
        votos_cancelados_suspensos=0,
        qtd_reinicializacoes=0,
        horario_abertura_brt=datetime(2022, 10, 2, 8, 0, 0),
        horario_primeiro_voto_brt=ts_primeiro,
        horario_ultimo_voto_brt=ts_ultimo,
        horario_encerramento_brt=datetime(2022, 10, 2, 17, 35, 0),
        relogio_suspeito=False,
        voto_apos_encerramento=False,
    )


def test_schemas_definitions() -> None:
    """Verifica que os esquemas Polars contêm as colunas e tipos corretos.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    assert len(RAW_SECTION_METRICS_SCHEMA) == 32
    assert len(UNPROCESSED_SECTIONS_SCHEMA) == 14
    assert "relogio_suspeito" in RAW_SECTION_METRICS_SCHEMA
    assert "error_code" in UNPROCESSED_SECTIONS_SCHEMA


def test_validate_dataframe_invariants_success() -> None:
    """Verifica que métricas conformes passam na validação vetorizada.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    m = _make_metric()
    df = pl.DataFrame([m.to_metrics_row()], schema=RAW_SECTION_METRICS_SCHEMA)
    validate_dataframe_invariants(df)


def test_validate_dataframe_invariants_failures() -> None:
    """Verifica detecção vetorizada de violação das Invariantes 1 a 5.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    # Invariante 1: total_votos != ate_17h + pos_17h
    m1 = _make_metric(total_votos=100, votos_ate_17h=70, votos_apos_17h=20)
    df1 = pl.DataFrame([m1.to_metrics_row()], schema=RAW_SECTION_METRICS_SCHEMA)
    with pytest.raises(InvariantViolationError, match="Invariante 1 violada"):
        validate_dataframe_invariants(df1)

    # Invariante 2: sem_bio_ate_17h > votos_ate_17h (85 > 80)
    m2 = _make_metric(
        total_votos=100,
        votos_ate_17h=80,
        votos_apos_17h=20,
        sem_bio_ate_17h=85,
    )
    df2 = pl.DataFrame([m2.to_metrics_row()], schema=RAW_SECTION_METRICS_SCHEMA)
    with pytest.raises(InvariantViolationError, match="Invariante 2 violada"):
        validate_dataframe_invariants(df2)

    # Invariante 3: sem_bio_apos_17h > votos_apos_17h (25 > 20)
    m3 = _make_metric(
        total_votos=100,
        votos_ate_17h=80,
        votos_apos_17h=20,
        sem_bio_apos_17h=25,
    )
    df3 = pl.DataFrame([m3.to_metrics_row()], schema=RAW_SECTION_METRICS_SCHEMA)
    with pytest.raises(InvariantViolationError, match="Invariante 3 violada"):
        validate_dataframe_invariants(df3)

    # Invariante 4: total_votos == 0 com timestamp não nulo
    m4 = _make_metric(
        total_votos=0,
        votos_ate_17h=0,
        votos_apos_17h=0,
        sem_bio_ate_17h=0,
        sem_bio_apos_17h=0,
        ts_primeiro=datetime(2022, 10, 2, 8, 10, 0),
        ts_ultimo=None,
    )
    df4 = pl.DataFrame([m4.to_metrics_row()], schema=RAW_SECTION_METRICS_SCHEMA)
    with pytest.raises(InvariantViolationError, match="Invariante 4 violada"):
        validate_dataframe_invariants(df4)

    # Invariante 5: primeiro_voto > ultimo_voto
    m5 = _make_metric(
        total_votos=100,
        votos_ate_17h=80,
        votos_apos_17h=20,
        ts_primeiro=datetime(2022, 10, 2, 18, 0, 0),
        ts_ultimo=datetime(2022, 10, 2, 17, 0, 0),
    )
    df5 = pl.DataFrame([m5.to_metrics_row()], schema=RAW_SECTION_METRICS_SCHEMA)
    with pytest.raises(InvariantViolationError, match="Invariante 5 violada"):
        validate_dataframe_invariants(df5)


def test_validate_denominator_completeness() -> None:
    """Verifica validação da Invariante 6 (total_manifest == success + errors).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    validate_denominator_completeness(
        total_manifest=100, total_success=95, total_errors=5
    )
    with pytest.raises(InvariantViolationError, match="Invariante 6 violada"):
        validate_denominator_completeness(
            total_manifest=100, total_success=90, total_errors=5
        )


def test_validate_dataframe_invariants_empty_and_no_success() -> None:
    """Verifica comportamento defensivo para DataFrame vazio ou sem status SUCCESS.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    empty_df = pl.DataFrame(schema=RAW_SECTION_METRICS_SCHEMA)
    validate_dataframe_invariants(empty_df)

    # DataFrame contendo apenas seções não processadas (erros)
    err_metric = _make_metric(secao=999)
    err_row = err_metric.to_metrics_row()
    err_row["status_processamento"] = "MISSING_LOG"
    df_err = pl.DataFrame([err_row], schema=RAW_SECTION_METRICS_SCHEMA)
    validate_dataframe_invariants(df_err)


def test_parquet_batch_writer_empty_returns_none(tmp_path: Path) -> None:
    """Verifica retorno None ao tentar gravar lotes vazios em ParquetBatchWriter.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(data_dir=tmp_path / "data")
    writer = ParquetBatchWriter(settings)
    assert writer.write_metrics_batch([]) is None
    assert writer.write_audit_batch([]) is None


def test_parquet_batch_writer_atomic_operations(tmp_path: Path) -> None:
    """Verifica escrita atômica e ausência de arquivos temporários órfãos.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(data_dir=tmp_path / "data")
    writer = ParquetBatchWriter(settings)

    # Lote de métricas
    metrics = [_make_metric(secao=1), _make_metric(secao=2)]
    out_metrics = writer.write_metrics_batch(metrics, chunk_id=1)
    assert out_metrics is not None
    assert out_metrics.is_file()
    assert out_metrics.name == "part-406-PE-0001.parquet"

    # Confirma que não há .tmp.parquet no diretório
    parent = out_metrics.parent
    tmp_files = list(parent.glob("*.tmp.parquet"))
    assert len(tmp_files) == 0

    # Lote de auditoria
    err = UnprocessedSectionError(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="PE",
        municipio_cod=30015,
        zona=1,
        secao=999,
        error_code="MISSING_LOG",
        error_message="Arquivo logjez inexistente no pacote",
        recorded_at=datetime(2022, 10, 2, 12, 0, 0),
    )
    out_audit = writer.write_audit_batch([err])
    assert out_audit is not None
    assert out_audit.is_file()
    assert out_audit.name == "unprocessed_PE.parquet"


def test_parquet_writer_get_next_chunk_id(tmp_path: Path) -> None:
    """Verifica determinação sequencial do próximo chunk_id para evitar sobrescritas.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(data_dir=tmp_path / "data")
    writer = ParquetBatchWriter(settings)

    # 1. Diretório vazio ou inexistente retorna chunk_id = 1
    assert writer.get_next_chunk_id(2022, 1, "PE", 406) == 1

    # 2. Gravar chunk 1
    metrics1 = [_make_metric(secao=1)]
    writer.write_metrics_batch(metrics1, chunk_id=1)

    # 3. Agora o próximo deve ser 2
    assert writer.get_next_chunk_id(2022, 1, "PE", 406) == 2

    # 4. Gravar chunk 2
    metrics2 = [_make_metric(secao=2)]
    writer.write_metrics_batch(metrics2, chunk_id=2)

    # 5. Próximo deve ser 3
    assert writer.get_next_chunk_id(2022, 1, "PE", 406) == 3
