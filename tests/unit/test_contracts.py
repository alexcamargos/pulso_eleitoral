"""Testes unitários dos contratos imutáveis e invariantes matemáticas (`REQ-QA-01`).

Valida a hierarquia de exceções canônicas (`FX-10`) e as Invariantes 1 a 6
definidas em `specs.md` Seção 6 sobre os modelos de handoff.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from pulso_eleitoral.contracts import (
    ContractValidationError,
    CorruptArchiveError,
    ErrorCode,
    FlagSeverityTier,
    HashMismatchError,
    HttpExhaustedError,
    IngestionCheckpoint,
    InvariantViolationError,
    LogArtifactPayload,
    LogParseError,
    MissingLogError,
    MunicipalityTzInfo,
    ParsedSectionMetrics,
    ProcessingStatus,
    SectionArtifactBundle,
    UnknownMunicipalityTimezoneError,
    UnprocessedSectionError,
)


def test_section_audit_exceptions_preserve_canonical_codes() -> None:
    """Verifica se cada exceção de seção carrega o `ErrorCode` e metadados exatos.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    missing = MissingLogError("ausente", source_uri="https://tse/1")
    corrupt = CorruptArchiveError("truncado", source_uri="sp.zip")
    mismatch = HashMismatchError(
        "divergente",
        source_uri="https://tse/log",
        sha512_expected="aa",
        sha512_actual="bb",
        attempt_count=3,
    )
    parse_err = LogParseError("erro tsv", source_uri="logd.dat")
    http_err = HttpExhaustedError(
        "timeout", source_uri="https://tse/aux", attempt_count=5
    )
    tz_err = UnknownMunicipalityTimezoneError("am", 99999)
    contract_err = ContractValidationError("schema invalido")

    assert missing.error_code == ErrorCode.MISSING_LOG
    assert corrupt.error_code == ErrorCode.CORRUPT_ARCHIVE
    assert mismatch.error_code == ErrorCode.HASH_MISMATCH
    assert mismatch.sha512_expected == "aa"
    assert mismatch.sha512_actual == "bb"
    assert mismatch.attempt_count == 3
    assert parse_err.error_code == ErrorCode.PARSE_ERROR
    assert http_err.error_code == ErrorCode.HTTP_EXHAUSTED
    assert tz_err.uf == "AM"
    assert tz_err.municipio_cod == 99999
    assert "99999" in tz_err.message
    assert contract_err.message == "schema invalido"
    assert FlagSeverityTier.TIER_3_CRITICAL_ANOMALY.value == "TIER_3_CRITICAL_ANOMALY"


def test_municipality_tz_info_rejects_invalid_brt_offset() -> None:
    """Garante falha imediata quando `fuso_horario_offset_brt` foge de `{-2, -1, 0, 1}`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    with pytest.raises(InvariantViolationError, match="Offset BRT inválido"):
        MunicipalityTzInfo(
            municipio_cod_tse=71072,
            municipio_cod_ibge=3550308,
            uf="SP",
            municipio_nome="SAO PAULO",
            iana_timezone="America/Sao_Paulo",
            fuso_horario_offset_brt=-3,
        )


def test_checkpoint_constant_time_lookup_and_bundle_immutability() -> None:
    """Verifica consulta em $O(1)$ de `IngestionCheckpoint` e imutabilidade do bundle.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    checkpoint = IngestionCheckpoint(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="AC",
        completed_sections=frozenset({(1392, 1, 10), (1392, 1, 11)}),
    )
    assert checkpoint.is_completed(1392, 1, 10) is True
    assert checkpoint.is_completed(1392, 1, 12) is False

    payload = LogArtifactPayload(
        filename="a.logjez", raw_bytes=b"123", sha512_expected="f0"
    )
    bundle = SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode="UNIFIED_BRT",
        uf="AC",
        municipio_cod=1392,
        municipio_ibge=1200401,
        municipio_nome="RIO BRANCO",
        zona=1,
        secao=10,
        fuso_horario_offset_brt=-2,
        total_aptos_manifest=350,
        log_artifacts=(payload,),
    )
    assert bundle.log_artifacts[0].filename == "a.logjez"


def test_valid_metrics_passes_all_invariants_and_exports_32_columns(
    sample_valid_metrics: ParsedSectionMetrics,
) -> None:
    """Confirma aprovação nas invariantes 1..5 e mapeamento exato de 32 colunas.

    Args:
        sample_valid_metrics: Fixture de seção válida (`FX-01`).

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    sample_valid_metrics.validate_invariants()
    row = sample_valid_metrics.to_metrics_row()
    assert len(row) == 32
    assert row["status_processamento"] == ProcessingStatus.SUCCESS.value


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"total_votos": 11}, "Invariante 1"),
        ({"sem_bio_ate_17h": 11}, "Invariante 2"),
        ({"sem_bio_ate_17h": -1}, "Invariante 2"),
        (
            {"votos_apos_17h": 2, "total_votos": 12, "sem_bio_apos_17h": 3},
            "Invariante 3",
        ),
        (
            {
                "total_votos": 0,
                "votos_ate_17h": 0,
                "sem_bio_ate_17h": 0,
                "horario_ultimo_voto_brt": None,
            },
            "Invariante 4",
        ),
        ({"horario_primeiro_voto_brt": None}, "Invariante 5"),
        (
            {
                "horario_primeiro_voto_brt": datetime(2022, 10, 2, 16, 50, 0),
                "horario_ultimo_voto_brt": datetime(2022, 10, 2, 8, 10, 0),
            },
            "Invariante 5",
        ),
    ],
)
def test_metrics_invariants_detect_every_violation(
    sample_valid_metrics: ParsedSectionMetrics,
    overrides: dict[str, object],
    expected_fragment: str,
) -> None:
    """Testa todas as violações possíveis das Invariantes Matemáticas 1 a 5.

    Args:
        sample_valid_metrics: Métrica base válida a ser perturbada.
        overrides: Campos alterados para induzir violação específica.
        expected_fragment: Trecho esperado na mensagem de `InvariantViolationError`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    broken = replace(sample_valid_metrics, **overrides)  # type: ignore[arg-type]
    with pytest.raises(InvariantViolationError, match=expected_fragment):
        broken.validate_invariants()


def test_mirror_metrics_from_unprocessed_error_satisfies_invariants() -> None:
    """Verifica geração da linha espelho zerada e truncamento de 500 caracteres.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    err = UnprocessedSectionError(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="SP",
        municipio_cod=71072,
        zona=1,
        secao=99,
        error_code=ErrorCode.CORRUPT_ARCHIVE.value,
        error_message="x" * 600,
        recorded_at=datetime(2022, 10, 2, 20, 0, 0),
        source_uri="u" * 600,
        municipio_ibge=3550308,
        municipio_nome="SAO PAULO",
    )
    audit_row = err.to_audit_row()
    assert len(audit_row) == 14
    assert len(str(audit_row["error_message"])) == 500
    assert len(str(audit_row["source_uri"])) == 500

    mirror = ParsedSectionMetrics.from_unprocessed_error(err)
    mirror.validate_invariants()
    assert mirror.total_votos == 0
    assert mirror.status_processamento == ErrorCode.CORRUPT_ARCHIVE.value
