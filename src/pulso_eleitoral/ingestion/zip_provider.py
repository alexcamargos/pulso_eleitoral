"""Provedor de ingestão em streaming para pacotes ZIP estaduais (`REQ-ING-01`).

Lê pacotes `bu_imgbu_logjez_rdv_vscmr_{ano}_{turno}t_{UF}.zip` do Portal de Dados
Abertos do TSE via diretório central (`ZipFile.infolist()`), extraindo para a RAM
exclusivamente os membros `.logjez` e `.bu` da seção corrente (`<= 8 GB` SLA).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
import zipfile
import zlib
from collections import defaultdict
from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath

import httpx

from pulso_eleitoral.config import ElectionRunConfig, PipelineSettings
from pulso_eleitoral.contracts.exceptions import (
    ContractValidationError,
    CorruptArchiveError,
    HttpExhaustedError,
    MissingLogError,
)
from pulso_eleitoral.contracts.models import (
    IngestionCheckpoint,
    LogArtifactPayload,
    SectionArtifactBundle,
    UnprocessedSectionError,
)
from pulso_eleitoral.ingestion.base import build_ingestion_error
from pulso_eleitoral.ingestion.timezone import TimezoneCatalog

_MEMBER_FILENAME_RE: re.Pattern[str] = re.compile(
    r"^o(?P<pleito>\d{5,6})-(?P<mun>\d{5})(?P<zona>\d{4})(?P<secao>\d{4})"
    r"(?:[-_][A-Za-z0-9]+)*\.(?P<ext>logjez|jez|bu|imgbu|rdv|vscmr)$",
    re.IGNORECASE,
)


class _SectionZipMembers:
    """Agrupador interno de entradas `ZipInfo` pertencentes a uma única seção.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    __slots__ = ("bu_infos", "has_any_artifact", "log_infos")

    def __init__(self) -> None:
        """Inicializa listas vazias de membros `.logjez` e `.bu`.

        Args:
            Nenhum.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self.log_infos: list[zipfile.ZipInfo] = []
        self.bu_infos: list[zipfile.ZipInfo] = []
        self.has_any_artifact: bool = False


class BulkZipArtifactProvider:
    """Estratégia Modo B: leitura seletiva de pacotes ZIP estaduais (`REQ-ING-01`).

    Args:
        run_cfg: Configuração imutável do pleito/turno.
        settings: Configurações operacionais de diretórios e rede.
        tz_catalog: Catálogo validado de fusos horários municipais.
        http_client: Cliente HTTP opcional para download paginado de ZIP remoto.
        allow_remote_download: Permite baixar o ZIP por streaming caso ausente.

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
        allow_remote_download: bool = True,
    ) -> None:
        """Inicializa o provedor de pacotes ZIP estaduais.

        Args:
            run_cfg: Configuração do pleito/turno.
            settings: Configurações operacionais globais.
            tz_catalog: Catálogo de fusos horários por código TSE.
            http_client: Cliente `httpx.AsyncClient` injetado opcionalmente.
            allow_remote_download: Se `True`, baixa pacote remoto quando necessário.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._run_cfg = run_cfg
        self._settings = settings
        self._tz_catalog = tz_catalog
        self._http_client = http_client
        self._allow_remote_download = allow_remote_download

    def build_zip_filename(self, uf: str) -> str:
        """Constrói o nome canônico do pacote estadual no Portal de Dados Abertos.

        Args:
            uf: Sigla da UF em 2 caracteres.

        Returns:
            Nome padrão `bu_imgbu_logjez_rdv_vscmr_{ano}_{turno}t_{UF}.zip`.

        Raises:
            Nenhum.
        """
        norm_uf = uf.strip().upper()
        return (
            f"bu_imgbu_logjez_rdv_vscmr_"
            f"{self._run_cfg.ano_eleicao}_{self._run_cfg.turno}t_{norm_uf}.zip"
        )

    def _find_local_zip(self, uf: str) -> Path | None:
        """Procura o pacote `.zip` estadual nos diretórios locais configurados.

        Args:
            uf: Sigla da UF em 2 caracteres.

        Returns:
            Caminho existente do arquivo `.zip` ou `None` se não encontrado.

        Raises:
            Nenhum.
        """
        filename = self.build_zip_filename(uf)
        candidates: list[Path] = []
        if self._run_cfg.input_dir is not None:
            if (
                self._run_cfg.input_dir.is_file()
                and self._run_cfg.input_dir.suffix.lower() == ".zip"
            ):
                return self._run_cfg.input_dir
            candidates.append(self._run_cfg.input_dir / filename)
            candidates.append(self._run_cfg.input_dir / filename.lower())
        candidates.append(self._settings.data_dir / "raw" / filename)
        for path in candidates:
            if path.is_file():
                return path
        return None

    async def _download_remote_zip_to_temp(self, uf: str) -> Path:
        """Realiza streaming de um pacote `.zip` remoto para disco temporário.

        Nunca armazena o arquivo estadual completo em memória RAM.

        Args:
            uf: Sigla da UF a baixar.

        Returns:
            Caminho do arquivo temporário criado em disco.

        Raises:
            HttpExhaustedError: Se o download remoto falhar por rede ou HTTP status.
        """
        filename = self.build_zip_filename(uf)
        base_url = self._settings.open_data_base_url.rstrip("/")
        url = f"{base_url}/{self._run_cfg.ano_eleicao}/{filename}"

        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(self._settings.http_timeout_seconds),
            headers={
                "User-Agent": self._settings.user_agent,
                "Accept-Encoding": "gzip, br",
            },
            follow_redirects=True,
        )

        with tempfile.NamedTemporaryFile(
            prefix=f"pulso_{uf.lower()}_",
            suffix=".zip",
            delete=False,
        ) as tmp_handle:
            tmp_path = Path(tmp_handle.name)

        try:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise HttpExhaustedError(
                        f"Falha HTTP {response.status_code} ao baixar pacote ZIP.",
                        source_uri=url,
                        attempt_count=1,
                    )
                with tmp_path.open("wb") as out_file:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        out_file.write(chunk)
            return tmp_path
        except httpx.HTTPError as exc:
            tmp_path.unlink(missing_ok=True)
            raise HttpExhaustedError(
                f"Erro de rede ao baixar pacote ZIP estadual: {exc}",
                source_uri=url,
                attempt_count=1,
            ) from exc
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        finally:
            if owns_client:
                await client.aclose()

    async def stream_uf(
        self,
        uf: str,
        checkpoint: IngestionCheckpoint | None = None,
    ) -> AsyncIterator[SectionArtifactBundle | UnprocessedSectionError]:
        """Itera seletivamente sobre o pacote `.zip` de uma UF sem estourar RAM.

        Args:
            uf: Sigla da Unidade Federativa em 2 letras.
            checkpoint: Conjunto opcional de seções já consolidadas (`SUCCESS`).

        Yields:
            `SectionArtifactBundle` ou `UnprocessedSectionError` por seção.

        Raises:
            ContractValidationError: Se o arquivo local exigido não existir ou se o
                diretório central do `.zip` estadual estiver ilegível.
            HttpExhaustedError: Se o download remoto por streaming falhar.
        """
        norm_uf = uf.strip().upper()
        local_zip = self._find_local_zip(norm_uf)
        cleanup_temp = False

        if local_zip is None:
            if not self._allow_remote_download:
                expected = self.build_zip_filename(norm_uf)
                raise ContractValidationError(
                    f"Pacote ZIP estadual ausente localmente para {norm_uf}: {expected}"
                )
            zip_path = await self._download_remote_zip_to_temp(norm_uf)
            cleanup_temp = True
        else:
            zip_path = local_zip

        try:
            async for item in self._iter_zip_archive(zip_path, norm_uf, checkpoint):
                yield item
        finally:
            if cleanup_temp:
                zip_path.unlink(missing_ok=True)

    async def _iter_zip_archive(
        self,
        zip_path: Path,
        norm_uf: str,
        checkpoint: IngestionCheckpoint | None,
    ) -> AsyncIterator[SectionArtifactBundle | UnprocessedSectionError]:
        """Indexa `infolist()` e extrai apenas `.logjez` e `.bu` seção a seção.

        Args:
            zip_path: Caminho físico do pacote `.zip` estadual.
            norm_uf: Sigla da UF normalizada em maiúsculas.
            checkpoint: Checkpoint opcional para salto $O(1)$ de seções concluídas.

        Yields:
            `SectionArtifactBundle` ou `UnprocessedSectionError`.

        Raises:
            ContractValidationError: Se o container `.zip` estadual não puder abrir.
        """
        assert self._run_cfg.election_date_iso is not None
        assert self._run_cfg.cutoff_mode is not None

        mun_filter = frozenset(self._run_cfg.municipios)

        try:
            zf = zipfile.ZipFile(zip_path, mode="r")
        except (zipfile.BadZipFile, OSError) as exc:
            raise ContractValidationError(
                f"Pacote ZIP estadual inválido ou corrompido ({zip_path}): {exc}"
            ) from exc

        with zf:
            grouped: dict[tuple[int, int, int], _SectionZipMembers] = defaultdict(
                _SectionZipMembers
            )
            for info in zf.infolist():
                if info.is_dir():
                    continue
                basename = PurePosixPath(info.filename).name
                match = _MEMBER_FILENAME_RE.match(basename)
                if match is None:
                    continue

                pleito_num = int(match.group("pleito"))
                if pleito_num != self._run_cfg.pleito_id:
                    continue

                mun_cod = int(match.group("mun"))
                if mun_filter and mun_cod not in mun_filter:
                    continue

                zona = int(match.group("zona"))
                secao = int(match.group("secao"))
                if checkpoint is not None and checkpoint.is_completed(
                    mun_cod, zona, secao
                ):
                    continue

                ext = match.group("ext").lower()
                bucket = grouped[(mun_cod, zona, secao)]
                bucket.has_any_artifact = True
                if ext in ("logjez", "jez"):
                    bucket.log_infos.append(info)
                elif ext == "bu":
                    bucket.bu_infos.append(info)

            for idx, (section_key, members) in enumerate(sorted(grouped.items())):
                if idx > 0 and idx % 64 == 0:
                    await asyncio.sleep(0)

                mun_cod, zona, secao = section_key
                tz_info = self._tz_catalog.resolve(mun_cod, norm_uf)
                section_uri = f"{zip_path.name}#m{mun_cod:05d}-z{zona:04d}-s{secao:04d}"

                if not members.log_infos:
                    yield build_ingestion_error(
                        self._run_cfg,
                        tz_info,
                        zona=zona,
                        secao=secao,
                        err=MissingLogError(
                            "Seção presente no ZIP estadual sem arquivo .logjez.",
                            source_uri=section_uri,
                        ),
                    )
                    continue

                try:
                    sorted_logs = sorted(
                        members.log_infos,
                        key=lambda item: PurePosixPath(item.filename).name,
                    )
                    log_payloads = tuple(
                        LogArtifactPayload(
                            filename=PurePosixPath(info.filename).name,
                            raw_bytes=zf.read(info),
                            sha512_expected=None,
                        )
                        for info in sorted_logs
                    )
                    bu_bytes: bytes | None = None
                    if members.bu_infos:
                        sorted_bus = sorted(
                            members.bu_infos,
                            key=lambda item: PurePosixPath(item.filename).name,
                        )
                        bu_bytes = zf.read(sorted_bus[-1])
                except (
                    zipfile.BadZipFile,
                    zlib.error,
                    EOFError,
                    OSError,
                ) as exc:
                    yield build_ingestion_error(
                        self._run_cfg,
                        tz_info,
                        zona=zona,
                        secao=secao,
                        err=CorruptArchiveError(
                            f"Falha de CRC/descompressão no pacote estadual: {exc}",
                            source_uri=section_uri,
                        ),
                    )
                    continue

                yield SectionArtifactBundle(
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
                    total_aptos_manifest=None,
                    log_artifacts=log_payloads,
                    bu_raw_bytes=bu_bytes,
                    source_uri=section_uri,
                )
