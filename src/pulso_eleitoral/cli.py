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

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Annotated

import typer

from pulso_eleitoral import __version__
from pulso_eleitoral.analytics.consolidator import DuckDbConsolidator
from pulso_eleitoral.analytics.orchestrator import PipelineOrchestrator
from pulso_eleitoral.analytics.verifier import PipelineVerifier
from pulso_eleitoral.config import (
    ElectionRunConfig,
    PipelineSettings,
    SourceMode,
)
from pulso_eleitoral.export.exporter import StaticJsonExporter
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog

logger = logging.getLogger(__name__)

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


ELECTION_TO_PLEITO_MAP: dict[tuple[int, int], int] = {
    # Mapeamento caso informado código de eleição federal no lugar do pleito:
    (2026, 6257): 3220,
    (2026, 6258): 3221,
    (2024, 456): 452,
    (2024, 457): 453,
}


def _resolve_default_pleito_id(ano: int, turno: int) -> int:
    """Resolve o ID canônico do pleito federal caso não seja especificado.

    Args:
        ano: Ano da eleição.
        turno: Turno da eleição (1 ou 2).

    Returns:
        ID inteiro do pleito no TSE.

    Raises:
        Nenhum.
    """
    if ano == 2026:
        return 3220 if turno == 1 else 3221
    if ano == 2024:
        return 452 if turno == 1 else 453
    if ano == 2020:
        return 304 if turno == 1 else 305
    return 406 if turno == 1 else 407


def _resolve_target_pleito_id(ano: int, turno: int, pleito: int | None) -> int:
    """Resolve o pleito alvo mapeando códigos de eleição informados por engano.

    Args:
        ano: Ano da eleição.
        turno: Turno da eleição (1 ou 2).
        pleito: Pleito informado na linha de comando ou None.

    Returns:
        Código canônico de pleito do TSE.

    Raises:
        Nenhum.
    """
    if pleito is not None:
        return ELECTION_TO_PLEITO_MAP.get((ano, pleito), pleito)
    return _resolve_default_pleito_id(ano, turno)


