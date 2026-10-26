"""Subsistema de ingestão de artefatos do TSE e resolução de fusos (`agent-ingestion`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pulso_eleitoral.ingestion.base import (
    SectionArtifactProvider,
    build_ingestion_error,
)
from pulso_eleitoral.ingestion.cdn_provider import CdnArtifactProvider
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
)
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog
from pulso_eleitoral.ingestion.zip_provider import BulkZipArtifactProvider

__all__ = [
    "BulkZipArtifactProvider",
    "CdnArtifactProvider",
    "CheckpointStore",
    "CircuitBreaker",
    "CircuitState",
    "SectionArtifactProvider",
    "TimezoneCatalog",
    "TokenBucketRateLimiter",
    "build_ingestion_error",
    "compute_full_jitter_delay",
    "compute_sha512_hex",
    "verify_artifact_digest",
]
