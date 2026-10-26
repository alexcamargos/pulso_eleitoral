"""Construtor determinístico das fixtures áureas `FX-01` a `FX-10` (`REQ-QA-01`).

Sintetiza arquivos `logd.dat` em `ISO-8859-1` com 6 colunas TSV, pacotes `.7z`
(`py7zr`), pacotes `.zip` (`zipfile`) e Boletins de Urna `.bu` em ASN.1 BER
cobrindo integralmente a matriz de `specs/05-testing-evals-and-roadmap.md`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from functools import lru_cache

import asn1tools
import py7zr

from pulso_eleitoral.config import DEFAULT_RESOURCES_DIR
from pulso_eleitoral.contracts.models import (
    CutoffMode,
    LogArtifactPayload,
    SectionArtifactBundle,
)


def make_tsv_line(
    timestamp_local: str,
    message: str,
    *,
    level: str = "INFO",
    ue_id: str = "67305985",
    app_name: str = "VOTA",
) -> str:
    r"""Formata uma linha TSV de 6 colunas compatível com `logd.dat` do TSE.

    Args:
        timestamp_local: Data/hora local `DD/MM/YYYY HH:MM:SS` (19 caracteres).
        message: Mensagem descritiva do evento em `ISO-8859-1`.
        level: Nível de severidade (`INFO`, `WARN`, `ERRO`).
        ue_id: Identificador numérico do equipamento de votação.
        app_name: Subsistema emissor (`VOTA`, `SCUE`, `GAP`, etc.).

    Returns:
        Linha TSV terminada em `\r\n` contendo MAC sintético determinístico de 16 hex.

    Raises:
        Nenhum.
    """
    core = f"{timestamp_local}\t{level}\t{ue_id}\t{app_name}\t{message}"
    mac_hex = hashlib.blake2b(core.encode("latin-1"), digest_size=8).hexdigest().upper()
    return f"{core}\t{mac_hex}\r\n"


def encode_logd_dat(lines: list[str]) -> bytes:
    """Codifica uma sequência de linhas TSV em `ISO-8859-1` (`latin-1`).

    Args:
        lines: Lista ordenada de linhas TSV do `logd.dat`.

    Returns:
        Buffer de bytes codificado em `latin-1`.

    Raises:
        Nenhum.
    """
    return "".join(lines).encode("latin-1")


def pack_7z(entries: dict[str, bytes]) -> bytes:
    """Empacota entradas `logd*.dat` em contêiner 7z/LZMA em memória.

    Args:
        entries: Mapa de nome de arquivo interno para bytes brutos.

    Returns:
        Bytes do arquivo `.7z` iniciando com assinatura `37 7A BC AF 27 1C`.

    Raises:
        Nenhum.
    """
    buffer = io.BytesIO()
    with py7zr.SevenZipFile(buffer, mode="w") as archive:
        for filename, content in entries.items():
            archive.writestr(content, filename)
    return buffer.getvalue()


def pack_zip(entries: dict[str, bytes]) -> bytes:
    """Empacota entradas `logd*.dat` em contêiner ZIP DEFLATE em memória.

    Args:
        entries: Mapa de nome de arquivo interno para bytes brutos.

    Returns:
        Bytes do arquivo `.zip` iniciando com assinatura `50 4B 03 04`.

    Raises:
        Nenhum.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for filename, content in entries.items():
            archive.writestr(filename, content)
    return buffer.getvalue()


@lru_cache(maxsize=1)
def _compiled_bu_asn1() -> asn1tools.compiler.Specification:
    """Compila uma única vez o schema `resources/asn1/bu_tse.asn1` em modo BER.

    Args:
        Nenhum.

    Returns:
        Especificação ASN.1 compilada pronta para codificação/decodificação BER.

    Raises:
        Nenhum.
    """
    asn1_path = DEFAULT_RESOURCES_DIR / "asn1" / "bu_tse.asn1"
    return asn1tools.compile_files(str(asn1_path), "ber")


