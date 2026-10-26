# Especificação 05: Testes, Fixtures Áureas, CLI e Roadmap de Execução SDD

**Agentes Responsáveis:** `agent-qa-verifier` e todos os agentes executores  
**Requisitos Cobertos:** `REQ-QA-01` e governança de qualidade fim-a-fim

---

## 1. Catálogo de Fixtures Áureas (`tests/fixtures/` — `FX-01` a `FX-10`)

Antes de conectar o pipeline à rede do TSE, 100% da lógica de extração, fuso horário, máquina de estados, agregação e exportação deve ser provada sobre **10 cenários sintéticos determinísticos** codificados em `ISO-8859-1` e empacotados em `.7z` e `.zip`:

| ID | Cenário Testado | Entrada Simulada | Resultado Esperado Determinístico |
| :--- | :--- | :--- | :--- |
| `FX-01` | Seção Padrão (`UTC-3`, SP) | 10 votos pré-17h (8 bio, 2 manual), 0 pós-17h, pacote `.logjez` em formato `7z`. | `total=10`, `ate_17h=10`, `apos_17h=0`, `sem_bio_ate=2`, `sem_bio_apos=0`, `status='SUCCESS'`. |
| `FX-02` | Fila Pós-17h na Fronteira Exata | Votos em `16:59:59`, `17:00:00` e `17:00:01` em `DF` (`offset=0`), formato `ZIP`. | `16:59:59` -> `ate_17h`; `17:00:00` e `17:00:01` -> `apos_17h` (`ate_17h=1`, `apos_17h=2`). |
| `FX-03` | Fuso Acre (`UTC-5`, `offset=-2`) | Votos às `14:59:59` locais e `15:00:00` locais em Rio Branco/AC (`UNIFIED_BRT`). | Convertidos para `16:59:59 BRT` (`ate_17h=1`) e `17:00:00 BRT` (`apos_17h=1`). |
| `FX-04` | Fuso Sudoeste AM (`UTC-5`) vs Manaus (`UTC-4`) | Dois logs do AM: Tabatinga (`offset=-2`) às `15:05:00` e Manaus (`offset=-1`) às `15:05:00`. | Tabatinga -> `17:05:00 BRT` (`apos_17h=1`); Manaus -> `16:05:00 BRT` (`ate_17h=1`). |
| `FX-05` | Fuso Fernando de Noronha (`UTC-2`, `offset=+1`) | Voto às `17:30:00` locais em Noronha (`UNIFIED_BRT`). | Convertido para `16:30:00 BRT` (`ate_17h=1`, `apos_17h=0`). |
| `FX-06` | Retentativas Biométricas e Cancelamento | Eleitor 1: 2 `BIO_FAIL` + `BIO_SUCCESS` + voto. Eleitor 2: `BIO_BYPASS` + `VOTER_ABORTED`. Eleitor 3: `BIO_SUCCESS` + voto. | `total_votos=2`, `sem_bio=0`, `tentativas_bio_falhas=2`, `votos_cancelados_suspensos=1` (zero vazamento do Eleitor 2 para o 3!). |
| `FX-07` | Logs de Carga Pré-Eleição + Reinicialização | Votos simulados em `D-3`, abertura oficial em `D`, reboot no meio do expediente em `D`. | Eventos de `D-3` ignorados; `qtd_reinicializacoes=1`; buffer limpo no reboot. |
| `FX-08` | Substituição por Urna de Contingência | Dois `.logjez` na mesma seção com linhas iniciais duplicadas na mídia transferida. | Linhas idênticas deduplicadas; `qtd_arquivos_log=2`; soma exata sem dupla contagem. |
| `FX-09` | Relógio Descalibrado (RTC Reset) e Divergência BU | Voto registrado às `03:15:00` locais (`< 08h`) e `.bu` indicando `comparecimento = 300` vs `298` no log. | `votos_antes_08h >= 1`, `relogio_suspeito=True`, `divergencia_bu_log=2`, classificado como `TIER_3_CRITICAL_ANOMALY`. |
| `FX-10` | Pacotes Corrompidos e Hash Divergente | Bytes truncados (`CorruptArchive`) e payload com `SHA-512` inválido (`HashMismatch`). | Lote não interrompe; registros gravados em `unprocessed_sections` com códigos exatos. |

---

## 2. Critérios de Aceite Comportamentais (BDD / Gherkin)

```gherkin
Funcionalidade: Auditoria determinística e idempotente de seções eleitorais

  Cenário: Isolamento de estado quando mesário cancela habilitação manual
    Dado um arquivo logd.dat onde o Eleitor A recebe habilitação manual sem biometria
    Mas tem sua votação cancelada pelo mesário antes da computação do voto
    E em seguida o Eleitor B é habilitado por biometria e confirma o voto às 17:10:00 BRT
    Quando o agent-parser processar a seção
    Então total_votos deve ser 1
    E votos_apos_17h deve ser 1
    E sem_bio_apos_17h deve ser 0
    E votos_cancelados_suspensos deve ser 1

  Cenário: Idempotência de reexecução sobre partições Parquet e DuckDB
    Dado que as seções da UF "AC" já foram processadas e consolidadas no DuckDB
    Quando o pipeline for reexecutado sobre o mesmo lote de arquivos da UF "AC"
    Então total_votos_brasil em summary_national deve permanecer rigorosamente inalterado
    E nenhuma chave primária duplicada deve existir em raw_section_metrics
```

