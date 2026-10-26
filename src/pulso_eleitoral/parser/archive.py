"""Extração in-memory multiformato (`.7z`/`.zip`) e fusão de logs (`REQ-PAR-01`).

Inspeciona os *magic bytes* dos pacotes `.logjez` sem confiar na extensão do
arquivo, valida integridade `SHA-512` quando informada e realiza fusão canônica
deduplicada em cenários de substituição por urna de contingência (`FX-08`).

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
import lzma
import posixpath
import zipfile
import zlib

import py7zr
import py7zr.exceptions
import py7zr.io

from pulso_eleitoral.contracts.exceptions import (
    CorruptArchiveError,
    HashMismatchError,
    MissingLogError,
)
from pulso_eleitoral.contracts.models import LogArtifactPayload

MAGIC_7Z: bytes = b"\x37\x7a\xbc\xaf\x27\x1c"
MAGIC_ZIP: bytes = b"\x50\x4b\x03\x04"
MAX_EXTRACTED_DAT_BYTES: int = 64 * 1024 * 1024


def _is_logd_member(member_name: str) -> bool:
    """Verifica se o caminho interno do arquivo corresponde a `logd*.dat`.

    Args:
        member_name: Nome ou caminho relativo dentro do pacote compactado.

    Returns:
        `True` se o basename em minúsculas iniciar com `logd` e terminar com `.dat`.

    Raises:
        Nenhum.
    """
    normalized = member_name.replace("\\", "/")
    base = posixpath.basename(normalized).lower()
    return base.startswith("logd") and base.endswith(".dat")


def _verify_payload_hash(payload: LogArtifactPayload) -> None:
    """Valida o hash `SHA-512` esperado do artefato, quando presente no contrato.

    Args:
        payload: Artefato `.logjez` contendo bytes e hash opcional esperado.

    Returns:
        Nenhum.

    Raises:
        HashMismatchError: Se o digest `SHA-512` calculado divergir do esperado.
    """
    if not payload.sha512_expected:
        return
    expected = payload.sha512_expected.strip().lower()
    actual = hashlib.sha512(payload.raw_bytes).hexdigest().lower()
    if actual != expected:
        raise HashMismatchError(
            f"SHA-512 divergente em '{payload.filename}'.",
            source_uri=payload.filename,
            sha512_expected=expected,
            sha512_actual=actual,
        )


def extract_logd_buffers(payload: LogArtifactPayload) -> list[bytes]:
    """Extrai em memória todos os membros `logd*.dat` de um `LogArtifactPayload`.

    Args:
        payload: Pacote `.logjez` em memória (`7z` ou `ZIP`).

    Returns:
        Lista ordenada de buffers `bytes` correspondentes aos arquivos `logd*.dat`.

    Raises:
        HashMismatchError: Se `sha512_expected` estiver preenchido e divergir.
        CorruptArchiveError: Se o buffer for vazio, truncado ou assinatura inválida.
        MissingLogError: Se o pacote for íntegro, mas não contiver nenhum `logd*.dat`.
    """
    _verify_payload_hash(payload)
    raw = payload.raw_bytes
    if not raw:
        raise CorruptArchiveError(
            f"Buffer vazio em '{payload.filename}'.",
            source_uri=payload.filename,
        )

    if raw.startswith(MAGIC_7Z):
        return _extract_from_7z(raw, payload.filename)
    if raw.startswith(MAGIC_ZIP):
        return _extract_from_zip(raw, payload.filename)

    prefix_hex = raw[:6].hex().upper()
    raise CorruptArchiveError(
        f"Assinatura binária desconhecida ({prefix_hex}) em '{payload.filename}'.",
        source_uri=payload.filename,
    )


def _extract_from_7z(raw_bytes: bytes, source_name: str) -> list[bytes]:
    """Extrai membros `logd*.dat` de um contêiner `7z`/LZMA usando `BytesIOFactory`.

    Args:
        raw_bytes: Bytes brutos do arquivo `.7z`.
        source_name: Nome identificador do arquivo para rastreabilidade de erros.

    Returns:
        Lista ordenada de conteúdos brutos `bytes` extraídos.

    Raises:
        CorruptArchiveError: Em caso de erro LZMA/7z ou estouro de limite em memória.
        MissingLogError: Caso nenhum membro `logd*.dat` exista no pacote.
    """
    try:
        with py7zr.SevenZipFile(io.BytesIO(raw_bytes), mode="r") as archive:
            targets = sorted(n for n in archive.getnames() if _is_logd_member(n))
            if not targets:
                raise MissingLogError(
                    f"Nenhum membro logd*.dat encontrado em '{source_name}'.",
                    source_uri=source_name,
                )
            factory = py7zr.io.BytesIOFactory(limit=MAX_EXTRACTED_DAT_BYTES)
            archive.extract(targets=targets, factory=factory)
            buffers: list[bytes] = []
            for name in targets:
                bio = factory.products[name]
                bio.seek(0)
                buffers.append(bio.read())
            return buffers
    except MissingLogError:
        raise
    except (
        py7zr.exceptions.ArchiveError,
        lzma.LZMAError,
        EOFError,
        OSError,
        ValueError,
        KeyError,
    ) as exc:
        raise CorruptArchiveError(
            f"Falha ao descompactar 7z '{source_name}': {exc}",
            source_uri=source_name,
        ) from exc


def _extract_from_zip(raw_bytes: bytes, source_name: str) -> list[bytes]:
    """Extrai membros `logd*.dat` de um contêiner `ZIP` padrão em memória.

    Args:
        raw_bytes: Bytes brutos do arquivo `.zip`.
        source_name: Nome identificador do arquivo para rastreabilidade de erros.

    Returns:
        Lista ordenada de conteúdos brutos `bytes` extraídos.

    Raises:
        CorruptArchiveError: Em caso de ZIP truncado, CRC inválido ou zip-bomb.
        MissingLogError: Caso nenhum membro `logd*.dat` exista no pacote.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes), mode="r") as archive:
            infos = sorted(
                (
                    i
                    for i in archive.infolist()
                    if not i.is_dir() and _is_logd_member(i.filename)
                ),
                key=lambda item: item.filename,
            )
            if not infos:
                raise MissingLogError(
                    f"Nenhum membro logd*.dat encontrado em '{source_name}'.",
                    source_uri=source_name,
                )
            buffers: list[bytes] = []
            for info in infos:
                if info.file_size > MAX_EXTRACTED_DAT_BYTES:
                    raise CorruptArchiveError(
                        f"Membro '{info.filename}' excede limite de 64 MB "
                        f"em '{source_name}'.",
                        source_uri=source_name,
                    )
                buffers.append(archive.read(info))
            return buffers
    except (MissingLogError, CorruptArchiveError):
        raise
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        zlib.error,
        EOFError,
        OSError,
        KeyError,
    ) as exc:
        raise CorruptArchiveError(
            f"Falha ao descompactar ZIP '{source_name}': {exc}",
            source_uri=source_name,
        ) from exc


