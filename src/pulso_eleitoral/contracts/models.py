"""Modelos imutáveis de handoff entre os agentes do pipeline Pulso Eleitoral.

Define os contratos em memória (`@dataclass(slots=True, frozen=True)`) exigidos
por `REQ-ING-01`..`03`, `REQ-PAR-01`..`03` e `REQ-ANA-01`..`02`, garantindo baixo
custo de memória, serialização limpa entre processos e validação das invariantes.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pulso_eleitoral.contracts.exceptions import (
    InvariantViolationError,
    ProcessingStatus,
)


class CutoffMode(StrEnum):
    """Modo de avaliação do corte temporal das 17:00:00 por ciclo eleitoral.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    UNIFIED_BRT = "UNIFIED_BRT"
    LOCAL_TIME = "LOCAL_TIME"


class FlagSeverityTier(StrEnum):
    """Níveis canônicos de classificação de seções sinalizadas (`REQ-ANA-02`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    TIER_1_POST_17H_NO_BIO = "TIER_1_POST_17H_NO_BIO"
    TIER_2_STATISTICAL_OUTLIER = "TIER_2_STATISTICAL_OUTLIER"
    TIER_3_CRITICAL_ANOMALY = "TIER_3_CRITICAL_ANOMALY"


@dataclass(slots=True, frozen=True)
class MunicipalityTzInfo:
    """Metadados geográficos e de fuso horário municipal (`REQ-ING-03`).

    Args:
        municipio_cod_tse: Código TSE de 5 dígitos (chave primária de lookup).
        municipio_cod_ibge: Código IBGE de 7 dígitos, quando aplicável.
        uf: Sigla da Unidade Federativa em 2 letras maiúsculas.
        municipio_nome: Nome oficial do município no cadastro eleitoral.
        iana_timezone: Identificador IANA oficial (ex.: `America/Eirunepe`).
        fuso_horario_offset_brt: Diferença em horas vs BRT (`-2`, `-1`, `0`, `+1`).

    Returns:
        Nenhum.

    Raises:
        InvariantViolationError: Se o offset BRT estiver fora de `{-2, -1, 0, 1}`.
    """

    municipio_cod_tse: int
    municipio_cod_ibge: int | None
    uf: str
    municipio_nome: str
    iana_timezone: str
    fuso_horario_offset_brt: int

    def __post_init__(self) -> None:
        """Valida o domínio permitido de `fuso_horario_offset_brt` na criação.

        Args:
            Nenhum.

        Returns:
            Nenhum.

        Raises:
            InvariantViolationError: Se o offset frente a Brasília não pertencer
                ao domínio `{-2, -1, 0, 1}`.
        """
        if self.fuso_horario_offset_brt not in (-2, -1, 0, 1):
            raise InvariantViolationError(
                f"Offset BRT inválido ({self.fuso_horario_offset_brt}) para "
                f"município {self.municipio_cod_tse} ({self.uf})."
            )


@dataclass(slots=True, frozen=True)
class LogArtifactPayload:
    """Representa um arquivo `.logjez` bruto carregado em memória (`REQ-ING-01`).

    Args:
        filename: Nome original do artefato (ex.: `o00406-7107200010102.logjez`).
        raw_bytes: Conteúdo binário integral do pacote `.logjez`.
        sha512_expected: Hash SHA-512 hexadecimal esperado segundo o manifesto.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    filename: str
    raw_bytes: bytes
    sha512_expected: str | None = None