def build_synthetic_bu(
    *,
    municipio_cod: int,
    zona: int,
    secao: int,
    aptos: int,
    comparecimento_por_cargo: list[int],
    wrapped_in_envelope: bool = True,
) -> bytes:
    """Gera um Boletim de Urna (`.bu`) codificado em ASN.1 BER determinístico.

    Args:
        municipio_cod: Código TSE do município (5 dígitos).
        zona: Número da zona eleitoral.
        secao: Número da seção eleitoral.
        aptos: Quantidade de eleitores aptos registrada no BU.
        comparecimento_por_cargo: Lista de comparecimentos por cargo em disputa.
        wrapped_in_envelope: Se `True`, envolve `EntidadeBoletimUrna` em
            `EntidadeEnvelopeGenerico` (formato padrão dos arquivos `.bu` do TSE).

    Returns:
        Bytes brutos em ASN.1 BER do arquivo `.bu`.

    Raises:
        Nenhum.
    """
    spec = _compiled_bu_asn1()
    identificacao = {
        "municipioZona": {"municipio": municipio_cod, "zona": zona},
        "local": 1015,
        "secao": secao,
    }
    bu_dict = {
        "cabecalho": {"dataGeracao": "20221002T170500", "idEleitoral": 406},
        "fase": 2,
        "identificacaoSecao": identificacao,
        "dataHoraEmissao": "20221002T170515",
        "resultadosVotacaoPorEleicao": [
            {
                "idEleicao": 544,
                "qtdEleitoresAptos": aptos,
                "resultadosVotacao": [
                    {"tipoCargo": idx + 1, "qtdComparecimento": comp}
                    for idx, comp in enumerate(comparecimento_por_cargo)
                ],
            }
        ],
    }
    bu_bytes: bytes = spec.encode("EntidadeBoletimUrna", bu_dict)
    if not wrapped_in_envelope:
        return bu_bytes

    envelope = {
        "cabecalho": {"dataGeracao": "20221002T170520", "idEleitoral": 406},
        "fase": 2,
        "identificacao": identificacao,
        "tipoEnvelope": "envelopeBoletimUrna",
        "conteudo": bu_bytes,
    }
    encoded_env: bytes = spec.encode("EntidadeEnvelopeGenerico", envelope)
    return encoded_env


