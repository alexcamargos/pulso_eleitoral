"""Testes unitários do catálogo nacional de fusos horários (`REQ-ING-03`).

Valida os 5.570 municípios em `resources/dim_municipio_fuso.csv`, incluindo
Fernando de Noronha (`+1`), Acre (`-2`), os 13 municípios do Sudoeste do AM (`-2`)
e a política Fail-Fast para `AM` e `PE`.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pulso_eleitoral.contracts.exceptions import (
    ContractValidationError,
    UnknownMunicipalityTimezoneError,
)
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog


def test_official_catalog_loads_all_5570_brazilian_municipalities(
    official_timezone_catalog: TimezoneCatalog,
) -> None:
    """Comprova cobertura nacional integral e distribuição exata dos 4 fusos.

    Args:
        official_timezone_catalog: Catálogo oficial carregado pela fixture de sessão.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    assert len(official_timezone_catalog) == 5570

    noronha = official_timezone_catalog.get(30015)
    assert noronha is not None
    assert noronha.uf == "PE"
    assert noronha.municipio_cod_ibge == 2605459
    assert noronha.fuso_horario_offset_brt == 1
    assert noronha.iana_timezone == "America/Noronha"

    sp = official_timezone_catalog.resolve(71072, "SP")
    assert sp.fuso_horario_offset_brt == 0

    manaus = official_timezone_catalog.resolve(2550, "AM")
    assert manaus.fuso_horario_offset_brt == -1

    tabatinga = official_timezone_catalog.resolve(98477, "AM")
    assert tabatinga.fuso_horario_offset_brt == -2
    assert tabatinga.iana_timezone == "America/Eirunepe"

    rio_branco = official_timezone_catalog.resolve(1392, "AC")
    assert rio_branco.fuso_horario_offset_brt == -2


def test_fail_fast_raises_on_unknown_municipality_in_am_or_pe(
    official_timezone_catalog: TimezoneCatalog,
) -> None:
    """Garante erro explícito ao omitir município em UF multi-fuso (`AM` e `PE`).

    Args:
        official_timezone_catalog: Catálogo oficial carregado pela fixture de sessão.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    with pytest.raises(UnknownMunicipalityTimezoneError, match="'AM'"):
        official_timezone_catalog.resolve(99991, "AM")

    with pytest.raises(UnknownMunicipalityTimezoneError, match="'PE'"):
        official_timezone_catalog.resolve(99992, "pe")


def test_deterministic_fallback_for_single_timezone_ufs(
    official_timezone_catalog: TimezoneCatalog,
) -> None:
    """Verifica fallbacks determinísticos para `AC` (`-2`), `MT` (`-1`) e `SP` (`0`).

    Args:
        official_timezone_catalog: Catálogo oficial carregado pela fixture de sessão.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    fb_ac = official_timezone_catalog.resolve(
        99993,
        "AC",
        municipio_nome_fallback="vila nova",
    )
    assert fb_ac.fuso_horario_offset_brt == -2
    assert fb_ac.municipio_nome == "VILA NOVA"

    fb_mt = official_timezone_catalog.resolve(99994, "MT")
    assert fb_mt.fuso_horario_offset_brt == -1
    assert fb_mt.municipio_nome == "MUNICIPIO_99994"

    fb_sp = official_timezone_catalog.resolve(99995, "SP")
    assert fb_sp.fuso_horario_offset_brt == 0

    with pytest.raises(ContractValidationError, match="UF desconhecida"):
        official_timezone_catalog.resolve(99996, "XX")


@pytest.mark.parametrize(
    ("csv_body", "expected_msg"),
    [
        ("municipio_cod_tse,uf\n1,SP\n", "Colunas ausentes"),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n",
            "não pode ser inicializado vazio",
        ),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n"
            "abc,1,SP,TESTE,America/Sao_Paulo,0\n",
            "Linha 2 inválida",
        ),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n"
            "100,1,SP,A,America/Sao_Paulo,0\n"
            "100,2,SP,B,America/Sao_Paulo,0\n",
            "Código TSE duplicado",
        ),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n"
            "100,1,SP,A,America/Noronha,1\n",
            "exclusivo de Fernando de Noronha",
        ),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n"
            "100,1,AC,A,America/Rio_Branco,-1\n",
            "Município do Acre",
        ),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n"
            "100,1,MT,A,America/Cuiaba,0\n",
            "Município de MT",
        ),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n"
            "100,1,SP,A,America/Sao_Paulo,-1\n",
            "Município de SP",
        ),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n"
            "100,1,AM,A,America/Manaus,0\n",
            "Município do AM",
        ),
        (
            "municipio_cod_tse,municipio_cod_ibge,uf,municipio_nome,"
            "iana_timezone,fuso_horario_offset_brt\n"
            "100,1,PE,A,America/Recife,-1\n",
            "Município de PE",
        ),
    ],
)
def test_timezone_catalog_rejects_corrupt_or_inconsistent_csv(
    tmp_path: Path,
    csv_body: str,
    expected_msg: str,
) -> None:
    """Valida todas as defesas de integridade no carregamento do CSV de fusos.

    Args:
        tmp_path: Diretório temporário isolado fornecido pelo `pytest`.
        csv_body: Conteúdo CSV malformado ou geograficamente inválido.
        expected_msg: Mensagem esperada em `ContractValidationError`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    bad_csv = tmp_path / "bad_fuso.csv"
    bad_csv.write_text(csv_body, encoding="utf-8")
    with pytest.raises(ContractValidationError, match=expected_msg):
        TimezoneCatalog.from_csv(bad_csv)


def test_timezone_catalog_raises_when_file_missing(tmp_path: Path) -> None:
    """Garante erro explícito quando o arquivo CSV apontado não existe.

    Args:
        tmp_path: Diretório temporário isolado fornecido pelo `pytest`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    with pytest.raises(ContractValidationError, match="Catálogo de fusos ausente"):
        TimezoneCatalog.from_csv(tmp_path / "inexistente.csv")
