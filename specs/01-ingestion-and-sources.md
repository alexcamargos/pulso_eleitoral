# Especificação 01: Motor de Ingestão, Fontes TSE e Fusos Horários

**Agente Responsável:** `agent-ingestion` (`src/pulso_eleitoral/ingestion/`)  
**Requisitos Cobertos:** `REQ-ING-01`, `REQ-ING-02`, `REQ-ING-03`

---

## 1. Arquitetura Dual de Fontes de Dados do TSE (`REQ-ING-01`)

O TSE disponibiliza os artefatos brutos de urna por dois canais oficiais com características operacionais radicalmente distintas. O módulo de ingestão deve implementar o protocolo abstrato `SectionArtifactProvider` com duas estratégias concretas:

### 1.1. Modo A: CDN Oficial de Resultados (`CdnArtifactProvider`)
Utilizado durante e logo após a apuração ou para auditoria seletiva por UF/Município/Seção.

1. **Hierarquia de URLs do TSE:**
   - **Catálogo de Configuração de Município/Zonas (Índice):**
     `https://resultados.tse.jus.br/oficial/ele{ano}/arquivo-urna/{pleito_id}/config/{uf_lower}/{uf_lower}-p{pleito_6dig}-cs.json`
   - **Metadados Auxiliares da Seção (`-aux.json`):**
     `https://resultados.tse.jus.br/oficial/ele{ano}/arquivo-urna/{pleito_id}/dados/{uf_lower}/{mun_5dig}/{zona_4dig}/{secao_4dig}/p{pleito_6dig}-{uf_lower}-m{mun_5dig}-z{zona_4dig}-s{secao_4dig}-aux.json`
   - **Download de Artefato Individual (`.logjez` / `.bu`):**
     `https://resultados.tse.jus.br/oficial/ele{ano}/arquivo-urna/{pleito_id}/dados/{uf_lower}/{mun_5dig}/{zona_4dig}/{secao_4dig}/{hash_dir}/{nome_arquivo}`
2. **Regras de Formatação de Parâmetros:**
   - `uf_lower`: Sigla da UF em minúsculas (`ac`, `am`, `sp`, ..., `zz` para exterior quando aplicável; por padrão o escopo nacional compreende as 27 UFs domésticas).
   - `pleito_6dig`: Código canônico do pleito (`cd_pleito`) com zero-padding de 6 dígitos (ex.: `000406` para 2022 1T, `000407` para 2022 2T, `000452` para 2024 1T, `000453` para 2024 2T, `003220` para 2026 1T, `003221` para 2026 2T). O pipeline mapeia automaticamente identificadores de eleição federais informados por engano (ex.: `6257->3220`, `6258->3221`, `456->452`, `457->453`).
   - `mun_5dig`: Código TSE do município com 5 dígitos (`00001` a `99999`, zero-padded à esquerda).
   - `zona_4dig` / `secao_4dig`: Inteiros formatados com 4 dígitos (`0001` a `9999`).
3. **Resolução de Múltiplos Logs na Mesma Seção e Suporte a `nmarq[]` / `arq[]`:**
   - O arquivo `-aux.json` contém o array `hashes[]`, onde cada objeto lista `st` (status), `ds`/`dr` (data), `hash` (identificador do subdiretório) e uma lista de arquivos que pode constar sob a chave `nmarq[]` (ciclos anteriores) ou `arq[]` contendo objetos `{nm: str, tp: str}` (ciclo 2026).
   - O artefato de log pode ser nomeado `*.logjez`, `*.jez` ou `*-log.jez` (`tp == 'log'`). O Boletim de Urna pode ser nomeado `*.bu` ou `*-bu.dat` (`tp == 'bu'`).
   - Caso haja mais de um `.logjez` na seção (substituição por urna de contingência), **todos** os arquivos `.logjez` listados devem ser baixados e entregues ordenados no `SectionArtifactBundle` para fusão e deduplicação pelo `agent-parser`.

### 1.2. Modo B: Pacotes ZIP Estaduais de Dados Abertos (`BulkZipArtifactProvider`)
Utilizado para reprocessamento nacional offline/batch de alta velocidade sem realizar centenas de milhares de requisições HTTP individuais.

1. **Nomenclatura Padrão e URL no Portal de Dados Abertos:**
   `bu_imgbu_logjez_rdv_vscmr_{ano}_{turno}t_{UF}.zip`, localizado no repositório de totalização do TSE:
   `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/arqurnatot/bu_imgbu_logjez_rdv_vscmr_{ano}_{turno}t_{UF}.zip`.
