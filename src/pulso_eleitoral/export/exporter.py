"""Exportador determinístico de payloads JSON imutáveis (`REQ-EXP-01`).

Gera a árvore completa de artefatos estáticos validados por Pydantic v2 e
armazenados com `orjson`, garantindo zero `NaN`/`Infinity`, arredondamento em 4
casas decimais, timestamps BRT (`-03:00`) e orçamento de payload (`<= 250 KB`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from pulso_eleitoral import __version__
from pulso_eleitoral.analytics.consolidator import DuckDbConsolidator
from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings
from pulso_eleitoral.contracts.exceptions import ContractValidationError
from pulso_eleitoral.export.models import (
    FlaggedCountsByTier,
    FlaggedSectionItem,
    FlaggedSectionsPayload,
    MetadataPayload,
    MunicipalitiesPayload,
    MunicipalitySummaryItem,
    NationalSummaryPayload,
    OutlierThresholdsPayload,
    StatesSummaryPayload,
    StateSummaryItem,
    export_json_schemas,
)


def compute_file_sha256(path: Path) -> str:
    """Calcula o digest SHA-256 hexadecimal de um arquivo físico em disco.

    Args:
        path: Caminho do arquivo a inspecionar.

    Returns:
        String hexadecimal de 64 caracteres em minúsculas.

    Raises:
        Nenhum.
    """
    if not path.is_file():
        return "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(64 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def _format_brt_timestamp(val: Any) -> str | None:
    """Formata valor datetime ou string em timestamp ISO-8601 com sufixo BRT `-03:00`.

    Args:
        val: Valor datetime, string ou None.

    Returns:
        String formatada `YYYY-MM-DDTHH:MM:SS-03:00` ou `None`.

    Raises:
        Nenhum.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%dT%H:%M:%S-03:00")
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned:
            return None
        if cleaned.endswith("-03:00"):
            return cleaned
        return f"{cleaned[:19]}-03:00"
    return None


