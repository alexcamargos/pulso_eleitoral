"""Testes unitários de ingestão de pacotes ZIP estaduais (`REQ-ING-01`).

Valida `BulkZipArtifactProvider` com arquivos `.zip` sintéticos, filtragem por
município, controle de checkpoint, detecção de erros e descarte de mídia supérflua.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest

from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings
from pulso_eleitoral.contracts.exceptions import ContractValidationError
from pulso_eleitoral.contracts.models import (
    IngestionCheckpoint,
    MunicipalityTzInfo,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog
from pulso_eleitoral.ingestion.zip_provider import BulkZipArtifactProvider


@pytest.fixture
def mock_tz_catalog() -> TimezoneCatalog:
    """Fixture que fornece um TimezoneCatalog sintético em memória.

    Args:
        Nenhum.

    Returns:
        Instância de TimezoneCatalog com municípios fictícios.

    Raises:
        Nenhum.
    """
    entries = {
        71072: MunicipalityTzInfo(
            municipio_cod_tse=71072,
            municipio_cod_ibge=3550308,
            uf="SP",
            municipio_nome="SAO PAULO",
            iana_timezone="America/Sao_Paulo",
            fuso_horario_offset_brt=0,
        ),
        30015: MunicipalityTzInfo(
            municipio_cod_tse=30015,
            municipio_cod_ibge=2605459,
            uf="PE",
            municipio_nome="FERNANDO DE NORONHA",
            iana_timezone="America/Noronha",
            fuso_horario_offset_brt=1,
        ),
    }
    return TimezoneCatalog(entries)


@pytest.fixture
def base_run_cfg() -> ElectionRunConfig:
    """Fixture de configuração básica para 2022 turno 1 pleito 406.

    Args:
        Nenhum.

    Returns:
        Instância de ElectionRunConfig.

    Raises:
        Nenhum.
    """
    return ElectionRunConfig(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        ufs=("SP",),
    )


@pytest.mark.asyncio
async def test_bulk_zip_provider_normal_extraction(
    tmp_path: Path,
    mock_tz_catalog: TimezoneCatalog,
    base_run_cfg: ElectionRunConfig,
) -> None:
    """Verifica extração correta de seções válidas de um pacote ZIP local.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.
        mock_tz_catalog: Catálogo simulado de fusos horários.
        base_run_cfg: Configuração padrão da eleição.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(data_dir=tmp_path / "data")
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    zip_filename = "bu_imgbu_logjez_rdv_vscmr_2022_1t_SP.zip"
    zip_path = raw_dir / zip_filename

    # Monta ZIP sintético com 2 seções:
    # Seção 1 (71072, 1, 101): possui .logjez, .bu, e .imgbu (que deve ser ignorado)
    # Seção 2 (71072, 1, 102): possui apenas .bu (sem logjez -> MISSING_LOG)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "o00406-7107200010101.logjez",
            b"fake 7z content section 101",
        )
        zf.writestr("o00406-7107200010101.bu", b"fake bu content section 101")
        zf.writestr(
            "o00406-7107200010101.imgbu",
            b"fake imgbu to ignore" * 100,
        )
        zf.writestr("o00406-7107200010102.bu", b"fake bu content section 102")

    provider = BulkZipArtifactProvider(
        base_run_cfg,
        settings,
        mock_tz_catalog,
        allow_remote_download=False,
    )

    results: list[SectionArtifactBundle | UnprocessedSectionError] = []
    async for item in provider.stream_uf("SP"):
        results.append(item)

    assert len(results) == 2

    # Seção 101 é um bundle válido
    bundle = results[0]
    assert isinstance(bundle, SectionArtifactBundle)
    assert bundle.municipio_cod == 71072
    assert bundle.zona == 1
    assert bundle.secao == 101
    assert len(bundle.log_artifacts) == 1
    assert bundle.log_artifacts[0].filename == "o00406-7107200010101.logjez"
    assert bundle.log_artifacts[0].raw_bytes == b"fake 7z content section 101"
    assert bundle.bu_raw_bytes == b"fake bu content section 101"

    # Seção 102 gera UnprocessedSectionError (MISSING_LOG)
    err = results[1]
    assert isinstance(err, UnprocessedSectionError)
    assert err.secao == 102
    assert err.error_code == "MISSING_LOG"


@pytest.mark.asyncio
async def test_bulk_zip_provider_filtering_and_checkpoint(
    tmp_path: Path,
    mock_tz_catalog: TimezoneCatalog,
) -> None:
    """Verifica filtragem por código de município e descarte via checkpoint.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.
        mock_tz_catalog: Catálogo simulado de fusos horários.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(data_dir=tmp_path / "data")
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    zip_filename = "bu_imgbu_logjez_rdv_vscmr_2022_1t_SP.zip"
    zip_path = raw_dir / zip_filename

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("o00406-7107200010101.logjez", b"sec 101")
        zf.writestr("o00406-7107200010102.logjez", b"sec 102")

    # Configuração filtrando apenas município 71072
    cfg = ElectionRunConfig(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        municipios=(71072,),
    )
    # Checkpoint onde seção 101 já foi concluída
    checkpoint = IngestionCheckpoint(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="SP",
        completed_sections=frozenset({(71072, 1, 101)}),
    )

    provider = BulkZipArtifactProvider(
        cfg,
        settings,
        mock_tz_catalog,
        allow_remote_download=False,
    )

    results = [item async for item in provider.stream_uf("SP", checkpoint)]
    assert len(results) == 1
    assert isinstance(results[0], SectionArtifactBundle)
    assert results[0].secao == 102


@pytest.mark.asyncio
async def test_bulk_zip_provider_missing_local_file_error(
    tmp_path: Path,
    mock_tz_catalog: TimezoneCatalog,
    base_run_cfg: ElectionRunConfig,
) -> None:
    """Verifica erro quando arquivo local não existe e download remoto é desativado.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.
        mock_tz_catalog: Catálogo simulado de fusos horários.
        base_run_cfg: Configuração padrão da eleição.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(data_dir=tmp_path / "data")
    provider = BulkZipArtifactProvider(
        base_run_cfg,
        settings,
        mock_tz_catalog,
        allow_remote_download=False,
    )
    with pytest.raises(ContractValidationError, match="Pacote ZIP estadual ausente"):
        async for _ in provider.stream_uf("SP"):
            pass


@pytest.mark.asyncio
async def test_bulk_zip_provider_remote_stream_download(
    tmp_path: Path,
    mock_tz_catalog: TimezoneCatalog,
    base_run_cfg: ElectionRunConfig,
) -> None:
    """Verifica streaming remoto para arquivo temporário e limpeza posterior.

    Args:
        tmp_path: Diretório temporário fornecido pelo pytest.
        mock_tz_catalog: Catálogo simulado de fusos horários.
        base_run_cfg: Configuração padrão da eleição.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(data_dir=tmp_path / "data")

    # Monta ZIP em memória para resposta HTTP simulada
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w") as zf:
        zf.writestr("o00406-7107200010101.logjez", b"downloaded log content")
    zip_bytes = mem_zip.getvalue()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=zip_bytes)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = BulkZipArtifactProvider(
        base_run_cfg,
        settings,
        mock_tz_catalog,
        http_client=client,
        allow_remote_download=True,
    )

    results = [item async for item in provider.stream_uf("SP")]
    assert len(results) == 1
    assert isinstance(results[0], SectionArtifactBundle)
    assert results[0].secao == 101
    await client.aclose()
