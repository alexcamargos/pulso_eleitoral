"""Reconciliador opcional e resiliente de Boletim de Urna `.bu` (`REQ-PAR-03`).

Decodifica estruturas `EntidadeEnvelopeGenerico` / `EntidadeBoletimUrna` em
ASN.1 BER via `asn1tools` (schema `resources/asn1/bu_tse.asn1`) com fallback
recursivo TLV BER para suportar variações entre gerações de urna sem jamais
abortar o processamento do `logd.dat`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import asn1tools

from pulso_eleitoral.config import DEFAULT_RESOURCES_DIR

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class BuReconciliationData:
    """Contadores oficiais extraídos do Boletim de Urna (`.bu`).

    Args:
        eleitores_aptos: Maior `qtdEleitoresAptos` encontrado nas eleições da seção.
        comparecimento_bu: Maior `qtdComparecimento` entre os cargos em disputa.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    eleitores_aptos: int | None
    comparecimento_bu: int | None


@lru_cache(maxsize=2)
def _load_bu_spec(asn1_path: Path) -> Any:
    """Compila e mantém em cache o schema `bu_tse.asn1` por processo worker.

    Args:
        asn1_path: Caminho absoluto do arquivo `.asn1`.

    Returns:
        Especificação compilada do `asn1tools` em modo BER.

    Raises:
        Exception: Caso o arquivo `.asn1` esteja ausente ou malformado.
    """
    return asn1tools.compile_files(str(asn1_path), "ber")


def decode_bu_metrics(
    bu_raw_bytes: bytes | None,
    *,
    resources_dir: Path | None = None,
) -> BuReconciliationData | None:
    """Extrai `eleitores_aptos` e `comparecimento_bu` de um payload `.bu`.

    Em conformidade com `specs/02-log-parser-and-fsm.md` Seção 5, qualquer falha
    isolada no parser do `.bu` emite um `logger.warning` estruturado e retorna
    `None`, preservando integralmente as métricas do `logd.dat`.

    Args:
        bu_raw_bytes: Bytes brutos do arquivo `.bu` ou `None`.
        resources_dir: Diretório opcional de recursos contendo `asn1/bu_tse.asn1`.

    Returns:
        `BuReconciliationData` quando extraído com sucesso, ou `None`.

    Raises:
        Nenhum.
    """
    if not bu_raw_bytes:
        return None

    base_dir = resources_dir or DEFAULT_RESOURCES_DIR
    asn1_file = base_dir / "asn1" / "bu_tse.asn1"

    decoded_via_schema = _try_decode_with_asn1tools(bu_raw_bytes, asn1_file)
    if decoded_via_schema is not None:
        return decoded_via_schema

    fallback_result = _try_decode_with_ber_tlv_walker(bu_raw_bytes)
    if fallback_result is not None:
        return fallback_result

    logger.warning(
        "Não foi possível decodificar o arquivo .bu (%d bytes); "
        "mantendo comparecimento_bu=None.",
        len(bu_raw_bytes),
    )
    return None


def _try_decode_with_asn1tools(
    bu_raw_bytes: bytes,
    asn1_file: Path,
) -> BuReconciliationData | None:
    """Tenta decodificar o `.bu` via `asn1tools` (com ou sem envelope externo).

    Args:
        bu_raw_bytes: Bytes brutos em ASN.1 BER.
        asn1_file: Caminho para `bu_tse.asn1`.

    Returns:
        `BuReconciliationData` ou `None` se o payload divergir do schema estrito.

    Raises:
        Nenhum.
    """
    try:
        spec = _load_bu_spec(asn1_file)
    except Exception as exc:
        logger.warning("Falha ao compilar schema ASN.1 '%s': %s", asn1_file, exc)
        return None

    inner_bytes = bu_raw_bytes
    try:
        env = spec.decode("EntidadeEnvelopeGenerico", bu_raw_bytes)
        if isinstance(env, dict) and isinstance(
            env.get("conteudo"), (bytes, bytearray)
        ):
            inner_bytes = bytes(env["conteudo"])
    except Exception:
        inner_bytes = bu_raw_bytes

    try:
        bu = spec.decode("EntidadeBoletimUrna", inner_bytes)
        if not isinstance(bu, dict):
            return None
        eleicoes = bu.get("resultadosVotacaoPorEleicao", [])
        if not isinstance(eleicoes, list) or not eleicoes:
            return None
        aptos_vals: list[int] = []
        comp_vals: list[int] = []
        for eleicao in eleicoes:
            if not isinstance(eleicao, dict):
                continue
            if isinstance(eleicao.get("qtdEleitoresAptos"), int):
                aptos_vals.append(int(eleicao["qtdEleitoresAptos"]))
            resultados = eleicao.get("resultadosVotacao", [])
            if isinstance(resultados, list):
                for res in resultados:
                    if isinstance(res, dict) and isinstance(
                        res.get("qtdComparecimento"), int
                    ):
                        comp_vals.append(int(res["qtdComparecimento"]))
        if not aptos_vals and not comp_vals:
            return None
        return BuReconciliationData(
            eleitores_aptos=max(aptos_vals) if aptos_vals else None,
            comparecimento_bu=max(comp_vals) if comp_vals else None,
        )
    except Exception:
        return None