class StaticJsonExporter:
    """Gerenciador de exportação determinística dos artefatos JSON para CDN.

    Args:
        settings: Configurações operacionais e caminhos.
        run_cfg: Configuração do pleito e turnos ativos.
        consolidator: Instância conectada de `DuckDbConsolidator` opcional.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        settings: PipelineSettings,
        run_cfg: ElectionRunConfig,
        consolidator: DuckDbConsolidator | None = None,
    ) -> None:
        """Inicializa o exportador estático.

        Args:
            settings: Configurações do pipeline.
            run_cfg: Configurações do pleito.
            consolidator: Consolidador DuckDB opcional.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._settings = settings
        self._run_cfg = run_cfg
        self._consolidator = consolidator or DuckDbConsolidator(settings)

    def export_all(self, output_dir: Path | None = None) -> dict[str, Path]:
        """Gera todos os arquivos JSON estáticos validados contra os contratos.

        Args:
            output_dir: Diretório raiz customizado de saída.

        Returns:
            Dicionário com os caminhos absolutos dos arquivos gerados.

        Raises:
            ContractValidationError: Se o orçamento inicial exceder 250 KB ou faltar
                dados necessários no banco consolidado.
        """
        assert self._run_cfg.cutoff_mode is not None
        ano = self._run_cfg.ano_eleicao
        turno = self._run_cfg.turno

        base_out = output_dir or (
            self._settings.data_dir / "exported" / f"ele{ano}" / f"turno{turno}"
        )
        base_out.mkdir(parents=True, exist_ok=True)
        mun_dir = base_out / "municipalities"
        mun_dir.mkdir(parents=True, exist_ok=True)
        flagged_dir = base_out / "flagged_sections"
        flagged_dir.mkdir(parents=True, exist_ok=True)

        generated_files: dict[str, Path] = {}

        # 1. Contagens de Tiers a partir de flagged_sections
        tier_counts_rows = self._consolidator.query(
            """
            SELECT severidade_sinalizacao, COUNT(*) as cnt
            FROM flagged_sections
            GROUP BY severidade_sinalizacao;
            """
        )
        tier_counts = {
            r["severidade_sinalizacao"]: int(r["cnt"]) for r in tier_counts_rows
        }
        flagged_counts = FlaggedCountsByTier(
            TIER_3_CRITICAL_ANOMALY=tier_counts.get("TIER_3_CRITICAL_ANOMALY", 0),
            TIER_2_STATISTICAL_OUTLIER=tier_counts.get("TIER_2_STATISTICAL_OUTLIER", 0),
            TIER_1_POST_17H_NO_BIO=tier_counts.get("TIER_1_POST_17H_NO_BIO", 0),
        )

        # 2. national_summary.json
        nat_rows = self._consolidator.query("SELECT * FROM summary_national LIMIT 1;")
        if not nat_rows:
            raise ContractValidationError(
                "Nenhum dado consolidado encontrado em summary_national."
            )
        nat_r = nat_rows[0]
        manifest_total = int(nat_r["total_secoes_manifesto"])
        analisadas_total = int(nat_r["total_secoes_analisadas"])
        cobertura_pct = (
            round((analisadas_total * 100.0) / manifest_total, 4)
            if manifest_total > 0
            else 0.0
        )

        nat_payload = NationalSummaryPayload(
            ano_eleicao=ano,
            turno=turno,
            total_secoes_manifesto=manifest_total,
            total_secoes_analisadas=analisadas_total,
            total_secoes_nao_processadas=int(nat_r["total_secoes_nao_processadas"]),
            cobertura_secoes_pct=cobertura_pct,
            total_aptos_brasil=int(nat_r["total_aptos_brasil"]),
            total_votos_brasil=int(nat_r["total_votos_brasil"]),
            votos_ate_17h_brasil=int(nat_r["votos_ate_17h_brasil"]),
            votos_apos_17h_brasil=int(nat_r["votos_apos_17h_brasil"]),
            sem_bio_ate_17h_brasil=int(nat_r["sem_bio_ate_17h_brasil"]),
            sem_bio_apos_17h_brasil=int(nat_r["sem_bio_apos_17h_brasil"]),
            pct_apos_17h=float(nat_r["pct_apos_17h"] or 0.0),
            pct_sem_bio_ate_17h=float(nat_r["pct_sem_bio_ate_17h"] or 0.0),
            pct_sem_bio_apos_17h=float(nat_r["pct_sem_bio_apos_17h"] or 0.0),
            flagged_counts_by_tier=flagged_counts,
        )
        nat_path = base_out / "national_summary.json"
        nat_path.write_bytes(
            orjson.dumps(nat_payload.model_dump(), option=orjson.OPT_INDENT_2)
        )
        generated_files["national_summary"] = nat_path

        # 3. states_summary.json
        uf_tier_rows = self._consolidator.query(
            """
            SELECT uf, severidade_sinalizacao, COUNT(*) as cnt
            FROM flagged_sections
            WHERE severidade_sinalizacao IN (
                'TIER_2_STATISTICAL_OUTLIER',
                'TIER_3_CRITICAL_ANOMALY'
            )
            GROUP BY uf, severidade_sinalizacao;
            """
        )
        tier2_by_uf: dict[str, int] = {}
        tier3_by_uf: dict[str, int] = {}
        for r in uf_tier_rows:
            uf_name = str(r["uf"])
            sev = str(r["severidade_sinalizacao"])
            cnt = int(r["cnt"])
            if sev == "TIER_2_STATISTICAL_OUTLIER":
                tier2_by_uf[uf_name] = cnt
            elif sev == "TIER_3_CRITICAL_ANOMALY":
                tier3_by_uf[uf_name] = cnt

        uf_rows = self._consolidator.query("SELECT * FROM summary_by_uf;")
        state_items: list[StateSummaryItem] = []
        for r in uf_rows:
            uf_code = str(r["uf"])
            state_items.append(
                StateSummaryItem(
                    uf=uf_code,
                    total_secoes_manifesto=int(r["total_secoes_manifesto"]),
                    total_secoes_analisadas=int(r["total_secoes_analisadas"]),
                    total_secoes_nao_processadas=int(r["total_secoes_nao_processadas"]),
                    total_votos=int(r["total_votos_uf"]),
                    votos_ate_17h=int(r["votos_ate_17h_uf"]),
                    votos_apos_17h=int(r["votos_apos_17h_uf"]),
                    sem_bio_ate_17h=int(r["sem_bio_ate_17h_uf"]),
                    sem_bio_apos_17h=int(r["sem_bio_apos_17h_uf"]),
                    pct_votos_apos_17h=float(r["pct_apos_17h"] or 0.0),
                    pct_sem_bio_ate_17h=float(r["pct_sem_bio_ate_17h"] or 0.0),
                    pct_sem_bio_apos_17h=float(r["pct_sem_bio_apos_17h"] or 0.0),
                    uf_mean_sem_bio_pos_17h=float(
                        r["avg_pct_sem_bio_pos_17h_uf"] or 0.0
                    ),
                    uf_std_sem_bio_pos_17h=float(
                        r["stddev_pct_sem_bio_pos_17h_uf"] or 0.0
                    ),
                    tier_2_outliers_count=tier2_by_uf.get(uf_code, 0),
                    tier_3_anomalies_count=tier3_by_uf.get(uf_code, 0),
                )
            )

        states_payload = StatesSummaryPayload(
            ano_eleicao=ano,
            turno=turno,
            states=state_items,
        )
        states_path = base_out / "states_summary.json"
        states_path.write_bytes(
            orjson.dumps(states_payload.model_dump(), option=orjson.OPT_INDENT_2)
        )
        generated_files["states_summary"] = states_path

        # 4. municipalities/{UF}.json
        mun_rows = self._consolidator.query("SELECT * FROM summary_by_municipio;")
        mun_by_uf: dict[str, list[MunicipalitySummaryItem]] = {}
        for r in mun_rows:
            uf_code = str(r["uf"])
            item = MunicipalitySummaryItem(
                municipio_cod=int(r["municipio_cod"]),
                municipio_ibge=(
                    int(r["municipio_ibge"])
                    if r.get("municipio_ibge") is not None
                    else None
                ),
                municipio_nome=str(r["municipio_nome"]),
                fuso_horario_offset_brt=int(r["fuso_horario_offset_brt"]),
                total_secoes_manifesto=int(r["total_secoes_manifesto"]),
                total_secoes_analisadas=int(r["total_secoes_analisadas"]),
                total_secoes_nao_processadas=int(r["total_secoes_nao_processadas"]),
                total_aptos=int(r["total_aptos_municipio"]),
                total_votos=int(r["total_votos_municipio"]),
                votos_ate_17h=int(r["votos_ate_17h_municipio"]),
                votos_apos_17h=int(r["votos_apos_17h_municipio"]),
                sem_bio_ate_17h=int(r["sem_bio_ate_17h_municipio"]),
                sem_bio_apos_17h=int(r["sem_bio_apos_17h_municipio"]),
                pct_apos_17h=float(r["pct_apos_17h"] or 0.0),
                pct_sem_bio_ate_17h=float(r["pct_sem_bio_ate_17h"] or 0.0),
                pct_sem_bio_apos_17h=float(r["pct_sem_bio_apos_17h"] or 0.0),
            )
            mun_by_uf.setdefault(uf_code, []).append(item)

        for uf_code, m_list in mun_by_uf.items():
            payload = MunicipalitiesPayload(
                ano_eleicao=ano,
                turno=turno,
                uf=uf_code,
                municipalities=m_list,
            )
            p = mun_dir / f"{uf_code}.json"
            p.write_bytes(orjson.dumps(payload.model_dump()))
            generated_files[f"municipalities_{uf_code}"] = p

        # 5. flagged_sections.json (index e por UF)
        flagged_rows = self._consolidator.query("SELECT * FROM flagged_sections;")
        all_flagged: list[FlaggedSectionItem] = []
        flagged_by_uf: dict[str, list[FlaggedSectionItem]] = {}

        for r in flagged_rows:
            uf_code = str(r["uf"])
            flagged_item = FlaggedSectionItem(
                uf=uf_code,
                municipio_cod=int(r["municipio_cod"]),
                municipio_nome=str(r["municipio_nome"]),
                zona=int(r["zona"]),
                secao=int(r["secao"]),
                fuso_horario_offset_brt=int(r["fuso_horario_offset_brt"]),
                total_aptos=(
                    int(r["total_aptos"]) if r.get("total_aptos") is not None else None
                ),
                total_votos=int(r["total_votos"]),
                votos_ate_17h=int(r["votos_ate_17h"]),
                votos_apos_17h=int(r["votos_apos_17h"]),
                sem_bio_ate_17h=int(r["sem_bio_ate_17h"]),
                sem_bio_apos_17h=int(r["sem_bio_apos_17h"]),
                pct_votos_apos_17h=float(r["pct_votos_apos_17h"] or 0.0),
                pct_sem_bio_ate_17h=float(r["pct_sem_bio_ate_17h"] or 0.0),
                pct_sem_bio_apos_17h=float(r["pct_sem_bio_apos_17h"] or 0.0),
                delta_sem_bio_pp=float(r["delta_sem_bio_pp"] or 0.0),
                z_score_uf_pos_17h=float(r["z_score_uf_pos_17h"] or 0.0),
                divergencia_bu_log=(
                    int(r["divergencia_bu_log"])
                    if r.get("divergencia_bu_log") is not None
                    else None
                ),
                relogio_suspeito=bool(r["relogio_suspeito"]),
                voto_apos_encerramento=bool(r["voto_apos_encerramento"]),
                horario_ultimo_voto_brt=_format_brt_timestamp(
                    r.get("horario_ultimo_voto_brt")
                ),
                severidade_sinalizacao=str(r["severidade_sinalizacao"]),
            )
            all_flagged.append(flagged_item)
            flagged_by_uf.setdefault(uf_code, []).append(flagged_item)

        # Top 1.000 nacional
        top_1000 = all_flagged[:1000]
        index_payload = FlaggedSectionsPayload(
            ano_eleicao=ano,
            turno=turno,
            scope="NATIONAL_TOP_1000",
            total_matching_sections=len(all_flagged),
            returned_sections=len(top_1000),
            items=top_1000,
        )
        index_bytes = orjson.dumps(index_payload.model_dump())
        idx_path = flagged_dir / "index.json"
        idx_path.write_bytes(index_bytes)
        generated_files["flagged_index"] = idx_path

        # Alias flagged_sections.json na raiz para compatibilidade
        root_alias_path = base_out / "flagged_sections.json"
        root_alias_path.write_bytes(index_bytes)
        generated_files["flagged_root_alias"] = root_alias_path

        # Top 2.000 por UF
        for uf_code, sec_list in flagged_by_uf.items():
            top_uf = sec_list[:2000]
            uf_payload = FlaggedSectionsPayload(
                ano_eleicao=ano,
                turno=turno,
                scope=f"UF_{uf_code}_TOP_2000",
                total_matching_sections=len(sec_list),
                returned_sections=len(top_uf),
                items=top_uf,
            )
            p = flagged_dir / f"{uf_code}.json"
            p.write_bytes(orjson.dumps(uf_payload.model_dump()))
            generated_files[f"flagged_{uf_code}"] = p

        # 6. metadata.json
        meta_payload = MetadataPayload(
            schema_version="1.0.0",
            pipeline_version=__version__,
            ano_eleicao=ano,
            turno=turno,
            pleito_id=self._run_cfg.pleito_id,
            cutoff_mode=self._run_cfg.cutoff_mode.value,
            generated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            duckdb_sha256=compute_file_sha256(self._settings.db_path),
            outlier_thresholds=OutlierThresholdsPayload(
                min_votos_pos_17h=self._settings.outlier_thresholds.min_votos_pos_17h,
                delta_sem_bio_pp=self._settings.outlier_thresholds.delta_sem_bio_pp,
                z_score_uf=self._settings.outlier_thresholds.z_score_uf,
            ),
        )
        meta_path = base_out / "metadata.json"
        meta_path.write_bytes(
            orjson.dumps(meta_payload.model_dump(), option=orjson.OPT_INDENT_2)
        )
        generated_files["metadata"] = meta_path

        # 7. Verificação do Orçamento SLA de Payload Inicial (<= 250 KB)
        initial_bundle_size = (
            meta_path.stat().st_size
            + nat_path.stat().st_size
            + states_path.stat().st_size
        )
        if initial_bundle_size > 250 * 1024:
            raise ContractValidationError(
                f"Payload inicial excedeu o orçamento SLA de 250 KB: "
                f"{initial_bundle_size / 1024:.2f} KB."
            )

        # 8. Exportar schemas JSON
        export_json_schemas(base_out / "schemas")

        return generated_files