@dataclass(slots=True, frozen=True)
class SectionArtifactBundle:
    """Contrato imutável entregue pelo `agent-ingestion` ao `agent-parser`.

    Args:
        ano_eleicao: Ano oficial do pleito (ex.: `2022`).
        turno: Número do turno (`1` ou `2`).
        pleito_id: Identificador numérico do pleito no TSE (ex.: `406`).
        election_date_iso: Data oficial do turno em ISO-8601 (`YYYY-MM-DD`).
        cutoff_mode: Modo de corte horário (`UNIFIED_BRT` ou `LOCAL_TIME`).
        uf: Sigla da UF em maiúsculas.
        municipio_cod: Código TSE do município (5 dígitos).
        municipio_ibge: Código IBGE do município (7 dígitos) ou `None`.
        municipio_nome: Nome oficial do município.
        zona: Número da zona eleitoral.
        secao: Número da seção eleitoral.
        fuso_horario_offset_brt: Offset em horas vs Brasília (`-2`, `-1`, `0`, `+1`).
        total_aptos_manifest: Eleitores aptos informados no manifesto, se disponível.
        log_artifacts: Tupla ordenada de pacotes `.logjez` da seção.
        bu_raw_bytes: Bytes brutos do Boletim de Urna (`.bu`), quando disponível.
        source_uri: URI diagnóstica da fonte (CDN ou pacote ZIP estadual).

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    ano_eleicao: int
    turno: int
    pleito_id: int
    election_date_iso: str
    cutoff_mode: str
    uf: str
    municipio_cod: int
    municipio_ibge: int | None
    municipio_nome: str
    zona: int
    secao: int
    fuso_horario_offset_brt: int
    total_aptos_manifest: int | None
    log_artifacts: tuple[LogArtifactPayload, ...]
    bu_raw_bytes: bytes | None = None
    source_uri: str | None = None


@dataclass(slots=True, frozen=True)
class IngestionCheckpoint:
    """Conjunto imutável de seções concluídas para retomada em $O(1)$ (`REQ-ING-02`).

    Args:
        ano_eleicao: Ano oficial do pleito.
        turno: Turno da eleição (`1` ou `2`).
        pleito_id: Identificador do pleito no TSE.
        uf: Sigla da UF em maiúsculas.
        completed_sections: Tuplas `(municipio_cod, zona, secao)` já consolidadas.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    ano_eleicao: int
    turno: int
    pleito_id: int
    uf: str
    completed_sections: frozenset[tuple[int, int, int]]

    def is_completed(self, municipio_cod: int, zona: int, secao: int) -> bool:
        """Verifica em $O(1)$ se uma seção já foi processada com sucesso.

        Args:
            municipio_cod: Código TSE do município.
            zona: Número da zona eleitoral.
            secao: Número da seção eleitoral.

        Returns:
            `True` caso a seção já conste como `SUCCESS`, `False` caso contrário.

        Raises:
            Nenhum.
        """
        return (municipio_cod, zona, secao) in self.completed_sections


