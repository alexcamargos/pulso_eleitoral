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
        [
            "ingest-parse",
            "--ano",
            "2022",
            "--turno",
            "1",
            "--pleito",
            "406",
            "--uf",
            "AC",
        ],
        ["consolidate"],
        ["export-json"],
        ["verify"],
        ["run-all"],
    ],
)
def test_cli_placeholder_subcommands_validate_arguments(args: list[str]) -> None:
    """Confirma validação de argumentos e retorno exit code 2 nos placeholders.

    Args:
        args: Lista de argumentos da linha de comando a invocar.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    result = runner.invoke(app, args)
    assert result.exit_code == 2


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
