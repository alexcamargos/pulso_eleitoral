"""Testes unitários de resiliência HTTP, integridade e checkpoint (`REQ-ING-02`).

Valida `TokenBucketRateLimiter`, `CircuitBreaker`, `compute_full_jitter_delay`,
`verify_artifact_digest` e `CheckpointStore` sobre partições Parquet temporárias.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path

import polars as pl
import pytest

from pulso_eleitoral.config import ElectionRunConfig
from pulso_eleitoral.contracts.exceptions import (
    CorruptArchiveError,
    ProcessingStatus,
)
from pulso_eleitoral.contracts.models import MunicipalityTzInfo
from pulso_eleitoral.ingestion.base import build_ingestion_error
from pulso_eleitoral.ingestion.checkpoint import CheckpointStore
from pulso_eleitoral.ingestion.integrity import (
    compute_sha512_hex,
    verify_artifact_digest,
)
from pulso_eleitoral.ingestion.resilience import (
    CircuitBreaker,
    CircuitState,
    TokenBucketRateLimiter,
    compute_full_jitter_delay,
    compute_rate_limit_delay,
)


def test_integrity_verification_sha512_and_sha256() -> None:
    """Verifica o cálculo de digest SHA-512 e SHA-256 e detecção de divergência.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    payload = b"test payload for checksum"
    digest512 = compute_sha512_hex(payload)
    assert len(digest512) == 128

    valid, calculated = verify_artifact_digest(payload, digest512)
    assert valid is True
    assert calculated == digest512

    valid_upper, _ = verify_artifact_digest(payload, digest512.upper())
    assert valid_upper is True

    valid_empty, _ = verify_artifact_digest(payload, None)
    assert valid_empty is True

    valid_mismatch, calc_mismatch = verify_artifact_digest(payload, "0" * 128)
    assert valid_mismatch is False
    assert calc_mismatch == digest512

    # Teste para digest SHA-256 (64 hex characters)
    import hashlib

    digest256 = hashlib.sha256(payload).hexdigest()
    valid256, calc256 = verify_artifact_digest(payload, digest256)
    assert valid256 is True
    assert calc256 == digest256


def test_full_jitter_delay_calculation() -> None:
    """Verifica que o atraso Full Jitter respeita limites e Retry-After.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    rng = random.Random(42)
    delay1 = compute_full_jitter_delay(1, rng=rng)
    assert 0.0 <= delay1 <= 1.0

    delay_retry_after = compute_full_jitter_delay(1, retry_after_header="5.5", rng=rng)
    assert delay_retry_after >= 5.5

    delay_bad_header = compute_full_jitter_delay(
        1, retry_after_header="invalid", rng=rng
    )
    assert 0.0 <= delay_bad_header <= 1.0

    delay_high_attempt = compute_full_jitter_delay(10, rng=rng)
    assert 0.0 <= delay_high_attempt <= 60.0


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter() -> None:
    """Verifica aquisição de tokens e contenção de vazão sustentada.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    with pytest.raises(ValueError, match="estritamente positivo"):
        TokenBucketRateLimiter(-1.0)

    limiter = TokenBucketRateLimiter(rate_per_sec=100.0, burst=2.0)
    await limiter.acquire()
    await limiter.acquire()
    # Próxima aquisição exigirá espera fracionária mínima
    await limiter.acquire()


@pytest.mark.asyncio
async def test_circuit_breaker_transitions() -> None:
    """Verifica transições CLOSED -> OPEN -> HALF_OPEN -> CLOSED.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=0.05)
    assert breaker.state == CircuitState.CLOSED

    await breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED

    await breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # Dentro da janela de recuperação, o circuito permanece OPEN
    # e before_request aguarda até expirar
    await breaker.before_request()
    assert breaker.state == CircuitState.HALF_OPEN

    # Sucesso fecha o circuito
    await breaker.record_success()
    assert breaker.state == CircuitState.CLOSED

    # Falha em HALF_OPEN reabre imediatamente
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    await asyncio.sleep(0.06)
    await breaker.before_request()
    assert breaker.state == CircuitState.HALF_OPEN
    await breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_build_ingestion_error_structure() -> None:
    """Verifica a conversão de SectionAuditError em UnprocessedSectionError.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    cfg = ElectionRunConfig(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
    )
    tz_info = MunicipalityTzInfo(
        municipio_cod_tse=30015,
        municipio_cod_ibge=2605459,
        uf="PE",
        municipio_nome="FERNANDO DE NORONHA",
        iana_timezone="America/Noronha",
        fuso_horario_offset_brt=1,
    )
    err = CorruptArchiveError(
        "Arquivo corrompido de teste",
        source_uri="http://cdn.test/log.jez",
    )
    unprocessed = build_ingestion_error(
        cfg,
        tz_info,
        zona=1,
        secao=1,
        err=err,
        total_aptos_manifest=150,
    )
    assert unprocessed.error_code == "CORRUPT_ARCHIVE"
    assert unprocessed.total_aptos_manifest == 150
    assert unprocessed.fuso_horario_offset_brt == 1
    audit_row = unprocessed.to_audit_row()
    assert audit_row["municipio_cod"] == 30015


