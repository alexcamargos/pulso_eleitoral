"""Carregamento e pré-compilação versionada de padrões de log (`REQ-PAR-02`).

Carrega arquivos `resources/log_patterns/{profile}.toml` uma única vez por
processo worker, compilando um autômato único de grupos nomeados em C para os
10 eventos canônicos da Máquina de Estados Finita.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pulso_eleitoral.config import DEFAULT_RESOURCES_DIR
from pulso_eleitoral.contracts.exceptions import ContractValidationError


class CanonicalEvent(StrEnum):
    """Eventos canônicos reconhecidos pela FSM do eleitor (`specs/02` Seção 3).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    VOTING_OPENED = "VOTING_OPENED"
    VOTER_SESSION_START = "VOTER_SESSION_START"
    BIO_SUCCESS = "BIO_SUCCESS"
    BIO_FAIL = "BIO_FAIL"
    BIO_BYPASS = "BIO_BYPASS"
    VOTER_ENABLED = "VOTER_ENABLED"
    VOTE_CONFIRMED = "VOTE_CONFIRMED"
    VOTER_ABORTED = "VOTER_ABORTED"
    SYSTEM_REBOOT = "SYSTEM_REBOOT"
    SECTION_CLOSED = "SECTION_CLOSED"


EVENT_EVALUATION_ORDER: tuple[CanonicalEvent, ...] = (
    CanonicalEvent.VOTE_CONFIRMED,
    CanonicalEvent.VOTER_ABORTED,
    CanonicalEvent.BIO_SUCCESS,
    CanonicalEvent.BIO_BYPASS,
    CanonicalEvent.BIO_FAIL,
    CanonicalEvent.VOTER_ENABLED,
    CanonicalEvent.VOTER_SESSION_START,
    CanonicalEvent.VOTING_OPENED,
    CanonicalEvent.SECTION_CLOSED,
    CanonicalEvent.SYSTEM_REBOOT,
)

EVENT_BY_NAME: dict[str, CanonicalEvent] = {ev.value: ev for ev in CanonicalEvent}


@dataclass(slots=True, frozen=True)
class LogPatternProfile:
    r"""Perfil imutável de expressões regulares pré-compiladas por ciclo eleitoral.

    Args:
        profile_id: Identificador do perfil (ex.: `v2022_2026`).
        vota_app_tokens_bytes: Tokens em `bytes` (`b"\tVOTA\t"`, etc.) para fast-path.
        master_event_pattern: Autômato regex único com grupos nomeados em C.
        aptos_pattern: Regex opcional para extrair eleitores aptos do cabeçalho do log.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    profile_id: str
    vota_app_tokens_bytes: tuple[bytes, ...]
    master_event_pattern: re.Pattern[str]
    aptos_pattern: re.Pattern[str] | None = None

    def classify_message(self, message: str) -> CanonicalEvent | None:
        """Classifica a mensagem descritiva (`col[4]`) em passagem única em C.

        Args:
            message: Texto decodificado em `latin-1` da 5ª coluna do `logd.dat`.

        Returns:
            `CanonicalEvent` correspondente ou `None` se a linha for irrelevante.

        Raises:
            Nenhum.
        """
        match = self.master_event_pattern.search(message)
        if match is not None and match.lastgroup is not None:
            return EVENT_BY_NAME[match.lastgroup]
        return None


@lru_cache(maxsize=8)
def load_pattern_profile(
    profile_id: str = "v2022_2026",
    resources_dir: Path | None = None,
) -> LogPatternProfile:
    """Carrega e pré-compila um perfil `.toml` de padrões de log (`@lru_cache`).

    Args:
        profile_id: Nome do perfil sem extensão (ex.: `v2022_2026` ou `v2020`).
        resources_dir: Diretório raiz opcional de recursos.

    Returns:
        Instância cacheada de `LogPatternProfile`.

    Raises:
        ContractValidationError: Se o arquivo `.toml` não existir ou omitir eventos.
    """
    base_dir = resources_dir or DEFAULT_RESOURCES_DIR
    toml_path = base_dir / "log_patterns" / f"{profile_id}.toml"
    if not toml_path.is_file():
        raise ContractValidationError(
            f"Perfil de padrões de log ausente em: {toml_path}"
        )

    raw_data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    flags = re.IGNORECASE if raw_data.get("case_insensitive", True) else 0
    raw_tokens = raw_data.get("vota_app_tokens", ["VOTA", "GAP"])
    app_tokens = tuple(f"\t{tok!s}\t".encode("latin-1") for tok in raw_tokens)

    events_section = raw_data.get("events", {})
    if not isinstance(events_section, dict):
        raise ContractValidationError(
            f"Seção [events] inválida no perfil '{profile_id}'."
        )

    named_branches: list[str] = []
    for canonical in EVENT_EVALUATION_ORDER:
        patterns_list = events_section.get(canonical.value)
        if not isinstance(patterns_list, list) or not patterns_list:
            raise ContractValidationError(
                f"Evento obrigatório '{canonical.value}' ausente "
                f"em '{profile_id}.toml'."
            )
        joined = "|".join(f"(?:{pat})" for pat in patterns_list)
        named_branches.append(f"(?P<{canonical.value}>{joined})")

    master_regex = re.compile("|".join(named_branches), flags)

    meta_section = raw_data.get("metadata", {})
    aptos_raw = (
        meta_section.get("eleitores_aptos") if isinstance(meta_section, dict) else None
    )
    aptos_regex = re.compile(str(aptos_raw), flags) if aptos_raw else None

    return LogPatternProfile(
        profile_id=str(raw_data.get("profile_id", profile_id)),
        vota_app_tokens_bytes=app_tokens,
        master_event_pattern=master_regex,
        aptos_pattern=aptos_regex,
    )