@dataclass(slots=True, frozen=True)
class UnprocessedSectionError:
    """Registro de auditoria para seção não processada (`unprocessed_sections`).

    Args:
        ano_eleicao: Ano oficial do pleito.
        turno: Número do turno (`1` ou `2`).
        pleito_id: Identificador do pleito no TSE.
        uf: Sigla da UF em maiúsculas.
        municipio_cod: Código TSE do município.
        zona: Número da zona eleitoral.
        secao: Número da seção eleitoral.
        error_code: Código canônico da falha (`MISSING_LOG`, `CORRUPT_ARCHIVE`, etc.).
        error_message: Mensagem diagnóstica limitada a 500 caracteres.
        recorded_at: Timestamp UTC/BRT do registro da falha.
        source_uri: URI ou caminho do artefato problemático.
        sha512_expected: Hash SHA-512 esperado segundo o manifesto.
        sha512_actual: Hash SHA-512 calculado sobre os bytes recebidos.
        attempt_count: Quantidade de tentativas efetuadas.
        municipio_ibge: Código IBGE opcional para geração da linha espelho.
        municipio_nome: Nome do município para geração da linha espelho.
        fuso_horario_offset_brt: Offset em horas vs BRT para a linha espelho.
        cutoff_mode: Modo de corte horário do pleito para a linha espelho.
        total_aptos_manifest: Total de aptos conhecido via manifesto, se houver.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    ano_eleicao: int
    turno: int
    pleito_id: int
    uf: str
    municipio_cod: int
    zona: int
    secao: int
    error_code: str
    error_message: str
    recorded_at: datetime
    source_uri: str | None = None
    sha512_expected: str | None = None
    sha512_actual: str | None = None
    attempt_count: int = 1
    municipio_ibge: int | None = None
    municipio_nome: str = "DESCONHECIDO"
    fuso_horario_offset_brt: int = 0
    cutoff_mode: str = CutoffMode.UNIFIED_BRT.value
    total_aptos_manifest: int | None = None

    def to_audit_row(self) -> dict[str, object]:
        """Converte o erro para o dicionário das 14 colunas de `unprocessed_sections`.

        Args:
            Nenhum.

        Returns:
            Dicionário compatível com o schema colunar de `unprocessed_sections`.

        Raises:
            Nenhum.
        """
        return {
            "ano_eleicao": self.ano_eleicao,
            "turno": self.turno,
            "pleito_id": self.pleito_id,
            "uf": self.uf,
            "municipio_cod": self.municipio_cod,
            "zona": self.zona,
            "secao": self.secao,
            "error_code": self.error_code,
            "error_message": self.error_message[:500],
            "source_uri": self.source_uri[:500] if self.source_uri else None,
            "sha512_expected": self.sha512_expected,
            "sha512_actual": self.sha512_actual,
            "attempt_count": self.attempt_count,
            "recorded_at": self.recorded_at,
        }


@dataclass(slots=True, frozen=True)
class ParsedSectionMetrics:
    """Métricas granulares auditadas de uma seção eleitoral (`raw_section_metrics`).

    Espelha exatamente as 32 colunas de `RAW_SECTION_METRICS_SCHEMA` definidas
    em `specs/03-data-schemas-and-analytics.md`.

    Args:
        ano_eleicao: Ano oficial do pleito.
        turno: Número do turno (`1` ou `2`).
        pleito_id: Identificador do pleito no TSE.
        uf: Sigla da UF em maiúsculas.
        municipio_cod: Código TSE do município (5 dígitos).
        municipio_ibge: Código IBGE do município (7 dígitos) ou `None`.
        municipio_nome: Nome oficial do município.
        zona: Número da zona eleitoral.
        secao: Número da seção eleitoral.
        fuso_horario_offset_brt: Offset em horas vs Brasília (`-2`, `-1`, `0`, `+1`).
        cutoff_mode: Modo de corte (`UNIFIED_BRT` ou `LOCAL_TIME`).
        qtd_arquivos_log: Quantidade de arquivos `.logjez`/`logd.dat` fundidos na seção.
        total_aptos: Total de eleitores aptos da seção, quando disponível.
        comparecimento_bu: Comparecimento extraído do `.bu`, quando reconciliado.
        total_votos: Total de votos confirmados no `logd.dat`.
        divergencia_bu_log: Diferença `comparecimento_bu - total_votos` ou `None`.
        votos_antes_08h: Votos confirmados antes das `08:00:00` locais.
        votos_ate_17h: Votos confirmados na janela `< 17:00:00` do referencial.
        votos_apos_17h: Votos confirmados na janela `>= 17:00:00` do referencial.
        sem_bio_ate_17h: Votos sem habilitação biométrica antes das `17:00:00`.
        sem_bio_apos_17h: Votos sem habilitação biométrica a partir das `17:00:00`.
        bio_status_indefinido: Votos sem linha explícita de modo de habilitação.
        tentativas_bio_falhas: Eventos de falha de leitura de digital registrados.
        votos_cancelados_suspensos: Eleitores suspensos/cancelados pelo mesário.
        qtd_reinicializacoes: Quantidade de reinicializações da urna no expediente.
        horario_abertura_brt: Timestamp em BRT da abertura da votação.
        horario_primeiro_voto_brt: Timestamp em BRT do primeiro voto computado.
        horario_ultimo_voto_brt: Timestamp em BRT do último voto computado.
        horario_encerramento_brt: Timestamp em BRT do encerramento da seção.
        relogio_suspeito: Indica anomalia de relógio interno (RTC).
        voto_apos_encerramento: Indica voto computado após `SECTION_CLOSED`.
        status_processamento: Status final (`SUCCESS` ou código de erro canônico).

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    ano_eleicao: int
    turno: int
    pleito_id: int
    uf: str
    municipio_cod: int
    municipio_ibge: int | None
    municipio_nome: str
    zona: int
    secao: int
    fuso_horario_offset_brt: int
    cutoff_mode: str
    qtd_arquivos_log: int
    total_aptos: int | None
    comparecimento_bu: int | None
    total_votos: int
    divergencia_bu_log: int | None
    votos_antes_08h: int
    votos_ate_17h: int
    votos_apos_17h: int
    sem_bio_ate_17h: int
    sem_bio_apos_17h: int
    bio_status_indefinido: int
    tentativas_bio_falhas: int
    votos_cancelados_suspensos: int
    qtd_reinicializacoes: int
    horario_abertura_brt: datetime | None
    horario_primeiro_voto_brt: datetime | None
    horario_ultimo_voto_brt: datetime | None
    horario_encerramento_brt: datetime | None
    relogio_suspeito: bool
    voto_apos_encerramento: bool
    status_processamento: str = ProcessingStatus.SUCCESS.value

    def validate_invariants(self) -> None:
        """Verifica as Invariantes Matemáticas 1 a 5 definidas em `specs.md` Seção 6.

        Args:
            Nenhum.

        Returns:
            Nenhum.

        Raises:
            InvariantViolationError: Se alguma invariante aritmética ou temporal falhar.
        """
        section_id = (
            f"{self.uf}/{self.municipio_cod:05d}/Z{self.zona:04d}/S{self.secao:04d}"
        )
        if self.total_votos != self.votos_ate_17h + self.votos_apos_17h:
            raise InvariantViolationError(
                f"[{section_id}] Invariante 1 violada: total_votos "
                f"({self.total_votos}) != votos_ate_17h ({self.votos_ate_17h}) + "
                f"votos_apos_17h ({self.votos_apos_17h})."
            )
        if not (0 <= self.sem_bio_ate_17h <= self.votos_ate_17h):
            raise InvariantViolationError(
                f"[{section_id}] Invariante 2 violada: sem_bio_ate_17h "
                f"({self.sem_bio_ate_17h}) fora de [0, {self.votos_ate_17h}]."
            )
        if not (0 <= self.sem_bio_apos_17h <= self.votos_apos_17h):
            raise InvariantViolationError(
                f"[{section_id}] Invariante 3 violada: sem_bio_apos_17h "
                f"({self.sem_bio_apos_17h}) fora de [0, {self.votos_apos_17h}]."
            )
        if self.total_votos == 0 and (
            self.horario_primeiro_voto_brt is not None
            or self.horario_ultimo_voto_brt is not None
        ):
            raise InvariantViolationError(
                f"[{section_id}] Invariante 4 violada: total_votos == 0 exige "
                "timestamps de primeiro e último voto nulos."
            )
        if self.total_votos > 0:
            if (
                self.horario_primeiro_voto_brt is None
                or self.horario_ultimo_voto_brt is None
            ):
                raise InvariantViolationError(
                    f"[{section_id}] Invariante 5 violada: total_votos > 0 exige "
                    "timestamps de primeiro e último voto preenchidos."
                )
            if self.horario_primeiro_voto_brt > self.horario_ultimo_voto_brt:
                raise InvariantViolationError(
                    f"[{section_id}] Invariante 5 violada: horario_primeiro_voto_brt "
                    f"({self.horario_primeiro_voto_brt}) > horario_ultimo_voto_brt "
                    f"({self.horario_ultimo_voto_brt})."
                )

    @classmethod
    def from_unprocessed_error(
        cls,
        err: UnprocessedSectionError,
    ) -> ParsedSectionMetrics:
        """Cria linha espelho zerada em `raw_section_metrics` para falha auditada.

        Cumpre a Invariante 6 (`specs.md` Seção 6) e a regra de completude do
        denominador em `specs/03-data-schemas-and-analytics.md` Seção 2.

        Args:
            err: Objeto de erro auditável capturado na ingestão ou parsing.

        Returns:
            Instância de `ParsedSectionMetrics` zerada com o `error_code` registrado.

        Raises:
            Nenhum.
        """
        return cls(
            ano_eleicao=err.ano_eleicao,
            turno=err.turno,
            pleito_id=err.pleito_id,
            uf=err.uf,
            municipio_cod=err.municipio_cod,
            municipio_ibge=err.municipio_ibge,
            municipio_nome=err.municipio_nome,
            zona=err.zona,
            secao=err.secao,
            fuso_horario_offset_brt=err.fuso_horario_offset_brt,
            cutoff_mode=err.cutoff_mode,
            qtd_arquivos_log=0,
            total_aptos=err.total_aptos_manifest,
            comparecimento_bu=None,
            total_votos=0,
            divergencia_bu_log=None,
            votos_antes_08h=0,
            votos_ate_17h=0,
            votos_apos_17h=0,
            sem_bio_ate_17h=0,
            sem_bio_apos_17h=0,
            bio_status_indefinido=0,
            tentativas_bio_falhas=0,
            votos_cancelados_suspensos=0,
            qtd_reinicializacoes=0,
            horario_abertura_brt=None,
            horario_primeiro_voto_brt=None,
            horario_ultimo_voto_brt=None,
            horario_encerramento_brt=None,
            relogio_suspeito=False,
            voto_apos_encerramento=False,
            status_processamento=err.error_code,
        )

    def to_metrics_row(self) -> dict[str, object]:
        """Converte a instância para o dicionário exato das 32 colunas Polars/DuckDB.

        Args:
            Nenhum.

        Returns:
            Dicionário ordenado conforme `RAW_SECTION_METRICS_SCHEMA`.

        Raises:
            Nenhum.
        """
        return {
            "ano_eleicao": self.ano_eleicao,
            "turno": self.turno,
            "pleito_id": self.pleito_id,
            "uf": self.uf,
            "municipio_cod": self.municipio_cod,
            "municipio_ibge": self.municipio_ibge,
            "municipio_nome": self.municipio_nome,
            "zona": self.zona,
            "secao": self.secao,
            "fuso_horario_offset_brt": self.fuso_horario_offset_brt,
            "cutoff_mode": self.cutoff_mode,
            "qtd_arquivos_log": self.qtd_arquivos_log,
            "total_aptos": self.total_aptos,
            "comparecimento_bu": self.comparecimento_bu,
            "total_votos": self.total_votos,
            "divergencia_bu_log": self.divergencia_bu_log,
            "votos_antes_08h": self.votos_antes_08h,
            "votos_ate_17h": self.votos_ate_17h,
            "votos_apos_17h": self.votos_apos_17h,
            "sem_bio_ate_17h": self.sem_bio_ate_17h,
            "sem_bio_apos_17h": self.sem_bio_apos_17h,
            "bio_status_indefinido": self.bio_status_indefinido,
            "tentativas_bio_falhas": self.tentativas_bio_falhas,
            "votos_cancelados_suspensos": self.votos_cancelados_suspensos,
            "qtd_reinicializacoes": self.qtd_reinicializacoes,
            "horario_abertura_brt": self.horario_abertura_brt,
            "horario_primeiro_voto_brt": self.horario_primeiro_voto_brt,
            "horario_ultimo_voto_brt": self.horario_ultimo_voto_brt,
            "horario_encerramento_brt": self.horario_encerramento_brt,
            "relogio_suspeito": self.relogio_suspeito,
            "voto_apos_encerramento": self.voto_apos_encerramento,
            "status_processamento": self.status_processamento,
        }


