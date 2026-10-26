"""Testes unitários dos contratos de exportação e StaticJsonExporter (`REQ-EXP-01`).

Valida a geração de JSON Schemas Draft 2020-12, cálculo de SHA-256 do DuckDB,
formatação de timestamps BRT (`-03:00`), geração de payloads e SLA de 250 KB.

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

import orjson

from pulso_eleitoral.analytics.consolidator import DuckDbConsolidator
from pulso_eleitoral.analytics.parquet_writer import ParquetBatchWriter
from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings
from pulso_eleitoral.contracts.models import CutoffMode, ParsedSectionMetrics
from pulso_eleitoral.export.exporter import (
    StaticJsonExporter,
    _format_brt_timestamp,
    compute_file_sha256,
)
from pulso_eleitoral.export.models import (
    FlaggedSectionsPayload,
    MetadataPayload,
    MunicipalitiesPayload,
    NationalSummaryPayload,
    StatesSummaryPayload,
    export_json_schemas,
)


def _make_metric(secao: int = 1) -> ParsedSectionMetrics:
    """Helper para criar uma instância de ParsedSectionMetrics para testes.

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
        total_aptos=250,
        comparecimento_bu=100,
        total_votos=100,
        divergencia_bu_log=0,
        votos_antes_08h=0,
        votos_ate_17h=80,
        votos_apos_17h=20,
        sem_bio_ate_17h=10,
        sem_bio_apos_17h=5,
        bio_status_indefinido=0,
        tentativas_bio_falhas=1,
        votos_cancelados_suspensos=0,
        qtd_reinicializacoes=0,
        horario_abertura_brt=datetime(2022, 10, 2, 8, 0, 0),
        horario_primeiro_voto_brt=datetime(2022, 10, 2, 8, 5, 0),
        horario_ultimo_voto_brt=datetime(2022, 10, 2, 17, 25, 0),
        horario_encerramento_brt=datetime(2022, 10, 2, 17, 30, 0),
        relogio_suspeito=False,
        voto_apos_encerramento=False,
    )


def test_export_json_schemas(tmp_path: Path) -> None:
    """Verifica geração dos 5 schemas JSON Draft 2020-12.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    schemas = export_json_schemas(tmp_path / "schemas")
    assert len(schemas) == 5
    for _name, path in schemas.items():
        assert path.is_file()
        data = orjson.loads(path.read_bytes())
        assert "$defs" in data or "properties" in data or "title" in data


def test_compute_file_sha256(tmp_path: Path) -> None:
    """Verifica cálculo do hash SHA-256 e fallback para arquivo inexistente.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    sample_file = tmp_path / "sample.bin"
    sample_file.write_bytes(b"sample bytes for sha256")
    digest = compute_file_sha256(sample_file)
    assert len(digest) == 64

    missing_digest = compute_file_sha256(tmp_path / "non_existent.bin")
    assert len(missing_digest) == 64


def test_format_brt_timestamp() -> None:
    """Verifica formatação estrita de timestamps BRT com sufixo -03:00.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    assert _format_brt_timestamp(None) is None
    assert _format_brt_timestamp("") is None

    dt = datetime(2022, 10, 2, 17, 30, 0)
    res_dt = _format_brt_timestamp(dt)
    assert res_dt == "2022-10-02T17:30:00-03:00"

    res_str = _format_brt_timestamp("2022-10-02 17:30:00")
    assert res_str == "2022-10-02 17:30:00-03:00"

    res_already = _format_brt_timestamp("2022-10-02T17:30:00-03:00")
    assert res_already == "2022-10-02T17:30:00-03:00"


def test_static_json_exporter_full_tree(tmp_path: Path) -> None:
    """Verifica geração completa da árvore estática JSON e SLA de 250 KB.

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
    writer.write_metrics_batch([_make_metric(secao=1), _make_metric(secao=2)])

    consolidator = DuckDbConsolidator(settings)
    consolidator.consolidate()

    run_cfg = ElectionRunConfig(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        ufs=("PE",),
    )
    exporter = StaticJsonExporter(settings, run_cfg, consolidator)
    out_dir = tmp_path / "public" / "api" / "v1" / "ele2022" / "turno1"
    generated = exporter.export_all(output_dir=out_dir)

    assert "metadata" in generated
    assert "national_summary" in generated
    assert "states_summary" in generated
    assert "flagged_index" in generated
    assert "flagged_root_alias" in generated

    # Validação dos contratos Pydantic v2
    meta_data = orjson.loads(generated["metadata"].read_bytes())
    MetadataPayload.model_validate(meta_data)

    nat_data = orjson.loads(generated["national_summary"].read_bytes())
    nat_obj = NationalSummaryPayload.model_validate(nat_data)
    assert nat_obj.total_votos_brasil == 200

    states_data = orjson.loads(generated["states_summary"].read_bytes())
    states_obj = StatesSummaryPayload.model_validate(states_data)
    assert len(states_obj.states) == 1
    assert states_obj.states[0].uf == "PE"

    mun_path = out_dir / "municipalities" / "PE.json"
    assert mun_path.is_file()
    mun_data = orjson.loads(mun_path.read_bytes())
    MunicipalitiesPayload.model_validate(mun_data)

    flagged_data = orjson.loads(generated["flagged_index"].read_bytes())
    FlaggedSectionsPayload.model_validate(flagged_data)

    # Orçamento SLA <= 250 KB
    bundle_size = (
        generated["metadata"].stat().st_size
        + generated["national_summary"].stat().st_size
        + generated["states_summary"].stat().st_size
    )
    assert bundle_size <= 250 * 1024
