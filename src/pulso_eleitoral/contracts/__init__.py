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
    FlagSeverityTier,
    IngestionCheckpoint,
    LogArtifactPayload,
    MunicipalityTzInfo,
    ParsedSectionMetrics,
    SectionArtifactBundle,
    UnprocessedSectionError,
)

__all__ = [
    "ContractValidationError",
    "CorruptArchiveError",
    "CutoffMode",
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
    "ParsedSectionMetrics",
    "ProcessingStatus",
    "PulsoEleitoralError",
    "SectionArtifactBundle",
    "SectionAuditError",
    "UnknownMunicipalityTimezoneError",
    "UnprocessedSectionError",
]
