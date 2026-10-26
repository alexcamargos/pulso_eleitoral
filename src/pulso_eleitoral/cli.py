"""Interface unificada de linha de comando (`pulso`) do Pulso Eleitoral.

Define a superfície de comandos especificada em `specs/05-testing-evals-and-roadmap.md`
Seção 3 (`ingest-parse`, `consolidate`, `export-json`, `verify`, `run-all`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pulso_eleitoral import __version__
from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings, SourceMode

app = typer.Typer(
    name="pulso",
    help="Pulso Eleitoral — Pipeline determinístico de auditoria de logs e BUs do TSE.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    """Exibe a versão atual do pipeline e encerra com código zero.

    Args:
        value: Flag booleana indicando se `--version` foi acionada.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Encerra imediatamente a execução após imprimir a versão.
    """
    if value:
        typer.echo(f"pulso-eleitoral {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def cli_root(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Exibe a versão do Pulso Eleitoral e encerra.",
        ),
    ] = None,
) -> None:
    """Ponto de entrada global da CLI `pulso`.

    Args:
        version: Opção eager `--version`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    _ = version


@app.command("ingest-parse")
def ingest_parse(
    ano: Annotated[int, typer.Option("--ano", help="Ano oficial da eleição.")] = 2022,
    turno: Annotated[int, typer.Option("--turno", help="Turno (1 ou 2).")] = 1,
    pleito: Annotated[int, typer.Option("--pleito", help="ID do pleito TSE.")] = 406,
    uf: Annotated[str, typer.Option("--uf", help="Sigla da UF ou ALL.")] = "ALL",
    source: Annotated[
        SourceMode,
        typer.Option("--source", help="Fonte oficial TSE (cdn ou zip)."),
    ] = SourceMode.ZIP,
    input_dir: Annotated[
        Path | None,
        typer.Option("--input-dir", help="Diretório local dos pacotes estaduais."),
    ] = None,
    workers: Annotated[
        int,
        typer.Option("--workers", help="Workers paralelos no ProcessPoolExecutor."),
    ] = 8,
    force: Annotated[
        bool,
        typer.Option("--force", help="Ignora checkpoints e reprocessa seções."),
    ] = False,
) -> None:
    """Executa ingestão, parsing multiprocesso e gravação atômica Parquet.

    Args:
        ano: Ano oficial da eleição.
        turno: Turno da eleição (`1` ou `2`).
        pleito: Identificador numérico do pleito no TSE.
        uf: UF alvo ou `"ALL"`.
        source: Modo de obtenção (`cdn` ou `zip`).
        input_dir: Diretório de entrada quando `source=zip`.
        workers: Quantidade de processos paralelos.
        force: Se `True`, reprocessa seções já consolidadas.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Caso a configuração seja inválida ou estágio ainda não conectado.
    """
    run_cfg = ElectionRunConfig(
        ano_eleicao=ano,
        turno=turno,
        pleito_id=pleito,
        ufs=(uf,),
        source_mode=source,
        force_reprocess=force,
        input_dir=input_dir,
    )
    settings = PipelineSettings(workers=workers)
    typer.echo(
        f"[pulso] Config validada: ano={run_cfg.ano_eleicao} turno={run_cfg.turno} "
        f"pleito={run_cfg.pleito_id} cutoff={run_cfg.cutoff_mode} "
        f"ufs={len(run_cfg.ufs)} workers={settings.workers}"
    )
    raise typer.Exit(code=2)


@app.command("consolidate")
def consolidate(
    ano: Annotated[int, typer.Option("--ano", help="Ano oficial da eleição.")] = 2022,
    turno: Annotated[int, typer.Option("--turno", help="Turno (1 ou 2).")] = 1,
    db_path: Annotated[
        Path,
        typer.Option("--db-path", help="Caminho do banco analítico DuckDB."),
    ] = Path("data/pulso_eleitoral.duckdb"),
) -> None:
    """Consolida partições Parquet e cria views analíticas OLAP no DuckDB.

    Args:
        ano: Ano oficial da eleição.
        turno: Turno (`1` ou `2`).
        db_path: Caminho do arquivo `.duckdb`.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Enquanto aguarda conexão do motor OLAP na Sprint 4.
    """
    _ = (ano, turno, db_path)
    raise typer.Exit(code=2)


@app.command("export-json")
def export_json(
    ano: Annotated[int, typer.Option("--ano", help="Ano oficial da eleição.")] = 2022,
    turno: Annotated[int, typer.Option("--turno", help="Turno (1 ou 2).")] = 1,
    db_path: Annotated[
        Path,
        typer.Option("--db-path", help="Caminho do banco analítico DuckDB."),
    ] = Path("data/pulso_eleitoral.duckdb"),
    out_dir: Annotated[
        Path,
        typer.Option("--out-dir", help="Diretório base de exportação JSON."),
    ] = Path("frontend/public/api/v1"),
) -> None:
    """Exporta payloads JSON estáticos determinísticos validados por schema.

    Args:
        ano: Ano oficial da eleição.
        turno: Turno (`1` ou `2`).
        db_path: Caminho do arquivo `.duckdb`.
        out_dir: Diretório raiz da API estática.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Enquanto aguarda conexão do exportador na Sprint 5.
    """
    _ = (ano, turno, db_path, out_dir)
    raise typer.Exit(code=2)


@app.command("verify")
def verify(
    db_path: Annotated[
        Path,
        typer.Option("--db-path", help="Caminho do banco analítico DuckDB."),
    ] = Path("data/pulso_eleitoral.duckdb"),
    json_dir: Annotated[
        Path,
        typer.Option("--json-dir", help="Diretório dos JSONs exportados."),
    ] = Path("frontend/public/api/v1"),
) -> None:
    """Executa bateria de auditoria pós-execução (invariantes e somas cruzadas).

    Args:
        db_path: Caminho do arquivo `.duckdb`.
        json_dir: Diretório dos artefatos JSON gerados.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Enquanto aguarda conexão do verificador na Sprint 5.
    """
    _ = (db_path, json_dir)
    raise typer.Exit(code=2)


@app.command("run-all")
def run_all(
    ano: Annotated[int, typer.Option("--ano", help="Ano oficial da eleição.")] = 2022,
    turno: Annotated[int, typer.Option("--turno", help="Turno (1 ou 2).")] = 1,
    pleito: Annotated[int, typer.Option("--pleito", help="ID do pleito TSE.")] = 406,
    uf: Annotated[str, typer.Option("--uf", help="Sigla da UF ou ALL.")] = "ALL",
    source: Annotated[
        SourceMode,
        typer.Option("--source", help="Fonte oficial TSE (cdn ou zip)."),
    ] = SourceMode.ZIP,
) -> None:
    """Orquestra em sequência `ingest-parse`, `consolidate`, `export-json` e `verify`.

    Args:
        ano: Ano oficial da eleição.
        turno: Turno (`1` ou `2`).
        pleito: Identificador numérico do pleito no TSE.
        uf: UF alvo ou `"ALL"`.
        source: Modo de obtenção (`cdn` ou `zip`).

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Enquanto aguarda conexão fim-a-fim na Sprint 5.
    """
    _ = (ano, turno, pleito, uf, source)
    raise typer.Exit(code=2)


def main() -> None:
    """Entrypoint principal registrado em `[project.scripts]` (`pulso`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    app()
