# Pulso Eleitoral — TSE Audit Pipeline

Plataforma ETL, analítica colunar e de visualização estática de alta performance para auditoria técnica, determinística e reproduzível dos logs públicos de urnas eletrônicas (`.logjez` / `logd.dat`) e Boletins de Urna (`.bu`) disponibilizados pelo Tribunal Superior Eleitoral (TSE).

Permite quantificar com rigor estatístico:
- Votos computados antes (`< 17:00:00`) e a partir (`>= 17:00:00`) do horário oficial de encerramento normalizado para o Horário de Brasília (BRT / UTC-3).
- Proporção de eleitores habilitados por biometria vs. habilitação manual pelo mesário em cada faixa horária.
- Reconciliação entre total de votos computados no log (`logd.dat`) e comparecimento oficial registrado no Boletim de Urna (`.bu`), além de detecção de anomalias de relógio interno (RTC).
- Sumarização e classificação multinível de seções atípicas (*outliers* estatísticos e anomalias operacionais) em granularidade nacional, estadual (UF), municipal e por seção eleitoral.

---

## 1. Arquitetura do Sistema e Pipeline

```
                              +-------------------------------------------------+
                              |  Fontes Oficiais TSE (CDN / Dados Abertos ZIP)  |
                              +-------------------------------------------------+
                                                       |
                                                       v
                                    +------------------------------------+
                                    |    Provedor Ingestão Assíncrono    |
                                    |   (SHA-512, Rate Limit, Retries)   |
                                    +------------------------------------+
                                                       |
                                                       v
                                    +------------------------------------+
                                    |       Motor de Parsing & FSM       |
                                    |  (7z/ZIP in-memory, ISO-8859-1)    |
                                    +------------------------------------+
                                                       |
                                                       v
                                    +------------------------------------+
                                    |       Partições Parquet ZSTD       |
                                    |     (Hive: ano/turno/uf/part-*)    |
                                    +------------------------------------+
                                                       |
                                                       v
                                    +------------------------------------+
                                    |       Banco Analítico DuckDB       |
                                    |   (4 Views OLAP, Deduplicação)     |
                                    +------------------------------------+
                                                       |
                                                       v
                                    +------------------------------------+
                                    |       Exportador JSON Estático     |
                                    |   (SLA <= 250 KB, Sharding por UF) |
                                    +------------------------------------+
                                                       |
                                                       v
                                    +------------------------------------+
                                    |       Painel SPA Next.js 15        |
                                    |   (React 19, WCAG AA, Static HTML) |
                                    +------------------------------------+
```

### Mapa de Contratos e Especificações (SDD)
- [`AGENTS.MD`](./AGENTS.MD) — Governança de agentes, protocolo Spec-First, padrões PEP 8, tipagem estrita e convenções de commit.
- [`specs.md`](./specs.md) — Especificação técnica mestra e índice de requisitos (`REQ-*`).
- [`specs/01-ingestion-and-sources.md`](./specs/01-ingestion-and-sources.md) — Ingestão CDN HTTP/2, streaming de ZIPs estaduais e dicionário de fusos.
- [`specs/02-log-parser-and-fsm.md`](./specs/02-log-parser-and-fsm.md) — Extração in-memory, Máquina de Estados Finita (FSM) e reconciliação `.bu`.
- [`specs/03-data-schemas-and-analytics.md`](./specs/03-data-schemas-and-analytics.md) — Particionamento Parquet, consolidação DuckDB (`<= 200 MB`) e detecção de outliers.
- [`specs/04-static-api-and-frontend.md`](./specs/04-static-api-and-frontend.md) — JSON Schemas e especificação do painel SPA.
- [`specs/05-testing-evals-and-roadmap.md`](./specs/05-testing-evals-and-roadmap.md) — Fixtures áureas `FX-01`..`FX-10`, CLI `pulso` e critérios DoD.

---

## 2. Instalação e Requisitos

### Pré-requisitos
- **Python** `>= 3.12`
- **Astral `uv`** (gerenciador de dependências e ambiente)
- **Node.js** `>= 20` e **npm** (para build do painel estático)

### Configuração do Ambiente Python
```bash
# Sincronizar dependências no ambiente virtual via uv
uv sync
```

### Configuração do Painel Frontend
```bash
cd frontend
npm install
cd ..
```

---

## 3. Interface de Linha de Comando (`pulso`)

A CLI é invocável via `uv run pulso` com suporte aos seguintes subcomandos:

