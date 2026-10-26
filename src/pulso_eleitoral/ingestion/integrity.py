"""Verificação criptográfica de integridade (`SHA-512` / `SHA-256`) (`REQ-ING-02`).

Valida em memória os bytes recebidos contra os digests publicados nos manifestos
`-aux.json` do TSE antes do enfileiramento para o `ProcessPoolExecutor`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import hashlib


def compute_sha512_hex(payload: bytes) -> str:
    """Calcula o digest `SHA-512` hexadecimal em minúsculas de um buffer.

    Args:
        payload: Conteúdo binário em memória.

    Returns:
        String hexadecimal de 128 caracteres.

    Raises:
        Nenhum.
    """
    return hashlib.sha512(payload).hexdigest().lower()


def verify_artifact_digest(
    payload: bytes,
    expected_hex: str | None,
) -> tuple[bool, str]:
    """Compara o digest de `payload` contra `expected_hex` (`SHA-512` ou `SHA-256`).

    Args:
        payload: Bytes brutos baixados ou extraídos.
        expected_hex: Hash hexadecimal esperado (`128` hex para SHA-512 ou `64`
            hex para SHA-256), ou `None` quando o manifesto não informar hash.

    Returns:
        Tupla `(is_valid, actual_digest_hex)`. Quando `expected_hex` é `None` ou
        vazio, retorna `(True, sha512_hex)`.

    Raises:
        Nenhum.
    """
    if not expected_hex or not expected_hex.strip():
        return True, compute_sha512_hex(payload)

    clean_expected = expected_hex.strip().lower()
    if len(clean_expected) == 64:
        actual = hashlib.sha256(payload).hexdigest().lower()
    else:
        actual = compute_sha512_hex(payload)
    return actual == clean_expected, actual
