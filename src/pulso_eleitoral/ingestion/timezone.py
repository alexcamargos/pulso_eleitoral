"""Catálogo e resolvedor determinístico de fusos horários municipais (`REQ-ING-03`).

Carrega `resources/dim_municipio_fuso.csv`, valida as regras geográficas oficiais
do Brasil no boot e aplica a política Fail-Fast para UFs com múltiplos fusos
(`AM` e `PE`) descrita em `specs/01-ingestion-and-sources.md` Seção 3.2.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from pulso_eleitoral.config import DEFAULT_RESOURCES_DIR
from pulso_eleitoral.contracts.exceptions import (
    ContractValidationError,
    UnknownMunicipalityTimezoneError,
)
from pulso_eleitoral.contracts.models import MunicipalityTzInfo

logger = logging.getLogger(__name__)

REQUIRED_CSV_COLUMNS: frozenset[str] = frozenset(
    {
        "municipio_cod_tse",
        "municipio_cod_ibge",
        "uf",
        "municipio_nome",
        "iana_timezone",
        "fuso_horario_offset_brt",
    }
)

MULTI_TZ_UFS: frozenset[str] = frozenset({"AM", "PE"})
UTC4_SINGLE_TZ_IANA: dict[str, str] = {
    "MS": "America/Campo_Grande",
    "MT": "America/Cuiaba",
    "RO": "America/Porto_Velho",
    "RR": "America/Boa_Vista",
}
UTC3_SINGLE_TZ_IANA: dict[str, str] = {
    "AL": "America/Maceio",
    "AP": "America/Belem",
    "BA": "America/Bahia",
    "CE": "America/Fortaleza",
    "DF": "America/Sao_Paulo",
    "ES": "America/Sao_Paulo",
    "GO": "America/Sao_Paulo",
    "MA": "America/Fortaleza",
    "MG": "America/Sao_Paulo",
    "PA": "America/Belem",
    "PB": "America/Fortaleza",
    "PI": "America/Fortaleza",
    "PR": "America/Sao_Paulo",
    "RJ": "America/Sao_Paulo",
    "RN": "America/Fortaleza",
    "RS": "America/Sao_Paulo",
    "SC": "America/Sao_Paulo",
    "SE": "America/Maceio",
    "SP": "America/Sao_Paulo",
    "TO": "America/Araguaina",
    "ZZ": "America/Sao_Paulo",
}


class TimezoneCatalog:
    """Índice imutável em memória de fusos horários por código TSE (`REQ-ING-03`).

    Args:
        entries_by_tse: Mapa de `municipio_cod_tse` para `MunicipalityTzInfo`.

    Returns:
        Nenhum.

    Raises:
        ContractValidationError: Se o dicionário fornecido estiver vazio.
    """

    def __init__(self, entries_by_tse: dict[int, MunicipalityTzInfo]) -> None:
        """Inicializa o catálogo validado em memória.

        Args:
            entries_by_tse: Mapa de código TSE para metadados de fuso municipal.

        Returns:
            Nenhum.

        Raises:
            ContractValidationError: Se nenhuma entrada válida estiver presente.
        """
        if not entries_by_tse:
            raise ContractValidationError(
                "Catálogo de fusos horários não pode ser inicializado vazio."
            )
        self._by_tse: dict[int, MunicipalityTzInfo] = dict(entries_by_tse)

    def __len__(self) -> int:
        """Retorna o total de municípios indexados no catálogo.

        Args:
            Nenhum.

        Returns:
            Quantidade inteira de municípios carregados.

        Raises:
            Nenhum.
        """
        return len(self._by_tse)

    @classmethod
    def from_csv(cls, csv_path: Path | None = None) -> TimezoneCatalog:
        """Carrega e valida `dim_municipio_fuso.csv` aplicando checagens geográficas.

        Args:
            csv_path: Caminho opcional do arquivo CSV; por padrão usa `resources/`.

        Returns:
            Instância pronta e validada de `TimezoneCatalog`.

        Raises:
            ContractValidationError: Se o arquivo não existir, faltar coluna exigida,
                houver código TSE duplicado ou regra geográfica inválida por UF.
        """
        target_path = csv_path or (DEFAULT_RESOURCES_DIR / "dim_municipio_fuso.csv")
        if not target_path.is_file():
            raise ContractValidationError(
                f"Catálogo de fusos ausente em: {target_path}"
            )

        entries: dict[int, MunicipalityTzInfo] = {}
        with target_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            header = set(reader.fieldnames or [])
            missing_cols = REQUIRED_CSV_COLUMNS - header
            if missing_cols:
                missing_str = ", ".join(sorted(missing_cols))
                raise ContractValidationError(
                    f"Colunas ausentes em dim_municipio_fuso.csv: {missing_str}"
                )

            for line_num, row in enumerate(reader, start=2):
                try:
                    cod_tse = int(row["municipio_cod_tse"])
                    raw_ibge = row["municipio_cod_ibge"].strip()
                    cod_ibge = int(raw_ibge) if raw_ibge and int(raw_ibge) > 0 else None
                    uf = row["uf"].strip().upper()
                    nome = row["municipio_nome"].strip().upper()
                    iana = row["iana_timezone"].strip()
                    offset = int(row["fuso_horario_offset_brt"])
                except (TypeError, ValueError) as exc:
                    raise ContractValidationError(
                        f"Linha {line_num} inválida em {target_path}: {exc}"
                    ) from exc

                if cod_tse in entries:
                    raise ContractValidationError(
                        f"Código TSE duplicado ({cod_tse:05d}) na linha {line_num}."
                    )

                cls._validate_geographic_rule(
                    cod_tse=cod_tse,
                    cod_ibge=cod_ibge,
                    uf=uf,
                    offset=offset,
                )
                entries[cod_tse] = MunicipalityTzInfo(
                    municipio_cod_tse=cod_tse,
                    municipio_cod_ibge=cod_ibge,
                    uf=uf,
                    municipio_nome=nome,
                    iana_timezone=iana,
                    fuso_horario_offset_brt=offset,
                )

        return cls(entries)

    @staticmethod
    def _validate_geographic_rule(
        *,
        cod_tse: int,
        cod_ibge: int | None,
        uf: str,
        offset: int,
    ) -> None:
        """Valida a coerência geográfica entre UF, código IBGE e offset BRT.

        Args:
            cod_tse: Código TSE de 5 dígitos.
            cod_ibge: Código IBGE de 7 dígitos ou `None`.
            uf: Sigla da UF em maiúsculas.
            offset: Diferença em horas frente a Brasília (`-2`, `-1`, `0`, `+1`).

        Returns:
            Nenhum.

        Raises:
            ContractValidationError: Se o offset contradisser a legislação da UF.
        """
        if offset == 1 and (uf != "PE" or cod_ibge != 2605459):
            raise ContractValidationError(
                f"Offset +1 (UTC-2) exclusivo de Fernando de Noronha; "
                f"encontrado em {uf}/{cod_tse:05d}."
            )
        if uf == "AC" and offset != -2:
            raise ContractValidationError(
                f"Município do Acre ({cod_tse:05d}) deve ter offset -2, "
                f"obteve {offset}."
            )
        if uf in UTC4_SINGLE_TZ_IANA and offset != -1:
            raise ContractValidationError(
                f"Município de {uf} ({cod_tse:05d}) deve ter offset -1, "
                f"obteve {offset}."
            )
        if uf in UTC3_SINGLE_TZ_IANA and offset != 0:
            raise ContractValidationError(
                f"Município de {uf} ({cod_tse:05d}) deve ter offset 0, obteve {offset}."
            )
        if uf == "AM" and offset not in (-2, -1):
            raise ContractValidationError(
                f"Município do AM ({cod_tse:05d}) deve ter offset -1 ou -2, "
                f"obteve {offset}."
            )
        if uf == "PE" and offset not in (0, 1):
            raise ContractValidationError(
                f"Município de PE ({cod_tse:05d}) deve ter offset 0 ou +1, "
                f"obteve {offset}."
            )

    def get(self, municipio_cod_tse: int) -> MunicipalityTzInfo | None:
        """Obtém diretamente os metadados do município em $O(1)$ sem fallback.

        Args:
            municipio_cod_tse: Código TSE de 5 dígitos.

        Returns:
            `MunicipalityTzInfo` correspondente ou `None` se inexistente.

        Raises:
            Nenhum.
        """
        return self._by_tse.get(municipio_cod_tse)

    def resolve(
        self,
        municipio_cod_tse: int,
        uf: str,
        *,
        municipio_nome_fallback: str | None = None,
    ) -> MunicipalityTzInfo:
        """Resolve o fuso horário municipal aplicando a regra Fail-Fast (`REQ-ING-03`).

        Se `municipio_cod_tse` não existir no catálogo:
        - Para `AM` e `PE` (UFs multi-fuso), dispara `UnknownMunicipalityTimezoneError`.
        - Para `AC`, aplica fallback determinístico `-2` com log de alerta.
        - Para `MT`, `MS`, `RO`, `RR`, aplica fallback `-1` com log de alerta.
        - Para as 20 UFs `UTC-3` (e `ZZ`), aplica fallback `0` com log de alerta.

        Args:
            municipio_cod_tse: Código TSE de 5 dígitos.
            uf: Sigla da UF informada no manifesto.
            municipio_nome_fallback: Nome opcional do município oriundo do manifesto.

        Returns:
            Instância de `MunicipalityTzInfo` validada para a seção.

        Raises:
            UnknownMunicipalityTimezoneError: Se `uf` for `AM` ou `PE` e o código
                não constar no catálogo.
            ContractValidationError: Se a sigla de `uf` for desconhecida.
        """
        found = self._by_tse.get(municipio_cod_tse)
        if found is not None:
            return found

        norm_uf = uf.strip().upper()
        if norm_uf in MULTI_TZ_UFS:
            raise UnknownMunicipalityTimezoneError(
                uf=norm_uf,
                municipio_cod=municipio_cod_tse,
            )

        fallback_name = (
            municipio_nome_fallback.strip().upper()
            if municipio_nome_fallback
            else f"MUNICIPIO_{municipio_cod_tse:05d}"
        )

        if norm_uf == "AC":
            iana, offset = "America/Rio_Branco", -2
        elif norm_uf in UTC4_SINGLE_TZ_IANA:
            iana, offset = UTC4_SINGLE_TZ_IANA[norm_uf], -1
        elif norm_uf in UTC3_SINGLE_TZ_IANA:
            iana, offset = UTC3_SINGLE_TZ_IANA[norm_uf], 0
        else:
            raise ContractValidationError(
                f"UF desconhecida '{norm_uf}' ao resolver município "
                f"{municipio_cod_tse:05d}."
            )

        logger.warning(
            "Município TSE %05d (%s) ausente em dim_municipio_fuso.csv; "
            "aplicado fallback determinístico offset=%d (%s).",
            municipio_cod_tse,
            norm_uf,
            offset,
            iana,
        )
        return MunicipalityTzInfo(
            municipio_cod_tse=municipio_cod_tse,
            municipio_cod_ibge=None,
            uf=norm_uf,
            municipio_nome=fallback_name,
            iana_timezone=iana,
            fuso_horario_offset_brt=offset,
        )
