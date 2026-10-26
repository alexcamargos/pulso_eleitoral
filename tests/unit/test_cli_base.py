"""Testes unitários da superfície inicial da CLI unificada `pulso` (`REQ-QA-01`).

Verifica flag `--version`, `--help` e validação inicial dos 5 subcomandos
declarados em `specs/05-testing-evals-and-roadmap.md` Seção 3.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from pulso_eleitoral import __version__
from pulso_eleitoral import cli as cli_module
from pulso_eleitoral.cli import app

runner = CliRunner()


def test_cli_version_and_help_commands() -> None:
    """Confirma resposta de `--version` e listagem dos 5 subcomandos no `--help`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    ver_res = runner.invoke(app, ["--version"])
    assert ver_res.exit_code == 0
    assert __version__ in ver_res.stdout

    help_res = runner.invoke(app, ["--help"])
    assert help_res.exit_code == 0
    for cmd in ("ingest-parse", "consolidate", "export-json", "verify", "run-all"):
        assert cmd in help_res.stdout


@pytest.mark.parametrize(
    "args",
    [
        ["export-json", "--db-path", "missing.duckdb"],
        ["verify", "--db-path", "missing.duckdb"],
    ],
)
def test_cli_subcommands_fail_gracefully_when_db_missing(args: list[str]) -> None:
    """Confirma falha graciosa dos subcomandos quando banco DuckDB não existe.

    Args:
        args: Lista de argumentos da linha de comando a invocar.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    result = runner.invoke(app, args)
    assert result.exit_code == 1


def test_cli_main_entrypoint_invokes_typer_app(mocker: MockerFixture) -> None:
    """Verifica invocação do objeto Typer pelo entrypoint `main()` usando `pytest-mock`.

    Args:
        mocker: Fixture oficial do `pytest-mock`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    mocked_app = mocker.patch.object(cli_module, "app")
    cli_module.main()
    mocked_app.assert_called_once_with()


def test_cli_pleito_resolution_and_aliases() -> None:
    """Verifica resolução de pleitos canônicos e mapeamento de códigos de eleição.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    # Defaults de 2026
    assert cli_module._resolve_default_pleito_id(2026, 1) == 3220
    assert cli_module._resolve_default_pleito_id(2026, 2) == 3221

    # Defaults de 2024
    assert cli_module._resolve_default_pleito_id(2024, 1) == 452
    assert cli_module._resolve_default_pleito_id(2024, 2) == 453

    # Tolerância a código de eleição informado na linha de comando
    assert cli_module._resolve_target_pleito_id(2026, 2, 6258) == 3221
    assert cli_module._resolve_target_pleito_id(2026, 1, 6257) == 3220
    assert cli_module._resolve_target_pleito_id(2024, 1, 456) == 452
    assert cli_module._resolve_target_pleito_id(2024, 2, 457) == 453

    # Pleito explícito não alterado quando já canônico
    assert cli_module._resolve_target_pleito_id(2026, 2, 3221) == 3221
    assert cli_module._resolve_target_pleito_id(2022, 2, 407) == 407
