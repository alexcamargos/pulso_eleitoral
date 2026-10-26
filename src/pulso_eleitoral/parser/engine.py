"""Motor unificado de processamento de seção eleitoral (`agent-parser`).

Orquestra descompactação in-memory, fusão de logs de contingência, execução da
FSM, reconciliação opcional com `.bu` e validação das invariantes matemáticas,
convertendo falhas auditáveis em `UnprocessedSectionError` sem quebrar o lote.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pulso_eleitoral.contracts.exceptions import (
    ProcessingStatus,
    SectionAuditError,
)
from pulso_eleitoral.contracts.models import (
    ParsedSectionMetrics,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.parser.archive import extract_and_merge_section_logs
from pulso_eleitoral.parser.bu_reconciler import decode_bu_metrics
from pulso_eleitoral.parser.fsm import run_log_fsm
from pulso_eleitoral.parser.patterns import load_pattern_profile


def parse_section_bundle(
    bundle: SectionArtifactBundle,
    *,
    profile_id: str | None = None,
    resources_dir: Path | None = None,
) -> ParsedSectionMetrics | UnprocessedSectionError:
    """Processa integralmente um `SectionArtifactBundle` de modo determinístico.

    Compatível com execução direta em workers do `ProcessPoolExecutor`.

    Args:
        bundle: Pacote imutável de artefatos e metadados da seção eleitoral.
        profile_id: Perfil de regex (`v2020` ou `v2022_2026`); se omitido,
            é derivado automaticamente de `bundle.ano_eleicao`.
        resources_dir: Diretório opcional de recursos estáticos.

    Returns:
        `ParsedSectionMetrics` validado contra as invariantes 1..5 em caso de
        sucesso, ou `UnprocessedSectionError` para falhas isoladas de seção.

    Raises:
        InvariantViolationError: Se houver violação interna de invariante matemática.
        ContractValidationError: Se o perfil de regex solicitado não existir.
    """
    resolved_profile_id = profile_id or (
        "v2020" if bundle.ano_eleicao <= 2020 else "v2022_2026"
    )
    profile = load_pattern_profile(resolved_profile_id, resources_dir=resources_dir)

    try:
        merged_lines, qtd_logs = extract_and_merge_section_logs(bundle.log_artifacts)
        fsm_res = run_log_fsm(
            merged_lines,
            election_date_iso=bundle.election_date_iso,
            fuso_horario_offset_brt=bundle.fuso_horario_offset_brt,
            cutoff_mode=bundle.cutoff_mode,
            profile=profile,
        )
    except SectionAuditError as err:
        return UnprocessedSectionError(
            ano_eleicao=bundle.ano_eleicao,
            turno=bundle.turno,
            pleito_id=bundle.pleito_id,
            uf=bundle.uf,
            municipio_cod=bundle.municipio_cod,
            zona=bundle.zona,
            secao=bundle.secao,
            error_code=err.error_code.value,
            error_message=err.message,
            recorded_at=datetime.now(UTC).replace(tzinfo=None),
            source_uri=err.source_uri or bundle.source_uri,
            sha512_expected=err.sha512_expected,
            sha512_actual=err.sha512_actual,
            attempt_count=err.attempt_count,
            municipio_ibge=bundle.municipio_ibge,
            municipio_nome=bundle.municipio_nome,
            fuso_horario_offset_brt=bundle.fuso_horario_offset_brt,
            cutoff_mode=bundle.cutoff_mode,
            total_aptos_manifest=bundle.total_aptos_manifest,
        )

    bu_data = decode_bu_metrics(bundle.bu_raw_bytes, resources_dir=resources_dir)
    total_aptos: int | None
    if bu_data is not None and bu_data.eleitores_aptos is not None:
        total_aptos = bu_data.eleitores_aptos
    elif bundle.total_aptos_manifest is not None:
        total_aptos = bundle.total_aptos_manifest
    else:
        total_aptos = fsm_res.aptos_from_log

    comparecimento_bu = bu_data.comparecimento_bu if bu_data is not None else None
    divergencia_bu_log = (
        comparecimento_bu - fsm_res.total_votos
        if comparecimento_bu is not None
        else None
    )

    metrics = ParsedSectionMetrics(
        ano_eleicao=bundle.ano_eleicao,
        turno=bundle.turno,
        pleito_id=bundle.pleito_id,
        uf=bundle.uf,
        municipio_cod=bundle.municipio_cod,
        municipio_ibge=bundle.municipio_ibge,
        municipio_nome=bundle.municipio_nome,
        zona=bundle.zona,
        secao=bundle.secao,
        fuso_horario_offset_brt=bundle.fuso_horario_offset_brt,
        cutoff_mode=bundle.cutoff_mode,
        qtd_arquivos_log=qtd_logs,
        total_aptos=total_aptos,
        comparecimento_bu=comparecimento_bu,
        total_votos=fsm_res.total_votos,
        divergencia_bu_log=divergencia_bu_log,
        votos_antes_08h=fsm_res.votos_antes_08h,
        votos_ate_17h=fsm_res.votos_ate_17h,
        votos_apos_17h=fsm_res.votos_apos_17h,
        sem_bio_ate_17h=fsm_res.sem_bio_ate_17h,
        sem_bio_apos_17h=fsm_res.sem_bio_apos_17h,
        bio_status_indefinido=fsm_res.bio_status_indefinido,
        tentativas_bio_falhas=fsm_res.tentativas_bio_falhas,
        votos_cancelados_suspensos=fsm_res.votos_cancelados_suspensos,
        qtd_reinicializacoes=fsm_res.qtd_reinicializacoes,
        horario_abertura_brt=fsm_res.horario_abertura_brt,
        horario_primeiro_voto_brt=fsm_res.horario_primeiro_voto_brt,
        horario_ultimo_voto_brt=fsm_res.horario_ultimo_voto_brt,
        horario_encerramento_brt=fsm_res.horario_encerramento_brt,
        relogio_suspeito=fsm_res.relogio_suspeito,
        voto_apos_encerramento=fsm_res.voto_apos_encerramento,
        status_processamento=ProcessingStatus.SUCCESS.value,
    )
    metrics.validate_invariants()
    return metrics
