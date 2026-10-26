# Especificação 03: Modelagem Colunar, DuckDB OLAP e Detecção de Outliers

**Agente Responsável:** `agent-analytics` (`src/pulso_eleitoral/analytics/`)  
**Requisitos Cobertos:** `REQ-ANA-01`, `REQ-ANA-02`

---

## 1. Orquestração Multiprocesso e Controle de Memória (`REQ-ANA-01`)

1. **Arquitetura Producer-Workers-Collector:**
   - **Producer (AsyncIO no processo principal):** Obtém `SectionArtifactBundle` e os insere em uma fila limitada (`max_in_flight = workers * 16`, ex.: `128` itens para `8` workers). Se os workers estiverem ocupados, o *backpressure* pausa novas leituras de rede/ZIP automaticamente.
   - **Worker Pool (`concurrent.futures.ProcessPoolExecutor`):** Inicializado uma única vez com `initializer` que carrega `LogPatternProfile` pré-compilado na memória de cada processo filho, evitando serialização repetida.
   - **Collector / Batch Writer:** Acumula objetos `ParsedSectionMetrics` até atingir `batch_size = 10_000` seções (ou término de uma UF), valida todas as invariantes matemáticas em vetor via **Polars** e grava uma partição Parquet atômica.

2. **Escrita Atômica e Particionamento Hive:**
   - Caminho padrão: `data/processed/ano={ano}/turno={turno}/uf={UF}/part-{pleito_id}-{uf}-{chunk_id:04d}.parquet`.
   - Escrita via arquivo temporário `.tmp.parquet` no mesmo volume seguida de `os.replace()` atômico, garantindo que leitores DuckDB nunca encontrem arquivos Parquet truncados em caso de queda abrupta.
   - Compressão obrigatória: `compression="zstd"`, `compression_level=3`, `statistics=True`.

---

## 2. Schema Estrito Polars (`RAW_SECTION_METRICS_SCHEMA`)

```python
import polars as pl

RAW_SECTION_METRICS_SCHEMA: dict[str, pl.DataType] = {
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
```

> **Regra para Seções Não Processadas:** Quando `status_processamento != 'SUCCESS'`, uma linha espelho com contadores zerados (`total_votos = 0`, `votos_ate_17h = 0`, etc.) e `status_processamento = error_code` é gravada em `raw_section_metrics` para completude do denominador de cobertura de seções, enquanto os detalhes completos do erro são gravados em `data/processed/audit/ano={ano}/turno={turno}/unprocessed_{uf}.parquet`.

---

## 3. Consolidação Idempotente no DuckDB e Orçamento de 200 MB

Na etapa de consolidação (`pulso consolidate`), o DuckDB carrega os arquivos Parquet garantindo **idempotência absoluta** mesmo que existam arquivos de lotes reprocessados:

```sql
CREATE OR REPLACE TABLE raw_section_metrics AS
SELECT * EXCLUDE (rn)
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY ano_eleicao, turno, pleito_id, uf, municipio_cod, zona, secao
            ORDER BY (status_processamento = 'SUCCESS') DESC
        ) AS rn
    FROM read_parquet('data/processed/ano=*/turno=*/uf=*/*.parquet', hive_partitioning = false)
)
WHERE rn = 1
ORDER BY ano_eleicao, turno, uf, municipio_cod, zona, secao;
```
*(Ordenar fisicamente por `(ano_eleicao, turno, uf, municipio_cod, zona, secao)` maximiza a compressão de dicionário/RLE interna do DuckDB, mantendo 500.000 linhas confortavelmente abaixo de `45 MB–80 MB`, muito aquém do teto de `200 MB`!)*

---

## 4. Definição SQL Canônica das Visões Analíticas (`REQ-ANA-02`)