def _append_voter(
    lines: list[str],
    date_ddmmyyyy: str,
    hhmmss_start: str,
    hhmmss_vote: str,
    *,
    biometric: bool = True,
    bio_failures: int = 0,
    ue_id: str = "67305985",
) -> None:
    """Adiciona uma sequência completa de atendimento e confirmação de voto.

    Args:
        lines: Acumulador mutável de linhas TSV.
        date_ddmmyyyy: Data local `DD/MM/YYYY`.
        hhmmss_start: Horário `HH:MM:SS` de início da habilitação.
        hhmmss_vote: Horário `HH:MM:SS` de confirmação do voto.
        biometric: `True` para habilitação biométrica; `False` para manual.
        bio_failures: Quantidade de falhas de digital anteriores à habilitação.
        ue_id: Identificador do equipamento.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    ts_start = f"{date_ddmmyyyy} {hhmmss_start}"
    ts_vote = f"{date_ddmmyyyy} {hhmmss_vote}"
    lines.append(
        make_tsv_line(
            ts_start,
            "Título digitado pelo mesário",
            ue_id=ue_id,
        )
    )
    for _ in range(bio_failures):
        lines.append(
            make_tsv_line(
                ts_start,
                "Tentativa de identificação biométrica falhou",
                ue_id=ue_id,
            )
        )
    hab_msg = (
        "Tipo de habilitação do eleitor [biométrica]"
        if biometric
        else "Tipo de habilitação do eleitor [manual]"
    )
    lines.append(make_tsv_line(ts_start, hab_msg, ue_id=ue_id))
    lines.append(make_tsv_line(ts_start, "Eleitor foi habilitado", ue_id=ue_id))
    lines.append(
        make_tsv_line(
            ts_vote,
            "O voto do eleitor foi computado",
            ue_id=ue_id,
        )
    )


def build_fx01_sp_standard() -> SectionArtifactBundle:
    """Constrói `FX-01`: Seção padrão em SP (`UTC-3`, 10 votos pré-17h, 7z).

    Args:
        Nenhum.

    Returns:
        `SectionArtifactBundle` determinístico de `FX-01`.

    Raises:
        Nenhum.
    """
    lines = [
        make_tsv_line(
            "02/10/2022 07:30:00",
            "Verificando integridade de hardware e bateria",
            app_name="SCUE",
        ),
        make_tsv_line("02/10/2022 07:55:00", "Eleitores aptos na seção: 400"),
        make_tsv_line("02/10/2022 08:00:00", "Urna pronta para receber votos"),
    ]
    for idx in range(10):
        minute = 5 + idx * 10
        hh = 8 + (minute // 60)
        mm = minute % 60
        _append_voter(
            lines,
            "02/10/2022",
            f"{hh:02d}:{mm:02d}:10",
            f"{hh:02d}:{mm:02d}:45",
            biometric=(idx not in (2, 7)),
        )
    lines.append(
        make_tsv_line("02/10/2022 17:01:00", "Encerramento da seção eleitoral")
    )
    raw_7z = pack_7z({"logd.dat": encode_logd_dat(lines)})
    sha = hashlib.sha512(raw_7z).hexdigest()
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="SP",
        municipio_cod=71072,
        municipio_ibge=3550308,
        municipio_nome="SAO PAULO",
        zona=1,
        secao=101,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=400,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-7107200010101.logjez",
                raw_bytes=raw_7z,
                sha512_expected=sha,
            ),
        ),
    )


def build_fx02_df_exact_boundary() -> SectionArtifactBundle:
    """Constrói `FX-02`: Fronteira `16:59:59`, `17:00:00`, `17:00:01` em DF (`ZIP`).

    Args:
        Nenhum.

    Returns:
        `SectionArtifactBundle` determinístico de `FX-02`.

    Raises:
        Nenhum.
    """
    lines = [make_tsv_line("02/10/2022 08:00:00", "Urna pronta para receber votos")]
    _append_voter(lines, "02/10/2022", "16:59:10", "16:59:59", biometric=True)
    _append_voter(lines, "02/10/2022", "16:59:59", "17:00:00", biometric=True)
    _append_voter(lines, "02/10/2022", "17:00:00", "17:00:01", biometric=False)
    lines.append(make_tsv_line("02/10/2022 17:05:00", "Votação encerrada"))
    raw_zip = pack_zip({"logd.dat": encode_logd_dat(lines)})
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="DF",
        municipio_cod=97012,
        municipio_ibge=5300108,
        municipio_nome="BRASILIA",
        zona=1,
        secao=202,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=350,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-9701200010202.logjez", raw_bytes=raw_zip
            ),
        ),
    )


def build_fx03_acre_timezone() -> SectionArtifactBundle:
    """Constrói `FX-03`: Rio Branco/AC (`offset=-2`) em `14:59:59` e `15:00:00`.

    Args:
        Nenhum.

    Returns:
        `SectionArtifactBundle` determinístico de `FX-03`.

    Raises:
        Nenhum.
    """
    lines = [make_tsv_line("02/10/2022 06:00:00", "Urna pronta para receber votos")]
    _append_voter(lines, "02/10/2022", "14:59:10", "14:59:59", biometric=True)
    _append_voter(lines, "02/10/2022", "14:59:59", "15:00:00", biometric=False)
    lines.append(
        make_tsv_line("02/10/2022 15:05:00", "Encerramento da seção eleitoral")
    )
    raw_7z = pack_7z({"logd.dat": encode_logd_dat(lines)})
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="AC",
        municipio_cod=1392,
        municipio_ibge=1200401,
        municipio_nome="RIO BRANCO",
        zona=1,
        secao=10,
        fuso_horario_offset_brt=-2,
        total_aptos_manifest=300,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-0139200010010.logjez", raw_bytes=raw_7z
            ),
        ),
    )


def build_fx04_amazonas_dual_tz() -> tuple[
    SectionArtifactBundle, SectionArtifactBundle
]:
    """Constrói `FX-04`: Tabatinga (`offset=-2`) vs Manaus (`offset=-1`) às `15:05:00`.

    Args:
        Nenhum.

    Returns:
        Par `(tabatinga_bundle, manaus_bundle)` comprovando divergência de 1h no AM.

    Raises:
        Nenhum.
    """
    lines_tab = [make_tsv_line("02/10/2022 06:00:00", "Urna pronta para receber votos")]
    _append_voter(lines_tab, "02/10/2022", "15:04:15", "15:05:00", biometric=False)
    lines_tab.append(make_tsv_line("02/10/2022 15:10:00", "Votação encerrada"))

    lines_man = [make_tsv_line("02/10/2022 07:00:00", "Urna pronta para receber votos")]
    _append_voter(lines_man, "02/10/2022", "15:04:15", "15:05:00", biometric=False)
    lines_man.append(make_tsv_line("02/10/2022 16:05:00", "Votação encerrada"))

    tab_bundle = SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="AM",
        municipio_cod=98477,
        municipio_ibge=1304062,
        municipio_nome="TABATINGA",
        zona=36,
        secao=1,
        fuso_horario_offset_brt=-2,
        total_aptos_manifest=250,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-9847700360001.logjez",
                raw_bytes=pack_7z({"logd.dat": encode_logd_dat(lines_tab)}),
            ),
        ),
    )
    man_bundle = SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="AM",
        municipio_cod=2550,
        municipio_ibge=1302603,
        municipio_nome="MANAUS",
        zona=1,
        secao=1,
        fuso_horario_offset_brt=-1,
        total_aptos_manifest=250,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-0255000010001.logjez",
                raw_bytes=pack_7z({"logd.dat": encode_logd_dat(lines_man)}),
            ),
        ),
    )
    return tab_bundle, man_bundle


def build_fx05_fernando_noronha() -> SectionArtifactBundle:
    """Constrói `FX-05`: Fernando de Noronha (`UTC-2`, `offset=+1`) voto às `17:30:00`.

    Args:
        Nenhum.

    Returns:
        `SectionArtifactBundle` determinístico de `FX-05` (`17:30` local = `16:30 BRT`).

    Raises:
        Nenhum.
    """
    lines = [make_tsv_line("02/10/2022 09:00:00", "Urna pronta para receber votos")]
    _append_voter(lines, "02/10/2022", "17:29:20", "17:30:00", biometric=True)
    lines.append(
        make_tsv_line("02/10/2022 18:00:00", "Encerramento da seção eleitoral")
    )
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="PE",
        municipio_cod=30015,
        municipio_ibge=2605459,
        municipio_nome="FERNANDO DE NORONHA",
        zona=1,
        secao=1,
        fuso_horario_offset_brt=1,
        total_aptos_manifest=310,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-3001500010001.logjez",
                raw_bytes=pack_zip({"logd.dat": encode_logd_dat(lines)}),
            ),
        ),
    )


def build_fx06_bio_retries_and_abort() -> SectionArtifactBundle:
    """Constrói `FX-06`: Retentativas biométricas e cancelamento sem vazamento.

    Args:
        Nenhum.

    Returns:
        `SectionArtifactBundle` determinístico de `FX-06`.

    Raises:
        Nenhum.
    """
    lines = [make_tsv_line("02/10/2022 08:00:00", "Urna pronta para receber votos")]
    # Eleitor 1: 2 falhas biometricas seguidas de sucesso biometrico
    _append_voter(
        lines,
        "02/10/2022",
        "10:15:00",
        "10:16:00",
        biometric=True,
        bio_failures=2,
    )
    # Eleitor 2: habilitacao manual sem biometria mas cancelado pelo mesario
    lines.extend(
        [
            make_tsv_line("02/10/2022 17:08:00", "Título digitado pelo mesário"),
            make_tsv_line(
                "02/10/2022 17:08:15",
                "Habilitação manual sem biometria",
            ),
            make_tsv_line("02/10/2022 17:08:40", "Votação cancelada pelo mesário"),
        ]
    )
    # Eleitor 3: habilitado por biometria as 17:10:00 BRT (zero contaminacao!)
    _append_voter(lines, "02/10/2022", "17:09:20", "17:10:00", biometric=True)
    lines.append(
        make_tsv_line("02/10/2022 17:15:00", "Encerramento da seção eleitoral")
    )
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="SP",
        municipio_cod=71072,
        municipio_ibge=3550308,
        municipio_nome="SAO PAULO",
        zona=2,
        secao=15,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=380,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-7107200020015.logjez",
                raw_bytes=pack_7z({"logd.dat": encode_logd_dat(lines)}),
            ),
        ),
    )


def build_fx07_pre_election_and_reboot() -> SectionArtifactBundle:
    """Constrói `FX-07`: Simulado em `D-3` ignorado e reboot limpando sessão em `D`.

    Args:
        Nenhum.

    Returns:
        `SectionArtifactBundle` determinístico de `FX-07`.

    Raises:
        Nenhum.
    """
    lines: list[str] = [
        make_tsv_line("29/09/2022 14:00:00", "Urna pronta para receber votos"),
    ]
    _append_voter(lines, "29/09/2022", "14:05:00", "14:05:30", biometric=False)
    lines.extend(
        [
            make_tsv_line("02/10/2022 07:45:00", "Urna ligada", app_name="GAP"),
            make_tsv_line("02/10/2022 08:00:00", "Urna pronta para receber votos"),
            make_tsv_line("02/10/2022 11:20:00", "Título digitado pelo mesário"),
            make_tsv_line(
                "02/10/2022 11:20:10",
                "Tipo de habilitação do eleitor [manual]",
            ),
            make_tsv_line("02/10/2022 11:22:00", "Reinício do sistema", app_name="GAP"),
        ]
    )
    _append_voter(lines, "02/10/2022", "11:25:00", "11:25:45", biometric=True)
    lines.append(
        make_tsv_line("02/10/2022 17:00:30", "Encerramento da seção eleitoral")
    )
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="MG",
        municipio_cod=41238,
        municipio_ibge=3106200,
        municipio_nome="BELO HORIZONTE",
        zona=13,
        secao=44,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=390,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-4123800130044.logjez",
                raw_bytes=pack_7z({"logd.dat": encode_logd_dat(lines)}),
            ),
        ),
    )


def build_fx08_contingency_urna_merge() -> SectionArtifactBundle:
    """Constrói `FX-08`: Dois `.logjez` com linhas iniciais duplicadas na contingência.

    Args:
        Nenhum.

    Returns:
        `SectionArtifactBundle` determinístico de `FX-08` (`qtd_arquivos_log=2`).

    Raises:
        Nenhum.
    """
    shared_lines = [
        make_tsv_line(
            "02/10/2022 08:00:00",
            "Urna pronta para receber votos",
            ue_id="11111111",
        ),
    ]
    _append_voter(
        shared_lines,
        "02/10/2022",
        "09:00:00",
        "09:00:40",
        biometric=True,
        ue_id="11111111",
    )
    _append_voter(
        shared_lines,
        "02/10/2022",
        "10:00:00",
        "10:00:40",
        biometric=False,
        ue_id="11111111",
    )

    contingency_lines = list(shared_lines)
    _append_voter(
        contingency_lines,
        "02/10/2022",
        "14:30:00",
        "14:30:50",
        biometric=True,
        ue_id="22222222",
    )
    contingency_lines.append(
        make_tsv_line(
            "02/10/2022 17:02:00",
            "Encerramento da seção eleitoral",
            ue_id="22222222",
        )
    )
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="RJ",
        municipio_cod=60011,
        municipio_ibge=3304557,
        municipio_nome="RIO DE JANEIRO",
        zona=4,
        secao=88,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=420,
        log_artifacts=(
            LogArtifactPayload(
                filename="urna1.logjez",
                raw_bytes=pack_7z({"logd.dat": encode_logd_dat(shared_lines)}),
            ),
            LogArtifactPayload(
                filename="urna2.logjez",
                raw_bytes=pack_zip({"logd.dat": encode_logd_dat(contingency_lines)}),
            ),
        ),
    )


def build_fx09_rtc_reset_and_bu_divergence() -> SectionArtifactBundle:
    """Constrói `FX-09`: Voto às `03:15:00` (`< 08h`) e BU `300` vs `298` no log.

    Args:
        Nenhum.

    Returns:
        `SectionArtifactBundle` determinístico de `FX-09` (`TIER_3_CRITICAL_ANOMALY`).

    Raises:
        Nenhum.
    """
    lines = [make_tsv_line("02/10/2022 03:10:00", "Urna pronta para receber votos")]
    _append_voter(lines, "02/10/2022", "03:14:20", "03:15:00", biometric=True)
    for idx in range(297):
        sec_offset = 8 * 3600 + 60 + idx * 60
        hh = sec_offset // 3600
        mm = (sec_offset % 3600) // 60
        _append_voter(
            lines,
            "02/10/2022",
            f"{hh:02d}:{mm:02d}:05",
            f"{hh:02d}:{mm:02d}:35",
            biometric=True,
        )
    lines.append(
        make_tsv_line("02/10/2022 17:01:00", "Encerramento da seção eleitoral")
    )

    bu_bytes = build_synthetic_bu(
        municipio_cod=71072,
        zona=10,
        secao=99,
        aptos=410,
        comparecimento_por_cargo=[299, 300],
    )
    return SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="SP",
        municipio_cod=71072,
        municipio_ibge=3550308,
        municipio_nome="SAO PAULO",
        zona=10,
        secao=99,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=405,
        log_artifacts=(
            LogArtifactPayload(
                filename="o00406-7107200100099.logjez",
                raw_bytes=pack_7z({"logd.dat": encode_logd_dat(lines)}),
            ),
        ),
        bu_raw_bytes=bu_bytes,
    )


def build_fx10_corrupt_and_hash_mismatch() -> tuple[
    SectionArtifactBundle, SectionArtifactBundle
]:
    """Constrói `FX-10`: Pacote truncado (`CORRUPT_ARCHIVE`) e hash inválido.

    Args:
        Nenhum.

    Returns:
        Par `(corrupt_bundle, hash_mismatch_bundle)` para auditoria de falhas.

    Raises:
        Nenhum.
    """
    corrupt_bundle = SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="BA",
        municipio_cod=38490,
        municipio_ibge=2927408,
        municipio_nome="SALVADOR",
        zona=1,
        secao=50,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=360,
        log_artifacts=(
            LogArtifactPayload(
                filename="corrupt.logjez",
                raw_bytes=b"\x37\x7a\xbc\xaf\x27\x1cTRUNCATED_LZMA_STREAM",
            ),
        ),
    )

    valid_base = build_fx01_sp_standard()
    bad_hash_payload = LogArtifactPayload(
        filename=valid_base.log_artifacts[0].filename,
        raw_bytes=valid_base.log_artifacts[0].raw_bytes,
        sha512_expected="0" * 128,
    )
    mismatch_bundle = SectionArtifactBundle(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        election_date_iso="2022-10-02",
        cutoff_mode=CutoffMode.UNIFIED_BRT.value,
        uf="BA",
        municipio_cod=38490,
        municipio_ibge=2927408,
        municipio_nome="SALVADOR",
        zona=1,
        secao=51,
        fuso_horario_offset_brt=0,
        total_aptos_manifest=360,
        log_artifacts=(bad_hash_payload,),
    )
    return corrupt_bundle, mismatch_bundle