@app.command("ingest-parse")
def ingest_parse(
    ano: Annotated[int, typer.Option("--ano", help="Ano oficial da eleição.")] = 2022,
    turno: Annotated[int, typer.Option("--turno", help="Turno (1 ou 2).")] = 1,
    pleito: Annotated[
        int | None, typer.Option("--pleito", help="ID do pleito TSE.")
    ] = None,
    uf: Annotated[str, typer.Option("--uf", help="Sigla da UF ou ALL.")] = "ALL",
    municipio: Annotated[
        str | None,
        typer.Option("--municipio", "-m", help="Códigos TSE municipais para filtro."),
    ] = None,
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
        municipio: Filtro de municípios TSE opcional.
        source: Modo de obtenção (`cdn` ou `zip`).
        input_dir: Diretório de entrada quando `source=zip`.
        workers: Quantidade de processos paralelos.
        force: Se `True`, reprocessa seções já consolidadas.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Caso a execução falhe.
    """
    try:
        resolved_pleito = _resolve_target_pleito_id(ano, turno, pleito)
        mun_tuple: tuple[int, ...] = ()
        if municipio:
            mun_tuple = tuple(int(x.strip()) for x in municipio.split(",") if x.strip())
        run_cfg = ElectionRunConfig(
            ano_eleicao=ano,
            turno=turno,
            pleito_id=resolved_pleito,
            ufs=(uf,),
            municipios=mun_tuple,
            source_mode=source,
            force_reprocess=force,
            input_dir=input_dir,
        )
        settings = PipelineSettings(workers=workers)
        tz_catalog = TimezoneCatalog.from_csv(
            settings.resources_dir / "dim_municipio_fuso.csv"
        )
        orchestrator = PipelineOrchestrator(run_cfg, settings, tz_catalog)
        shared_pool: ProcessPoolExecutor | None = (
            ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
        )

        async def _run_all_ufs() -> None:
            for target_uf in run_cfg.ufs:
                typer.echo(f"[pulso] Processando UF: {target_uf}...")
                if shared_pool is not None:
                    summary = await orchestrator.run_uf(target_uf, executor=shared_pool)
                else:
                    summary = await orchestrator.run_uf(target_uf)
                if summary.checkpoint_sections > 0:
                    typer.echo(
                        f"[pulso] Concluído {summary.uf}: "
                        f"{summary.checkpoint_sections} em checkpoint, "
                        f"{summary.total_sections} nesta execução "
                        f"(sucesso={summary.success_sections} "
                        f"erros={summary.error_sections})"
                    )
                else:
                    typer.echo(
                        f"[pulso] Concluído {summary.uf}: "
                        f"total={summary.total_sections} "
                        f"sucesso={summary.success_sections} "
                        f"erros={summary.error_sections}"
                    )

        try:
            asyncio.run(_run_all_ufs())
        finally:
            if shared_pool is not None:
                shared_pool.shutdown(wait=True)
    except Exception as exc:
        typer.echo(f"[pulso erro] Falha em ingest-parse: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("consolidate")
def consolidate(
    ano: Annotated[int, typer.Option("--ano", help="Ano oficial da eleição.")] = 2022,
    turno: Annotated[int, typer.Option("--turno", help="Turno (1 ou 2).")] = 1,
    db_path: Annotated[
        Path,
        typer.Option("--db-path", help="Caminho do banco analítico DuckDB."),
    ] = Path("data/pulso_eleitoral.duckdb"),
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Diretório base de partições Parquet."),
    ] = None,
) -> None:
    """Consolida partições Parquet e cria views analíticas OLAP no DuckDB.

    Args:
        ano: Ano oficial da eleição.
        turno: Turno (`1` ou `2`).
        db_path: Caminho do arquivo `.duckdb`.
        data_dir: Diretório opcional contendo `processed/`.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Caso ocorra erro durante a consolidação.
    """
    _ = (ano, turno)
    try:
        resolved_data_dir = data_dir or (
            db_path.parent if (db_path.parent / "processed").is_dir() else Path("data")
        )
        settings = PipelineSettings(data_dir=resolved_data_dir, db_path=db_path)
        consolidator = DuckDbConsolidator(settings)
        result_path = consolidator.consolidate()
        rows = consolidator.query("SELECT COUNT(*) AS total FROM raw_section_metrics;")
        total = rows[0]["total"] if rows else 0
        typer.echo(
            f"[pulso] Consolidação DuckDB concluída com sucesso em {result_path} "
            f"({total} seções registradas)."
        )
    except Exception as exc:
        typer.echo(f"[pulso erro] Falha na consolidação DuckDB: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("export-json")
def export_json(
    ano: Annotated[int, typer.Option("--ano", help="Ano oficial da eleição.")] = 2022,
    turno: Annotated[int, typer.Option("--turno", help="Turno (1 ou 2).")] = 1,
    pleito: Annotated[
        int | None, typer.Option("--pleito", help="ID do pleito TSE.")
    ] = None,
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
        pleito: Identificador numérico do pleito TSE.
        db_path: Caminho do arquivo `.duckdb`.
        out_dir: Diretório raiz da API estática.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Caso ocorra falha na exportação.
    """
    try:
        resolved_pleito = _resolve_target_pleito_id(ano, turno, pleito)
        run_cfg = ElectionRunConfig(
            ano_eleicao=ano,
            turno=turno,
            pleito_id=resolved_pleito,
            ufs=("ALL",),
        )
        settings = PipelineSettings(db_path=db_path)
        exporter = StaticJsonExporter(settings, run_cfg)
        target_dir = out_dir / f"ele{ano}" / f"turno{turno}"
        generated = exporter.export_all(output_dir=target_dir)
        typer.echo(
            f"[pulso] Exportação concluída com sucesso: {len(generated)} arquivos "
            f"gerados em {target_dir}."
        )
    except Exception as exc:
        typer.echo(f"[pulso erro] Falha na exportação JSON: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("verify")
def verify(
    db_path: Annotated[
        Path,
        typer.Option("--db-path", help="Caminho do banco analítico DuckDB."),
    ] = Path("data/pulso_eleitoral.duckdb"),
    json_dir: Annotated[
        Path | None,
        typer.Option("--json-dir", help="Diretório dos JSONs exportados."),
    ] = None,
) -> None:
    """Executa bateria de auditoria pós-execução (invariantes e somas cruzadas).

    Args:
        db_path: Caminho do arquivo `.duckdb`.
        json_dir: Diretório opcional dos artefatos JSON gerados.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Caso a verificação encontre inconsistências.
    """
    try:
        settings = PipelineSettings(db_path=db_path)
        verifier = PipelineVerifier(settings)
        report = verifier.verify_all(json_dir=json_dir)
        typer.echo(
            f"[pulso auditoria] SUCESSO: {report.success_sections} seções válidas, "
            f"{report.error_sections} erros auditados. "
            f"DuckDB={report.db_size_mb} MB (SLA <= 200 MB). "
            f"Invariantes 1..6 e somas cruzadas 100% conformes."
        )
    except Exception as exc:
        typer.echo(f"[pulso erro] Auditoria reprovada: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("run-all")
def run_all(
    ano: Annotated[int, typer.Option("--ano", help="Ano oficial da eleição.")] = 2022,
    turno: Annotated[int, typer.Option("--turno", help="Turno (1 ou 2).")] = 1,
    pleito: Annotated[
        int | None, typer.Option("--pleito", help="ID do pleito TSE.")
    ] = None,
    uf: Annotated[str, typer.Option("--uf", help="Sigla da UF ou ALL.")] = "ALL",
    municipio: Annotated[
        str | None,
        typer.Option("--municipio", "-m", help="Códigos TSE municipais para filtro."),
    ] = None,
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
    db_path: Annotated[
        Path,
        typer.Option("--db-path", help="Caminho do banco analítico DuckDB."),
    ] = Path("data/pulso_eleitoral.duckdb"),
    out_dir: Annotated[
        Path,
        typer.Option("--out-dir", help="Diretório base de exportação JSON."),
    ] = Path("frontend/public/api/v1"),
) -> None:
    """Orquestra em sequência `ingest-parse`, `consolidate`, `export-json` e `verify`.

    Args:
        ano: Ano oficial da eleição.
        turno: Turno (`1` ou `2`).
        pleito: Identificador numérico do pleito no TSE.
        uf: UF alvo ou `"ALL"`.
        municipio: Filtro opcional de municípios TSE.
        source: Modo de obtenção (`cdn` ou `zip`).
        input_dir: Diretório de pacotes `.zip` estaduais.
        workers: Quantidade de processos paralelos no pool.
        force: Reprocessa seções mesmo se já consolidadas.
        db_path: Caminho do banco DuckDB.
        out_dir: Diretório de exportação JSON.

    Returns:
        Nenhum.

    Raises:
        typer.Exit: Caso alguma etapa falhe.
    """
    resolved_pleito = _resolve_target_pleito_id(ano, turno, pleito)
    typer.echo(
        f"[pulso pipeline] Iniciando execução completa para pleito {resolved_pleito}..."
    )
    # 1. Ingest-Parse
    ingest_parse(
        ano=ano,
        turno=turno,
        pleito=resolved_pleito,
        uf=uf,
        municipio=municipio,
        source=source,
        input_dir=input_dir,
        workers=workers,
        force=force,
    )
    # 2. Consolidate
    consolidate(ano=ano, turno=turno, db_path=db_path)
    # 3. Export JSON
    export_json(
        ano=ano,
        turno=turno,
        pleito=resolved_pleito,
        db_path=db_path,
        out_dir=out_dir,
    )
    # 4. Verify
    target_json_dir = out_dir / f"ele{ano}" / f"turno{turno}"
    verify(db_path=db_path, json_dir=target_json_dir)
    typer.echo("[pulso pipeline] Execução concluída e auditada com sucesso!")


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
