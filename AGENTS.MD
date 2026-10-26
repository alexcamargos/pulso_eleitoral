# AGENTS.MD: Governança de Agentes e Desenvolvimento Orientado por Especificações (SDD)

## 1. Visão Geral do Sistema e Missão Analítica
O projeto **Pulso Eleitoral (TSE Audit Pipeline)** é uma plataforma ETL, analítica e de visualização estática de alta performance para auditoria técnica e reproduzível de dados públicos de urnas eletrônicas brasileiras (eleições gerais e municipais) disponibilizados pelo Tribunal Superior Eleitoral (TSE).

O objetivo primordial é processar de forma determinística os pacotes de log de urna (`.logjez` contendo `logd.dat`) e reconciliá-los com os metadados de seção e Boletins de Urna (`.bu`), quantificando com rigor estatístico:
- Votos computados antes (`< 17:00:00`) e a partir (`>= 17:00:00`) do horário oficial de encerramento (normalizado para `America/Sao_Paulo` em eleições unificadas >= 2022, ou fuso local em pleitos não unificados <= 2020).
- Proporção de eleitores habilitados por leitura biométrica vs. habilitação manual/biográfica pelo mesário em cada faixa horária.
- Reconciliação entre total de votos computados no log (`logd.dat`) e comparecimento oficial registrado no Boletim de Urna (`.bu`), além de detecção de desvios de relógio interno (RTC).
- Sumarização e classificação multinível de seções atípicas (*outliers* estatísticos e anomalias operacionais) em granularidade nacional, estadual (UF), municipal e por seção eleitoral.

---

## 2. Protocolo de Desenvolvimento Orientado por Especificações (AI-Native SDD)

Todo agente de IA ou desenvolvedor humano atuando neste repositório **DEVE** seguir estritamente o ciclo **Spec-First**:

1. **Fonte Única da Verdade (*Single Source of Truth*):**
   - Nenhuma funcionalidade, coluna de banco, endpoint JSON ou expressão regular pode ser implementada no código sem estar previamente definida em [`specs.md`](./specs.md) e nos contratos detalhados em [`specs/`](./specs/).
   - Em caso de ambiguidade ou lacuna durante a implementação, o agente **NÃO DEVE adivinhar ou inferir silenciosamente**: deve atualizar a especificação correspondente (ou solicitar alinhamento) antes de codificar.
2. **Rastreabilidade por Identificadores (`REQ-*` e `FX-*`):**
   - Cada módulo, docstring de componente principal e suíte de teste deve referenciar os IDs de requisito (`REQ-ING-*`, `REQ-PAR-*`, `REQ-ANA-*`, `REQ-EXP-*`, `REQ-WEB-*`) e fixtures canônicas (`FX-01` a `FX-10`) que implementa ou valida.
3. **Fluxo Operacional Obrigatório por Tarefa Atômica:**
   - **Passo 1 (Leitura de Contexto Mínimo):** Ler `AGENTS.MD`, `specs.md` e apenas o documento específico em `specs/0X-*.md` pertinente ao escopo da tarefa.
   - **Passo 2 (Contrato e Testes Primeiro — TDD/SDD):** Definir/validar os schemas Pydantic/Polars e escrever os testes funcionais `pytest` cobrindo casos normais, fronteiras e invariantes matemáticas.
   - **Passo 3 (Implementação Isolada):** Implementar o código estritamente dentro das fronteiras de diretório do respectivo agente.
   - **Passo 4 (Portão de Verificação — *Verification Gate*):** Executar linting, checagem estática de tipos e suíte de testes automatizados (`uv run ruff check`, `uv run mypy`, `uv run pytest`).
   - **Passo 5 (Commit Atômico):** Realizar commit granular seguindo Conventional Commits em `pt-BR`.

---

## 3. Topologia Canônica do Repositório e Fronteiras de Escopo

Para evitar colisão entre agentes paralelos e deriva arquitetural, a estrutura de diretórios abaixo é mandatória:

```text
pulso_eleitoral/
├── AGENTS.MD                          # Governança de agentes, padrões e protocolo SDD
├── specs.md                           # Especificação mestra, arquitetura e índice de requisitos
├── specs/                             # Contratos executáveis detalhados por domínio
│   ├── 01-ingestion-and-sources.md    # Fontes TSE (CDN/ZIP), fusos IBGE/TSE, rede e checkpoints
│   ├── 02-log-parser-and-fsm.md       # Extração 7z/ZIP, gramática TSV, regex e FSM de votação
│   ├── 03-data-schemas-and-analytics.md # Schemas Parquet/DuckDB, invariantes e detecção de outliers
│   ├── 04-static-api-and-frontend.md  # JSON Schemas estáticos, SPA Next.js/React e transparência
│   └── 05-testing-evals-and-roadmap.md # Fixtures áureas, critérios Gherkin, CLI e roadmap atômico
├── src/
│   └── pulso_eleitoral/
│       ├── __init__.py
│       ├── cli.py                     # Interface de linha de comando unificada (`pulso`)
│       ├── config.py                  # Configurações tipadas (Pydantic Settings)
│       ├── contracts/                 # Contratos compartilhados imutáveis entre agentes
│       │   ├── models.py              # Dataclasses/Pydantic de handoff entre estágios
│       │   └── exceptions.py          # Hierarquia de exceções e códigos de erro de auditoria
│       ├── ingestion/                 # Escopo exclusivo: `agent-ingestion`
│       ├── parser/                    # Escopo exclusivo: `agent-parser`
│       ├── analytics/                 # Escopo exclusivo: `agent-analytics`
│       └── export/                    # Escopo exclusivo: `agent-frontend-export`
├── resources/
│   ├── asn1/                          # Schemas ASN.1 versionados do Boletim de Urna TSE
│   ├── dim_municipio_fuso.csv         # Tabela versionada de fusos por município TSE/IBGE
│   └── log_patterns/                  # Perfis versionados de regex por ciclo (2020, 2022, 2024, 2026)
├── tests/
│   ├── conftest.py                    # Fixtures nativas pytest compartilhadas
│   ├── fixtures/                      # Logs `logd.dat` sintéticos/anonimizados (`FX-01`..`FX-10`)
│   ├── unit/
│   ├── integration/
│   └── property/                      # Testes de invariantes matemáticas e máquina de estados
├── frontend/                          # Aplicação SPA estática (Next.js/React/TypeScript)
└── data/                              # IGNORADO NO GIT: raw cache opcional, parquet, duckdb, json
```

---

## 4. Papéis, Contratos de Handoff e Especializações dos Agentes

| Agente | Diretório de Escopo | Spec Obrigatória | Entrada (Input Contract) | Saída (Output Contract) |
| :--- | :--- | :--- | :--- | :--- |
| **`agent-ingestion`** | `src/pulso_eleitoral/ingestion/` | [`specs/01-ingestion-and-sources.md`](./specs/01-ingestion-and-sources.md) | `ElectionRunConfig` + Manifesto TSE | Stream de `SectionArtifactBundle` + `IngestionCheckpoint` |
| **`agent-parser`** | `src/pulso_eleitoral/parser/` | [`specs/02-log-parser-and-fsm.md`](./specs/02-log-parser-and-fsm.md) | `SectionArtifactBundle` + `MunicipalityTzInfo` | `ParsedSectionMetrics` \| `UnprocessedSectionError` |
| **`agent-analytics`** | `src/pulso_eleitoral/analytics/` | [`specs/03-data-schemas-and-analytics.md`](./specs/03-data-schemas-and-analytics.md) | Lotes de `ParsedSectionMetrics` e `UnprocessedSectionError` | Partições Parquet ZSTD + Banco DuckDB consolidado |
| **`agent-frontend-export`** | `src/pulso_eleitoral/export/` e `frontend/` | [`specs/04-static-api-and-frontend.md`](./specs/04-static-api-and-frontend.md) | Views analíticas DuckDB | Payloads JSON validados por JSON Schema + Build estático SPA |
| **`agent-qa-verifier`** | `tests/` e `resources/` | [`specs/05-testing-evals-and-roadmap.md`](./specs/05-testing-evals-and-roadmap.md) | Código-fonte + Fixtures `FX-*` | Relatório de cobertura, invariantes e validação fim-a-fim |

