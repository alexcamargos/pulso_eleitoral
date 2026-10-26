# Especificação 04: Contratos de Artefatos JSON Estáticos e Painel SPA

**Agente Responsável:** `agent-frontend-export` (`src/pulso_eleitoral/export/` e `frontend/`)  
**Requisitos Cobertos:** `REQ-EXP-01`, `REQ-WEB-01`

---

## 1. Arquitetura de Exportação Estática (`REQ-EXP-01`)

Para garantir disponibilidade em CDN estática (Cloudflare Pages, GitHub Pages, S3) com zero custo de servidor de banco de dados em produção, o módulo `export` gera arquivos JSON imutáveis validados por modelos **Pydantic v2** (e exporta automaticamente o respectivo JSON Schema Draft 2020-12 para consumo de tipagem no TypeScript).

### 1.1. Árvore de Artefatos Gerados por Pleito
Diretório de saída: `data/exported/ele{ano}/turno{turno}/` (espelhado para `frontend/public/api/v1/ele{ano}/turno{turno}/` durante o build):

```text
api/v1/ele{ano}/turno{turno}/
├── metadata.json                  # Versão do schema, hash do banco, cobertura e parâmetros
├── national_summary.json          # KPIs consolidados do Brasil
├── states_summary.json            # Lista ordenada das 27 UFs com KPIs e baselines
├── municipalities/
│   ├── AC.json                    # Resumo de todos os municípios da UF
│   ├── ...
│   └── TO.json
└── flagged_sections/
    ├── index.json                 # Contadores globais por Tier + Top 1.000 seções prioritárias
    ├── AC.json                    # Seções sinalizadas paginadas/filtradas por UF (Top 2.000/UF)
    ├── ...
    └── TO.json
```

> **Motivação de Engenharia (Proteção de Payload):** Em eleições com ~472.000 seções, dezenas de milhares de seções podem registrar ao menos 1 voto sem biometria em fila pós-17h (`TIER_1`). Um arquivo único `flagged_sections.json` monolítico ultrapassaria `25 MB–40 MB`, degradando severamente dispositivos móveis. A divisão em `flagged_sections/index.json` (resumo + Top 1.000 outliers `TIER_3`/`TIER_2`) + shard por UF mantém cada requisição abaixo de `300 KB` gzipada! (Para retrocompatibilidade literal com consumidores simples, `flagged_sections.json` na raiz é gerado como alias idêntico a `flagged_sections/index.json`).

---

## 2. Contratos Estritos de Payload JSON

Regras globais de serialização (`orjson`):
- Proibido emitir `NaN` ou `Infinity` (converter divisões com denominador zero para `0.0`).
- Todos os percentuais são `float` na escala `0.0` a `100.0` arredondados em `4` casas decimais.
- Todos os timestamps seguem ISO 8601 estrito em Horário de Brasília (`YYYY-MM-DDTHH:MM:SS-03:00`) ou `null`.

### 2.1. `metadata.json`
```json
{
  "schema_version": "1.0.0",
  "pipeline_version": "0.1.0",
  "ano_eleicao": 2022,
  "turno": 1,
  "pleito_id": 406,
  "cutoff_mode": "UNIFIED_BRT",
  "generated_at": "2026-10-26T09:00:00Z",
  "duckdb_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "outlier_thresholds": {
    "min_votos_pos_17h": 10,
    "delta_sem_bio_pp": 15.0,
    "z_score_uf": 3.0
  }
}
```

### 2.2. `national_summary.json`
```json
{
  "ano_eleicao": 2022,
  "turno": 1,
  "total_secoes_manifesto": 472075,
  "total_secoes_analisadas": 471890,
  "total_secoes_nao_processadas": 185,
  "cobertura_secoes_pct": 99.9608,
  "total_aptos_brasil": 156454011,
  "total_votos_brasil": 123682372,
  "votos_ate_17h_brasil": 119850120,
  "votos_apos_17h_brasil": 3832252,
  "sem_bio_ate_17h_brasil": 14382014,
  "sem_bio_apos_17h_brasil": 512430,
  "pct_apos_17h": 3.0985,
  "pct_sem_bio_ate_17h": 12.0000,
  "pct_sem_bio_apos_17h": 13.3715,
  "flagged_counts_by_tier": {
    "TIER_3_CRITICAL_ANOMALY": 12,
    "TIER_2_STATISTICAL_OUTLIER": 438,
    "TIER_1_POST_17H_NO_BIO": 64210
  }
}
```