### 4.1. Totalizador Nacional (`summary_national`)
```sql
CREATE OR REPLACE VIEW summary_national AS
SELECT
    ano_eleicao,
    turno,
    COUNT(*) AS total_secoes_manifesto,
    COUNT(*) FILTER (WHERE status_processamento = 'SUCCESS') AS total_secoes_analisadas,
    COUNT(*) FILTER (WHERE status_processamento <> 'SUCCESS') AS total_secoes_nao_processadas,
    COALESCE(SUM(total_aptos) FILTER (WHERE status_processamento = 'SUCCESS'), 0) AS total_aptos_brasil,
    COALESCE(SUM(total_votos) FILTER (WHERE status_processamento = 'SUCCESS'), 0) AS total_votos_brasil,
    COALESCE(SUM(votos_ate_17h) FILTER (WHERE status_processamento = 'SUCCESS'), 0) AS votos_ate_17h_brasil,
    COALESCE(SUM(votos_apos_17h) FILTER (WHERE status_processamento = 'SUCCESS'), 0) AS votos_apos_17h_brasil,
    COALESCE(SUM(sem_bio_ate_17h) FILTER (WHERE status_processamento = 'SUCCESS'), 0) AS sem_bio_ate_17h_brasil,
    COALESCE(SUM(sem_bio_apos_17h) FILTER (WHERE status_processamento = 'SUCCESS'), 0) AS sem_bio_apos_17h_brasil,
    ROUND(COALESCE(SUM(votos_apos_17h) FILTER (WHERE status_processamento = 'SUCCESS') * 100.0 / NULLIF(SUM(total_votos) FILTER (WHERE status_processamento = 'SUCCESS'), 0), 0.0), 4) AS pct_apos_17h,
    ROUND(COALESCE(SUM(sem_bio_ate_17h) FILTER (WHERE status_processamento = 'SUCCESS') * 100.0 / NULLIF(SUM(votos_ate_17h) FILTER (WHERE status_processamento = 'SUCCESS'), 0), 0.0), 4) AS pct_sem_bio_ate_17h,
    ROUND(COALESCE(SUM(sem_bio_apos_17h) FILTER (WHERE status_processamento = 'SUCCESS') * 100.0 / NULLIF(SUM(votos_apos_17h) FILTER (WHERE status_processamento = 'SUCCESS'), 0), 0.0), 4) AS pct_sem_bio_apos_17h
FROM raw_section_metrics
GROUP BY ano_eleicao, turno;
```

### 4.2. Totalizador Estadual (`summary_by_uf`) e Municipal (`summary_by_municipio`)
- **`summary_by_uf`:** Agrupa por `(ano_eleicao, turno, uf)`, expondo as mesmas métricas percentuais de `summary_national` mais estatísticas estaduais de dispersão (`avg_pct_sem_bio_pos_17h_uf` e `stddev_pct_sem_bio_pos_17h_uf` calculadas sobre seções com `votos_apos_17h >= 10`) para embasar o Z-Score de outliers.
- **`summary_by_municipio`:** Agrupa por `(ano_eleicao, turno, uf, municipio_cod, municipio_ibge, municipio_nome, fuso_horario_offset_brt)`, permitindo análise municipal sem custo de reagregação no cliente.

### 4.3. Classificação Multinível de Seções Sinalizadas (`flagged_sections`)
Reconcilia o critério literal (`sem_bio_apos_17h >= 1`) com o critério estatístico de limites de controle:

```sql
CREATE OR REPLACE VIEW flagged_sections AS
WITH section_rates AS (
    SELECT
        m.*,
        ROUND(COALESCE(m.votos_apos_17h * 100.0 / NULLIF(m.total_votos, 0), 0.0), 4) AS pct_votos_apos_17h,
        ROUND(COALESCE(m.sem_bio_ate_17h * 100.0 / NULLIF(m.votos_ate_17h, 0), 0.0), 4) AS pct_sem_bio_ate_17h,
        ROUND(COALESCE(m.sem_bio_apos_17h * 100.0 / NULLIF(m.votos_apos_17h, 0), 0.0), 4) AS pct_sem_bio_apos_17h
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
    WHERE votos_apos_17h >= 10
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
    ROUND(s.pct_sem_bio_apos_17h - s.pct_sem_bio_ate_17h, 4) AS delta_sem_bio_pp,
    ROUND(
        CASE
            WHEN s.votos_apos_17h >= 10 AND COALESCE(b.uf_std_sem_bio_pos_17h, 0) > 0
            THEN (s.pct_sem_bio_apos_17h - b.uf_mean_sem_bio_pos_17h) / b.uf_std_sem_bio_pos_17h
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
        WHEN s.votos_apos_17h >= 10
             AND (
                 (s.pct_sem_bio_apos_17h - s.pct_sem_bio_ate_17h) >= 15.0
                 OR (
                     COALESCE(b.uf_std_sem_bio_pos_17h, 0) > 0
                     AND (s.pct_sem_bio_apos_17h - b.uf_mean_sem_bio_pos_17h) / b.uf_std_sem_bio_pos_17h >= 3.0
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
```
