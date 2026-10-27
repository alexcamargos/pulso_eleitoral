"""Pacote de contratos imutáveis e exceções compartilhadas entre estágios.

Exporta modelos `@dataclass(slots=True, frozen=True)` e a árvore canônica de
exceções auditáveis utilizadas por ingestão, parser, analytics e exportação.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pulso_eleitoral.contracts.exceptions import (
    ContractValidationError,
    CorruptArchiveError,
    ErrorCode,
    HashMismatchError,
    HttpExhaustedError,
    InvariantViolationError,
    LogParseError,
    MissingLogError,
    ProcessingStatus,
    PulsoEleitoralError,
    SectionAuditError,
    UnknownMunicipalityTimezoneError,
)
from pulso_eleitoral.contracts.models import (
    CutoffMode,
    ElectoralImpactReport,
    FlagSeverityTier,
    IngestionCheckpoint,
    LogArtifactPayload,
    MunicipalityTzInfo,
    ParametricRegressionResult,
    ParsedSectionMetrics,
    SectionArtifactBundle,
    SensitivityBoundsResult,
    UnprocessedSectionError,
)

__all__ = [
    "ContractValidationError",
    "CorruptArchiveError",
    "CutoffMode",
    "ElectoralImpactReport",
    "ErrorCode",
    "FlagSeverityTier",
    "HashMismatchError",
    "HttpExhaustedError",
    "IngestionCheckpoint",
    "InvariantViolationError",
    "LogArtifactPayload",
    "LogParseError",
    "MissingLogError",
    "MunicipalityTzInfo",
    "ParametricRegressionResult",
    "ParsedSectionMetrics",
    "ProcessingStatus",
    "PulsoEleitoralError",
    "SectionArtifactBundle",
    "SectionAuditError",
    "SensitivityBoundsResult",
    "UnknownMunicipalityTimezoneError",
    "UnprocessedSectionError",
]
