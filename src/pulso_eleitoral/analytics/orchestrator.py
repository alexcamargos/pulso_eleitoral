"""Orquestrador multiprocesso com controle de backpressure de memória (`REQ-ANA-01`).

Coordena o pipeline Producer (AsyncIO) -> Workers (ProcessPoolExecutor) ->
Collector / ParquetBatchWriter, garantindo o limite estrito de memória (`<= 8 GB RAM`)
e persistência em lotes atômicos.

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
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pulso_eleitoral.analytics.parquet_writer import ParquetBatchWriter
from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings, SourceMode
from pulso_eleitoral.contracts.exceptions import ErrorCode
from pulso_eleitoral.contracts.models import (
    IngestionCheckpoint,
    ParsedSectionMetrics,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.ingestion.base import SectionArtifactProvider
from pulso_eleitoral.ingestion.cdn_provider import CdnArtifactProvider
from pulso_eleitoral.ingestion.checkpoint import CheckpointStore
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog
from pulso_eleitoral.ingestion.zip_provider import BulkZipArtifactProvider
from pulso_eleitoral.parser.engine import parse_section_bundle

logger = logging.getLogger(__name__)


def _parse_bundle_worker(
    bundle: SectionArtifactBundle,
    resources_dir: Path,
    profile_name: str,
) -> ParsedSectionMetrics | UnprocessedSectionError:
    """Função de nível superior executada nos processos workers.

    Args:
        bundle: Pacote de artefatos da seção entregue pela ingestão.
        resources_dir: Caminho dos recursos estáticos versionados.
        profile_name: Perfil de expressões regulares ativo.

    Returns:
        Métricas auditadas ou erro de seção não processada.

    Raises:
        Nenhum.
    """
    return parse_section_bundle(
        bundle,
        profile_id=profile_name,
        resources_dir=resources_dir,
    )


@dataclass(slots=True, frozen=True)
class UfExecutionSummary:
    """Sumário de execução do processamento de uma Unidade Federativa.

    Args:
        uf: Sigla da UF em 2 letras.
        total_sections: Total de seções avaliadas no fluxo desta execução.
        success_sections: Quantidade de seções concluídas com sucesso.
        error_sections: Quantidade de seções com erro registradas em auditoria.
        parquet_files: Caminhos das partições Parquet geradas.
        checkpoint_sections: Quantidade de seções já consolidadas em execuções prévias.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    uf: str
    total_sections: int
    success_sections: int
    error_sections: int
    parquet_files: tuple[Path, ...]
    checkpoint_sections: int = 0


