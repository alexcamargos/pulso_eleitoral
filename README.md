# Pulso Eleitoral — TSE Audit Pipeline

Plataforma ETL, analítica colunar e de visualização estática de alta performance para auditoria técnica, determinística e reproduzível dos logs públicos de urnas eletrônicas (`.logjez` / `logd.dat`) e Boletins de Urna (`.bu`) disponibilizados pelo Tribunal Superior Eleitoral (TSE).

---

## Arquitetura Orientada por Especificações (AI-Native SDD)

Este projeto adota **Desenvolvimento Orientado por Especificações (*Specification-Driven Development* — SDD)** estruturado para execução coordenada por agentes de IA e engenharia de dados auditável.

### Mapa de Documentação e Contratos

- [`AGENTS.MD`](./AGENTS.MD) — Constituição de governança, protocolo *Spec-First*, fronteiras de diretórios por agente, padrões Python/PEP 8/`pytest`/`uv` e política de commits.
- [`specs.md`](./specs.md) — Especificação técnica mestra, matriz de requisitos (`REQ-*`), semântica temporal de fusos horários, invariantes matemáticas e SLAs.
- [`specs/01-ingestion-and-sources.md`](./specs/01-ingestion-and-sources.md) — Provedores de ingestão (CDN `resultados.tse.jus.br` e ZIPs estaduais `dadosabertos.tse.jus.br`), validação `SHA-512`, *checkpoints* e dicionário municipal de fusos (`UTC-2` a `UTC-5`).
- [`specs/02-log-parser-and-fsm.md`](./specs/02-log-parser-and-fsm.md) — Extração in-memory (`7z`/LZMA e `ZIP` via *magic bytes*), gramática TSV do `logd.dat`, perfis versionados de regex, Máquina de Estados Finita (FSM) e reconciliação com `.bu`.
- [`specs/03-data-schemas-and-analytics.md`](./specs/03-data-schemas-and-analytics.md) — Modelagem Polars/Parquet (`ZSTD`), consolidação idempotente em DuckDB (`<= 200 MB`), visões OLAP e classificação multinível de seções sinalizadas (*outliers*).
- [`specs/04-static-api-and-frontend.md`](./specs/04-static-api-and-frontend.md) — JSON Schemas estritos dos artefatos estáticos e especificação funcional/metodológica do painel SPA (Next.js/React).
- [`specs/05-testing-evals-and-roadmap.md`](./specs/05-testing-evals-and-roadmap.md) — Catálogo de fixtures áureas (`FX-01`..`FX-10`), critérios BDD, especificação da CLI `pulso`, portões de qualidade e roadmap em fases atômicas.

---

## Pré-requisitos de Desenvolvimento

- **Python** `>= 3.12`
- **Astral `uv`** para gerenciamento de pacotes e execução isolada
- **Node.js** `>= 20` (para build estático do painel `frontend/` na Fase 5)