def _read_ber_tlv(
    data: bytes,
    offset: int,
) -> tuple[int, bool, bytes, int] | None:
    """Lê um elemento TLV (Tag, Length, Value) em codificação ASN.1 BER.

    Args:
        data: Buffer binário completo.
        offset: Posição inicial de leitura.

    Returns:
        Tupla `(tag_byte, is_constructed, value_bytes, next_offset)` ou `None`.

    Raises:
        Nenhum.
    """
    n = len(data)
    if offset >= n:
        return None
    first_tag = data[offset]
    is_constructed = bool(first_tag & 0x20)
    pos = offset + 1
    if (first_tag & 0x1F) == 0x1F:
        while pos < n and (data[pos] & 0x80):
            pos += 1
        pos += 1
    if pos >= n:
        return None

    first_len = data[pos]
    pos += 1
    if first_len < 0x80:
        length = first_len
    elif first_len == 0x80:
        return None
    else:
        num_octets = first_len & 0x7F
        if num_octets > 4 or pos + num_octets > n:
            return None
        length = int.from_bytes(data[pos : pos + num_octets], "big")
        pos += num_octets

    end = pos + length
    if end > n:
        return None
    return first_tag, is_constructed, data[pos:end], end


def _parse_ber_children(data: bytes) -> list[tuple[int, bool, bytes]] | None:
    """Desempacota todos os filhos imediatos de um nó BER construído.

    Args:
        data: Conteúdo de bytes do nó pai.

    Returns:
        Lista de `(tag, is_constructed, value)` se `data` for sequência TLV íntegra.

    Raises:
        Nenhum.
    """
    children: list[tuple[int, bool, bytes]] = []
    idx = 0
    while idx < len(data):
        parsed = _read_ber_tlv(data, idx)
        if parsed is None:
            return None
        tag, constructed, val, idx = parsed
        children.append((tag, constructed, val))
    return children


def _decode_non_negative_int(raw: bytes) -> int | None:
    """Decodifica um `INTEGER` ASN.1 não-negativo em inteiro Python.

    Args:
        raw: Bytes de valor do campo `INTEGER`.

    Returns:
        Valor inteiro `>= 0` ou `None` se vazio ou negativo.

    Raises:
        Nenhum.
    """
    if not raw or (raw[0] & 0x80):
        return None
    return int.from_bytes(raw, "big", signed=False)


def _try_decode_with_ber_tlv_walker(bu_raw_bytes: bytes) -> BuReconciliationData | None:
    """Extrai `qtdEleitoresAptos` e `qtdComparecimento` via inspeção estrutural TLV.

    Percorre nós `SEQUENCE` e `OCTET STRING` encapsulados procurando assinaturas
    estruturais de `ResultadoVotacaoPorEleicao` do TSE (`idEleicao`,
    `qtdEleitoresAptos` em `1..10000` e `SEQUENCE OF ResultadoVotacao`).

    Args:
        bu_raw_bytes: Payload binário `.bu` em ASN.1 BER.

    Returns:
        `BuReconciliationData` se localizar contadores consistentes, ou `None`.

    Raises:
        Nenhum.
    """
    aptos_candidates: list[int] = []
    comp_candidates: list[int] = []
    stack: list[bytes] = [bu_raw_bytes]
    visited = 0

    while stack and visited < 4096:
        visited += 1
        chunk = stack.pop()
        children = _parse_ber_children(chunk)
        if not children:
            continue

        # Padrao ResultadoVotacaoPorEleicao: [INTEGER id, INTEGER aptos, ..., SEQUENCE OF ResultadoVotacao]
        if (
            len(children) >= 3
            and children[0][0] == 0x02
            and children[1][0] == 0x02
        ):
            id_eleicao = _decode_non_negative_int(children[0][2])
            aptos = _decode_non_negative_int(children[1][2])
            if (
                id_eleicao is not None
                and aptos is not None
                and 1 <= aptos <= 10_000
            ):
                matched_comps: list[int] = []
                for _, is_const, seq_val in children[2:]:
                    if not is_const:
                        continue
                    sub_items = _parse_ber_children(seq_val)
                    if not sub_items:
                        continue
                    for _, sub_const, sub_val in sub_items:
                        if not sub_const:
                            continue
                        rv_fields = _parse_ber_children(sub_val)
                        if (
                            rv_fields
                            and len(rv_fields) >= 2
                            and rv_fields[0][0] in (0x02, 0x0A)
                            and rv_fields[1][0] == 0x02
                        ):
                            comp = _decode_non_negative_int(rv_fields[1][2])
                            if comp is not None and 0 <= comp <= aptos:
                                matched_comps.append(comp)
                    if matched_comps:
                        aptos_candidates.append(aptos)
                        comp_candidates.extend(matched_comps)
                        break
                if matched_comps:
                    continue

        for tag, is_const, val in children:
            if is_const or (tag == 0x04 and len(val) >= 8):
                stack.append(val)

    if not aptos_candidates and not comp_candidates:
        return None
    return BuReconciliationData(
        eleitores_aptos=max(aptos_candidates) if aptos_candidates else None,
        comparecimento_bu=max(comp_candidates) if comp_candidates else None,
    )
