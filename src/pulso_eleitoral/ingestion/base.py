"""Protocolos abstratos e utilitários compartilhados de ingestão (`REQ-ING-01`).

Define o contrato `SectionArtifactProvider` consumido pelo orquestrador e a
conversão padronizada de falhas de ingestão para `UnprocessedSectionError`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Protocol

from pulso_eleitoral.config import ElectionRunConfig
from pulso_eleitoral.contracts.exceptions import SectionAuditError
from pulso_eleitoral.contracts.models import (
    IngestionCheckpoint,
    MunicipalityTzInfo,
    SectionArtifactBundle,
    UnprocessedSectionError,
)


class SectionArtifactProvider(Protocol):
    """Protocolo assíncrono para obtenção de artefatos por UF (`REQ-ING-01`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def stream_uf(
        self,
        uf: str,
        checkpoint: IngestionCheckpoint | None = None,
    ) -> AsyncIterator[SectionArtifactBundle | UnprocessedSectionError]:
        """Produz assincronamente bundles ou erros estruturados de uma UF.

        Args:
            uf: Sigla da Unidade Federativa em 2 letras.
            checkpoint: Checkpoint opcional com seções já concluídas (`SUCCESS`).

        Returns:
            Iterador assíncrono emitindo `SectionArtifactBundle` ou erro auditável.

        Raises:
            Nenhum.
        """
        ...


def build_ingestion_error(
    run_cfg: ElectionRunConfig,
    tz_info: MunicipalityTzInfo,
    *,
    zona: int,
    secao: int,
    err: SectionAuditError,
    total_aptos_manifest: int | None = None,
) -> UnprocessedSectionError:
    """Converte uma `SectionAuditError` em `UnprocessedSectionError` completo.

    Args:
        run_cfg: Configuração ativa do pleito/turno.
        tz_info: Metadados geográficos e de fuso horário do município.
        zona: Número da zona eleitoral.
        secao: Número da seção eleitoral.
        err: Exceção auditável capturada na rede, hash ou leitura do pacote.
        total_aptos_manifest: Eleitores aptos informados no manifesto, se houver.

    Returns:
        Instância imutável de `UnprocessedSectionError` pronta para persistência.

    Raises:
        Nenhum.
    """
    assert run_cfg.cutoff_mode is not None
    return UnprocessedSectionError(
        ano_eleicao=run_cfg.ano_eleicao,
        turno=run_cfg.turno,
        pleito_id=run_cfg.pleito_id,
        uf=tz_info.uf,
        municipio_cod=tz_info.municipio_cod_tse,
        zona=zona,
        secao=secao,
        error_code=err.error_code.value,
        error_message=err.message,
        recorded_at=datetime.now(UTC).replace(tzinfo=None),
        source_uri=err.source_uri,
        sha512_expected=err.sha512_expected,
        sha512_actual=err.sha512_actual,
        attempt_count=err.attempt_count,
        municipio_ibge=tz_info.municipio_cod_ibge,
        municipio_nome=tz_info.municipio_nome,
        fuso_horario_offset_brt=tz_info.fuso_horario_offset_brt,
        cutoff_mode=run_cfg.cutoff_mode.value,
        total_aptos_manifest=total_aptos_manifest,
    )
