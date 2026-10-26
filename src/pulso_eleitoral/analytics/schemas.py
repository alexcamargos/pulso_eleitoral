"""Schemas colunares estritos Polars para persistência analítica (`REQ-ANA-01`).

Define os esquemas colunares `RAW_SECTION_METRICS_SCHEMA` (32 colunas) e
`UNPROCESSED_SECTIONS_SCHEMA` (14 colunas) segundo `specs/03`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import polars as pl

RAW_SECTION_METRICS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "ano_eleicao": pl.Int16,
    "turno": pl.Int8,
    "pleito_id": pl.Int32,
    "uf": pl.String,
    "municipio_cod": pl.Int32,
    "municipio_ibge": pl.Int32,
    "municipio_nome": pl.String,
    "zona": pl.Int16,
    "secao": pl.Int16,
    "fuso_horario_offset_brt": pl.Int8,
    "cutoff_mode": pl.String,
    "qtd_arquivos_log": pl.Int8,
    "total_aptos": pl.Int32,
    "comparecimento_bu": pl.Int32,
    "total_votos": pl.Int32,
    "divergencia_bu_log": pl.Int32,
    "votos_antes_08h": pl.Int32,
    "votos_ate_17h": pl.Int32,
    "votos_apos_17h": pl.Int32,
    "sem_bio_ate_17h": pl.Int32,
    "sem_bio_apos_17h": pl.Int32,
    "bio_status_indefinido": pl.Int32,
    "tentativas_bio_falhas": pl.Int32,
    "votos_cancelados_suspensos": pl.Int32,
    "qtd_reinicializacoes": pl.Int16,
    "horario_abertura_brt": pl.Datetime("us"),
    "horario_primeiro_voto_brt": pl.Datetime("us"),
    "horario_ultimo_voto_brt": pl.Datetime("us"),
    "horario_encerramento_brt": pl.Datetime("us"),
    "relogio_suspeito": pl.Boolean,
    "voto_apos_encerramento": pl.Boolean,
    "status_processamento": pl.String,
}

UNPROCESSED_SECTIONS_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "ano_eleicao": pl.Int16,
    "turno": pl.Int8,
    "pleito_id": pl.Int32,
    "uf": pl.String,
    "municipio_cod": pl.Int32,
    "zona": pl.Int16,
    "secao": pl.Int16,
    "error_code": pl.String,
    "error_message": pl.String,
    "source_uri": pl.String,
    "sha512_expected": pl.String,
    "sha512_actual": pl.String,
    "attempt_count": pl.Int8,
    "recorded_at": pl.Datetime("us"),
}
