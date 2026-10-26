"""Modelos Pydantic v2 e gerador de JSON Schema para a API estática (`REQ-EXP-01`).

Define os contratos estritos dos payloads JSON imutáveis especificados em
`specs/04-static-api-and-frontend.md` e provê exportação do JSON Schema Draft 2020-12
para sincronização com o TypeScript do frontend.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class OutlierThresholdsPayload(BaseModel):
    """Limiares estatísticos aplicados na classificação de outliers.

    Args:
        min_votos_pos_17h: Votos mínimos pós-17h para elegibilidade.
        delta_sem_bio_pp: Salto percentual mínimo pós vs pré-17h.
        z_score_uf: Limiar de Z-Score frente à distribuição estadual.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    min_votos_pos_17h: Annotated[int, Field(ge=1)] = 10
    delta_sem_bio_pp: Annotated[float, Field(gt=0.0)] = 15.0
    z_score_uf: Annotated[float, Field(gt=0.0)] = 3.0


class MetadataPayload(BaseModel):
    """Contrato de `metadata.json` contendo versão, parâmetros e hash SHA-256.

    Args:
        schema_version: Versão do contrato JSON.
        pipeline_version: Versão da release do pipeline Pulso Eleitoral.
        ano_eleicao: Ano da eleição.
        turno: Número do turno (`1` ou `2`).
        pleito_id: Identificador numérico do pleito TSE.
        cutoff_mode: Modo de corte (`UNIFIED_BRT` ou `LOCAL_TIME`).
        generated_at: Timestamp UTC da geração dos artefatos estáticos.
        duckdb_sha256: Digest SHA-256 do arquivo `.duckdb` consolidado.
        outlier_thresholds: Parâmetros estatísticos ativos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0.0"
    pipeline_version: str = "0.1.0"
    ano_eleicao: int
    turno: int
    pleito_id: int
    cutoff_mode: str
    generated_at: str
    duckdb_sha256: str
    outlier_thresholds: OutlierThresholdsPayload


class FlaggedCountsByTier(BaseModel):
    """Contadores consolidados de seções sinalizadas por nível de severidade.

    Args:
        TIER_3_CRITICAL_ANOMALY: Seções com anomalia crítica (RTC, BU, pós-fecho).
        TIER_2_STATISTICAL_OUTLIER: Seções com salto anômalo pós-17h (delta ou Z).
        TIER_1_POST_17H_NO_BIO: Seções com ao menos 1 voto manual pós-17h.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    TIER_3_CRITICAL_ANOMALY: int = 0
    TIER_2_STATISTICAL_OUTLIER: int = 0
    TIER_1_POST_17H_NO_BIO: int = 0


