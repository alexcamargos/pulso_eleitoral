"""Testes de casos de borda de extração, FSM, perfis e `.bu` (`REQ-PAR-01`..`03`).

Cobre logs truncados sem `VOTING_OPENED`, votos após encerramento, fila cruzando
meia-noite (`D+1`), regressão monotônica de RTC, `bio_status_indefinido` e
fallback estrutural TLV BER no Boletim de Urna.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from pulso_eleitoral.contracts.exceptions import (
    ContractValidationError,
    CorruptArchiveError,
    ErrorCode,
    MissingLogError,
)
from pulso_eleitoral.contracts.models import (
    CutoffMode,
    LogArtifactPayload,
    ParsedSectionMetrics,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.parser import (
    bu_reconciler,
    decode_bu_metrics,
    extract_and_merge_section_logs,
    extract_logd_buffers,
    load_pattern_profile,
    parse_section_bundle,
)
from pulso_eleitoral.parser.archive import MAX_EXTRACTED_DAT_BYTES
from tests.fixtures.builder import (
    build_fx01_sp_standard,
    build_synthetic_bu,
    encode_logd_dat,
    make_tsv_line,
    pack_7z,
    pack_zip,
)


def _make_bundle_from_lines(
    lines: list[str],
    *,
    bu_raw_bytes: bytes | None = None,
    total_aptos_manifest: int | None = None,
    election_date_iso: str = "2022-10-02",
) -> SectionArtifactBundle:
    """Cria rapidamente um `SectionArtifactBundle` a partir de linhas TSV.

    Args:
        lines: Linhas TSV a empacotar em `logd.dat`.
        bu_raw_bytes: Bytes opcionais do `.bu`.
        total_aptos_manifest: Aptos opcionais do manifesto.
        election_date_iso: Data oficial do turno.

    Returns:
        `SectionArtifactBundle` sintético para testes de borda.

    Raises:
        Nenhum.
    """
    raw = pack_zip({"logd.dat": encode_logd_dat(lines)})
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso=election_date_iso,
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="SP",
        municipio_cod=71072,
        municipio_ibge=3550308,
        municipio_nome="SAO PAULO",
        zona=1,
        secao=1,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=total_aptos_manifest,
        log_artifacts=(LogArtifactPayload(filename="sec.logjez", raw_bytes=raw),),
        bu_raw_bytes=bu_raw_bytes,
    )


def test_archive_edge_cases_empty_unknown_missing_and_zipbomb(
    mocker: MockerFixture,
) -> None:
    """Valida defesas contra buffers vazios, magic inválido, ausência de dat e zip-bomb.

    Args:
        mocker: Fixture oficial do `pytest-mock`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    with pytest.raises(MissingLogError):
        extract_and_merge_section_logs(())

    with pytest.raises(CorruptArchiveError, match="Buffer vazio"):
        extract_logd_buffers(LogArtifactPayload(filename="empty.jez", raw_bytes=b""))

    with pytest.raises(CorruptArchiveError, match="Assinatura binária"):
        extract_logd_buffers(
            LogArtifactPayload(filename="bad.jez", raw_bytes=b"NOT_AN_ARCHIVE")
        )

    with pytest.raises(CorruptArchiveError, match="Falha ao descompactar ZIP"):
        extract_logd_buffers(
            LogArtifactPayload(filename="trunc.zip", raw_bytes=b"PK\x03\x04TRUNC")
        )

    with pytest.raises(MissingLogError, match="Nenhum membro"):
        extract_logd_buffers(
            LogArtifactPayload(
                filename="no_dat.7z",
                raw_bytes=pack_7z({"outro.txt": b"abc"}),
            )
        )

    with pytest.raises(MissingLogError, match="Nenhum membro"):
        extract_logd_buffers(
            LogArtifactPayload(
                filename="no_dat.zip",
                raw_bytes=pack_zip({"outro.txt": b"abc"}),
            )
        )

    # Simula membro ZIP declarando tamanho acima de 64 MB sem alocar memoria real
    valid_zip = pack_zip({"logd.dat": b"02/10/2022 08:00:00\tINFO\t1\tVOTA\tOk\tAA\n"})
    orig_infolist = zipfile.ZipFile.infolist

    def fake_infolist(self: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        infos = orig_infolist(self)
        infos[0].file_size = MAX_EXTRACTED_DAT_BYTES + 1
        return infos

    mocker.patch.object(zipfile.ZipFile, "infolist", fake_infolist)
    with pytest.raises(CorruptArchiveError, match="excede limite de 64 MB"):
        extract_logd_buffers(
            LogArtifactPayload(filename="bomb.zip", raw_bytes=valid_zip)
        )


def test_multi_log_merge_handles_malformed_and_short_tsv_lines() -> None:
    """Verifica descarte seguro de linhas corrompidas na fusão de múltiplos logs.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    l1 = b"linha_curta\r\n99/99/2022 25:00:00\tbad\r\n02/10/2022 08:00:00\tcurta\r\n"
    l2 = encode_logd_dat(
        [
            make_tsv_line("02/10/2022 08:00:00", "Urna pronta para receber votos"),
            "02/10/2022 08:01:00\tSEM_SEIS_COLUNAS\r\n",
        ]
    )
    merged, count = extract_and_merge_section_logs(
        (
            LogArtifactPayload(filename="u1.jez", raw_bytes=pack_zip({"logd.dat": l1})),
            LogArtifactPayload(filename="u2.jez", raw_bytes=pack_zip({"logd.dat": l2})),
        )
    )
    assert count == 2
    assert len(merged) >= 2


def test_fsm_truncated_open_indeterminate_bio_post_close_and_midnight() -> None:
    """Valida abertura truncada, `bio_status_indefinido`, voto pós-fecho e `D+1`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    lines = [
        # Aptos capturado em D-2 quando manifesto e BU nao informam
        make_tsv_line("30/09/2022 10:00:00", "Eleitores aptos: 275"),
        # Sem VOTING_OPENED no dia D (log truncado no inicio)
        make_tsv_line("02/10/2022 12:00:00", "Título digitado pelo mesário"),
        # Voto confirmado sem linha BIO_SUCCESS nem BIO_BYPASS -> bio_status_indefinido
        make_tsv_line("02/10/2022 12:00:30", "O voto do eleitor foi computado"),
        # Regressao monotonica de relogio > 60s na mesma urna
        make_tsv_line("02/10/2022 11:55:00", "Aguardando digitação do título"),
        make_tsv_line(
            "02/10/2022 11:55:10",
            "Tipo de habilitação do eleitor [manual]",
        ),
        # Fila extrema cruzando meia-noite para D+1 (03/10/2022 00:02:00)
        make_tsv_line("03/10/2022 00:02:00", "O voto do eleitor foi computado"),
        make_tsv_line("03/10/2022 00:05:00", "Encerramento da seção eleitoral"),
        # Voto anomalo apos encerramento formal!
        make_tsv_line("03/10/2022 00:06:00", "O voto do eleitor foi computado"),
    ]
    res = parse_section_bundle(_make_bundle_from_lines(lines))
    assert isinstance(res, ParsedSectionMetrics)
    assert res.total_aptos == 275
    assert res.total_votos == 3
    assert res.votos_ate_17h == 1
    assert res.votos_apos_17h == 2
    assert res.sem_bio_apos_17h == 1
    assert res.bio_status_indefinido == 2
    assert res.relogio_suspeito is True
    assert res.voto_apos_encerramento is True


def test_fsm_invalid_date_and_empty_tsv_produce_parse_error() -> None:
    """Garante conversão de data inválida ou arquivo sem TSV para `PARSE_ERROR`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    bad_date = _make_bundle_from_lines(
        [make_tsv_line("02/10/2022 08:00:00", "Urna pronta para receber votos")],
        election_date_iso="data-invalida",
    )
    err1 = parse_section_bundle(bad_date)
    assert isinstance(err1, UnprocessedSectionError)
    assert err1.error_code == ErrorCode.PARSE_ERROR.value

    no_tsv = replace(
        build_fx01_sp_standard(),
        log_artifacts=(
            LogArtifactPayload(
                filename="garbage.zip",
                raw_bytes=pack_zip({"logd.dat": b"apenas texto sem tabulacao\n"}),
            ),
        ),
    )
    err2 = parse_section_bundle(no_tsv)
    assert isinstance(err2, UnprocessedSectionError)
    assert err2.error_code == ErrorCode.PARSE_ERROR.value


def test_bu_reconciler_unwrapped_tlv_fallback_and_corrupt_tolerance(
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    """Testa BU sem envelope, walker TLV BER de fallback e tolerância a BU inválido.

    Args:
        mocker: Fixture oficial do `pytest-mock`.
        tmp_path: Diretório temporário do `pytest`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    raw_unwrapped = build_synthetic_bu(
        municipio_cod=71072,
        zona=1,
        secao=1,
        aptos=320,
        comparecimento_por_cargo=[250],
        wrapped_in_envelope=False,
    )
    direct = decode_bu_metrics(raw_unwrapped)
    assert direct is not None
    assert direct.eleitores_aptos == 320
    assert direct.comparecimento_bu == 250

    # Forca falha no schema asn1tools para exercitar o fallback estrutural TLV BER!
    raw_enveloped = build_synthetic_bu(
        municipio_cod=71072,
        zona=1,
        secao=1,
        aptos=395,
        comparecimento_por_cargo=[310, 312],
        wrapped_in_envelope=True,
    )
    mocker.patch.object(bu_reconciler, "_try_decode_with_asn1tools", return_value=None)
    via_tlv = decode_bu_metrics(raw_enveloped)
    assert via_tlv is not None
    assert via_tlv.eleitores_aptos == 395
    assert via_tlv.comparecimento_bu == 312

    # BU corrompido nao invalida a secao: preserva logd.dat com comparecimento_bu=None
    base = build_fx01_sp_standard()
    with_corrupt_bu = replace(base, bu_raw_bytes=b"\x30\x80INVALID_INDEFINITE_BER")
    parsed = parse_section_bundle(with_corrupt_bu)
    assert isinstance(parsed, ParsedSectionMetrics)
    assert parsed.total_votos == 10
    assert parsed.comparecimento_bu is None
    assert parsed.divergencia_bu_log is None

    # Diretorio sem schema ASN.1 aciona warning limpo e cai no fallback/None
    assert decode_bu_metrics(b"\xff\xff", resources_dir=tmp_path) is None


def test_pattern_profile_validation_errors(tmp_path: Path) -> None:
    """Verifica erros de contrato quando perfil `.toml` falta ou omite eventos.

    Args:
        tmp_path: Diretório temporário do `pytest`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    load_pattern_profile.cache_clear()
    with pytest.raises(ContractValidationError, match="ausente"):
        load_pattern_profile("inexistente", resources_dir=tmp_path)

    pat_dir = tmp_path / "log_patterns"
    pat_dir.mkdir(parents=True)
    (pat_dir / "incompleto.toml").write_text(
        'profile_id = "inc"\n[events]\nVOTING_OPENED = ["ok"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ContractValidationError, match="Evento obrigatório"):
        load_pattern_profile("incompleto", resources_dir=tmp_path)

    (pat_dir / "invalido.toml").write_text('events = "nao_dict"\n', encoding="utf-8")
    with pytest.raises(ContractValidationError, match="inválida"):
        load_pattern_profile("invalido", resources_dir=tmp_path)