@dataclass(slots=True, frozen=True)
class SensitivityBoundsResult:
    """Resultado determinístico do teste de limites extremos (Bounds de Manski).

    Confronta o volume total de votos pós-17h com a margem de vitória do pleito.

    Args:
        total_votos_analisados: Total de votos computados no conjunto auditado.
        votos_pos_17h: Total absoluto de votos registrados a partir das 17:00:00.
        pct_pos_17h: Proporção percentual de votos pós-17h frente ao total.
        margem_eleitoral_referencia: Diferença absoluta oficial entre os candidatos.
        impacto_maximo_possivel_votos: Deslocamento contrafactual máximo possível.
        impacto_maximo_pct_margem: Razão percentual do impacto máximo sobre a margem.
        risco_inversao_resultado: Se o volume da janela poderia alterar o vencedor.
        veredito_deterministico: Mensagem conclusiva formal do teste.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    total_votos_analisados: int
    votos_pos_17h: int
    pct_pos_17h: float
    margem_eleitoral_referencia: int
    impacto_maximo_possivel_votos: int
    impacto_maximo_pct_margem: float
    risco_inversao_resultado: bool
    veredito_deterministico: str


@dataclass(slots=True, frozen=True)
class ParametricRegressionResult:
    """Resultado do modelo econométrico de regressão com efeitos fixos municipais.

    Estima o viés da proporção pós-17h sobre o desempenho relativo dos candidatos.

    Args:
        beta_pos_17h: Coeficiente estimado para a taxa de votos pós-17h.
        std_err_cluster: Erro-padrão robusto clusterizado no nível de município.
        t_statistic: Estatística t de Student calculada para H0: beta_1 = 0.
        p_value: Valor-p bicaudal do teste t.
        ci_95_lower: Limite inferior do intervalo de confiança de 95%.
        ci_95_upper: Limite superior do intervalo de confiança de 95%.
        r_squared_within: Coeficiente de determinação within da regressão.
        n_secoes: Quantidade de seções eleitorais incluídas na estimação.
        n_municipios: Quantidade de clusters municipais com efeitos fixos.
        votos_liquidos_deslocados_estimados: Estimativa pontual de votos deslocados.
        candidato_favorecido: Identificador do candidato favorecido (ou 'NEUTRO').
        conclusao_estatistica: Síntese textual da inferência estatística.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    beta_pos_17h: float
    std_err_cluster: float
    t_statistic: float
    p_value: float
    ci_95_lower: float
    ci_95_upper: float
    r_squared_within: float
    n_secoes: int
    n_municipios: int
    votos_liquidos_deslocados_estimados: float
    candidato_favorecido: str
    conclusao_estatistica: str


@dataclass(slots=True, frozen=True)
class ElectoralImpactReport:
    """Relatório consolidado unindo limites determinísticos e inferência paramétrica.

    Args:
        ano_eleicao: Ano da eleição auditada.
        turno: Turno da eleição auditada.
        bounds: Resultado dos limites extremos determinísticos de Manski.
        parametric: Resultado do teste paramétrico de regressão (se dados disponíveis).
        timestamp_analise: Carimbo de data/hora da geração da auditoria.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    ano_eleicao: int
    turno: int
    bounds: SensitivityBoundsResult
    parametric: ParametricRegressionResult | None
    timestamp_analise: datetime