class NationalSummaryPayload(BaseModel):
    """Contrato de `national_summary.json` contendo KPIs do Brasil.

    Args:
        ano_eleicao: Ano da eleição.
        turno: Turno (`1` ou `2`).
        total_secoes_manifesto: Seções totais conhecidas.
        total_secoes_analisadas: Seções com `SUCCESS`.
        total_secoes_nao_processadas: Seções com erro.
        cobertura_secoes_pct: Percentual de cobertura analisada.
        total_aptos_brasil: Eleitores aptos totais.
        total_votos_brasil: Votos confirmados totais.
        votos_ate_17h_brasil: Votos até as 17:00:00 BRT.
        votos_apos_17h_brasil: Votos a partir das 17:00:00 BRT.
        sem_bio_ate_17h_brasil: Votos sem biometria até 17h.
        sem_bio_apos_17h_brasil: Votos sem biometria pós-17h.
        pct_apos_17h: Percentual de votos pós-17h.
        pct_sem_bio_ate_17h: Taxa sem biometria pré-17h.
        pct_sem_bio_apos_17h: Taxa sem biometria pós-17h.
        flagged_counts_by_tier: Contagem de seções por Tier.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    ano_eleicao: int
    turno: int
    total_secoes_manifesto: int
    total_secoes_analisadas: int
    total_secoes_nao_processadas: int
    cobertura_secoes_pct: float
    total_aptos_brasil: int
    total_votos_brasil: int
    votos_ate_17h_brasil: int
    votos_apos_17h_brasil: int
    sem_bio_ate_17h_brasil: int
    sem_bio_apos_17h_brasil: int
    pct_apos_17h: float
    pct_sem_bio_ate_17h: float
    pct_sem_bio_apos_17h: float
    flagged_counts_by_tier: FlaggedCountsByTier


class StateSummaryItem(BaseModel):
    """KPIs agregados de uma Unidade Federativa em `states_summary.json`.

    Args:
        uf: Sigla da UF.
        total_secoes_manifesto: Seções no manifesto.
        total_secoes_analisadas: Seções com `SUCCESS`.
        total_secoes_nao_processadas: Seções não processadas.
        total_votos: Total de votos confirmados na UF.
        votos_ate_17h: Votos antes das 17h.
        votos_apos_17h: Votos a partir das 17h.
        sem_bio_ate_17h: Votos sem biometria antes das 17h.
        sem_bio_apos_17h: Votos sem biometria pós-17h.
        pct_votos_apos_17h: Percentual de votos pós-17h.
        pct_sem_bio_ate_17h: Taxa sem biometria pré-17h.
        pct_sem_bio_apos_17h: Taxa sem biometria pós-17h.
        uf_mean_sem_bio_pos_17h: Média estadual pós-17h (seções >= 10 votos).
        uf_std_sem_bio_pos_17h: Desvio padrão populacional estadual pós-17h.
        tier_2_outliers_count: Total de seções TIER_2 na UF.
        tier_3_anomalies_count: Total de seções TIER_3 na UF.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    uf: str
    total_secoes_manifesto: int
    total_secoes_analisadas: int
    total_secoes_nao_processadas: int
    total_votos: int
    votos_ate_17h: int
    votos_apos_17h: int
    sem_bio_ate_17h: int
    sem_bio_apos_17h: int
    pct_votos_apos_17h: float
    pct_sem_bio_ate_17h: float
    pct_sem_bio_apos_17h: float
    uf_mean_sem_bio_pos_17h: float
    uf_std_sem_bio_pos_17h: float
    tier_2_outliers_count: int
    tier_3_anomalies_count: int


class StatesSummaryPayload(BaseModel):
    """Contrato raiz de `states_summary.json`.

    Args:
        ano_eleicao: Ano da eleição.
        turno: Turno (`1` ou `2`).
        states: Lista ordenada das 27 UFs.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    ano_eleicao: int
    turno: int
    states: list[StateSummaryItem]


class MunicipalitySummaryItem(BaseModel):
    """Resumo consolidado de um município em `municipalities/{UF}.json`.

    Args:
        municipio_cod: Código TSE do município.
        municipio_ibge: Código IBGE de 7 dígitos ou `None`.
        municipio_nome: Nome oficial do município.
        fuso_horario_offset_brt: Diferença em horas vs Brasília.
        total_secoes_manifesto: Total de seções do município.
        total_secoes_analisadas: Seções com `SUCCESS`.
        total_secoes_nao_processadas: Seções com falha.
        total_aptos: Total de aptos informado.
        total_votos: Votos confirmados totais.
        votos_ate_17h: Votos até as 17h.
        votos_apos_17h: Votos a partir das 17h.
        sem_bio_ate_17h: Votos manuais até as 17h.
        sem_bio_apos_17h: Votos manuais a partir das 17h.
        pct_apos_17h: Percentual de votos pós-17h.
        pct_sem_bio_ate_17h: Taxa sem biometria pré-17h.
        pct_sem_bio_apos_17h: Taxa sem biometria pós-17h.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    municipio_cod: int
    municipio_ibge: int | None
    municipio_nome: str
    fuso_horario_offset_brt: int
    total_secoes_manifesto: int
    total_secoes_analisadas: int
    total_secoes_nao_processadas: int
    total_aptos: int
    total_votos: int
    votos_ate_17h: int
    votos_apos_17h: int
    sem_bio_ate_17h: int
    sem_bio_apos_17h: int
    pct_apos_17h: float
    pct_sem_bio_ate_17h: float
    pct_sem_bio_apos_17h: float