def _timestamp_sort_key(line: bytes) -> tuple[int, int, int, int, int, int] | None:
    """Extrai chave cronológica `(YYYY, MM, DD, HH, MM, SS)` por slicing ASCII.

    Args:
        line: Linha em `bytes` do `logd.dat`.

    Returns:
        Tupla inteira ordenável cronologicamente ou `None` se o cabeçalho for inválido.

    Raises:
        Nenhum.
    """
    if len(line) < 19 or line[2] != 47 or line[5] != 47 or line[10] != 32:
        return None
    if line[13] != 58 or line[16] != 58:
        return None
    try:
        dd = (line[0] - 48) * 10 + (line[1] - 48)
        mo = (line[3] - 48) * 10 + (line[4] - 48)
        yy = (
            (line[6] - 48) * 1000
            + (line[7] - 48) * 100
            + (line[8] - 48) * 10
            + (line[9] - 48)
        )
        hh = (line[11] - 48) * 10 + (line[12] - 48)
        mm = (line[14] - 48) * 10 + (line[15] - 48)
        ss = (line[17] - 48) * 10 + (line[18] - 48)
    except IndexError:
        return None
    if not (
        1 <= mo <= 12
        and 1 <= dd <= 31
        and 0 <= hh <= 23
        and 0 <= mm <= 59
        and 0 <= ss <= 59
    ):
        return None
    return (yy, mo, dd, hh, mm, ss)


def extract_and_merge_section_logs(
    log_artifacts: tuple[LogArtifactPayload, ...],
) -> tuple[list[bytes], int]:
    """Extrai e funde de modo idempotente todos os logs de uma seção (`FX-08`).

    No caso comum de arquivo único (`qtd == 1`), retorna `splitlines()` diretamente
    sem custo extra de ordenação. Em múltiplos logs (urna de contingência),
    deduplica linhas transferidas usando `(timestamp, mensagem, MAC_HEX)` e
    ordena cronologicamente preservando a sequência intra-segundo original.

    Args:
        log_artifacts: Tupla de pacotes `.logjez` associados à seção eleitoral.

    Returns:
        Tupla `(linhas_bytes_ordenadas, qtd_arquivos_log)`.

    Raises:
        MissingLogError: Se nenhum artefato ou membro `logd*.dat` estiver presente.
        CorruptArchiveError: Se qualquer pacote estiver truncado ou corrompido.
        HashMismatchError: Se algum pacote violar o hash `SHA-512` esperado.
    """
    if not log_artifacts:
        raise MissingLogError("Bundle da seção não possui nenhum artefato .logjez.")

    all_buffers: list[bytes] = []
    for artifact in log_artifacts:
        all_buffers.extend(extract_logd_buffers(artifact))

    qtd_logs = max(len(log_artifacts), len(all_buffers))
    if len(all_buffers) == 1:
        return all_buffers[0].splitlines(), qtd_logs

    seen_keys: set[tuple[bytes, bytes, bytes]] = set()
    sortable_lines: list[
        tuple[tuple[int, int, int, int, int, int], int, int, bytes]
    ] = []

    for file_idx, buf in enumerate(all_buffers):
        for line_idx, raw_line in enumerate(buf.splitlines()):
            ts_key = _timestamp_sort_key(raw_line)
            if ts_key is None:
                continue
            parts = raw_line.split(b"\t")
            if len(parts) >= 6:
                dedup_key = (parts[0], parts[4], parts[5].strip())
            else:
                dedup_key = (raw_line[:19], raw_line, b"")

            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            sortable_lines.append((ts_key, file_idx, line_idx, raw_line))

    sortable_lines.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in sortable_lines], qtd_logs
