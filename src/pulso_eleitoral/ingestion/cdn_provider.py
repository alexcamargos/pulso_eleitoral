"""Provedor assíncrono de ingestão via CDN Oficial de Resultados (`REQ-ING-01`).

Resolve hierarquicamente os catálogos `-cs.json` e manifestos `-aux.json` em
`resultados.tse.jus.br`, baixando em memória todos os `.logjez` (incluindo urnas
de contingência) e `.bu` com HTTP/2, *Token Bucket*, *Retry Full Jitter*,
*Circuit Breaker* e validação criptográfica `SHA-512` (`REQ-ING-02`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import httpx
import orjson

from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings
from pulso_eleitoral.contracts.exceptions import (
    CorruptArchiveError,
    ErrorCode,
    HashMismatchError,
    HttpExhaustedError,
    MissingLogError,
    SectionAuditError,
)
from pulso_eleitoral.contracts.models import (
    IngestionCheckpoint,
    LogArtifactPayload,
    MunicipalityTzInfo,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.ingestion.base import build_ingestion_error
from pulso_eleitoral.ingestion.integrity import verify_artifact_digest
from pulso_eleitoral.ingestion.resilience import (
    RETRYABLE_STATUS_CODES,
    CircuitBreaker,
    TokenBucketRateLimiter,
    compute_full_jitter_delay,
)
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog

SleepFunc = Callable[[float], Coroutine[Any, Any, None]]


class CdnArtifactProvider:
    """Estratégia Modo A: download assíncrono seletivo do CDN TSE (`REQ-ING-01`).

    Args:
        run_cfg: Configuração imutável do pleito/turno.
        settings: Configurações operacionais de rede, timeouts e limites.
        tz_catalog: Catálogo validado de fusos horários municipais.
        http_client: Cliente `httpx.AsyncClient` opcional (ex.: `MockTransport`).
        rate_limiter: Limitador *Token Bucket* opcional.
        circuit_breaker: Disjuntor assíncrono opcional.
        sleep_func: Função assíncrona de espera injetável para testes rápidos.
        rng: Gerador pseudoaleatório opcional para cálculo de *Full Jitter*.

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
        http_client: httpx.AsyncClient | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        sleep_func: SleepFunc = asyncio.sleep,
        rng: random.Random | None = None,
    ) -> None:
        """Inicializa o provedor CDN com primitivas de resiliência HTTP.

        Args:
            run_cfg: Configuração ativa do pleito/turno.
            settings: Configurações operacionais globais.
            tz_catalog: Catálogo validado de fusos horários.
            http_client: Cliente HTTP assíncrono opcional.
            rate_limiter: Limitador de taxa opcional.
            circuit_breaker: Disjuntor de falhas opcional.
            sleep_func: Corrotina de espera entre tentativas.
            rng: Gerador pseudoaleatório opcional para jitter.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._run_cfg = run_cfg
        self._settings = settings
        self._tz_catalog = tz_catalog
        self._external_client = http_client
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter(
            settings.requests_per_second
        )
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._sleep = sleep_func
        self._rng = rng

    def build_cs_url(self, uf: str) -> str:
        """Constrói a URL canônica do índice estadual `-cs.json` (`specs/01` 1.1).

        Args:
            uf: Sigla da UF em 2 caracteres.

        Returns:
            URL completa do arquivo `{uf_lower}-p{pleito_6dig}-cs.json`.

        Raises:
            Nenhum.
        """
        uf_lower = uf.strip().lower()
        pleito_6 = f"{self._run_cfg.pleito_id:06d}"
        base = self._settings.cdn_base_url.rstrip("/")
        return (
            f"{base}/ele{self._run_cfg.ano_eleicao}/arquivo-urna/"
            f"{self._run_cfg.pleito_id}/config/{uf_lower}/"
            f"{uf_lower}-p{pleito_6}-cs.json"
        )

    def build_aux_url(
        self,
        uf: str,
        municipio_cod: int,
        zona: int,
        secao: int,
    ) -> str:
        """Constrói a URL canônica do manifesto `-aux.json` da seção (`specs/01`).

        Args:
            uf: Sigla da UF em 2 caracteres.
            municipio_cod: Código TSE do município (`1..99999`).
            zona: Número da zona eleitoral (`1..9999`).
            secao: Número da seção eleitoral (`1..9999`).

        Returns:
            URL completa do manifesto `-aux.json` da seção.

        Raises:
            Nenhum.
        """
        uf_lower = uf.strip().lower()
        pleito_6 = f"{self._run_cfg.pleito_id:06d}"
        mun_5 = f"{municipio_cod:05d}"
        zona_4 = f"{zona:04d}"
        secao_4 = f"{secao:04d}"
        base = self._settings.cdn_base_url.rstrip("/")
        return (
            f"{base}/ele{self._run_cfg.ano_eleicao}/arquivo-urna/"
            f"{self._run_cfg.pleito_id}/dados/{uf_lower}/{mun_5}/"
            f"{zona_4}/{secao_4}/"
            f"p{pleito_6}-{uf_lower}-m{mun_5}-z{zona_4}-s{secao_4}-aux.json"
        )

    def build_artifact_url(
        self,
        uf: str,
        municipio_cod: int,
        zona: int,
        secao: int,
        hash_dir: str,
        filename: str,
    ) -> str:
        """Constrói a URL de download de um `.logjez` ou `.bu` individual.

        Args:
            uf: Sigla da UF em 2 caracteres.
            municipio_cod: Código TSE do município.
            zona: Número da zona eleitoral.
            secao: Número da seção eleitoral.
            hash_dir: Identificador de subdiretório oriundo de `hashes[].hash`.
            filename: Nome do arquivo listado em `nmarq[]`.

        Returns:
            URL completa do artefato binário no CDN do TSE.

        Raises:
            Nenhum.
        """
        uf_lower = uf.strip().lower()
        mun_5 = f"{municipio_cod:05d}"
        zona_4 = f"{zona:04d}"
        secao_4 = f"{secao:04d}"
        base = self._settings.cdn_base_url.rstrip("/")
        return (
            f"{base}/ele{self._run_cfg.ano_eleicao}/arquivo-urna/"
            f"{self._run_cfg.pleito_id}/dados/{uf_lower}/{mun_5}/"
            f"{zona_4}/{secao_4}/{hash_dir}/{filename}"
        )

    def _create_managed_client(self) -> httpx.AsyncClient:
        """Cria um `httpx.AsyncClient` com HTTP/2 e cabeçalhos obrigatórios.

        Args:
            Nenhum.

        Returns:
            Cliente assíncrono configurado conforme `specs/01` Seção 2.1.

        Raises:
            Nenhum.
        """
        limits = httpx.Limits(
            max_connections=self._settings.http_max_connections,
            max_keepalive_connections=self._settings.http_max_keepalive_connections,
        )
        return httpx.AsyncClient(
            http2=True,
            limits=limits,
            timeout=httpx.Timeout(self._settings.http_timeout_seconds),
            headers={
                "User-Agent": self._settings.user_agent,
                "Accept-Encoding": "gzip, br",
            },
            follow_redirects=True,
        )

    async def _get_bytes_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> bytes:
        """Executa `GET` com semáforo, Token Bucket, Circuit Breaker e Full Jitter.

        Args:
            client: Cliente HTTP ativo.
            url: URL completa a requisitar.

        Returns:
            Corpo binário da resposta HTTP `200`.

        Raises:
            MissingLogError: Imediatamente em caso de HTTP `404` definitivo.
            HttpExhaustedError: Quando falhas transitórias esgotam retentativas ou
                ocorre erro HTTP não recuperável.
        """
        max_attempts = self._settings.http_max_retries
        last_reason = "Erro desconhecido"

        for attempt in range(1, max_attempts + 1):
            await self._circuit_breaker.before_request()
            await self._rate_limiter.acquire()

            retry_after: str | None = None
            try:
                async with self._semaphore:
                    response = await client.get(url)
            except httpx.HTTPError as exc:
                last_reason = f"{type(exc).__name__}: {exc}"
                await self._circuit_breaker.record_failure()
                if attempt < max_attempts:
                    delay = compute_full_jitter_delay(attempt, rng=self._rng)
                    await self._sleep(delay)
                    continue
                raise HttpExhaustedError(
                    f"Tentativas HTTP esgotadas ({last_reason})",
                    source_uri=url,
                    attempt_count=attempt,
                ) from exc

            status = response.status_code
            if status == 200:
                await self._circuit_breaker.record_success()
                return response.content

            if status == 404:
                await self._circuit_breaker.record_success()
                raise MissingLogError(
                    "Artefato retornou HTTP 404 no CDN do TSE.",
                    source_uri=url,
                    attempt_count=attempt,
                )

            if status in RETRYABLE_STATUS_CODES:
                last_reason = f"HTTP {status}"
                retry_after = response.headers.get("Retry-After")
                await self._circuit_breaker.record_failure()
                if attempt < max_attempts:
                    delay = compute_full_jitter_delay(
                        attempt,
                        retry_after_header=retry_after,
                        rng=self._rng,
                    )
                    await self._sleep(delay)
                    continue
                raise HttpExhaustedError(
                    f"Tentativas HTTP esgotadas após {status}.",
                    source_uri=url,
                    attempt_count=attempt,
                )

            raise HttpExhaustedError(
                f"Resposta HTTP não recuperável: {status}.",
                source_uri=url,
                attempt_count=attempt,
            )

        raise HttpExhaustedError(
            f"Tentativas HTTP esgotadas ({last_reason}).",
            source_uri=url,
            attempt_count=max_attempts,
        )

    async def _fetch_verified_bytes(
        self,
        client: httpx.AsyncClient,
        url: str,
        expected_hash: str | None,
    ) -> bytes:
        """Baixa artefato e valida `SHA-512` com até 2 retentativas de integridade.

        Args:
            client: Cliente HTTP ativo.
            url: URL do artefato binário.
            expected_hash: Hash `SHA-512`/`SHA-256` esperado ou `None`.

        Returns:
            Payload binário íntegro em memória.

        Raises:
            HashMismatchError: Se o digest persistir divergente após 3 downloads.
            MissingLogError: Se o artefato retornar HTTP `404`.
            HttpExhaustedError: Se ocorrer falha de rede persistente.
        """
        max_hash_tries = 3 if expected_hash else 1
        actual_hex = ""
        for _hash_try in range(1, max_hash_tries + 1):
            payload = await self._get_bytes_with_retry(client, url)
            is_valid, actual_hex = verify_artifact_digest(payload, expected_hash)
            if is_valid:
                return payload

        raise HashMismatchError(
            "Divergência persistente de hash criptográfico após re-downloads.",
            source_uri=url,
            sha512_expected=expected_hash,
            sha512_actual=actual_hex,
            attempt_count=max_hash_tries,
        )

    def _parse_cs_sections(
        self,
        cs_bytes: bytes,
        norm_uf: str,
        checkpoint: IngestionCheckpoint | None,
        cs_url: str,
    ) -> list[tuple[MunicipalityTzInfo, int, int, int | None]]:
        """Extrai seções `(tz_info, zona, secao, aggregated_to)` do `-cs.json`.

        Args:
            cs_bytes: Conteúdo JSON bruto do catálogo estadual `-cs.json`.
            norm_uf: Sigla da UF em maiúsculas.
            checkpoint: Checkpoint opcional de seções já processadas com `SUCCESS`.
            cs_url: URL diagnóstica do índice `-cs.json`.

        Returns:
            Lista determinística de seções pendentes para download ou registro.
            O quarto elemento é o número da seção principal agregadora ou `None`.

        Raises:
            CorruptArchiveError: Se o JSON do índice estadual estiver malformado.
            UnknownMunicipalityTimezoneError: Se UF multi-fuso contiver município
                não cadastrado em `dim_municipio_fuso.csv`.
        """
        try:
            root = orjson.loads(cs_bytes)
        except orjson.JSONDecodeError as exc:
            raise CorruptArchiveError(
                f"Índice estadual -cs.json malformado: {exc}",
                source_uri=cs_url,
            ) from exc

        if not isinstance(root, dict):
            raise CorruptArchiveError(
                "Raiz do índice -cs.json não é um objeto JSON.",
                source_uri=cs_url,
            )

        mu_entries: list[dict[str, Any]] = []
        abr_list = root.get("abr")
        if isinstance(abr_list, list):
            for abr_item in abr_list:
                if isinstance(abr_item, dict):
                    sub_mu = abr_item.get("mu")
                    if isinstance(sub_mu, list):
                        mu_entries.extend(m for m in sub_mu if isinstance(m, dict))
        direct_mu = root.get("mu")
        if isinstance(direct_mu, list):
            mu_entries.extend(m for m in direct_mu if isinstance(m, dict))

        mun_filter = frozenset(self._run_cfg.municipios)
        sections: list[tuple[MunicipalityTzInfo, int, int, int | None]] = []
        seen: set[tuple[int, int, int]] = set()

        for mu_obj in mu_entries:
            raw_cd = mu_obj.get("cd")
            if raw_cd is None:
                continue
            mun_cod = int(str(raw_cd).strip())
            if mun_filter and mun_cod not in mun_filter:
                continue

            raw_nm = mu_obj.get("nm")
            mun_name = str(raw_nm).strip() if raw_nm is not None else None
            tz_info = self._tz_catalog.resolve(
                mun_cod,
                norm_uf,
                municipio_nome_fallback=mun_name,
            )

            zon_list = mu_obj.get("zon")
            if not isinstance(zon_list, list):
                continue
            for zon_obj in zon_list:
                if not isinstance(zon_obj, dict) or zon_obj.get("cd") is None:
                    continue
                zona = int(str(zon_obj["cd"]).strip())
                sec_list = zon_obj.get("sec")
                if not isinstance(sec_list, list):
                    continue
                for sec_obj in sec_list:
                    raw_nsp: object = None
                    if isinstance(sec_obj, dict):
                        raw_sec = sec_obj.get("ns") or sec_obj.get("cd")
                        raw_nsp = sec_obj.get("nsp")
                    else:
                        raw_sec = sec_obj
                    if raw_sec is None:
                        continue
                    secao = int(str(raw_sec).strip())
                    key = (mun_cod, zona, secao)
                    if key in seen:
                        continue
                    seen.add(key)
                    if checkpoint is not None and checkpoint.is_completed(
                        mun_cod, zona, secao
                    ):
                        continue
                    aggregated_to: int | None = None
                    if raw_nsp is not None:
                        nsp_int = int(str(raw_nsp).strip())
                        if nsp_int != secao:
                            aggregated_to = nsp_int
                    sections.append((tz_info, zona, secao, aggregated_to))

        sections.sort(key=lambda item: (item[0].municipio_cod_tse, item[1], item[2]))
        return sections

    @staticmethod
    def _extract_aux_targets(
        aux_bytes: bytes,
        aux_url: str,
    ) -> tuple[
        int | None,
        list[tuple[str, str, str | None]],
        list[tuple[str, str, str | None]],
    ]:
        """Interpreta `-aux.json` extraindo aptos, alvos `.logjez` e alvos `.bu`.

        Args:
            aux_bytes: Conteúdo JSON bruto do manifesto `-aux.json`.
            aux_url: URL diagnóstica do manifesto `-aux.json`.

        Returns:
            Tupla `(total_aptos, log_targets, bu_targets)`, onde cada alvo é
            `(hash_dir, filename, expected_sha512)`.

        Raises:
            CorruptArchiveError: Se o JSON do manifesto for inválido.
            MissingLogError: Se nenhum arquivo `.logjez`/`.jez` constar em `hashes[]`.
        """
        try:
            aux_data = orjson.loads(aux_bytes)
        except orjson.JSONDecodeError as exc:
            raise CorruptArchiveError(
                f"Manifesto -aux.json inválido: {exc}",
                source_uri=aux_url,
            ) from exc

        if not isinstance(aux_data, dict):
            raise CorruptArchiveError(
                "Manifesto -aux.json não possui objeto raiz válido.",
                source_uri=aux_url,
            )

        total_aptos: int | None = None
        for aptos_key in ("aptos", "eleitoresAptos", "qa"):
            raw_aptos = aux_data.get(aptos_key)
            if isinstance(raw_aptos, int) and not isinstance(raw_aptos, bool):
                total_aptos = raw_aptos
                break
            if isinstance(raw_aptos, str) and raw_aptos.strip().isdigit():
                total_aptos = int(raw_aptos.strip())
                break

        hashes_arr = aux_data.get("hashes")
        if not isinstance(hashes_arr, list) or not hashes_arr:
            raise MissingLogError(
                "Manifesto -aux.json sem entradas em 'hashes[]'.",
                source_uri=aux_url,
            )

        log_targets: list[tuple[str, str, str | None]] = []
        bu_targets: list[tuple[str, str, str | None]] = []
        seen_files: set[tuple[str, str]] = set()

        for entry in hashes_arr:
            if not isinstance(entry, dict):
                continue
            hash_dir = str(entry.get("hash", "")).strip()
            if not hash_dir:
                continue

            per_file_hashes: dict[str, str] = {}
            for map_key in ("sha512_arquivos", "file_hashes"):
                raw_map = entry.get(map_key)
                if isinstance(raw_map, dict):
                    for fname, fhash in raw_map.items():
                        if isinstance(fname, str) and isinstance(fhash, str):
                            per_file_hashes[fname] = fhash.strip()

            nmarq = entry.get("nmarq") or entry.get("arq")
            if not isinstance(nmarq, list):
                continue

            for file_entry in nmarq:
                filename = ""
                expected_sha: str | None = None
                file_type: str | None = None
                if isinstance(file_entry, str):
                    filename = file_entry.strip()
                    expected_sha = per_file_hashes.get(filename)
                elif isinstance(file_entry, dict):
                    raw_nm = file_entry.get("nm") or file_entry.get("filename")
                    if isinstance(raw_nm, str):
                        filename = raw_nm.strip()
                    raw_sha = file_entry.get("sha512") or file_entry.get("hash")
                    if isinstance(raw_sha, str) and raw_sha.strip():
                        expected_sha = raw_sha.strip()
                    elif filename:
                        expected_sha = per_file_hashes.get(filename)
                    raw_tp = file_entry.get("tp") or file_entry.get("type")
                    if isinstance(raw_tp, str):
                        file_type = raw_tp.strip().lower()

                if not filename or (hash_dir, filename) in seen_files:
                    continue
                seen_files.add((hash_dir, filename))

                lower_name = filename.lower()
                is_log = (
                    file_type in ("log", "logjez")
                    or lower_name.endswith((".logjez", ".jez"))
                    or "-log." in lower_name
                )
                is_bu = (
                    file_type == "bu"
                    or lower_name.endswith((".bu", "-bu.dat"))
                    or (
                        "-bu." in lower_name
                        and not lower_name.endswith((".rdv", ".vsc", ".imgbu"))
                    )
                )
                if is_log:
                    log_targets.append((hash_dir, filename, expected_sha))
                elif is_bu:
                    bu_targets.append((hash_dir, filename, expected_sha))

        if not log_targets:
            raise MissingLogError(
                "Manifesto -aux.json não lista nenhum arquivo .logjez.",
                source_uri=aux_url,
            )

        return total_aptos, log_targets, bu_targets

    async def _fetch_section_bundle(
        self,
        client: httpx.AsyncClient,
        tz_info: MunicipalityTzInfo,
        zona: int,
        secao: int,
    ) -> SectionArtifactBundle | UnprocessedSectionError:
        """Baixa `-aux.json`, todos os `.logjez` e o `.bu` de uma única seção.

        Args:
            client: Cliente HTTP assíncrono compartilhado.
            tz_info: Metadados geográficos do município.
            zona: Número da zona eleitoral.
            secao: Número da seção eleitoral.

        Returns:
            `SectionArtifactBundle` validado ou `UnprocessedSectionError` isolado.

        Raises:
            Nenhum.
        """
        assert self._run_cfg.election_date_iso is not None
        assert self._run_cfg.cutoff_mode is not None

        aux_url = self.build_aux_url(
            tz_info.uf,
            tz_info.municipio_cod_tse,
            zona,
            secao,
        )
        total_aptos: int | None = None
        try:
            aux_bytes = await self._get_bytes_with_retry(client, aux_url)
            total_aptos, log_targets, bu_targets = self._extract_aux_targets(
                aux_bytes,
                aux_url,
            )

            log_payloads: list[LogArtifactPayload] = []
            for hash_dir, filename, expected_sha in log_targets:
                art_url = self.build_artifact_url(
                    tz_info.uf,
                    tz_info.municipio_cod_tse,
                    zona,
                    secao,
                    hash_dir,
                    filename,
                )
                raw_bytes = await self._fetch_verified_bytes(
                    client,
                    art_url,
                    expected_sha,
                )
                log_payloads.append(
                    LogArtifactPayload(
                        filename=filename,
                        raw_bytes=raw_bytes,
                        sha512_expected=expected_sha,
                    )
                )

            bu_bytes: bytes | None = None
            if bu_targets:
                bu_hash_dir, bu_filename, bu_expected_sha = bu_targets[-1]
                bu_url = self.build_artifact_url(
                    tz_info.uf,
                    tz_info.municipio_cod_tse,
                    zona,
                    secao,
                    bu_hash_dir,
                    bu_filename,
                )
                try:
                    bu_bytes = await self._fetch_verified_bytes(
                        client,
                        bu_url,
                        bu_expected_sha,
                    )
                except MissingLogError:
                    bu_bytes = None

            return SectionArtifactBundle(
                ano_eleicao=self._run_cfg.ano_eleicao,
                turno=self._run_cfg.turno,
                pleito_id=self._run_cfg.pleito_id,
                election_date_iso=self._run_cfg.election_date_iso,
                cutoff_mode=self._run_cfg.cutoff_mode.value,
                uf=tz_info.uf,
                municipio_cod=tz_info.municipio_cod_tse,
                municipio_ibge=tz_info.municipio_cod_ibge,
                municipio_nome=tz_info.municipio_nome,
                zona=zona,
                secao=secao,
                fuso_horario_offset_brt=tz_info.fuso_horario_offset_brt,
                total_aptos_manifest=total_aptos,
                log_artifacts=tuple(log_payloads),
                bu_raw_bytes=bu_bytes,
                source_uri=aux_url,
            )
        except SectionAuditError as err:
            return build_ingestion_error(
                self._run_cfg,
                tz_info,
                zona=zona,
                secao=secao,
                err=err,
                total_aptos_manifest=total_aptos,
            )

    async def stream_uf(
        self,
        uf: str,
        checkpoint: IngestionCheckpoint | None = None,
    ) -> AsyncIterator[SectionArtifactBundle | UnprocessedSectionError]:
        """Resolve o índice estadual `-cs.json` e faz download concorrente limitado.

        Args:
            uf: Sigla da Unidade Federativa em 2 letras.
            checkpoint: Conjunto opcional de seções já consolidadas (`SUCCESS`).

        Yields:
            `SectionArtifactBundle` ou `UnprocessedSectionError` à medida que ficam
            prontos, respeitando backpressure de memória.

        Raises:
            MissingLogError: Se o próprio índice estadual `-cs.json` retornar `404`.
            HttpExhaustedError: Se o download do índice estadual falhar.
            CorruptArchiveError: Se o índice estadual contiver JSON inválido.
            UnknownMunicipalityTimezoneError: Se UF multi-fuso apresentar código
                municipal ausente do catálogo.
        """
        norm_uf = uf.strip().upper()
        owns_client = self._external_client is None
        client = self._external_client or self._create_managed_client()

        try:
            cs_url = self.build_cs_url(norm_uf)
            try:
                cs_bytes = await self._get_bytes_with_retry(client, cs_url)
            except MissingLogError as exc:
                raise MissingLogError(
                    f"Índice estadual '{norm_uf}' não encontrado no CDN do TSE "
                    f"(HTTP 404: {cs_url}). Nota: O CDN oficial "
                    "(resultados.tse.jus.br) disponibiliza apenas pleitos recentes "
                    "ativos. Para pleitos anteriores ou consolidados (ex.: 2022), "
                    "utilize '--source zip' para pacotes do Portal de Dados Abertos.",
                    source_uri=cs_url,
                ) from exc
            pending_sections = self._parse_cs_sections(
                cs_bytes,
                norm_uf,
                checkpoint,
                cs_url,
            )
            if not pending_sections:
                return

            regular_sections: list[tuple[MunicipalityTzInfo, int, int]] = []
            aggregated_sections: list[tuple[MunicipalityTzInfo, int, int, int]] = []
            for tz_info, zona, secao, aggregated_to in pending_sections:
                if aggregated_to is not None:
                    aggregated_sections.append((tz_info, zona, secao, aggregated_to))
                else:
                    regular_sections.append((tz_info, zona, secao))

            # 1. Emitir seções agregadas conhecidas imediatamente sem requisições HTTP
            for tz_info, zona, secao, agg_target in aggregated_sections:
                assert self._run_cfg.cutoff_mode is not None
                aux_url = self.build_aux_url(
                    tz_info.uf,
                    tz_info.municipio_cod_tse,
                    zona,
                    secao,
                )
                yield UnprocessedSectionError(
                    ano_eleicao=self._run_cfg.ano_eleicao,
                    turno=self._run_cfg.turno,
                    pleito_id=self._run_cfg.pleito_id,
                    uf=tz_info.uf,
                    municipio_cod=tz_info.municipio_cod_tse,
                    municipio_ibge=tz_info.municipio_cod_ibge,
                    municipio_nome=tz_info.municipio_nome,
                    zona=zona,
                    secao=secao,
                    fuso_horario_offset_brt=tz_info.fuso_horario_offset_brt,
                    cutoff_mode=self._run_cfg.cutoff_mode.value,
                    error_code=ErrorCode.MISSING_LOG.value,
                    error_message=(
                        f"Seção eleitoral agregada na seção principal {agg_target:04d} "
                        "(sem urna física própria no CDN TSE)."
                    ),
                    recorded_at=datetime.now(UTC).replace(tzinfo=None),
                    source_uri=aux_url,
                    attempt_count=0,
                )

            if not regular_sections:
                return

            work_queue: asyncio.Queue[tuple[MunicipalityTzInfo, int, int] | None] = (
                asyncio.Queue()
            )
            for item in regular_sections:
                work_queue.put_nowait(item)

            worker_count = min(
                len(regular_sections),
                self._settings.max_concurrent_requests,
            )
            for _ in range(worker_count):
                work_queue.put_nowait(None)

            max_queue_size = max(2, self._settings.max_concurrent_requests * 2)
            out_queue: asyncio.Queue[
                SectionArtifactBundle | UnprocessedSectionError | None
            ] = asyncio.Queue(maxsize=max_queue_size)

            async def _worker() -> None:
                try:
                    while True:
                        task_item = await work_queue.get()
                        if task_item is None:
                            return
                        tz_info, zona, secao = task_item
                        result = await self._fetch_section_bundle(
                            client,
                            tz_info,
                            zona,
                            secao,
                        )
                        await out_queue.put(result)
                finally:
                    await out_queue.put(None)

            workers = [asyncio.create_task(_worker()) for _ in range(worker_count)]
            finished_workers = 0
            try:
                while finished_workers < worker_count:
                    produced = await out_queue.get()
                    if produced is None:
                        finished_workers += 1
                    else:
                        yield produced
                await asyncio.gather(*workers)
            finally:
                for task in workers:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
        finally:
            if owns_client:
                await client.aclose()
