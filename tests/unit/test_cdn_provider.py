"""Testes unitários de ingestão assíncrona via CDN Oficial TSE (`REQ-ING-01`).

Valida `CdnArtifactProvider` com respostas HTTP mockadas, controle de retentativas
com Full Jitter, Circuit Breaker, verificação SHA-512 e resiliência a 404/5xx.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import random

import httpx
import orjson
import pytest

from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings
from pulso_eleitoral.contracts.models import (
    IngestionCheckpoint,
    MunicipalityTzInfo,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.ingestion.cdn_provider import CdnArtifactProvider
from pulso_eleitoral.ingestion.integrity import compute_sha512_hex
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog


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
        30015: MunicipalityTzInfo(
            municipio_cod_tse=30015,
            municipio_cod_ibge=2605459,
            uf="PE",
            municipio_nome="FERNANDO DE NORONHA",
            iana_timezone="America/Noronha",
            fuso_horario_offset_brt=1,
        ),
        71072: MunicipalityTzInfo(
            municipio_cod_tse=71072,
            municipio_cod_ibge=3550308,
            uf="SP",
            municipio_nome="SAO PAULO",
            iana_timezone="America/Sao_Paulo",
            fuso_horario_offset_brt=0,
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
        ufs=("PE",),
    )


def test_cdn_provider_url_builders(
    base_run_cfg: ElectionRunConfig,
    mock_tz_catalog: TimezoneCatalog,
) -> None:
    """Verifica formatação correta de URLs hierárquicas do CDN do TSE.

    Args:
        base_run_cfg: Configuração da eleição.
        mock_tz_catalog: Catálogo de fusos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings()
    provider = CdnArtifactProvider(base_run_cfg, settings, mock_tz_catalog)

    cs_url = provider.build_cs_url("PE")
    assert cs_url.endswith("/config/pe/pe-p000406-cs.json")

    aux_url = provider.build_aux_url("PE", 30015, 1, 1)
    assert aux_url.endswith(
        "/dados/pe/30015/0001/0001/p000406-pe-m30015-z0001-s0001-aux.json"
    )

    art_url = provider.build_artifact_url(
        "PE", 30015, 1, 1, "hashdir123", "o00406-3001500010001.logjez"
    )
    assert art_url.endswith("/hashdir123/o00406-3001500010001.logjez")


@pytest.mark.asyncio
async def test_cdn_provider_successful_streaming(
    base_run_cfg: ElectionRunConfig,
    mock_tz_catalog: TimezoneCatalog,
) -> None:
    """Verifica fluxo completo de sucesso: -cs.json -> -aux.json -> .logjez / .bu.

    Args:
        base_run_cfg: Configuração da eleição.
        mock_tz_catalog: Catálogo de fusos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(http_max_retries=2)
    fake_log_bytes = b"fake log contents"
    fake_bu_bytes = b"fake bu contents"
    log_sha = compute_sha512_hex(fake_log_bytes)

    cs_data = {
        "abr": [
            {
                "cd": "PE",
                "mu": [
                    {
                        "cd": "30015",
                        "nm": "FERNANDO DE NORONHA",
                        "zon": [{"cd": "0001", "sec": [{"ns": "0001"}]}],
                    }
                ],
            }
        ]
    }
    aux_data = {
        "aptos": 250,
        "hashes": [
            {
                "hash": "media_hash_abc",
                "nmarq": [
                    {"nm": "o00406-3001500010001.logjez", "sha512": log_sha},
                    "o00406-3001500010001.bu",
                ],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if url_str.endswith("cs.json"):
            return httpx.Response(200, content=orjson.dumps(cs_data))
        if url_str.endswith("aux.json"):
            return httpx.Response(200, content=orjson.dumps(aux_data))
        if url_str.endswith(".logjez"):
            return httpx.Response(200, content=fake_log_bytes)
        if url_str.endswith(".bu"):
            return httpx.Response(200, content=fake_bu_bytes)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CdnArtifactProvider(
        base_run_cfg,
        settings,
        mock_tz_catalog,
        http_client=client,
        rng=random.Random(42),
    )

    results = [item async for item in provider.stream_uf("PE")]
    assert len(results) == 1
    bundle = results[0]
    assert isinstance(bundle, SectionArtifactBundle)
    assert bundle.municipio_cod == 30015
    assert bundle.zona == 1
    assert bundle.secao == 1
    assert bundle.total_aptos_manifest == 250
    assert len(bundle.log_artifacts) == 1
    assert bundle.log_artifacts[0].raw_bytes == fake_log_bytes
    assert bundle.bu_raw_bytes == fake_bu_bytes
    await client.aclose()


@pytest.mark.asyncio
async def test_cdn_provider_hash_mismatch_and_retry(
    base_run_cfg: ElectionRunConfig,
    mock_tz_catalog: TimezoneCatalog,
) -> None:
    """Verifica que divergência de SHA-512 gera UnprocessedSectionError.

    Testa se retentativas de hash ocorrem antes de emitir erro auditável.

    Args:
        base_run_cfg: Configuração da eleição.
        mock_tz_catalog: Catálogo de fusos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(http_max_retries=2)
    cs_data = {
        "mu": [
            {
                "cd": "30015",
                "zon": [{"cd": "0001", "sec": ["0001"]}],
            }
        ]
    }
    aux_data = {
        "hashes": [
            {
                "hash": "media_hash_abc",
                "nmarq": [
                    {
                        "nm": "o00406-3001500010001.logjez",
                        "sha512": "e" * 128,  # Hash esperado incorreto
                    }
                ],
            }
        ]
    }

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        url_str = str(request.url)
        if url_str.endswith("cs.json"):
            return httpx.Response(200, content=orjson.dumps(cs_data))
        if url_str.endswith("aux.json"):
            return httpx.Response(200, content=orjson.dumps(aux_data))
        if url_str.endswith(".logjez"):
            call_count += 1
            return httpx.Response(200, content=b"corrupted or wrong bytes")
        return httpx.Response(404)

    async def no_delay_sleep(_: float) -> None:
        pass

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CdnArtifactProvider(
        base_run_cfg,
        settings,
        mock_tz_catalog,
        http_client=client,
        sleep_func=no_delay_sleep,
    )

    results = [item async for item in provider.stream_uf("PE")]
    assert len(results) == 1
    err = results[0]
    assert isinstance(err, UnprocessedSectionError)
    assert err.error_code == "HASH_MISMATCH"
    assert call_count == 3  # 1 inicial + 2 retentativas de hash
    await client.aclose()