class MunicipalitiesPayload(BaseModel):
    """Contrato de resumo de municípios por UF `municipalities/{UF}.json`.

    Args:
        ano_eleicao: Ano da eleição.
        turno: Turno (`1` ou `2`).
        uf: Sigla da UF.
        municipalities: Lista de municípios da UF.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    ano_eleicao: int
    turno: int
    uf: str
    municipalities: list[MunicipalitySummaryItem]


class FlaggedSectionItem(BaseModel):
    """Item individual de seção eleitoral em `flagged_sections`.

    Args:
        uf: Sigla da UF.
        municipio_cod: Código TSE do município.
        municipio_nome: Nome oficial do município.
        zona: Número da zona eleitoral.
        secao: Número da seção eleitoral.
        fuso_horario_offset_brt: Offset em horas vs Brasília.
        total_aptos: Total de eleitores aptos ou `None`.
        total_votos: Total de votos computados.
        votos_ate_17h: Votos até as 17h.
        votos_apos_17h: Votos a partir das 17h.
        sem_bio_ate_17h: Votos manuais até as 17h.
        sem_bio_apos_17h: Votos manuais a partir das 17h.
        pct_votos_apos_17h: Percentual pós-17h.
        pct_sem_bio_ate_17h: Taxa sem biometria pré-17h.
        pct_sem_bio_apos_17h: Taxa sem biometria pós-17h.
        delta_sem_bio_pp: Diferença em p.p. pós vs pré-17h.
        z_score_uf_pos_17h: Z-Score frente à distribuição estadual.
        divergencia_bu_log: Diferença entre BU e log ou `None`.
        relogio_suspeito: Indica anomalia de relógio.
        voto_apos_encerramento: Indica voto após encerramento da seção.
        horario_ultimo_voto_brt: Timestamp ISO-8601 do último voto ou `None`.
        severidade_sinalizacao: Tier canônico (`TIER_3`, `TIER_2`, `TIER_1`).

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    uf: str
    municipio_cod: int
    municipio_nome: str
    zona: int
    secao: int
    fuso_horario_offset_brt: int
    total_aptos: int | None
    total_votos: int
    votos_ate_17h: int
    votos_apos_17h: int
    sem_bio_ate_17h: int
    sem_bio_apos_17h: int
    pct_votos_apos_17h: float
    pct_sem_bio_ate_17h: float
    pct_sem_bio_apos_17h: float
    delta_sem_bio_pp: float
    z_score_uf_pos_17h: float
    divergencia_bu_log: int | None
    relogio_suspeito: bool
    voto_apos_encerramento: bool
    horario_ultimo_voto_brt: str | None
    severidade_sinalizacao: str


class FlaggedSectionsPayload(BaseModel):
    """Contrato de `flagged_sections.json`, `index.json` e shards por UF.

    Args:
        ano_eleicao: Ano da eleição.
        turno: Turno (`1` ou `2`).
        scope: Escopo do artefato (ex.: `NATIONAL_TOP_1000` ou `UF_SP_TOP_2000`).
        total_matching_sections: Total de seções sinalizadas no escopo.
        returned_sections: Quantidade de itens presentes na lista `items`.
        items: Lista ordenada de seções sinalizadas.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    model_config = ConfigDict(frozen=True)

    ano_eleicao: int
    turno: int
    scope: str
    total_matching_sections: int
    returned_sections: int
    items: list[FlaggedSectionItem]


def export_json_schemas(output_dir: Path) -> dict[str, Path]:
    """Gera arquivos JSON Schema Draft 2020-12 a partir dos modelos Pydantic v2.

    Args:
        output_dir: Diretório de destino para os arquivos de schema `.json`.

    Returns:
        Dicionário mapeando nome do schema ao caminho do arquivo gerado.

    Raises:
        Nenhum.
    """
    import orjson

    output_dir.mkdir(parents=True, exist_ok=True)
    targets: dict[str, type[BaseModel]] = {
        "metadata.schema.json": MetadataPayload,
        "national_summary.schema.json": NationalSummaryPayload,
        "states_summary.schema.json": StatesSummaryPayload,
        "municipalities.schema.json": MunicipalitiesPayload,
        "flagged_sections.schema.json": FlaggedSectionsPayload,
    }
    result: dict[str, Path] = {}
    for filename, model_cls in targets.items():
        schema_dict = model_cls.model_json_schema()
        target_path = output_dir / filename
        target_path.write_bytes(
            orjson.dumps(
                schema_dict,
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
            )
        )
        result[filename] = target_path
    return result
