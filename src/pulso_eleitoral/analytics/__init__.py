"""Subsistema analítico, particionamento Parquet e OLAP DuckDB (`agent-analytics`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pulso_eleitoral.analytics.consolidator import DuckDbConsolidator
from pulso_eleitoral.analytics.invariants import (
    validate_dataframe_invariants,
    validate_denominator_completeness,
)
from pulso_eleitoral.analytics.orchestrator import (
    PipelineOrchestrator,
    UfExecutionSummary,
)
from pulso_eleitoral.analytics.parquet_writer import ParquetBatchWriter
from pulso_eleitoral.analytics.schemas import (
    RAW_SECTION_METRICS_SCHEMA,
    UNPROCESSED_SECTIONS_SCHEMA,
)

__all__ = [
    "RAW_SECTION_METRICS_SCHEMA",
    "UNPROCESSED_SECTIONS_SCHEMA",
    "DuckDbConsolidator",
    "ParquetBatchWriter",
    "PipelineOrchestrator",
    "UfExecutionSummary",
    "validate_dataframe_invariants",
    "validate_denominator_completeness",
]
