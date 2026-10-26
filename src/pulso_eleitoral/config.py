"""Configurações tipadas de execução e parâmetros globais do pipeline.

Define modelos Pydantic v2 e Pydantic Settings para parametrização segura da
ingestão (`REQ-ING-01`..`02`), normalização temporal (`specs.md` Seção 2.1),
orquestração multiprocesso (`REQ-ANA-01`) e limiares de outliers (`REQ-ANA-02`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pulso_eleitoral.contracts.models import CutoffMode

DOMESTIC_UFS: tuple[str, ...] = (
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
)

KNOWN_PLEITO_DATES: dict[int, str] = {
    304: "2020-11-15",
    305: "2020-11-29",
    406: "2022-10-02",
    407: "2022-10-30",
    456: "2024-10-06",
    457: "2024-10-27",
}

DEFAULT_RESOURCES_DIR: Path = Path(__file__).resolve().parents[2] / "resources"


class SourceMode(StrEnum):
    """Canal oficial de obtenção dos artefatos de urna do TSE (`REQ-ING-01`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    CDN = "cdn"
    ZIP = "zip"


class OutlierThresholds(BaseModel):
    """Limiares estatísticos de classificação `TIER_2_STATISTICAL_OUTLIER`.

    Args:
        min_votos_pos_17h: Mínimo de votos pós-17h na seção para elegibilidade.
        delta_sem_bio_pp: Salto mínimo em pontos percentuais pós-17h vs pré-17h.
        z_score_uf: Z-Score mínimo frente à distribuição estadual.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    min_votos_pos_17h: Annotated[int, Field(ge=1)] = 10
    delta_sem_bio_pp: Annotated[float, Field(gt=0.0)] = 15.0
    z_score_uf: Annotated[float, Field(gt=0.0)] = 3.0


class ElectionRunConfig(BaseModel):
    """Contrato imutável de parametrização de um turno/pleito eleitoral.

    Args:
        ano_eleicao: Ano oficial da eleição (`>= 2014`).
        turno: Turno da eleição (`1` ou `2`).
        pleito_id: Código numérico do pleito no TSE (ex.: `406`).
        election_date_iso: Data oficial do turno (`YYYY-MM-DD`).
        ufs: Tupla de UFs a processar (ou `("ALL",)` para expandir as 27 UFs).
        municipios: Tupla opcional de códigos TSE de municípios para filtragem.
        source_mode: Canal de origem (`cdn` ou `zip`).
        cutoff_mode: Modo de avaliação do corte das 17h (`UNIFIED_BRT` ou `LOCAL_TIME`).
        log_pattern_profile: Nome do perfil de regex em `resources/log_patterns/`.
        force_reprocess: Quando `True`, ignora checkpoints existentes.
        input_dir: Diretório local contendo pacotes `.zip` estaduais ou manifestos.

    Returns:
        Nenhum.

    Raises:
        ValueError: Se parâmetros de UF, turno ou data oficial forem inválidos.
    """

    model_config = ConfigDict(frozen=True)

    ano_eleicao: Annotated[int, Field(ge=2014, le=2100)]
    turno: Annotated[int, Field(ge=1, le=2)]
    pleito_id: Annotated[int, Field(gt=0)]
    election_date_iso: str | None = None
    ufs: tuple[str, ...] = DOMESTIC_UFS
    municipios: tuple[int, ...] = ()
    source_mode: SourceMode = SourceMode.ZIP
    cutoff_mode: CutoffMode | None = None
    log_pattern_profile: str | None = None
    force_reprocess: bool = False
    input_dir: Path | None = None

    @field_validator("ufs", mode="before")
    @classmethod
    def _normalize_ufs(cls, value: object) -> tuple[str, ...]:
        """Normaliza lista, CSV ou `"ALL"` para tupla ordenada de UFs válidas.

        Args:
            value: Entrada bruta de UF(s) (ex.: `"ALL"`, `"ac,sp"`, `["AM"]`).

        Returns:
            Tupla ordenada e sem duplicatas de siglas de UF em maiúsculas.

        Raises:
            ValueError: Se alguma sigla informada não for uma UF válida nem `ZZ`.
        """
        raw_items: list[str]
        if isinstance(value, str):
            raw_items = [
                item.strip().upper() for item in value.split(",") if item.strip()
            ]
        elif isinstance(value, (list, tuple, set, frozenset)):
            raw_items = [
                str(item).strip().upper() for item in value if str(item).strip()
            ]
        else:
            raise ValueError("Parâmetro 'ufs' deve ser string ou sequência de siglas.")

        if not raw_items or "ALL" in raw_items:
            return DOMESTIC_UFS

        valid_set = set(DOMESTIC_UFS) | {"ZZ"}
        invalid = [uf for uf in raw_items if uf not in valid_set]
        if invalid:
            raise ValueError(f"Siglas de UF inválidas: {', '.join(sorted(invalid))}.")
        return tuple(sorted(set(raw_items)))

    @field_validator("municipios", mode="before")
    @classmethod
    def _normalize_municipios(cls, value: object) -> tuple[int, ...]:
        """Normaliza lista, CSV ou inteiro único de códigos TSE municipais.

        Args:
            value: Entrada bruta (ex.: `None`, `""`, `"30015,71072"`, `[30015]`).

        Returns:
            Tupla ordenada e sem duplicatas de códigos TSE inteiros (`> 0`).

        Raises:
            ValueError: Se algum código municipal não for inteiro positivo.
        """
        if value is None:
            return ()
        raw_codes: list[int] = []
        if isinstance(value, int) and not isinstance(value, bool):
            raw_codes = [value]
        elif isinstance(value, str):
            for part in value.split(","):
                stripped = part.strip()
                if stripped:
                    raw_codes.append(int(stripped))
        elif isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                raw_codes.append(int(str(item).strip()))
        else:
            raise ValueError(
                "Parâmetro 'municipios' deve ser inteiro, CSV ou sequência."
            )
        if any(code <= 0 or code > 99999 for code in raw_codes):
            raise ValueError("Códigos TSE municipais devem estar em [1, 99999].")
        return tuple(sorted(set(raw_codes)))

    @model_validator(mode="after")
    def _populate_defaults_and_validate_date(self) -> ElectionRunConfig:
        """Preenche `cutoff_mode`, `log_pattern_profile` e `election_date_iso`.

        Args:
            Nenhum.

        Returns:
            Instância validada de `ElectionRunConfig` com campos derivados preenchidos.

        Raises:
            ValueError: Se `election_date_iso` estiver ausente para pleito desconhecido
                ou não respeitar formato ISO `YYYY-MM-DD`.
        """
        resolved_cutoff = self.cutoff_mode or (
            CutoffMode.UNIFIED_BRT
            if self.ano_eleicao >= 2022
            else CutoffMode.LOCAL_TIME
        )
        resolved_profile = self.log_pattern_profile or (
            "v2020" if self.ano_eleicao <= 2020 else "v2022_2026"
        )
        resolved_date = self.election_date_iso or KNOWN_PLEITO_DATES.get(self.pleito_id)
        if resolved_date is None:
            raise ValueError(
                "Data oficial ('election_date_iso') obrigatória para "
                f"pleito_id={self.pleito_id}."
            )
        parsed = date.fromisoformat(resolved_date)
        if parsed.year != self.ano_eleicao:
            raise ValueError(
                f"Ano em election_date_iso ({parsed.year}) difere de "
                f"ano_eleicao ({self.ano_eleicao})."
            )

        object.__setattr__(self, "cutoff_mode", resolved_cutoff)
        object.__setattr__(self, "log_pattern_profile", resolved_profile)
        object.__setattr__(self, "election_date_iso", resolved_date)
        return self


class PipelineSettings(BaseSettings):
    """Configurações operacionais de infraestrutura, rede e recursos locais.

    Carrega variáveis de ambiente com prefixo `PULSO_` ou arquivo `.env`.

    Args:
        resources_dir: Diretório raiz dos recursos estáticos versionados.
        data_dir: Diretório base de artefatos Parquet, DuckDB e JSON exportados.
        db_path: Caminho do arquivo consolidado DuckDB (`<= 200 MB`).
        workers: Quantidade de processos no `ProcessPoolExecutor`.
        batch_size: Tamanho do lote de seções por partição Parquet (`10.000`).
        max_in_flight_multiplier: Fator multiplicador da fila de backpressure.
        cdn_base_url: URL raiz do CDN de resultados do TSE.
        open_data_base_url: URL raiz de pacotes estaduais no Portal de Dados Abertos.
        max_concurrent_requests: Semáforo máximo de requisições HTTP simultâneas.
        requests_per_second: Taxa sustentada do limitador Token Bucket.
        http_max_connections: Limite total do pool `httpx.AsyncClient`.
        http_max_keepalive_connections: Conexões keep-alive mantidas no pool.
        http_timeout_seconds: Timeout de leitura/conexão HTTP em segundos.
        http_max_retries: Máximo de retentativas exponenciais com Full Jitter.
        user_agent: Cabeçalho `User-Agent` obrigatório de auditoria cívica.
        outlier_thresholds: Parâmetros estatísticos para `flagged_sections`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = SettingsConfigDict(
        env_prefix="PULSO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    resources_dir: Path = DEFAULT_RESOURCES_DIR
    data_dir: Path = Path("data")
    db_path: Path = Path("data/pulso_eleitoral.duckdb")
    workers: Annotated[int, Field(ge=1, le=64)] = 8
    batch_size: Annotated[int, Field(ge=1)] = 10_000
    max_in_flight_multiplier: Annotated[int, Field(ge=1, le=64)] = 16
    cdn_base_url: str = "https://resultados.tse.jus.br/oficial"
    open_data_base_url: str = (
        "https://cdn.tse.jus.br/estatistica/sead/odsele/bu_imgbu_logjez_rdv_vscmr"
    )
    max_concurrent_requests: Annotated[int, Field(ge=1, le=256)] = 32
    requests_per_second: Annotated[float, Field(gt=0.0, le=500.0)] = 50.0
    http_max_connections: Annotated[int, Field(ge=1, le=512)] = 64
    http_max_keepalive_connections: Annotated[int, Field(ge=1, le=256)] = 32
    http_timeout_seconds: Annotated[float, Field(gt=0.0)] = 30.0
    http_max_retries: Annotated[int, Field(ge=1, le=10)] = 5
    user_agent: str = "PulsoEleitoral-AuditPipeline/0.1 (+reproducible-civic-audit)"
    outlier_thresholds: OutlierThresholds = Field(default_factory=OutlierThresholds)

    @property
    def max_in_flight(self) -> int:
        """Retorna a capacidade máxima da fila limitada de backpressure.

        Args:
            Nenhum.

        Returns:
            Inteiro correspondente a `workers * max_in_flight_multiplier`.

        Raises:
            Nenhum.
        """
        return self.workers * self.max_in_flight_multiplier

    @property
    def processed_dir(self) -> Path:
        """Retorna o diretório base das partições Parquet consolidadas.

        Args:
            Nenhum.

        Returns:
            Caminho `data_dir / "processed"`.

        Raises:
            Nenhum.
        """
        return self.data_dir / "processed"