2. **Nomenclatura Interna de Membros nos Pacotes ZIP Estaduais:**
   - **Padrão Ciclos <= 2022:** `o{pleito}-{mun_5dig}{zona_4dig}{secao_4dig}.{ext}` (extensões: `.logjez`, `.bu`, `.imgbu`, `.rdv`, `.vscmr`).
   - **Padrão Ciclos >= 2024:** `o{pleito}{uf}{mun_5dig}{zona_4dig}{secao_4dig}-{tipo}.{ext}` (ex.: `o03220ac0107400040385-log.jez`, `o03220ac0107400040385-bu.dat`).
3. **Restrição Crítica de Memória (`<= 8 GB RAM`):**
   - Um pacote estadual (ex.: `SP` ou `MG`) pode ultrapassar **30 GB a 45 GB**. É **estritamente proibido** ler o arquivo `.zip` estadual inteiro para `io.BytesIO`.
   - Para arquivo local: iterar sobre `zipfile.ZipFile(path, mode="r").infolist()`, agrupando entradas por chave `(mun_5dig, zona_4dig, secao_4dig)`, lendo para memória (`zf.read(info)`) **apenas** os bytes dos membros da seção corrente (~100 KB) e descartando entradas `.imgbu`, `.rdv` e `.vscmr`.
   - Para URL remota: download em *stream* para arquivo temporário paginado por UF antes da extração seletiva (ou leitura via HTTP `Range` quando viável). Caso o pacote ZIP retorne HTTP 404 em pleito recente cujos consolidados ainda não foram gerados pelo TSE, orientar explicitamente o uso do `--source cdn`.

---

## 2. Resiliência de Rede, Integridade e Checkpointing (`REQ-ING-02`)

### 2.1. Políticas HTTP e Concorrência
- **Cliente Assíncrono:** `httpx.AsyncClient(http2=True)` com pool de conexões reutilizável (`max_connections=64`, `max_keepalive_connections=32`).
- **Cabeçalhos Obrigatórios:** `User-Agent: PulsoEleitoral-AuditPipeline/0.1 (+reproducible-civic-audit)` e `Accept-Encoding: gzip, br`.
- **Controle de Taxa e Concorrência:**
  - `asyncio.Semaphore(max_concurrent_requests)` configurável (default: `32` para CDN).
  - Rate limiter *Token Bucket* configurável (`requests_per_second`, default: `50 req/s`).
- **Retry Exponencial com Full Jitter:**
  - Aplicável a timeouts de rede, erros transitórios de socket, HTTP `408`, `429` (respeitando cabeçalho `Retry-After` quando presente) e `500/502/503/504`.
  - Fórmula de espera na tentativa $k \in \{1, \dots, 5\}$:
    $$t_k = \text{Uniform}\left(0, \min\left(60.0, 0.5 \times 2^k\right)\right) \text{ segundos}$$
  - Erros HTTP `404` definitivos no `.logjez` (após manifesto indicar existência da seção) não sofrem retry infinito: são classificados imediatamente como `MISSING_LOG`.
  - Erros HTTP `404` no catálogo estadual `-cs.json` do CDN indicam que o ciclo eleitoral foi desativado/arquivado na infraestrutura de resultados ao vivo do TSE (devendo ser auditado via `--source zip`), ou que o `pleito_id` informado está incorreto.
  - Erros HTTP `404` no download de pacotes ZIP estaduais remotos em pleitos recém-realizados indicam que os pacotes consolidados de dados abertos ainda não foram disponibilizados pelo TSE, devendo o usuário recorrer ao `--source cdn`.

### 2.2. Verificação Criptográfica (`SHA-512`)
- Quando o manifesto fornecer hash `SHA-512` (ou `SHA-256`) esperado para o artefato:
  - Calcular `hashlib.sha512(payload_bytes).hexdigest()` imediatamente em memória antes de enfileirar para o `ProcessPoolExecutor`.
  - Se divergir: realizar até 2 novas tentativas de download (mitigando truncamento de rede); persistindo a divergência, emitir `UnprocessedSectionError(error_code="HASH_MISMATCH")`.

### 2.3. Checkpointing e Retomada Idempotente
- Antes de iniciar o download de uma UF, o motor consulta as chaves `(ano_eleicao, turno, pleito_id, uf, municipio_cod, zona, secao)` já consolidadas com `status_processamento = 'SUCCESS'` nas partições Parquet existentes (exceto se flag `--force-reprocess` estiver ativa).
- Seções já processadas com sucesso são ignoradas em $O(1)$ via `set[tuple[int, int, int]]` `(municipio_cod, zona, secao)` por UF, garantindo retomada instantânea após falhas de energia ou rede.

