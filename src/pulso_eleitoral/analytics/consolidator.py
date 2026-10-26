"""Consolidador analítico OLAP idempotente em DuckDB (`REQ-ANA-01`, `REQ-ANA-02`).

Consolida partições Parquet no banco de dados DuckDB (`data/pulso_eleitoral.duckdb`),
garantindo ordenação física para máxima compressão RLE (`<= 200 MB`) e criando as
4 visões analíticas canônicas: `summary_national`, `summary_by_uf`,
`summary_by_municipio` e `flagged_sections`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import glob
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb

from pulso_eleitoral.config import PipelineSettings
from pulso_eleitoral.contracts.exceptions import ContractValidationError


class DuckDbConsolidator:
    """Gerenciador de consolidação OLAP e execução de views analíticas.

    Args:
        settings: Configurações de caminhos de banco e partições Parquet.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(self, settings: PipelineSettings) -> None:
        """Inicializa o consolidador com as configurações do pipeline.

        Args:
            settings: Configurações operacionais.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._settings = settings
        self._db_path = settings.db_path

    def consolidate(
        self,
        *,
        parquet_glob: str | None = None,
        audit_glob: str | None = None,
    ) -> Path:
        """Carrega e consolida de forma idempotente os arquivos Parquet no DuckDB.

        Args:
            parquet_glob: Padrão glob customizado para métricas de seções.
            audit_glob: Padrão glob customizado para erros de auditoria.

        Returns:
            Caminho do arquivo `.duckdb` consolidado.

        Raises:
            ContractValidationError: Se nenhum arquivo Parquet for localizado.
        """
        norm_metrics_glob = parquet_glob or str(
            self._settings.processed_dir / "ano=*" / "turno=*" / "uf=*" / "*.parquet"
        ).replace("\\", "/")

        norm_audit_glob = audit_glob or str(
            self._settings.processed_dir / "audit" / "ano=*" / "turno=*" / "*.parquet"
        ).replace("\\", "/")

        found_metrics = [
            p for p in glob.glob(norm_metrics_glob) if not p.endswith(".tmp.parquet")
        ]
        if not found_metrics:
            raise ContractValidationError(
                "Nenhuma partição Parquet localizada para consolidação: "
                f"{norm_metrics_glob}"
            )

        found_audit = [
            p for p in glob.glob(norm_audit_glob) if not p.endswith(".tmp.parquet")
        ]

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(database=str(self._db_path), read_only=False)

        try:
            # 1. Tabela raw_section_metrics com desduplicação idempotente
            con.execute(
                f"""
                CREATE OR REPLACE TABLE raw_section_metrics AS
                SELECT * EXCLUDE (rn)
                FROM (
                    SELECT
                        *,
                        ROW_NUMBER() OVER (
                            PARTITION BY ano_eleicao, turno, pleito_id, uf,
                                         municipio_cod, zona, secao
                            ORDER BY (status_processamento = 'SUCCESS') DESC,
                                     qtd_arquivos_log DESC
                        ) AS rn
                    FROM read_parquet({found_metrics!r}, hive_partitioning = false)
                )
                WHERE rn = 1
                ORDER BY ano_eleicao, turno, uf, municipio_cod, zona, secao;
                """
            )

            # 2. Tabela unprocessed_sections
            if found_audit:
                con.execute(
                    f"""
                    CREATE OR REPLACE TABLE unprocessed_sections AS
                    SELECT * EXCLUDE (rn)
                    FROM (
                        SELECT
                            *,
                            ROW_NUMBER() OVER (
                                PARTITION BY ano_eleicao, turno, pleito_id, uf,
                                             municipio_cod, zona, secao
                                ORDER BY recorded_at DESC
                            ) AS rn
                        FROM read_parquet({found_audit!r}, hive_partitioning = false)
                    )
                    WHERE rn = 1
                    ORDER BY ano_eleicao, turno, uf, municipio_cod, zona, secao;
                    """
                )
            else:
                con.execute(
                    """
                    CREATE OR REPLACE TABLE unprocessed_sections (
                        ano_eleicao INT2,
                        turno INT1,
                        pleito_id INT4,
                        uf VARCHAR,
                        municipio_cod INT4,
                        zona INT2,
                        secao INT2,
                        error_code VARCHAR,
                        error_message VARCHAR,
                        source_uri VARCHAR,
                        sha512_expected VARCHAR,
                        sha512_actual VARCHAR,
                        attempt_count INT1,
                        recorded_at TIMESTAMP
                    );
                    """
                )

            # 3. Visão Canônica 1: summary_national
            con.execute(
                """
                CREATE OR REPLACE VIEW summary_national AS
                SELECT
                    ano_eleicao,
                    turno,
                    COUNT(*) AS total_secoes_manifesto,
                    COUNT(*) FILTER (WHERE status_processamento = 'SUCCESS')
                        AS total_secoes_analisadas,
                    COUNT(*) FILTER (WHERE status_processamento <> 'SUCCESS')
                        AS total_secoes_nao_processadas,
                    COALESCE(
                        SUM(total_aptos) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS total_aptos_brasil,
                    COALESCE(
                        SUM(total_votos) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS total_votos_brasil,
                    COALESCE(
                        SUM(votos_ate_17h) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS votos_ate_17h_brasil,
                    COALESCE(
                        SUM(votos_apos_17h) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS votos_apos_17h_brasil,
                    COALESCE(
                        SUM(sem_bio_ate_17h) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS sem_bio_ate_17h_brasil,
                    COALESCE(
                        SUM(sem_bio_apos_17h) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS sem_bio_apos_17h_brasil,
                    ROUND(
                        COALESCE(
                            SUM(votos_apos_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ) * 100.0 / NULLIF(
                                SUM(total_votos) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ),
                                0
                            ),
                            0.0
                        ),
                        4
                    ) AS pct_apos_17h,
                    ROUND(
                        COALESCE(
                            SUM(sem_bio_ate_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ) * 100.0 / NULLIF(
                                SUM(votos_ate_17h) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ),
                                0
                            ),
                            0.0
                        ),
                        4
                    ) AS pct_sem_bio_ate_17h,
                    ROUND(
                        COALESCE(
                            SUM(sem_bio_apos_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ) * 100.0 / NULLIF(
                                SUM(votos_apos_17h) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ),
                                0
                            ),
                            0.0
                        ),
                        4
                    ) AS pct_sem_bio_apos_17h
                FROM raw_section_metrics
                GROUP BY ano_eleicao, turno;
                """
            )

            # 4. Visão Canônica 2: summary_by_uf
            con.execute(
                """
                CREATE OR REPLACE VIEW summary_by_uf AS
                WITH uf_metrics AS (
                    SELECT
                        ano_eleicao,
                        turno,
                        uf,
                        COUNT(*) AS total_secoes_manifesto,
                        COUNT(*) FILTER (WHERE status_processamento = 'SUCCESS')
                            AS total_secoes_analisadas,
                        COUNT(*) FILTER (WHERE status_processamento <> 'SUCCESS')
                            AS total_secoes_nao_processadas,
                        COALESCE(
                            SUM(total_aptos) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ),
                            0
                        ) AS total_aptos_uf,
                        COALESCE(
                            SUM(total_votos) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ),
                            0
                        ) AS total_votos_uf,
                        COALESCE(
                            SUM(votos_ate_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ),
                            0
                        ) AS votos_ate_17h_uf,
                        COALESCE(
                            SUM(votos_apos_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ),
                            0
                        ) AS votos_apos_17h_uf,
                        COALESCE(
                            SUM(sem_bio_ate_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ),
                            0
                        ) AS sem_bio_ate_17h_uf,
                        COALESCE(
                            SUM(sem_bio_apos_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ),
                            0
                        ) AS sem_bio_apos_17h_uf,
                        ROUND(
                            COALESCE(
                                SUM(votos_apos_17h) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ) * 100.0 / NULLIF(
                                    SUM(total_votos) FILTER (
                                        WHERE status_processamento = 'SUCCESS'
                                    ),
                                    0
                                ),
                                0.0
                            ),
                            4
                        ) AS pct_apos_17h,
                        ROUND(
                            COALESCE(
                                SUM(sem_bio_ate_17h) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ) * 100.0 / NULLIF(
                                    SUM(votos_ate_17h) FILTER (
                                        WHERE status_processamento = 'SUCCESS'
                                    ),
                                    0
                                ),
                                0.0
                            ),
                            4
                        ) AS pct_sem_bio_ate_17h,
                        ROUND(
                            COALESCE(
                                SUM(sem_bio_apos_17h) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ) * 100.0 / NULLIF(
                                    SUM(votos_apos_17h) FILTER (
                                        WHERE status_processamento = 'SUCCESS'
                                    ),
                                    0
                                ),
                                0.0
                            ),
                            4
                        ) AS pct_sem_bio_apos_17h
                    FROM raw_section_metrics
                    GROUP BY ano_eleicao, turno, uf
                ),
                uf_dispersions AS (
                    SELECT
                        ano_eleicao,
                        turno,
                        uf,
                        ROUND(
                            AVG(
                                COALESCE(
                                    sem_bio_apos_17h * 100.0
                                    / NULLIF(votos_apos_17h, 0),
                                    0.0
                                )
                            ),
                            4
                        ) AS avg_pct_sem_bio_pos_17h_uf,
                        ROUND(
                            COALESCE(
                                STDDEV_POP(
                                    COALESCE(
                                        sem_bio_apos_17h * 100.0
                                        / NULLIF(votos_apos_17h, 0),
                                        0.0
                                    )
                                ),
                                0.0
                            ),
                            4
                        ) AS stddev_pct_sem_bio_pos_17h_uf
                    FROM raw_section_metrics
                    WHERE status_processamento = 'SUCCESS'
                      AND votos_apos_17h >= 10
                    GROUP BY ano_eleicao, turno, uf
                )
                SELECT
                    m.*,
                    COALESCE(
                        d.avg_pct_sem_bio_pos_17h_uf,
                        0.0
                    ) AS avg_pct_sem_bio_pos_17h_uf,
                    COALESCE(
                        d.stddev_pct_sem_bio_pos_17h_uf,
                        0.0
                    ) AS stddev_pct_sem_bio_pos_17h_uf
                FROM uf_metrics m
                LEFT JOIN uf_dispersions d
                    ON m.ano_eleicao = d.ano_eleicao
                   AND m.turno = d.turno
                   AND m.uf = d.uf
                ORDER BY m.ano_eleicao, m.turno, m.uf;
                """
            )

            # 5. Visão Canônica 3: summary_by_municipio
            con.execute(
                """
                CREATE OR REPLACE VIEW summary_by_municipio AS
                SELECT
                    ano_eleicao,
                    turno,
                    uf,
                    municipio_cod,
                    municipio_ibge,
                    municipio_nome,
                    fuso_horario_offset_brt,
                    COUNT(*) AS total_secoes_manifesto,
                    COUNT(*) FILTER (WHERE status_processamento = 'SUCCESS')
                        AS total_secoes_analisadas,
                    COUNT(*) FILTER (WHERE status_processamento <> 'SUCCESS')
                        AS total_secoes_nao_processadas,
                    COALESCE(
                        SUM(total_aptos) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS total_aptos_municipio,
                    COALESCE(
                        SUM(total_votos) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS total_votos_municipio,
                    COALESCE(
                        SUM(votos_ate_17h) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS votos_ate_17h_municipio,
                    COALESCE(
                        SUM(votos_apos_17h) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS votos_apos_17h_municipio,
                    COALESCE(
                        SUM(sem_bio_ate_17h) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS sem_bio_ate_17h_municipio,
                    COALESCE(
                        SUM(sem_bio_apos_17h) FILTER (
                            WHERE status_processamento = 'SUCCESS'
                        ),
                        0
                    ) AS sem_bio_apos_17h_municipio,
                    ROUND(
                        COALESCE(
                            SUM(votos_apos_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ) * 100.0 / NULLIF(
                                SUM(total_votos) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ),
                                0
                            ),
                            0.0
                        ),
                        4
                    ) AS pct_apos_17h,
                    ROUND(
                        COALESCE(
                            SUM(sem_bio_ate_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ) * 100.0 / NULLIF(
                                SUM(votos_ate_17h) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ),
                                0
                            ),
                            0.0
                        ),
                        4
                    ) AS pct_sem_bio_ate_17h,
                    ROUND(
                        COALESCE(
                            SUM(sem_bio_apos_17h) FILTER (
                                WHERE status_processamento = 'SUCCESS'
                            ) * 100.0 / NULLIF(
                                SUM(votos_apos_17h) FILTER (
                                    WHERE status_processamento = 'SUCCESS'
                                ),
                                0
                            ),
                            0.0
                        ),
                        4
                    ) AS pct_sem_bio_apos_17h
                FROM raw_section_metrics
                GROUP BY
                    ano_eleicao,
                    turno,
                    uf,
                    municipio_cod,
                    municipio_ibge,
                    municipio_nome,
                    fuso_horario_offset_brt
                ORDER BY ano_eleicao, turno, uf, municipio_nome;
                """
            )

            # 6. Visão Canônica 4: flagged_sections (3 Tiers)
            min_votos = self._settings.outlier_thresholds.min_votos_pos_17h
            delta_min = self._settings.outlier_thresholds.delta_sem_bio_pp
            z_min = self._settings.outlier_thresholds.z_score_uf

            con.execute(
                f"""
                CREATE OR REPLACE VIEW flagged_sections AS
                WITH section_rates AS (
                    SELECT
                        m.*,
                        ROUND(
                            COALESCE(
                                m.votos_apos_17h * 100.0 / NULLIF(m.total_votos, 0),
                                0.0
                            ),
                            4
                        ) AS pct_votos_apos_17h,
                        ROUND(
                            COALESCE(
                                m.sem_bio_ate_17h * 100.0 / NULLIF(m.votos_ate_17h, 0),
                                0.0
                            ),
                            4
                        ) AS pct_sem_bio_ate_17h,
                        ROUND(
                            COALESCE(
                                m.sem_bio_apos_17h * 100.0
                                / NULLIF(m.votos_apos_17h, 0),
                                0.0
                            ),
                            4
                        ) AS pct_sem_bio_apos_17h
                    FROM raw_section_metrics m
                    WHERE m.status_processamento = 'SUCCESS'
                ),
                uf_baselines AS (
                    SELECT
                        ano_eleicao,
                        turno,
                        uf,
                        AVG(pct_sem_bio_apos_17h) AS uf_mean_sem_bio_pos_17h,
                        STDDEV_POP(pct_sem_bio_apos_17h) AS uf_std_sem_bio_pos_17h
                    FROM section_rates
                    WHERE votos_apos_17h >= {min_votos}
                    GROUP BY ano_eleicao, turno, uf
                )
                SELECT
                    s.ano_eleicao,
                    s.turno,
                    s.uf,
                    s.municipio_cod,
                    s.municipio_nome,
                    s.zona,
                    s.secao,
                    s.fuso_horario_offset_brt,
                    s.total_aptos,
                    s.total_votos,
                    s.votos_ate_17h,
                    s.votos_apos_17h,
                    s.sem_bio_ate_17h,
                    s.sem_bio_apos_17h,
                    s.pct_votos_apos_17h,
                    s.pct_sem_bio_ate_17h,
                    s.pct_sem_bio_apos_17h,
                    ROUND(s.pct_sem_bio_apos_17h - s.pct_sem_bio_ate_17h, 4)
                        AS delta_sem_bio_pp,
                    ROUND(
                        CASE
                            WHEN s.votos_apos_17h >= {min_votos}
                                 AND COALESCE(b.uf_std_sem_bio_pos_17h, 0) > 0
                            THEN (s.pct_sem_bio_apos_17h - b.uf_mean_sem_bio_pos_17h)
                                 / b.uf_std_sem_bio_pos_17h
                            ELSE 0.0
                        END,
                        4
                    ) AS z_score_uf_pos_17h,
                    s.divergencia_bu_log,
                    s.relogio_suspeito,
                    s.voto_apos_encerramento,
                    s.horario_ultimo_voto_brt,
                    CASE
                        WHEN COALESCE(s.divergencia_bu_log, 0) <> 0
                             OR s.voto_apos_encerramento
                             OR s.relogio_suspeito
                            THEN 'TIER_3_CRITICAL_ANOMALY'
                        WHEN s.votos_apos_17h >= {min_votos}
                             AND (
                                 (s.pct_sem_bio_apos_17h
                                  - s.pct_sem_bio_ate_17h) >= {delta_min}
                                 OR (
                                     COALESCE(b.uf_std_sem_bio_pos_17h, 0) > 0
                                     AND (s.pct_sem_bio_apos_17h
                                          - b.uf_mean_sem_bio_pos_17h)
                                         / b.uf_std_sem_bio_pos_17h >= {z_min}
                                 )
                             )
                            THEN 'TIER_2_STATISTICAL_OUTLIER'
                        ELSE 'TIER_1_POST_17H_NO_BIO'
                    END AS severidade_sinalizacao
                FROM section_rates s
                LEFT JOIN uf_baselines b
                    ON s.ano_eleicao = b.ano_eleicao
                   AND s.turno = b.turno
                   AND s.uf = b.uf
                WHERE s.sem_bio_apos_17h >= 1
                   OR COALESCE(s.divergencia_bu_log, 0) <> 0
                   OR s.voto_apos_encerramento
                   OR s.relogio_suspeito
                ORDER BY
                    CASE severidade_sinalizacao
                        WHEN 'TIER_3_CRITICAL_ANOMALY' THEN 3
                        WHEN 'TIER_2_STATISTICAL_OUTLIER' THEN 2
                        ELSE 1
                    END DESC,
                    s.sem_bio_apos_17h DESC,
                    s.pct_sem_bio_apos_17h DESC,
                    s.uf ASC,
                    s.municipio_cod ASC,
                    s.zona ASC,
                    s.secao ASC;
                """
            )

        finally:
            con.close()

        # Validação do orçamento de armazenamento (<= 200 MB)
        if self._db_path.is_file():
            db_size = self._db_path.stat().st_size
            if db_size > 200 * 1024 * 1024:
                size_mb = db_size / (1024 * 1024)
                raise ContractValidationError(
                    f"Banco DuckDB excedeu o limite de 200 MB: {size_mb:.2f} MB."
                )

        return self._db_path

    def query(
        self,
        sql: str,
        params: Sequence[Any] = (),
    ) -> list[dict[str, Any]]:
        """Executa uma consulta SQL no banco consolidado e retorna dicionários.

        Args:
            sql: Consulta SQL a executar.
            params: Parâmetros parametrizados para substituição segura.

        Returns:
            Lista de dicionários representando as linhas retornadas.

        Raises:
            Nenhum.
        """
        con = duckdb.connect(database=str(self._db_path), read_only=True)
        try:
            rel = con.execute(sql, params)
            cols = [desc[0] for desc in rel.description or []]
            rows = rel.fetchall()
            return [dict(zip(cols, r, strict=True)) for r in rows]
        finally:
            con.close()