def test_checkpoint_store_reading(tmp_path: Path) -> None:
    """Verifica leitura de seções concluídas nas partições Parquet.

    Args:
        tmp_path: Diretório temporário fornecido pelo fixture pytest.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    processed_dir = tmp_path / "processed"
    store = CheckpointStore(processed_dir)

    # 1. Diretório inexistente retorna checkpoint vazio
    cp_empty = store.load_uf_checkpoint(
        ano_eleicao=2022, turno=1, pleito_id=406, uf="SP"
    )
    assert len(cp_empty.completed_sections) == 0
    assert cp_empty.is_completed(71072, 1, 1) is False

    # 2. Criar partição Parquet fictícia com seções SUCCESS e ERROR
    uf_dir = processed_dir / "ano=2022" / "turno=1" / "uf=SP"
    uf_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        {
            "pleito_id": [406, 406, 406],
            "municipio_cod": [71072, 71072, 71072],
            "zona": [1, 1, 1],
            "secao": [101, 102, 103],
            "status_processamento": [
                ProcessingStatus.SUCCESS.value,
                ProcessingStatus.SUCCESS.value,
                "MISSING_LOG",
            ],
        }
    )
    part_path = uf_dir / "part-406-SP-0001.parquet"
    df.write_parquet(part_path)

    cp = store.load_uf_checkpoint(ano_eleicao=2022, turno=1, pleito_id=406, uf="SP")
    assert len(cp.completed_sections) == 2
    assert cp.is_completed(71072, 1, 101) is True
    assert cp.is_completed(71072, 1, 102) is True
    assert cp.is_completed(71072, 1, 103) is False  # Não é SUCCESS

    # 3. Forçar reprocessamento ignora os arquivos existentes
    cp_forced = store.load_uf_checkpoint(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="SP",
        force_reprocess=True,
    )
    assert len(cp_forced.completed_sections) == 0


def test_rate_limit_delay_calculation() -> None:
    """Verifica atraso substancial e progressivo para HTTP 429.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    rng = random.Random(42)
    # 1. Sem Retry-After: atraso progressivo respeita limites
    delay1 = compute_rate_limit_delay(1, rng=rng)
    assert 5.0 <= delay1 <= 10.0

    delay2 = compute_rate_limit_delay(2, rng=rng)
    assert 10.0 <= delay2 <= 20.0

    delay5 = compute_rate_limit_delay(5, rng=rng)
    assert 25.0 <= delay5 <= 50.0

    delay10 = compute_rate_limit_delay(10, rng=rng)
    assert 50.0 <= delay10 <= 60.0

    delay15 = compute_rate_limit_delay(15, rng=rng)
    assert delay15 == 60.0  # limitada ao teto de 60s

    # 2. Com Retry-After numérico
    delay_header = compute_rate_limit_delay(1, retry_after_header="15.0", rng=rng)
    assert 15.0 <= delay_header <= 17.0

    # 3. Com Retry-After malformado aplica fallback progressivo
    delay_bad = compute_rate_limit_delay(1, retry_after_header="invalid", rng=rng)
    assert 5.0 <= delay_bad <= 10.0


@pytest.mark.asyncio
async def test_token_bucket_cooldown() -> None:
    """Verifica que apply_cooldown retém chamadas subsequentes e zera tokens.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    waited: list[float] = []
    fake_now = 1000.0

    def fake_time() -> float:
        return fake_now

    async def fake_sleep(sec: float) -> None:
        nonlocal fake_now
        waited.append(sec)
        fake_now += sec

    limiter = TokenBucketRateLimiter(
        rate_per_sec=10.0,
        burst=5.0,
        sleep_func=fake_sleep,
        time_func=fake_time,
    )
    # Inicialmente há tokens disponíveis imediatamente
    await limiter.acquire()
    assert len(waited) == 0

    # Aplica resfriamento de 15 segundos
    await limiter.apply_cooldown(15.0)

    # Próxima chamada a acquire deve aguardar a janela de resfriamento
    await limiter.acquire()
    assert len(waited) == 1
    assert waited[0] >= 14.9
    assert fake_now >= 1015.0