class PipelineOrchestrator:
    """Orquestrador multiprocesso com controle de concorrência e escrita atômica.

    Args:
        run_cfg: Configuração do pleito e turnos.
        settings: Configurações de diretórios, pools e limites.
        tz_catalog: Catálogo de fusos horários municipais.
        provider: Provedor opcional injetável de artefatos.
        checkpoint_store: Armazém opcional de checkpoints.
        writer: Escritor em lotes Parquet opcional.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        run_cfg: ElectionRunConfig,
        settings: PipelineSettings,
        tz_catalog: TimezoneCatalog,
        *,
        provider: SectionArtifactProvider | None = None,
        checkpoint_store: CheckpointStore | None = None,
        writer: ParquetBatchWriter | None = None,
    ) -> None:
        """Inicializa o orquestrador do pipeline de processamento.

        Args:
            run_cfg: Configuração do turno e parâmetros do pleito.
            settings: Configurações de recursos e paralelismo.
            tz_catalog: Catálogo geográfico de fusos horários.
            provider: Provedor de artefatos (CDN ou ZIP).
            checkpoint_store: Gerenciador de checkpoints Parquet.
            writer: Escritor de partições Parquet.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._run_cfg = run_cfg
        self._settings = settings
        self._tz_catalog = tz_catalog
        self._checkpoint_store = checkpoint_store or CheckpointStore(
            settings.processed_dir
        )
        self._writer = writer or ParquetBatchWriter(settings)
        if provider is not None:
            self._provider = provider
        elif run_cfg.source_mode == SourceMode.CDN:
            self._provider = CdnArtifactProvider(
                run_cfg=run_cfg,
                settings=settings,
                tz_catalog=tz_catalog,
            )
        else:
            self._provider = BulkZipArtifactProvider(
                run_cfg=run_cfg,
                settings=settings,
                tz_catalog=tz_catalog,
            )

    async def run_uf(
        self,
        uf: str,
        *,
        executor: Executor | None = None,
    ) -> UfExecutionSummary:
        """Processa uma UF com streaming assíncrono e paralelismo limitado.

        Args:
            uf: Sigla da UF em 2 letras.
            executor: Executor de processos ou threads opcionalmente injetado.

        Returns:
            Instância de `UfExecutionSummary` com as estatísticas do processamento.

        Raises:
            Nenhum.
        """
        norm_uf = uf.strip().upper()
        assert self._run_cfg.log_pattern_profile is not None
        profile_name = self._run_cfg.log_pattern_profile

        checkpoint: IngestionCheckpoint | None = None
        if not self._run_cfg.force_reprocess:
            checkpoint = self._checkpoint_store.load_uf_checkpoint(
                ano_eleicao=self._run_cfg.ano_eleicao,
                turno=self._run_cfg.turno,
                pleito_id=self._run_cfg.pleito_id,
                uf=norm_uf,
                force_reprocess=False,
            )

        loop = asyncio.get_running_loop()
        owns_executor = False
        pool = executor

        if pool is None:
            if self._settings.workers > 1:
                owns_executor = True
                pool = ProcessPoolExecutor(max_workers=self._settings.workers)
            else:
                pool = None

        metrics_buffer: list[ParsedSectionMetrics] = []
        errors_buffer: list[UnprocessedSectionError] = []
        written_files: list[Path] = []
        chunk_id = 1
        total_sections = 0
        success_sections = 0
        error_sections = 0

        # Semáforo para garantir backpressure rigoroso
        max_in_flight = max(1, self._settings.max_in_flight)
        sem = asyncio.Semaphore(max_in_flight)
        TaskFuture = asyncio.Future[ParsedSectionMetrics | UnprocessedSectionError]
        in_flight_tasks: set[TaskFuture] = set()

        def flush_batch() -> None:
            nonlocal chunk_id
            if metrics_buffer:
                target = self._writer.write_metrics_batch(
                    metrics_buffer,
                    chunk_id=chunk_id,
                )
                if target:
                    written_files.append(target)
                chunk_id += 1
                metrics_buffer.clear()

        def collect_result(res: ParsedSectionMetrics | UnprocessedSectionError) -> None:
            nonlocal success_sections, error_sections
            if isinstance(res, ParsedSectionMetrics):
                metrics_buffer.append(res)
                if res.status_processamento == "SUCCESS":
                    success_sections += 1
                else:
                    error_sections += 1
            else:
                # Seção com erro: gera registro em auditoria e linha espelho zerada
                error_sections += 1
                errors_buffer.append(res)
                mirror_metric = ParsedSectionMetrics.from_unprocessed_error(res)
                metrics_buffer.append(mirror_metric)

            if len(metrics_buffer) >= self._settings.batch_size:
                flush_batch()

        try:
            async for item in self._provider.stream_uf(norm_uf, checkpoint):
                total_sections += 1
                if isinstance(item, UnprocessedSectionError):
                    collect_result(item)
                    continue

                # Submeter para processamento assíncrono / multiprocesso
                await sem.acquire()

                async def _task_wrapper(
                    b: SectionArtifactBundle,
                ) -> ParsedSectionMetrics | UnprocessedSectionError:
                    try:
                        if pool is not None:
                            try:
                                res = await loop.run_in_executor(
                                    pool,
                                    _parse_bundle_worker,
                                    b,
                                    self._settings.resources_dir,
                                    profile_name,
                                )
                                return res
                            except Exception as pool_exc:
                                logger.warning(
                                    "Falha no worker pool para seção %s/%s/%s: %s. "
                                    "Executando fallback local.",
                                    b.uf,
                                    b.zona,
                                    b.secao,
                                    pool_exc,
                                )
                                return _parse_bundle_worker(
                                    b,
                                    self._settings.resources_dir,
                                    profile_name,
                                )
                        # Execução no processo local (1 worker)
                        return _parse_bundle_worker(
                            b,
                            self._settings.resources_dir,
                            profile_name,
                        )
                    except Exception as fatal_exc:
                        logger.error(
                            "Erro irrecuperável no parsing da seção %s/%s/%s: %s",
                            b.uf,
                            b.zona,
                            b.secao,
                            fatal_exc,
                        )
                        return UnprocessedSectionError(
                            ano_eleicao=b.ano_eleicao,
                            turno=b.turno,
                            pleito_id=b.pleito_id,
                            uf=b.uf,
                            municipio_cod=b.municipio_cod,
                            municipio_ibge=b.municipio_ibge,
                            municipio_nome=b.municipio_nome,
                            zona=b.zona,
                            secao=b.secao,
                            fuso_horario_offset_brt=b.fuso_horario_offset_brt,
                            cutoff_mode=b.cutoff_mode,
                            error_code=ErrorCode.PARSE_ERROR.value,
                            error_message=(
                                f"Falha de parsing irrecuperável: {fatal_exc}"
                            ),
                            recorded_at=datetime.now(UTC).replace(tzinfo=None),
                            source_uri=b.source_uri,
                            attempt_count=1,
                        )
                    finally:
                        sem.release()

                fut = asyncio.create_task(_task_wrapper(item))
                in_flight_tasks.add(fut)

                # Limpar tarefas concluídas para evitar acúmulo
                done = {t for t in in_flight_tasks if t.done()}
                for t in done:
                    in_flight_tasks.remove(t)
                    collect_result(await t)

            # Aguardar todas as tarefas pendentes
            if in_flight_tasks:
                pending_results = await asyncio.gather(*in_flight_tasks)
                for res in pending_results:
                    collect_result(res)
                in_flight_tasks.clear()

            # Descarga final dos buffers
            flush_batch()
            if errors_buffer:
                audit_target = self._writer.write_audit_batch(errors_buffer)
                if audit_target:
                    written_files.append(audit_target)
                errors_buffer.clear()

        finally:
            if owns_executor and pool is not None:
                pool.shutdown(wait=True)

        checkpoint_count = (
            len(checkpoint.completed_sections) if checkpoint is not None else 0
        )
        return UfExecutionSummary(
            uf=norm_uf,
            total_sections=total_sections,
            success_sections=success_sections,
            error_sections=error_sections,
            parquet_files=tuple(written_files),
            checkpoint_sections=checkpoint_count,
        )