### 3.1. Ingestão e Processamento (`ingest-parse`)
Executa a obtenção e parsing de seções eleitorais, persistindo partições Parquet:
```bash
# Execução via pacote estadual ZIP (recomendado para lotes grandes)
uv run pulso ingest-parse --ano 2022 --turno 1 --pleito 406 --uf PE --source zip

# Execução via CDN do TSE
uv run pulso ingest-parse --ano 2022 --turno 1 --pleito 406 --uf PE --source cdn --workers 4
```

### 3.2. Consolidação Analítica DuckDB (`consolidate`)
Consolida partições Parquet em um banco DuckDB com deduplicação idempotente e criação das 4 views OLAP:
```bash
uv run pulso consolidate --ano 2022 --turno 1 --db-path data/pulso_eleitoral.duckdb
```

### 3.3. Exportação de Artefatos Estáticos (`export-json`)
Gera artefatos JSON validados por JSON Schema (Draft 2020-12) com orçamento inicial `<= 250 KB`:
```bash
uv run pulso export-json --ano 2022 --turno 1 --pleito 406 --db-path data/pulso_eleitoral.duckdb --out-dir frontend/public/api/v1
```

### 3.4. Auditoria e Verificação Cruzada (`verify`)
Audita integridade matemática (Invariantes 1..6), somas cruzadas (UF == Nacional) e SLA de tamanho do banco (`<= 200 MB`):
```bash
uv run pulso verify --db-path data/pulso_eleitoral.duckdb --json-dir frontend/public/api/v1/ele2022/turno1
```

### 3.5. Pipeline Completo (`run-all`)
Orquestra em sequência `ingest-parse` &rarr; `consolidate` &rarr; `export-json` &rarr; `verify`:
```bash
uv run pulso run-all --ano 2022 --turno 1 --pleito 406 --uf PE --source cdn
```

---

## 4. Metodologia e Critérios de Auditoria

### 4.1. Regra Legal das Filas e Normalização de Horários
- **Direito de Voto às 17h:** Nos termos do Código Eleitoral (Lei nº 4.737/1965, art. 149) e da Resolução TSE nº 23.669/2021 (art. 153), eleitores presentes na fila até as 17h00 têm direito ao voto por distribuição de senhas numeradas.
- **Fuso Horário Unificado:** Em eleições gerais a partir de 2022, o encerramento é unificado no Horário de Brasília (BRT / UTC-3). Seções em fusos `UTC-2` (Fernando de Noronha) até `UTC-5` (Acre e oeste do Amazonas) são normalizadas aritmeticamente com base no catálogo oficial de 5.570 municípios (`resources/dim_municipio_fuso.csv`).

### 4.2. Classificação Multinível de Seções (Tiers)
- **TIER 1 (Informativo):** Seções com voto pós-17h e ao menos 1 eleitor habilitado sem biometria.
- **TIER 2 (Outlier Estatístico):** Seções com desvio estatístico relevante ($\ge 10$ votos pós-17h e $Z$-Score da UF $\ge 3.0\sigma$).
- **TIER 3 (Anomalia Operacional):** Inconsistência material observável no log (discrepância entre total de votos no log e comparecimento no BU, desvio severo do relógio RTC $> 30$ min, ou voto registrado após comando de encerramento).

---

## 5. Interface Web SPA (`frontend/`)

Painel 100% estático desenvolvido em **Next.js 15 (App Router com `output: "export"`)**, **React 19**, **TypeScript estrito** e **Tailwind CSS**, aderente às diretrizes de acessibilidade **WCAG 2.1 AA**:

```bash
cd frontend

# Executar servidor de desenvolvimento
npm run dev

# Validação de tipagem TypeScript estrita
npm run typecheck

# Gerar build estático para deploy em CDN (HTML/CSS/JS exportados para frontend/out/)
npm run build
```

---

## 6. Qualidade, Testes e Verificação (DoD)

O projeto cumpre integralmente os portões de verificação (*Definition of Done*):

```bash
# 1. Linting e conformidade PEP 8
uv run ruff check src tests

# 2. Formatação de código
uv run ruff format --check src tests

# 3. Tipagem estática estrita
uv run mypy --strict src

# 4. Suíte de testes automatizados com cobertura >= 90%
uv run pytest -q --cov=pulso_eleitoral --cov-fail-under=90 -m "not live_tse"

# 5. Smoke test real contra CDN do TSE (Fernando de Noronha)
uv run pytest -q -m live_tse
```

---

## 7. Licença e Transparência Cidadã

Projeto open-source desenvolvido para transparência, reproduzibilidade e controle social do processo eleitoral brasileiro. Todos os dados analisados são de domínio público, providos pelo Tribunal Superior Eleitoral (TSE).
