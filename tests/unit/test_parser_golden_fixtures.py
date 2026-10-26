"""Suíte de validação das Fixtures Áureas `FX-01` a `FX-10` (`REQ-PAR-01`..`03`).

Comprova deterministicamente todos os 10 cenários canônicos e o cenário BDD
Gherkin especificados em `specs/05-testing-evals-and-roadmap.md`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from dataclasses import replace

from pulso_eleitoral.contracts.exceptions import ErrorCode, ProcessingStatus
from pulso_eleitoral.contracts.models import (
    CutoffMode,
    ParsedSectionMetrics,
    UnprocessedSectionError,
)
from pulso_eleitoral.parser import parse_section_bundle
from tests.fixtures.builder import (
    build_fx01_sp_standard,
    build_fx02_df_exact_boundary,
    build_fx03_acre_timezone,
    build_fx04_amazonas_dual_tz,
    build_fx05_fernando_noronha,
    build_fx06_bio_retries_and_abort,
    build_fx07_pre_election_and_reboot,
    build_fx08_contingency_urna_merge,
    build_fx09_rtc_reset_and_bu_divergence,
    build_fx10_corrupt_and_hash_mismatch,
)


def test_fx01_sp_standard_7z_section() -> None:
    """Valida `FX-01`: 10 votos pré-17h (8 bio, 2 manual) em SP (`7z`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    res = parse_section_bundle(build_fx01_sp_standard())
    assert isinstance(res, ParsedSectionMetrics)
    assert res.status_processamento == ProcessingStatus.SUCCESS.value
    assert res.total_votos == 10
    assert res.votos_ate_17h == 10
    assert res.votos_apos_17h == 0
    assert res.sem_bio_ate_17h == 2
    assert res.sem_bio_apos_17h == 0
    assert res.relogio_suspeito is False


def test_fx02_df_exact_17h_boundary_zip() -> None:
    """Valida `FX-02`: Fronteira exata `16:59:59`, `17:00:00`, `17:00:01` (`ZIP`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    res = parse_section_bundle(build_fx02_df_exact_boundary())
    assert isinstance(res, ParsedSectionMetrics)
    assert res.total_votos == 3
    assert res.votos_ate_17h == 1
    assert res.votos_apos_17h == 2
    assert res.sem_bio_ate_17h == 0
    assert res.sem_bio_apos_17h == 1


def test_fx03_acre_timezone_unified_vs_local() -> None:
    """Valida `FX-03`: Rio Branco/AC (`offset=-2`) em `UNIFIED_BRT` e `LOCAL_TIME`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    bundle_brt = build_fx03_acre_timezone()
    res_brt = parse_section_bundle(bundle_brt)
    assert isinstance(res_brt, ParsedSectionMetrics)
    assert res_brt.votos_ate_17h == 1
    assert res_brt.votos_apos_17h == 1
    assert res_brt.relogio_suspeito is False

    # Em pleito <= 2020 (LOCAL_TIME), 15:00:00 local ainda e antes das 17h locais!
    bundle_local = replace(
        bundle_brt,
        ano_eleicao=2020,
        cutoff_mode=CutoffMode.LOCAL_TIME.value,
    )
    res_local = parse_section_bundle(bundle_local)
    assert isinstance(res_local, ParsedSectionMetrics)
    assert res_local.votos_ate_17h == 2
    assert res_local.votos_apos_17h == 0


def test_fx04_southwest_amazonas_vs_manaus() -> None:
    """Valida `FX-04`: Tabatinga (`offset=-2`) vs Manaus (`offset=-1`) às `15:05:00`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    tabatinga, manaus = build_fx04_amazonas_dual_tz()
    res_tab = parse_section_bundle(tabatinga)
    res_man = parse_section_bundle(manaus)

    assert isinstance(res_tab, ParsedSectionMetrics)
    assert isinstance(res_man, ParsedSectionMetrics)
    assert res_tab.votos_ate_17h == 0
    assert res_tab.votos_apos_17h == 1
    assert res_tab.sem_bio_apos_17h == 1

    assert res_man.votos_ate_17h == 1
    assert res_man.votos_apos_17h == 0
    assert res_man.sem_bio_ate_17h == 1


def test_fx05_fernando_noronha_utc_minus_2() -> None:
    """Valida `FX-05`: Fernando de Noronha (`offset=+1`) às `17:30:00` -> `16:30 BRT`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    res = parse_section_bundle(build_fx05_fernando_noronha())
    assert isinstance(res, ParsedSectionMetrics)
    assert res.total_votos == 1
    assert res.votos_ate_17h == 1
    assert res.votos_apos_17h == 0
    assert res.relogio_suspeito is False


def test_fx06_biometric_retries_and_aborted_manual_voter_isolation() -> None:
    """Valida `FX-06` e Gherkin: zero vazamento após cancelamento de mesário.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    res = parse_section_bundle(build_fx06_bio_retries_and_abort())
    assert isinstance(res, ParsedSectionMetrics)
    assert res.total_votos == 2
    assert res.votos_ate_17h == 1
    assert res.votos_apos_17h == 1
    assert res.sem_bio_ate_17h == 0
    assert res.sem_bio_apos_17h == 0
    assert res.tentativas_bio_falhas == 2
    assert res.votos_cancelados_suspensos == 1


def test_fx07_pre_election_load_ignored_and_reboot_clears_buffer() -> None:
    """Valida `FX-07`: Eventos de `D-3` ignorados e reboot limpando `bio_mode`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    res = parse_section_bundle(build_fx07_pre_election_and_reboot())
    assert isinstance(res, ParsedSectionMetrics)
    assert res.total_votos == 1
    assert res.sem_bio_ate_17h == 0
    assert res.qtd_reinicializacoes == 1


def test_fx08_contingency_urna_deduplicated_merge() -> None:
    """Valida `FX-08`: Dois `.logjez` fundidos sem dupla contagem (`qtd=2`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    res = parse_section_bundle(build_fx08_contingency_urna_merge())
    assert isinstance(res, ParsedSectionMetrics)
    assert res.qtd_arquivos_log == 2
    assert res.total_votos == 3
    assert res.votos_ate_17h == 3
    assert res.sem_bio_ate_17h == 1


def test_fx09_rtc_reset_and_bu_reconciliation_divergence() -> None:
    """Valida `FX-09`: Voto às `03:15:00` (`relogio_suspeito=True`) e BU `300 vs 298`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    res = parse_section_bundle(build_fx09_rtc_reset_and_bu_divergence())
    assert isinstance(res, ParsedSectionMetrics)
    assert res.total_votos == 298
    assert res.comparecimento_bu == 300
    assert res.total_aptos == 410
    assert res.divergencia_bu_log == 2
    assert res.votos_antes_08h == 1
    assert res.relogio_suspeito is True


def test_fx10_corrupt_archive_and_hash_mismatch_audit_errors() -> None:
    """Valida `FX-10`: Retorno estruturado `CORRUPT_ARCHIVE` e `HASH_MISMATCH`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    corrupt_bundle, mismatch_bundle = build_fx10_corrupt_and_hash_mismatch()

    err_corrupt = parse_section_bundle(corrupt_bundle)
    assert isinstance(err_corrupt, UnprocessedSectionError)
    assert err_corrupt.error_code == ErrorCode.CORRUPT_ARCHIVE.value

    err_hash = parse_section_bundle(mismatch_bundle)
    assert isinstance(err_hash, UnprocessedSectionError)
    assert err_hash.error_code == ErrorCode.HASH_MISMATCH.value
    assert err_hash.sha512_expected == "0" * 128
    assert err_hash.sha512_actual is not None