### 4.1. Agente 1: Ingestion & Network Engineer (`agent-ingestion`)
- **Foco:** Descoberta de manifestos e obtenção assíncrona resiliente a partir das duas fontes oficiais do TSE:
  1. **Modo CDN (`resultados.tse.jus.br`):** Resolução hierárquica de `-aux.json` por seção e download em memória (`bytes` / `io.BytesIO`) dos artefatos `.logjez` e `.bu`.
  2. **Modo Pacote Estadual (`dadosabertos.tse.jus.br`):** Leitura em *streaming* de arquivos `.zip` estaduais massivos (`bu_imgbu_logjez_rdv_vscmr_*.zip`) via diretório central/stream sequencial, **nunca** carregando o `.zip` estadual inteiro na RAM.
- **Competências:**
  - Controle de concorrência adaptativo (`asyncio.Semaphore`), rate-limiting (Token Bucket), retries exponenciais com *full jitter* e *Circuit Breaker* para HTTP `429`/`5xx`.
  - Validação estrita de integridade via hash `SHA-512` (confrontando o manifesto `-aux.json` antes do parsing).
  - Gerenciamento de *checkpoints* idempotentes para retomada após interrupções sem reprocessamento de seções já consolidadas.

### 4.2. Agente 2: Core Parsing & Binary Specialist (`agent-parser`)
- **Foco:** Descompactação in-memory multiformato (`7z`/LZMA e `ZIP` detectados por *magic bytes*), decodificação `ISO-8859-1` e execução da Máquina de Estados Finita (FSM) sobre `logd.dat` (incluindo múltiplos logs em caso de substituição de urna) e reconciliação opcional com `.bu` (ASN.1).
- **Competências:**
  - Pré-filtragem em nível de `bytes` (`VOTA\t`) para descartar linhas irrelevantes de hardware/sistema sem custo de alocação de strings Python.
  - Perfis de expressões regulares pré-compiladas e versionadas por ciclo eleitoral (`LogPatternProfile`).
  - Máquina de estados determinística à prova de vazamento de estado em cancelamentos de mesário, falhas biométricas seguidas de sucesso, reinicializações de urna e logs de preparação pré-zerésima.
  - Normalização aritmética exata de fuso horário por código de município TSE/IBGE (incluindo os 13 municípios `UTC-5` do Amazonas e Fernando de Noronha `UTC-2`).

### 4.3. Agente 3: Analytical Engine & Pipeline Architect (`agent-analytics`)
- **Foco:** Orquestração multiprocesso limitada por *backpressure*, escrita colunar atômica e motor analítico OLAP.
- **Competências:**
  - Execução paralela CPU-bound via `ProcessPoolExecutor` alimentada por filas com tamanho máximo (*bounded queues*) para respeitar o teto estrito de 8 GB de RAM.
  - Escrita colunar com **Polars** em partições Hive atômicas (`data/processed/ano={ANO}/turno={T}/uf={UF}/part-{batch}.parquet`, compressão ZSTD) seguida de consolidação idempotente (`INSERT OR REPLACE` / `QUALIFY ROW_NUMBER()`) no **DuckDB**.
  - Cálculo das visões nacional, estadual, municipal e classificação multinível de seções sinalizadas (*outliers* estatísticos e anomalias de reconciliação/relógio).

