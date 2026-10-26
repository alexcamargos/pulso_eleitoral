"""Subsistema de extração binária in-memory, FSM e reconciliação `.bu` (`agent-parser`).

Implementa integralmente os requisitos `REQ-PAR-01`, `REQ-PAR-02` e `REQ-PAR-03`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pulso_eleitoral.parser.archive import (
    extract_and_merge_section_logs,
    extract_logd_buffers,
)
from pulso_eleitoral.parser.bu_reconciler import (
    BuReconciliationData,
    decode_bu_metrics,
)
from pulso_eleitoral.parser.engine import parse_section_bundle
from pulso_eleitoral.parser.fsm import FsmExecutionResult, run_log_fsm
from pulso_eleitoral.parser.patterns import (
    CanonicalEvent,
    LogPatternProfile,
    load_pattern_profile,
)

__all__ = [
    "BuReconciliationData",
    "CanonicalEvent",
    "FsmExecutionResult",
    "LogPatternProfile",
    "decode_bu_metrics",
    "extract_and_merge_section_logs",
    "extract_logd_buffers",
    "load_pattern_profile",
    "parse_section_bundle",
    "run_log_fsm",
]
