"""Verificador determinístico pós-execução e auditoria de invariantes (`REQ-QA-01`).

Valida integridade cruzada (Brasil == Soma UFs == Soma Municípios), cumprimento
das Invariantes 1 a 6, conformidade de schemas dos JSONs exportados e SLAs de
armazenamento (DuckDB `<= 200 MB`, bundle inicial `<= 250 KB`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import orjson

from pulso_eleitoral.analytics.consolidator import DuckDbConsolidator
from pulso_eleitoral.config import PipelineSettings
from pulso_eleitoral.contracts.exceptions import (
    ContractValidationError,
    InvariantViolationError,
)
from pulso_eleitoral.export.models import (
    MetadataPayload,
    NationalSummaryPayload,
    StatesSummaryPayload,
)


@dataclass(slots=True, frozen=True)
class PipelineVerificationReport:
    """Relatório estruturado de verificação e auditoria do pipeline.

    Args:
        db_path: Caminho do banco DuckDB auditado.
        db_size_mb: Tamanho do banco em megabytes.
        total_sections: Total de seções avaliadas.
        success_sections: Total de seções bem-sucedidas.
        error_sections: Total de seções não processadas registradas.
        invariants_passed: `True` se todas as invariantes forem válidas.
        cross_sums_passed: `True` se as somas cruzadas baterem exatamente.
        static_bundle_size_kb: Tamanho do pacote inicial estático em KB.
        json_schemas_valid: `True` se os artefatos JSON forem válidos.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    db_path: Path
    db_size_mb: float
    total_sections: int
    success_sections: int
    error_sections: int
    invariants_passed: bool
    cross_sums_passed: bool
    static_bundle_size_kb: float
    json_schemas_valid: bool


