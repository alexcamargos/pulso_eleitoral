"""Gerenciamento de checkpoints idempotentes sobre partições Parquet (`REQ-ING-02`).

Consulta as partições Hive existentes com pushdown de colunas/predicados no
Polars para construir conjuntos $O(1)$ de seções já processadas com `SUCCESS`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from pulso_eleitoral.contracts.exceptions import ProcessingStatus
from pulso_eleitoral.contracts.models import IngestionCheckpoint


class CheckpointStore:
    """Leitor idempotente de seções já consolidadas nas partições Parquet.

    Args:
        processed_dir: Diretório raiz `data/processed` contendo partições Hive.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(self, processed_dir: Path) -> None:
        """Inicializa o repositório de leitura de checkpoints.

        Args:
            processed_dir: Caminho raiz das partições Parquet (`data/processed`).

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._processed_dir = processed_dir

    def load_uf_checkpoint(
        self,
        *,
        ano_eleicao: int,
        turno: int,
        pleito_id: int,
        uf: str,
        force_reprocess: bool = False,
    ) -> IngestionCheckpoint:
        """Carrega o conjunto de seções `SUCCESS` de uma UF em $O(1)$ de consulta.

        Args:
            ano_eleicao: Ano oficial do pleito.
            turno: Número do turno (`1` ou `2`).
            pleito_id: Código numérico do pleito no TSE.
            uf: Sigla da UF em 2 letras.
            force_reprocess: Se `True`, ignora partições prévias e retorna vazio.

        Returns:
            `IngestionCheckpoint` imutável para filtragem durante a ingestão.

        Raises:
            Nenhum.
        """
        norm_uf = uf.strip().upper()
        if force_reprocess:
            return IngestionCheckpoint(
                ano_eleicao=ano_eleicao,
                turno=turno,
                pleito_id=pleito_id,
                uf=norm_uf,
                completed_sections=frozenset(),
            )

        uf_dir = (
            self._processed_dir
            / f"ano={ano_eleicao}"
            / f"turno={turno}"
            / f"uf={norm_uf}"
        )
        parquet_files = (
            sorted(
                p
                for p in uf_dir.glob("*.parquet")
                if not p.name.endswith(".tmp.parquet")
            )
            if uf_dir.is_dir()
            else []
        )

        if not parquet_files:
            return IngestionCheckpoint(
                ano_eleicao=ano_eleicao,
                turno=turno,
                pleito_id=pleito_id,
                uf=norm_uf,
                completed_sections=frozenset(),
            )

        df = (
            pl.scan_parquet(parquet_files, hive_partitioning=False)
            .filter(
                (pl.col("pleito_id") == pleito_id)
                & (pl.col("status_processamento") == ProcessingStatus.SUCCESS.value)
            )
            .select(["municipio_cod", "zona", "secao"])
            .collect()
        )
        completed = frozenset(
            (int(m), int(z), int(s))
            for m, z, s in zip(
                df["municipio_cod"].to_list(),
                df["zona"].to_list(),
                df["secao"].to_list(),
                strict=True,
            )
        )
        return IngestionCheckpoint(
            ano_eleicao=ano_eleicao,
            turno=turno,
            pleito_id=pleito_id,
            uf=norm_uf,
            completed_sections=completed,
        )