@pytest.mark.asyncio
async def test_cdn_provider_404_missing_log(
    base_run_cfg: ElectionRunConfig,
    mock_tz_catalog: TimezoneCatalog,
) -> None:
    """Verifica que resposta 404 em .logjez resulta imediatamente em MISSING_LOG.

    Args:
        base_run_cfg: Configuração da eleição.
        mock_tz_catalog: Catálogo de fusos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings(http_max_retries=3)
    cs_data = {
        "mu": [
            {
                "cd": "30015",
                "zon": [{"cd": "0001", "sec": ["0001"]}],
            }
        ]
    }
    aux_data = {
        "hashes": [
            {
                "hash": "hash_dir_1",
                "nmarq": ["o00406-3001500010001.logjez"],
            }
        ]
    }

    log_tries = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal log_tries
        url_str = str(request.url)
        if url_str.endswith("cs.json"):
            return httpx.Response(200, content=orjson.dumps(cs_data))
        if url_str.endswith("aux.json"):
            return httpx.Response(200, content=orjson.dumps(aux_data))
        if url_str.endswith(".logjez"):
            log_tries += 1
            return httpx.Response(404)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CdnArtifactProvider(
        base_run_cfg,
        settings,
        mock_tz_catalog,
        http_client=client,
    )

    results = [item async for item in provider.stream_uf("PE")]
    assert len(results) == 1
    err = results[0]
    assert isinstance(err, UnprocessedSectionError)
    assert err.error_code == "MISSING_LOG"
    assert log_tries == 1  # 404 definitivo não é retentado
    await client.aclose()


@pytest.mark.asyncio
async def test_cdn_provider_skips_checkpoint(
    base_run_cfg: ElectionRunConfig,
    mock_tz_catalog: TimezoneCatalog,
) -> None:
    """Verifica que seções presentes no checkpoint são puladas sem requisições HTTP.

    Args:
        base_run_cfg: Configuração da eleição.
        mock_tz_catalog: Catálogo de fusos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings()
    cs_data = {
        "mu": [
            {
                "cd": "30015",
                "zon": [{"cd": "0001", "sec": ["0001"]}],
            }
        ]
    }

    aux_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal aux_called
        url_str = str(request.url)
        if url_str.endswith("cs.json"):
            return httpx.Response(200, content=orjson.dumps(cs_data))
        if url_str.endswith("aux.json"):
            aux_called = True
        return httpx.Response(200)

    checkpoint = IngestionCheckpoint(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="PE",
        completed_sections=frozenset({(30015, 1, 1)}),
    )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CdnArtifactProvider(
        base_run_cfg,
        settings,
        mock_tz_catalog,
        http_client=client,
    )

    results = [item async for item in provider.stream_uf("PE", checkpoint)]
    assert len(results) == 0
    assert aux_called is False
    await client.aclose()


def test_cdn_provider_extracts_aux_targets_2026_arq_format() -> None:
    """Verifica extração de alvos .log.jez e .bu.dat usando formato 'arq' do ciclo 2026.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    aux_payload = {
        "dg": "25/10/2026",
        "hg": "20:31:31",
        "hashes": [
            {
                "hash": "test_hash_dir",
                "arq": [
                    {"nm": "o03221ac0107400040001-rdv.dat", "tp": "rdv"},
                    {"nm": "o03221ac0107400040001-vota.vsc", "tp": "vota"},
                    {"nm": "o03221ac0107400040001-bu.dat", "tp": "bu"},
                    {"nm": "o03221ac0107400040001-log.jez", "tp": "log"},
                ],
            }
        ],
    }
    raw_bytes = orjson.dumps(aux_payload)
    _aptos, log_targets, bu_targets = CdnArtifactProvider._extract_aux_targets(
        raw_bytes,
        "https://resultados.tse.jus.br/test-aux.json",
    )
    assert len(log_targets) == 1
    assert log_targets[0][0] == "test_hash_dir"
    assert log_targets[0][1] == "o03221ac0107400040001-log.jez"

    assert len(bu_targets) == 1
    assert bu_targets[0][0] == "test_hash_dir"
    assert bu_targets[0][1] == "o03221ac0107400040001-bu.dat"


@pytest.mark.asyncio
async def test_cdn_provider_cs_url_404_informative_message(
    base_run_cfg: ElectionRunConfig,
    mock_tz_catalog: TimezoneCatalog,
) -> None:
    """Confirma erro explicativo indicando '--source zip' quando índice é 404.

    Args:
        base_run_cfg: Configuração da eleição.
        mock_tz_catalog: Catálogo de fusos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    settings = PipelineSettings()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CdnArtifactProvider(
        base_run_cfg,
        settings,
        mock_tz_catalog,
        http_client=client,
    )

    with pytest.raises(Exception, match="Índice estadual") as exc_info:
        _ = [item async for item in provider.stream_uf("PE")]

    assert "--source zip" in str(exc_info.value)
    await client.aclose()
