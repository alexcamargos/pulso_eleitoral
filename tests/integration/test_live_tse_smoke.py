"""Teste de fumaça (smoke test) em ambiente real contra o TSE (`REQ-ING-01`).

Valida a obtenção e auditoria ao vivo de seções eleitorais de Fernando de Noronha
(PE, município 30015, pleito 406, Eleições Gerais 2022, 1º Turno) conectando
diretamente à infraestrutura oficial do Tribunal Superior Eleitoral (TSE).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from pulso_eleitoral.analytics.consolidator import DuckDbConsolidator
from pulso_eleitoral.analytics.parquet_writer import ParquetBatchWriter
from pulso_eleitoral.analytics.verifier import PipelineVerifier
from pulso_eleitoral.config import (
    ElectionRunConfig,
    PipelineSettings,
)
from pulso_eleitoral.contracts.models import (
    ParsedSectionMetrics,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.export.exporter import StaticJsonExporter
from pulso_eleitoral.ingestion.cdn_provider import CdnArtifactProvider
from pulso_eleitoral.ingestion.resilience import (
    CircuitBreaker,
    TokenBucketRateLimiter,
)
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog
from pulso_eleitoral.parser.engine import parse_section_bundle
from tests.fixtures.builder import build_fx01_sp_standard


@pytest.mark.live_tse
@pytest.mark.asyncio
async def test_live_tse_noronha_smoke_audit(tmp_path: Path) -> None:
    """Executa auditoria fim-a-fim contra o CDN oficial do TSE para Fernando de Noronha.

    Conecta ao CDN público do TSE (`resultados.tse.jus.br`) para verificar
    a obtenção do manifesto `-aux.json` e dos artefatos da seção de Fernando de Noronha
    (PE, município TSE 30015, zona 4, pleito 406). Caso a seção esteja arquivada ou
    indisponível no CDN ao vivo, valida a classificação resiliente de erro sem
    interrupção do pipeline. Caso retornada, processa na FSM, consolida no DuckDB
    e exporta os JSONs estáticos.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.

    Returns:
        Nenhum.

    Raises:
        AssertionError: Caso ocorra deriva de invariantes ou falha de protocolo.
    """
    run_cfg = ElectionRunConfig(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
    )
    settings = PipelineSettings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "smoke.duckdb",
        max_concurrent_requests=4,
        requests_per_second=10.0,
        http_timeout_seconds=15.0,
    )
    tz_catalog = TimezoneCatalog.from_csv(Path("resources/dim_municipio_fuso.csv"))
    noronha_tz = tz_catalog.get(30015)
    assert noronha_tz is not None
    assert noronha_tz.uf == "PE"
    assert noronha_tz.fuso_horario_offset_brt == 1  # UTC-2

    rate_limiter = TokenBucketRateLimiter(settings.requests_per_second)
    circuit_breaker = CircuitBreaker()

    async with httpx.AsyncClient(
        http2=True,
        timeout=settings.http_timeout_seconds,
    ) as http_client:
        provider = CdnArtifactProvider(
            run_cfg,
            settings,
            tz_catalog,
            http_client=http_client,
            rate_limiter=rate_limiter,
            circuit_breaker=circuit_breaker,
        )

        # Testa conexão real com a seção 1 da Zona 4 de Fernando de Noronha
        # Utiliza método interno protegido de busca de seção
        result = await provider._fetch_section_bundle(
            http_client,
            noronha_tz,
            zona=4,
            secao=1,
        )

        assert isinstance(result, (SectionArtifactBundle, UnprocessedSectionError))

        writer = ParquetBatchWriter(settings)

        if isinstance(result, SectionArtifactBundle):
            parsed = parse_section_bundle(result)
            if isinstance(parsed, ParsedSectionMetrics):
                writer.write_metrics_batch([parsed])
            else:
                writer.write_audit_batch([parsed])
        else:
            # Se o TSE arquivou a seção no CDN, valida registro estruturado de erro
            writer.write_audit_batch([result])
            fx_parsed = parse_section_bundle(build_fx01_sp_standard())
            assert isinstance(fx_parsed, ParsedSectionMetrics)
            writer.write_metrics_batch([fx_parsed])

    # Consolida no DuckDB
    consolidator = DuckDbConsolidator(settings)
    db_file = consolidator.consolidate()
    assert db_file.is_file()

    # Exporta artefatos estáticos
    exporter = StaticJsonExporter(settings, run_cfg, consolidator)
    exported = exporter.export_all()
    assert "metadata" in exported
    assert "national_summary" in exported
    assert "states_summary" in exported

    # Auditoria com PipelineVerifier
    verifier = PipelineVerifier(settings)
    report = verifier.verify_all(json_dir=exported["metadata"].parent)
    assert report.db_size_mb <= 200.0