### 2.3. `states_summary.json`
Objeto raiz `{ "ano_eleicao": int, "turno": int, "states": StateSummaryItem[] }` ordenado alfabeticamente por `uf`:
```json
{
  "ano_eleicao": 2022,
  "turno": 1,
  "states": [
    {
      "uf": "AC",
      "total_secoes_manifesto": 2134,
      "total_secoes_analisadas": 2134,
      "total_secoes_nao_processadas": 0,
      "total_votos": 455903,
      "votos_ate_17h": 452100,
      "votos_apos_17h": 3803,
      "sem_bio_ate_17h": 31647,
      "sem_bio_apos_17h": 289,
      "pct_votos_apos_17h": 0.8342,
      "pct_sem_bio_ate_17h": 7.0000,
      "pct_sem_bio_apos_17h": 7.5993,
      "uf_mean_sem_bio_pos_17h": 7.4120,
      "uf_std_sem_bio_pos_17h": 4.1850,
      "tier_2_outliers_count": 3,
      "tier_3_anomalies_count": 0
    }
  ]
}
```

### 2.4. `flagged_sections.json` (e `flagged_sections/{UF}.json`)
```json
{
  "ano_eleicao": 2022,
  "turno": 1,
  "scope": "NATIONAL_TOP_1000",
  "total_matching_sections": 64660,
  "returned_sections": 1000,
  "items": [
    {
      "uf": "SP",
      "municipio_cod": 71072,
      "municipio_nome": "SAO PAULO",
      "zona": 1,
      "secao": 102,
      "fuso_horario_offset_brt": 0,
      "total_aptos": 398,
      "total_votos": 342,
      "votos_ate_17h": 302,
      "votos_apos_17h": 40,
      "sem_bio_ate_17h": 18,
      "sem_bio_apos_17h": 19,
      "pct_votos_apos_17h": 11.6959,
      "pct_sem_bio_ate_17h": 5.9603,
      "pct_sem_bio_apos_17h": 47.5000,
      "delta_sem_bio_pp": 41.5397,
      "z_score_uf_pos_17h": 5.8421,
      "divergencia_bu_log": 0,
      "relogio_suspeito": false,
      "voto_apos_encerramento": false,
      "horario_ultimo_voto_brt": "2022-10-02T17:48:12-03:00",
      "severidade_sinalizacao": "TIER_2_STATISTICAL_OUTLIER"
    }
  ]
}
```

---

## 3. Especificação Funcional da Interface Web SPA (`REQ-WEB-01`)

### 3.1. Stack e Build
- **Framework:** Next.js (App Router com `output: "export"` — 100% estático) + React 19 + TypeScript estrito + Tailwind CSS.
- **Acessibilidade:** Conformidade WCAG 2.1 AA (navegação completa por teclado, contraste `>= 4.5:1`, tabelas semânticas ordenáveis e rótulos ARIA em gráficos).

### 3.2. Visões e Componentes Obrigatórios
1. **Seletor Global de Pleito/Turno:** Permite alternar entre eleições e turnos exportados (`metadata.json`).
2. **Painel Executivo Nacional (KPI Cards):**
   - Total de votos auditados e cobertura percentual de seções processadas vs. não processadas.
   - Percentual e volume de votos pós-17h (BRT).
   - Comparativo lado a lado: Taxa sem biometria até 17h vs. Taxa sem biometria pós-17h.
   - Contagem de seções sinalizadas segregada claramente por `TIER_3`, `TIER_2` e `TIER_1`.
3. **Visão Comparativa por UF e Drill-down Municipal:**
   - Tabela/gráfico interativo das 27 UFs comparando linha de base pré-17h vs. pós-17h.
   - Ao selecionar uma UF, carrega sob demanda `municipalities/{UF}.json` e `flagged_sections/{UF}.json`.
4. **Explorador Auditável de Seções Sinalizadas:**
   - Filtros por UF, Município, Severidade (`TIER_3`, `TIER_2`, `TIER_1`), volume mínimo pós-17h e busca direta por `Zona + Seção`.
   - Link direto de verificação externa apontando para o portal oficial de resultados do TSE daquela exata seção (`resultados.tse.jus.br`), permitindo auditoria cidadã independente nos dados primários!
5. **Banner e Modal de Transparência Metodológica (Obrigatório):**
   - Explicação técnica clara e apartidária informando:
     1. A regra legal de distribuição de senhas até as 17h para eleitores já presentes na fila;
     2. Como a normalização de fusos horários (`UTC-2` a `UTC-5` -> `BRT`) foi aplicada;
     3. A distinção estatística entre *outlier* quantitativo e irregularidade material;
     4. O hash `SHA-256` do banco auditado e a versão exata do pipeline.