---

## 3. Especificação da Interface CLI (`pulso`)

Implementada em `src/pulso_eleitoral/cli.py` (via `typer` ou `argparse` tipado), invocável com `uv run pulso`:

| Comando | Argumentos Principais | Responsabilidade |
| :--- | :--- | :--- |
| `pulso ingest-parse` | `--ano`, `--turno`, `--pleito`, `--uf` (ou `ALL`), `--source [cdn\|zip]`, `--input-dir`, `--workers 8`, `--force` | Executa ingestão + parsing multiprocesso + escrita atômica de partições Parquet e auditoria de falhas. |
| `pulso consolidate` | `--ano`, `--turno`, `--db-path data/pulso_eleitoral.duckdb` | Constrói/atualiza tabelas e views analíticas no DuckDB validando todas as invariantes matemáticas e tamanho `<= 200 MB`. |
| `pulso export-json` | `--ano`, `--turno`, `--db-path`, `--out-dir frontend/public/api/v1` | Exporta os payloads JSON estáticos validados contra os schemas Pydantic/JSON Schema. |
| `pulso verify` | `--db-path`, `--json-dir` | Executa bateria de auditoria de integridade pós-execução (invariantes, cobertura, somas cruzadas UF == Nacional). |
| `pulso run-all` | `--ano`, `--turno`, `--pleito`, `--uf`, `--source` | Orquestra sequencialmente `ingest-parse` -> `consolidate` -> `export-json` -> `verify`. |

---

## 4. Portões de Qualidade (*Definition of Done* — DoD)

Nenhuma etapa do roadmap é considerada concluída por um agente sem aprovação integral nos comandos abaixo:
1. `uv run ruff check src tests` (Zero erros de PEP 8, imports ou docstrings).
2. `uv run ruff format --check src tests` (Formatação 100% aderente).
3. `uv run mypy --strict src` (Tipagem estática estrita 100% limpa).
4. `uv run pytest -q --cov=pulso_eleitoral --cov-fail-under=90` (Exclusivamente funções `pytest` + `pytest-mock`; zero `unittest`).

---

## 5. Roadmap de Implementação em Tarefas Atômicas (Pronto para Orquestração IA)

Cada etapa abaixo corresponde a entregas coesas e commits granulares (`Conventional Commits` em `pt-BR`):

- **Fase 1 — Fundação, Ambiente e Contratos (`contracts` & `resources`):**
  - `chore(deps): configurar pyproject.toml com dependencias nativas e ferramentas de qa` (incluindo `polars`, `duckdb`, `httpx`, `py7zr`, `pydantic`, `orjson`, `typer`, `uvloop; sys_platform != 'win32'`, `pytest`, `pytest-mock`, `pytest-asyncio`, `hypothesis`, `ruff`, `mypy`).
  - `feat(contracts): definir modelos imutaveis de handoff e excecoes de auditoria` (`src/pulso_eleitoral/contracts/`).
  - `data(resources): adicionar dicionario de fusos municipais e perfis de regex do log` (`resources/dim_municipio_fuso.csv` e `resources/log_patterns/v2022_2026.toml`).
- **Fase 2 — Motor de Extração Binária e FSM de Parsing (`agent-parser`):**
  - `test(fixtures): criar gerador deterministico e suite de fixtures aureas FX-01 a FX-10`.
  - `feat(parser): implementar extrator in-memory multiformato 7z e zip por magic bytes`.
  - `feat(parser): implementar maquina de estados finita do logd.dat e reconciliacao de bu`.
- **Fase 3 — Motor de Ingestão Assíncrona (`agent-ingestion`):**
  - `feat(ingestion): implementar provedor de pacotes zip estaduais em streaming`.
  - `feat(ingestion): implementar cliente assincrono cdn tse com retry sha512 e checkpoint`.
- **Fase 4 — Motor Analítico Polars/DuckDB (`agent-analytics`):**
  - `feat(analytics): implementar orquestrador multiprocesso com backpressure e parquet zstd`.
  - `feat(analytics): implementar consolidacao duckdb views olap e classificacao de outliers`.
- **Fase 5 — Exportador Estático, CLI e Painel SPA (`agent-frontend-export`):**
  - `feat(export): implementar exportador json deterministico validado por schema`.
  - `feat(cli): implementar interface de linha de comando pulso com verificacao fim-a-fim`.
  - `feat(frontend): criar painel estatico nextjs com visoes nacional estadual e explorador de secoes`.
