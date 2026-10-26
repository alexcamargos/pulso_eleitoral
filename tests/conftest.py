"""Fixtures nativas `pytest` compartilhadas pela suíte do Pulso Eleitoral.

Fornece instâncias canônicas reutilizáveis para validação dos requisitos
`REQ-ING-01`..`03`, `REQ-PAR-01`..`03`, `REQ-ANA-01`..`02` e `REQ-QA-01`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from pulso_eleitoral.contracts.models import (
    CutoffMode,
    ParsedSectionMetrics,
)
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog


@pytest.fixture(scope="session")
def official_timezone_catalog() -> TimezoneCatalog:
    """Carrega uma única vez por sessão o catálogo oficial `dim_municipio_fuso.csv`.

    Args:
        Nenhum.

    Returns:
        Instância validada de `TimezoneCatalog` contendo os 5.570 municípios.

    Raises:
        Nenhum.
    """
    return TimezoneCatalog.from_csv()


@pytest.fixture
def sample_valid_metrics() -> ParsedSectionMetrics:
    """Retorna uma instância válida de `ParsedSectionMetrics` representando `FX-01`.

    Args:
        Nenhum.

    Returns:
        Instância imutável de `ParsedSectionMetrics` aderente às invariantes 1..5.

    Raises:
        Nenhum.
    """
    return ParsedSectionMetrics(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="SP",
        municipio_cod=71072,
        municipio_ibge=3550308,
        municipio_nome="SAO PAULO",
        zona=1,
        secao=102,
        fuso_horario_offset_brt=0,
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        qtd_arquivos_log=1,
        total_aptos=400,
        comparecimento_bu=10,
        total_votos=10,
        divergencia_bu_log=0,
        votos_antes_08h=0,
        votos_ate_17h=10,
        votos_apos_17h=0,
        sem_bio_ate_17h=2,
        sem_bio_apos_17h=0,
        bio_status_indefinido=0,
        tentativas_bio_falhas=1,
        votos_cancelados_suspensos=0,
        qtd_reinicializacoes=0,
        horario_abertura_brt=datetime(2022, 10, 2, 7, 59, 0),
        horario_primeiro_voto_brt=datetime(2022, 10, 2, 8, 1, 12),
        horario_ultimo_voto_brt=datetime(2022, 10, 2, 16, 45, 30),
        horario_encerramento_brt=datetime(2022, 10, 2, 17, 2, 0),
        relogio_suspeito=False,
        voto_apos_encerramento=False,
    )