---

## 3. Dicionário Canônico de Fusos Horários por Município (`REQ-ING-03`)

O arquivo `resources/dim_municipio_fuso.csv` deve ser versionado no repositório e validado no boot do pipeline.

### 3.1. Esquema de `dim_municipio_fuso.csv`
| Coluna | Tipo | Exemplo | Descrição |
| :--- | :--- | :--- | :--- |
| `municipio_cod_tse` | `int` | `02550` | Código TSE de 5 dígitos (chave primária de lookup). |
| `municipio_cod_ibge` | `int` | `1302603` | Código IBGE de 7 dígitos. |
| `uf` | `str` | `AM` | Sigla da UF (2 caracteres maiúsculos). |
| `municipio_nome` | `str` | `MANAUS` | Nome oficial do município no cadastro do TSE. |
| `iana_timezone` | `str` | `America/Manaus` | Identificador IANA oficial. |
| `fuso_horario_offset_brt` | `int` | `-1` | Diferença inteira em horas frente a Brasília (`UTC-3`). |

### 3.2. Regras Geográficas Exatas do Brasil (Sem Exceções Omitidas)
1. **`fuso_horario_offset_brt = +1` (`UTC-2`, `America/Noronha`):**
   - Exclusivamente o distrito estadual de **Fernando de Noronha (`PE`)** (código IBGE `2605459` / código TSE `30015` — validado contra tabela oficial TSE do pleito).
2. **`fuso_horario_offset_brt = 0` (`UTC-3`, `America/Sao_Paulo` e equivalentes):**
   - Todos os municípios de: `AL`, `AP`, `BA`, `CE`, `DF`, `ES`, `GO`, `MA`, `MG`, `PA`, `PB`, `PI`, `PR`, `RJ`, `RN`, `RS`, `SC`, `SE`, `SP`, `TO`, e todos os municípios de `PE` **exceto** Fernando de Noronha.
3. **`fuso_horario_offset_brt = -1` (`UTC-4`, `America/Manaus` / `America/Cuiaba` / `America/Campo_Grande`):**
   - Todos os municípios de: `MT`, `MS`, `RO`, `RR`.
   - Todos os municípios do **Amazonas (`AM`)**, **EXCETO** os 13 municípios do Sudoeste Amazonense listados abaixo.
4. **`fuso_horario_offset_brt = -2` (`UTC-5`, `America/Rio_Branco` / `America/Eirunepe`):**
   - Todos os 22 municípios do **Acre (`AC`)**.
   - Os **13 municípios do Sudoeste do Amazonas (`AM`)** (Lei nº 12.876/2013):
     `Atalaia do Norte`, `Benjamin Constant`, `Boca do Acre`, `Eirunepé`, `Envira`, `Guajará`, `Ipixuna`, `Itamarati`, `Jutaí`, `Lábrea`, `Pauini`, `São Paulo de Olivença` e `Tabatinga`.

> **Regra de Segurança (Fail-Fast):** Caso o manifesto do TSE apresente um `municipio_cod` inexistente em `dim_municipio_fuso.csv`, o pipeline **NÃO DEVE** assumir silenciosamente `offset = 0` para `AM` ou `PE`: para `AC` aplica fallback `-2`, para `MT/MS/RO/RR` aplica `-1`, e para `AM`/`PE` emite alerta estruturado exigindo atualização do cadastro antes de consolidar o lote oficial.

---

## 4. Contrato Python de Handoff (`SectionArtifactBundle`)

Definido em `src/pulso_eleitoral/contracts/models.py`:

```python
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class LogArtifactPayload:
    """Representa um arquivo .logjez bruto carregado em memória."""

    filename: str
    raw_bytes: bytes
    sha512_expected: str | None = None


@dataclass(slots=True, frozen=True)
class SectionArtifactBundle:
    """Contrato imutável entregue pelo agent-ingestion ao agent-parser."""

    ano_eleicao: int
    turno: int
    pleito_id: int
    election_date_iso: str          # Ex.: "2022-10-02" ou "2026-10-04"
    cutoff_mode: str                # "UNIFIED_BRT" | "LOCAL_TIME"
    uf: str
    municipio_cod: int
    municipio_ibge: int | None
    municipio_nome: str
    zona: int
    secao: int
    fuso_horario_offset_brt: int    # -2, -1, 0, +1
    total_aptos_manifest: int | None
    log_artifacts: tuple[LogArtifactPayload, ...]
    bu_raw_bytes: bytes | None = None
```