### 4.4. Agente 4: Web & Static Artifact Generator (`agent-frontend-export`)
- **Foco:** Exportação determinística de contratos JSON estáticos e construção da interface web analítica SPA.
- **Competências:**
  - Geração validada de `metadata.json`, `national_summary.json`, `states_summary.json`, `municipalities/{uf}.json` e `flagged_sections.json` (com controle de payload e paginação).
  - Manutenção de paridade estrita entre JSON Schema (Python) e tipos TypeScript (Next.js/React).
  - Implementação de visualizações claras, acessíveis (WCAG AA) e acompanhadas de notas metodológicas neutras e auditáveis sobre o funcionamento legal das filas pós-17h (distribuição de senhas) e limitações dos logs públicos.

### 4.5. Agente 5: QA, Fixtures & Invariant Verifier (`agent-qa-verifier`)
- **Foco:** Garantia de qualidade orientada por especificações, geração de fixtures áureas (`FX-01`..`FX-10`) e validação de invariantes matemáticas fim-a-fim.

---

## 5. Diretrizes de Código, Testes e Governança de Repositório

1. **Padrões Python e Documentação:**
   - **Python >= 3.12** com conformidade estrita à **PEP 8** (validada via `ruff`).
   - **Tipagem Estrita:** 100% das assinaturas de funções, métodos e atributos tipados (`mypy --strict`), utilizando `Pydantic v2` nas fronteiras de I/O e `@dataclass(slots=True, frozen=True)` nos caminhos críticos de CPU/memória.
   - **Google Style Docstrings Obrigatórias:** Todo módulo, classe, método e função deve possuir docstring no padrão Google contendo obrigatoriamente as seções `Args:`, `Returns:` e `Raises:`.
   - **Ordem de Imports:** Biblioteca padrão, pacotes de terceiros e módulos locais, separados por linha em branco.
2. **Ambiente, Dependências e Compatibilidade Multiplataforma (Windows/Linux/macOS):**
   - Gerenciamento exclusivo via **Astral `uv`** (`uv sync`, `uv add`, `uv run`). É proibido sugerir ou utilizar `pip` diretamente.
   - Zero dependência de JVM; priorizar bibliotecas nativas C/Rust (`polars`, `duckdb`, `httpx`/`aiohttp`, `py7zr`, `pydantic`, `orjson`).
   - **Regra Crítica de Plataforma:** Como `uvloop` suporta apenas POSIX (`Linux`/`macOS`), sua declaração no `pyproject.toml` deve usar marcador condicional (`uvloop; sys_platform != 'win32'`), utilizando `winloop` opcional ou `asyncio` nativo no Windows sem quebrar a instalação.
3. **Padrões Estritos de Teste:**
   - **Framework Exclusivo:** `pytest` em 100% da suíte. Todos os testes devem ser baseados em funções e fixtures nativas do `pytest`.
   - **Mocking:** Utilizar exclusivamente `pytest-mock` (fixture `mocker`).
   - **Proibição Absoluta:** É estritamente proibido importar ou utilizar `unittest`, `unittest.TestCase` ou `unittest.mock`.
4. **Resiliência, Auditoria de Falhas e Idempotência:**
   - Arquivos corrompidos, hashes divergentes ou logs ausentes jamais devem abortar o processamento em lote: devem gerar registro estruturado em `unprocessed_sections` com código canônico (`MISSING_LOG`, `CORRUPT_ARCHIVE`, `HASH_MISMATCH`, `PARSE_ERROR`, `HTTP_EXHAUSTED`) e detalhes diagnósticos.
   - Reexecuções do pipeline sobre o mesmo conjunto de entrada devem convergir para estado idêntico no Parquet, DuckDB e JSONs exportados.
5. **Governança de Commits e Higiene do Git:**
   - Commits **granulares e atômicos** (preferencialmente 1 a 2 arquivos coesos por commit).
   - **Conventional Commits em `pt-BR`** no modo imperativo, concisos e sem preâmbulos (`feat`, `fix`, `test`, `docs`, `chore`, `refactor`, `perf`, `ci`, `data`).
   - **Proibição de Versionamento de Dados:** Jamais versionar `data/`, bancos `.duckdb`, credenciais, `.env` ou diretórios de cache/build.
