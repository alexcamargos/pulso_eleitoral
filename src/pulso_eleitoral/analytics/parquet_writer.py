"""Escritor atômico de partições Parquet com compressão ZSTD (`REQ-ANA-01`).

Persiste lotes de métricas e erros de auditoria no layout Hive em disco,
utilizando arquivos temporários `.tmp.parquet` seguidos de substituição atômica
(`os.replace`) e validação prévia de invariantes matemáticas.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import polars as pl

from pulso_eleitoral.analytics.invariants import validate_dataframe_invariants
from pulso_eleitoral.analytics.schemas import (
    RAW_SECTION_METRICS_SCHEMA,
    UNPROCESSED_SECTIONS_SCHEMA,
)
from pulso_eleitoral.config import PipelineSettings
from pulso_eleitoral.contracts.models import (
    ParsedSectionMetrics,
    UnprocessedSectionError,
)


class ParquetBatchWriter:
    """Gerencia a escrita atômica e o particionamento Hive de dados processados.

    Args:
        settings: Configurações operacionais contendo o diretório base `data_dir`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(self, settings: PipelineSettings) -> None:
        """Inicializa o escritor com o diretório raiz configurado.

        Args:
            settings: Configurações operacionais do pipeline.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._settings = settings
        self._processed_dir = settings.processed_dir

    def get_metrics_partition_dir(
        self,
        ano_eleicao: int,
        turno: int,
        uf: str,
    ) -> Path:
        """Retorna o diretório particionado Hive para uma UF e turno.

        Args:
            ano_eleicao: Ano do pleito eleitoral.
            turno: Número do turno (`1` ou `2`).
            uf: Sigla da UF em 2 letras.

        Returns:
            Caminho `processed_dir / ano={ano} / turno={turno} / uf={UF}`.

        Raises:
            Nenhum.
        """
        norm_uf = uf.strip().upper()
        return (
            self._processed_dir
            / f"ano={ano_eleicao}"
            / f"turno={turno}"
            / f"uf={norm_uf}"
        )

    def get_audit_partition_dir(
        self,
        ano_eleicao: int,
        turno: int,
    ) -> Path:
        """Retorna o diretório particionado de auditoria para seções não processadas.

        Args:
            ano_eleicao: Ano do pleito eleitoral.
            turno: Número do turno (`1` ou `2`).

        Returns:
            Caminho `processed_dir / audit / ano={ano} / turno={turno}`.

        Raises:
            Nenhum.
        """
        return self._processed_dir / "audit" / f"ano={ano_eleicao}" / f"turno={turno}"

    def get_next_chunk_id(
        self,
        ano_eleicao: int,
        turno: int,
        uf: str,
        pleito_id: int,
    ) -> int:
        """Determina o próximo chunk_id disponível na partição da UF.

        Evita que novas execuções com checkpoint sobrescrevam partições Parquet
        previamente consolidadas.

        Args:
            ano_eleicao: Ano oficial da eleição.
            turno: Turno da eleição.
            uf: Sigla da UF.
            pleito_id: Identificador numérico do pleito.

        Returns:
            Próximo inteiro sequencial (`>= 1`).

        Raises:
            Nenhum.
        """
        part_dir = self.get_metrics_partition_dir(ano_eleicao, turno, uf)
        if not part_dir.exists():
            return 1
        prefix = f"part-{pleito_id}-{uf.strip().upper()}-"
        max_id = 0
        for entry in part_dir.glob(f"{prefix}*.parquet"):
            stem = entry.stem
            if stem.endswith(".tmp"):
                continue
            suffix = stem[len(prefix):]
            if suffix.isdigit():
                max_id = max(max_id, int(suffix))
        return max_id + 1

    def write_metrics_batch(
        self,
        metrics: Sequence[ParsedSectionMetrics],
        *,
        chunk_id: int = 1,
    ) -> Path | None:
        """Valida e escreve atomicamente um lote de métricas de seções em Parquet.

        Args:
            metrics: Sequência de instâncias de `ParsedSectionMetrics`.
            chunk_id: Identificador incremental do chunk dentro da UF.

        Returns:
            Caminho do arquivo `.parquet` consolidado ou `None` se o lote for vazio.

        Raises:
            InvariantViolationError: Se alguma invariante matemática falhar no lote.
        """
        if not metrics:
            return None

        first = metrics[0]
        ano = first.ano_eleicao
        turno = first.turno
        pleito_id = first.pleito_id
        uf = first.uf.strip().upper()

        rows = [item.to_metrics_row() for item in metrics]
        df = pl.DataFrame(rows, schema=RAW_SECTION_METRICS_SCHEMA)

        # Validação vetorizada das Invariantes 1 a 5 antes de persistir em disco
        validate_dataframe_invariants(df)

        part_dir = self.get_metrics_partition_dir(ano, turno, uf)
        part_dir.mkdir(parents=True, exist_ok=True)

        target_file = part_dir / f"part-{pleito_id}-{uf}-{chunk_id:04d}.parquet"
        tmp_file = part_dir / f"part-{pleito_id}-{uf}-{chunk_id:04d}.tmp.parquet"

        df.write_parquet(
            tmp_file,
            compression="zstd",
            compression_level=3,
            statistics=True,
        )
        os.replace(tmp_file, target_file)
        return target_file

    def write_audit_batch(
        self,
        errors: Sequence[UnprocessedSectionError],
    ) -> Path | None:
        """Escreve atomicamente seções com erro em `data/processed/audit/...`.

        Args:
            errors: Sequência de instâncias de `UnprocessedSectionError`.

        Returns:
            Caminho do arquivo `.parquet` gerado ou `None` se a lista for vazia.

        Raises:
            Nenhum.
        """
        if not errors:
            return None

        first = errors[0]
        ano = first.ano_eleicao
        turno = first.turno
        uf = first.uf.strip().upper()

        rows = [err.to_audit_row() for err in errors]
        df = pl.DataFrame(rows, schema=UNPROCESSED_SECTIONS_SCHEMA)

        audit_dir = self.get_audit_partition_dir(ano, turno)
        audit_dir.mkdir(parents=True, exist_ok=True)

        target_file = audit_dir / f"unprocessed_{uf}.parquet"
        tmp_file = audit_dir / f"unprocessed_{uf}.tmp.parquet"

        df.write_parquet(
            tmp_file,
            compression="zstd",
            compression_level=3,
            statistics=True,
        )
        os.replace(tmp_file, target_file)
        return target_file
