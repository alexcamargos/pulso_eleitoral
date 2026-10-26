"""Pacote raiz da plataforma de auditoria determinística Pulso Eleitoral.

Implementa o pipeline orientado por especificações (SDD) cobrindo ingestão
(`REQ-ING-01`..`03`), parsing binário e FSM (`REQ-PAR-01`..`03`), motor colunar
Polars/DuckDB (`REQ-ANA-01`..`02`) e exportação estática (`REQ-EXP-01`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__: str = "0.1.0"
