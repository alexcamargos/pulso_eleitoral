"""Validação vetorizada das Invariantes Matemáticas 1 a 6 (`REQ-ANA-01`).

Aplica expressões vetorizadas em Polars sobre os lotes de métricas calculadas
antes da persistência atômica em Parquet, garantindo a integridade dos dados.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import polars as pl

from pulso_eleitoral.contracts.exceptions import (
    InvariantViolationError,
    ProcessingStatus,
)


def validate_dataframe_invariants(df: pl.DataFrame) -> None:
    """Valida as Invariantes 1 a 5 de forma vetorizada sobre um DataFrame Polars.

    Verifica apenas seções com `status_processamento == 'SUCCESS'`. Seções não
    processadas contêm valores zerados e status de erro canônico.

    Args:
        df: DataFrame contendo as 32 colunas de `RAW_SECTION_METRICS_SCHEMA`.

    Returns:
        Nenhum.

    Raises:
        InvariantViolationError: Se qualquer linha violar uma das 5 invariantes.
    """
    if df.is_empty():
        return

    success_df = df.filter(
        pl.col("status_processamento") == ProcessingStatus.SUCCESS.value
    )
    if success_df.is_empty():
        return

    # Invariante 1: total_votos == votos_ate_17h + votos_apos_17h
    inv1_fails = success_df.filter(
        pl.col("total_votos") != (pl.col("votos_ate_17h") + pl.col("votos_apos_17h"))
    )
    if not inv1_fails.is_empty():
        first = inv1_fails.row(0, named=True)
        sec_id = (
            f"{first['uf']}/{first['municipio_cod']}/Z{first['zona']}/S{first['secao']}"
        )
        raise InvariantViolationError(
            f"Invariante 1 violada em {len(inv1_fails)} seção(ões). "
            f"Exemplo: {sec_id}: total_votos={first['total_votos']} != "
            f"ate_17h={first['votos_ate_17h']} + pos_17h={first['votos_apos_17h']}."
        )

    # Invariante 2: 0 <= sem_bio_ate_17h <= votos_ate_17h
    inv2_fails = success_df.filter(
        (pl.col("sem_bio_ate_17h") < 0)
        | (pl.col("sem_bio_ate_17h") > pl.col("votos_ate_17h"))
    )
    if not inv2_fails.is_empty():
        first = inv2_fails.row(0, named=True)
        sec_id = (
            f"{first['uf']}/{first['municipio_cod']}/Z{first['zona']}/S{first['secao']}"
        )
        raise InvariantViolationError(
            f"Invariante 2 violada em {len(inv2_fails)} seção(ões). "
            f"Exemplo: {sec_id}: sem_bio_ate_17h={first['sem_bio_ate_17h']} "
            f"fora de [0, {first['votos_ate_17h']}]."
        )

    # Invariante 3: 0 <= sem_bio_apos_17h <= votos_apos_17h
    inv3_fails = success_df.filter(
        (pl.col("sem_bio_apos_17h") < 0)
        | (pl.col("sem_bio_apos_17h") > pl.col("votos_apos_17h"))
    )
    if not inv3_fails.is_empty():
        first = inv3_fails.row(0, named=True)
        sec_id = (
            f"{first['uf']}/{first['municipio_cod']}/Z{first['zona']}/S{first['secao']}"
        )
        raise InvariantViolationError(
            f"Invariante 3 violada em {len(inv3_fails)} seção(ões). "
            f"Exemplo: {sec_id}: sem_bio_apos_17h={first['sem_bio_apos_17h']} "
            f"fora de [0, {first['votos_apos_17h']}]."
        )

    # Invariante 4: total_votos == 0 -> timestamps nulos
    inv4_fails = success_df.filter(
        (pl.col("total_votos") == 0)
        & (
            pl.col("horario_primeiro_voto_brt").is_not_null()
            | pl.col("horario_ultimo_voto_brt").is_not_null()
        )
    )
    if not inv4_fails.is_empty():
        first = inv4_fails.row(0, named=True)
        sec_id = (
            f"{first['uf']}/{first['municipio_cod']}/Z{first['zona']}/S{first['secao']}"
        )
        raise InvariantViolationError(
            f"Invariante 4 violada em {len(inv4_fails)} seção(ões). "
            f"Exemplo: {sec_id}: total_votos == 0 exige timestamps nulos."
        )

    # Invariante 5: total_votos > 0 -> timestamps preenchidos e primeiro <= ultimo
    inv5_fails = success_df.filter(
        (pl.col("total_votos") > 0)
        & (
            pl.col("horario_primeiro_voto_brt").is_null()
            | pl.col("horario_ultimo_voto_brt").is_null()
            | (pl.col("horario_primeiro_voto_brt") > pl.col("horario_ultimo_voto_brt"))
        )
    )
    if not inv5_fails.is_empty():
        first = inv5_fails.row(0, named=True)
        sec_id = (
            f"{first['uf']}/{first['municipio_cod']}/Z{first['zona']}/S{first['secao']}"
        )
        raise InvariantViolationError(
            f"Invariante 5 violada em {len(inv5_fails)} seção(ões). "
            f"Exemplo: {sec_id}: primeiro_voto={first['horario_primeiro_voto_brt']} > "
            f"ultimo_voto={first['horario_ultimo_voto_brt']}."
        )


def validate_denominator_completeness(
    total_manifest: int,
    total_success: int,
    total_errors: int,
) -> None:
    """Valida a Invariante 6: completude do denominador (`total = success + error`).

    Args:
        total_manifest: Total de seções conhecidas via catálogo/manifesto.
        total_success: Total de seções auditadas com `SUCCESS`.
        total_errors: Total de seções registradas em `unprocessed_sections`.

    Returns:
        Nenhum.

    Raises:
        InvariantViolationError: Se a soma diferir do total do manifesto.
    """
    if total_manifest != (total_success + total_errors):
        raise InvariantViolationError(
            f"Invariante 6 violada: total_manifest ({total_manifest}) != "
            f"success ({total_success}) + errors ({total_errors})."
        )