class PipelineVerifier:
    """Auditor de integridade cruzada e SLAs do pipeline Pulso Eleitoral.

    Args:
        settings: Configurações contendo caminhos do banco DuckDB.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(self, settings: PipelineSettings) -> None:
        """Inicializa o verificador analítico.

        Args:
            settings: Configurações operacionais.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._settings = settings
        self._consolidator = DuckDbConsolidator(settings)

    def verify_all(
        self,
        *,
        json_dir: Path | None = None,
    ) -> PipelineVerificationReport:
        """Executa a suíte completa de auditoria contra o DuckDB e artefatos JSON.

        Args:
            json_dir: Diretório raiz opcional contendo os artefatos JSON exportados.

        Returns:
            Instância de `PipelineVerificationReport` detalhando a auditoria.

        Raises:
            ContractValidationError: Se o banco DuckDB não existir ou SLAs falharem.
            InvariantViolationError: Se qualquer invariante matemática for violada.
        """
        if not self._settings.db_path.is_file():
            raise ContractValidationError(
                f"Banco DuckDB inexistente para verificação: {self._settings.db_path}"
            )

        db_size = self._settings.db_path.stat().st_size
        db_size_mb = db_size / (1024 * 1024)
        if db_size > 200 * 1024 * 1024:
            raise ContractValidationError(
                f"SLA de armazenamento DuckDB violado: {db_size_mb:.2f} MB > 200 MB."
            )

        # 1. Checagem das Invariantes 1 a 5 no DuckDB
        inv1 = self._consolidator.query(
            """
            SELECT COUNT(*) AS cnt
            FROM raw_section_metrics
            WHERE status_processamento = 'SUCCESS'
              AND total_votos <> (votos_ate_17h + votos_apos_17h);
            """
        )
        if inv1 and int(inv1[0]["cnt"]) > 0:
            raise InvariantViolationError(
                f"Invariante 1 violada em {inv1[0]['cnt']} seções no DuckDB."
            )

        inv2 = self._consolidator.query(
            """
            SELECT COUNT(*) AS cnt
            FROM raw_section_metrics
            WHERE status_processamento = 'SUCCESS'
              AND (sem_bio_ate_17h < 0 OR sem_bio_ate_17h > votos_ate_17h);
            """
        )
        if inv2 and int(inv2[0]["cnt"]) > 0:
            raise InvariantViolationError(
                f"Invariante 2 violada em {inv2[0]['cnt']} seções no DuckDB."
            )

        inv3 = self._consolidator.query(
            """
            SELECT COUNT(*) AS cnt
            FROM raw_section_metrics
            WHERE status_processamento = 'SUCCESS'
              AND (sem_bio_apos_17h < 0 OR sem_bio_apos_17h > votos_apos_17h);
            """
        )
        if inv3 and int(inv3[0]["cnt"]) > 0:
            raise InvariantViolationError(
                f"Invariante 3 violada em {inv3[0]['cnt']} seções no DuckDB."
            )

        inv4 = self._consolidator.query(
            """
            SELECT COUNT(*) AS cnt
            FROM raw_section_metrics
            WHERE status_processamento = 'SUCCESS'
              AND total_votos = 0
              AND (
                  horario_primeiro_voto_brt IS NOT NULL
                  OR horario_ultimo_voto_brt IS NOT NULL
              );
            """
        )
        if inv4 and int(inv4[0]["cnt"]) > 0:
            raise InvariantViolationError(
                f"Invariante 4 violada em {inv4[0]['cnt']} seções no DuckDB."
            )

        inv5 = self._consolidator.query(
            """
            SELECT COUNT(*) AS cnt
            FROM raw_section_metrics
            WHERE status_processamento = 'SUCCESS'
              AND total_votos > 0
              AND (
                  horario_primeiro_voto_brt IS NULL
                  OR horario_ultimo_voto_brt IS NULL
                  OR horario_primeiro_voto_brt > horario_ultimo_voto_brt
              );
            """
        )
        if inv5 and int(inv5[0]["cnt"]) > 0:
            raise InvariantViolationError(
                f"Invariante 5 violada em {inv5[0]['cnt']} seções no DuckDB."
            )

        # 2. Invariante 6: Completude do Denominador
        nat_rows = self._consolidator.query(
            """
            SELECT
                total_secoes_manifesto,
                total_secoes_analisadas,
                total_secoes_nao_processadas,
                total_votos_brasil
            FROM summary_national
            LIMIT 1;
            """
        )
        if not nat_rows:
            raise ContractValidationError("View summary_national sem dados.")

        nat = nat_rows[0]
        manifest = int(nat["total_secoes_manifesto"])
        success = int(nat["total_secoes_analisadas"])
        errors = int(nat["total_secoes_nao_processadas"])
        if manifest != (success + errors):
            raise InvariantViolationError(
                f"Invariante 6 violada: total_manifest ({manifest}) != "
                f"success ({success}) + errors ({errors})."
            )

        # 3. Somas Cruzadas (Nacional == Soma UFs == Soma Municípios)
        cross_uf = self._consolidator.query(
            """
            SELECT
                COALESCE(SUM(total_votos_uf), 0) AS sum_votos_uf,
                COALESCE(SUM(total_secoes_analisadas), 0) AS sum_secoes_uf
            FROM summary_by_uf;
            """
        )
        cross_mun = self._consolidator.query(
            """
            SELECT
                COALESCE(SUM(total_votos_municipio), 0) AS sum_votos_mun,
                COALESCE(SUM(total_secoes_analisadas), 0) AS sum_secoes_mun
            FROM summary_by_municipio;
            """
        )
        total_votos_brasil = int(nat["total_votos_brasil"])
        sum_votos_uf = int(cross_uf[0]["sum_votos_uf"]) if cross_uf else 0
        sum_votos_mun = int(cross_mun[0]["sum_votos_mun"]) if cross_mun else 0

        if not (total_votos_brasil == sum_votos_uf == sum_votos_mun):
            raise InvariantViolationError(
                f"Divergência de soma cruzada de votos: Brasil={total_votos_brasil}, "
                f"Soma UFs={sum_votos_uf}, Soma Municípios={sum_votos_mun}."
            )

        # 4. Auditoria dos arquivos JSON e SLA de 250 KB
        static_bundle_size_kb = 0.0
        json_valid = True
        if json_dir is not None and json_dir.is_dir():
            meta_file = json_dir / "metadata.json"
            nat_file = json_dir / "national_summary.json"
            states_file = json_dir / "states_summary.json"

            for required_file in (meta_file, nat_file, states_file):
                if not required_file.is_file():
                    raise ContractValidationError(
                        f"Arquivo obrigatório ausente em {json_dir}: "
                        f"{required_file.name}"
                    )

            bundle_bytes = (
                meta_file.stat().st_size
                + nat_file.stat().st_size
                + states_file.stat().st_size
            )
            static_bundle_size_kb = bundle_bytes / 1024
            if bundle_bytes > 250 * 1024:
                raise ContractValidationError(
                    f"SLA de payload inicial estático violado: "
                    f"{static_bundle_size_kb:.2f} KB > 250 KB."
                )

            # Validação Pydantic dos artefatos
            MetadataPayload.model_validate(orjson.loads(meta_file.read_bytes()))
            NationalSummaryPayload.model_validate(orjson.loads(nat_file.read_bytes()))
            StatesSummaryPayload.model_validate(orjson.loads(states_file.read_bytes()))

        return PipelineVerificationReport(
            db_path=self._settings.db_path,
            db_size_mb=round(db_size_mb, 2),
            total_sections=manifest,
            success_sections=success,
            error_sections=errors,
            invariants_passed=True,
            cross_sums_passed=True,
            static_bundle_size_kb=round(static_bundle_size_kb, 2),
            json_schemas_valid=json_valid,
        )
