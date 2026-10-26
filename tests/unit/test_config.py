"""Testes unitários das configurações tipadas de pleito e infraestrutura.

Valida derivação automática de `cutoff_mode` (`UNIFIED_BRT` vs `LOCAL_TIME`),
normalização de UFs e leitura de variáveis `PULSO_*` via Pydantic Settings.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pulso_eleitoral.config import (
    DOMESTIC_UFS,
    ElectionRunConfig,
    PipelineSettings,
    SourceMode,
)
from pulso_eleitoral.contracts.models import CutoffMode


def test_election_run_config_derives_unified_brt_for_2022() -> None:
    """Verifica derivação automática para pleito unificado >= 2022 (`pleito_id=406`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    cfg = ElectionRunConfig(ano_eleicao=2022, turno=1, pleito_id=406, ufs="ALL")
    assert cfg.cutoff_mode == CutoffMode.UNIFIED_BRT
    assert cfg.log_pattern_profile == "v2022_2026"
    assert cfg.election_date_iso == "2022-10-02"
    assert cfg.ufs == DOMESTIC_UFS
    assert len(cfg.ufs) == 27


def test_election_run_config_derives_local_time_for_2020_and_parses_csv_ufs() -> None:
    """Verifica modo `LOCAL_TIME` em eleições <= 2020 e parsing CSV de UFs.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    cfg = ElectionRunConfig(
        ano_eleicao=2020,
        turno=1,
        pleito_id=304,
        ufs="sp, ac, am, sp, zz",  # type: ignore[arg-type]
        source_mode=SourceMode.CDN,
    )
    assert cfg.cutoff_mode == CutoffMode.LOCAL_TIME
    assert cfg.log_pattern_profile == "v2020"
    assert cfg.election_date_iso == "2020-11-15"
    assert cfg.ufs == ("AC", "AM", "SP", "ZZ")


def test_election_run_config_accepts_empty_sequence_as_all_domestic_ufs() -> None:
    """Confirma expansão para as 27 UFs quando uma sequência vazia é informada.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    cfg = ElectionRunConfig(ano_eleicao=2024, turno=1, pleito_id=456, ufs=())
    assert cfg.ufs == DOMESTIC_UFS


@pytest.mark.parametrize(
    ("kwargs", "match_msg"),
    [
        (
            {"ano_eleicao": 2022, "turno": 1, "pleito_id": 406, "ufs": "XX"},
            "Siglas de UF inválidas",
        ),
        (
            {"ano_eleicao": 2022, "turno": 1, "pleito_id": 406, "ufs": 123},
            "deve ser string ou sequência",
        ),
        (
            {"ano_eleicao": 2026, "turno": 1, "pleito_id": 999},
            "election_date_iso",
        ),
        (
            {
                "ano_eleicao": 2026,
                "turno": 1,
                "pleito_id": 999,
                "election_date_iso": "2022-10-02",
            },
            "difere de ano_eleicao",
        ),
    ],
)
def test_election_run_config_rejects_invalid_inputs(
    kwargs: dict[str, object],
    match_msg: str,
) -> None:
    """Garante rejeição imediata de siglas inválidas ou datas incoerentes.

    Args:
        kwargs: Parâmetros inválidos submetidos a `ElectionRunConfig`.
        match_msg: Expressão esperada na exceção `ValueError`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    with pytest.raises(ValueError, match=match_msg):
        ElectionRunConfig(**kwargs)  # type: ignore[arg-type]


def test_pipeline_settings_reads_env_and_computes_backpressure_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica leitura de variáveis `PULSO_*` e cálculo de `max_in_flight`.

    Args:
        monkeypatch: Fixture nativa do `pytest` para isolar variáveis de ambiente.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    monkeypatch.setenv("PULSO_WORKERS", "4")
    monkeypatch.setenv("PULSO_DATA_DIR", "custom_data")
    settings = PipelineSettings()
    assert settings.workers == 4
    assert settings.max_in_flight == 64
    assert settings.processed_dir == Path("custom_data") / "processed"
