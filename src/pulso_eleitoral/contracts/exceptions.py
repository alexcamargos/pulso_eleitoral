"""Hierarquia de exceções e códigos canônicos de auditoria do Pulso Eleitoral.

Implementa os códigos de erro estruturados exigidos por `REQ-ING-02`,
`REQ-PAR-01`..`03`, `REQ-ANA-01` e pela governança de resiliência (`FX-10`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Códigos canônicos de falha por seção eleitoral (`unprocessed_sections`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    MISSING_LOG = "MISSING_LOG"
    CORRUPT_ARCHIVE = "CORRUPT_ARCHIVE"
    HASH_MISMATCH = "HASH_MISMATCH"
    PARSE_ERROR = "PARSE_ERROR"
    HTTP_EXHAUSTED = "HTTP_EXHAUSTED"


class ProcessingStatus(StrEnum):
    """Estados possíveis da coluna `status_processamento` em `raw_section_metrics`.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    SUCCESS = "SUCCESS"
    MISSING_LOG = "MISSING_LOG"
    CORRUPT_ARCHIVE = "CORRUPT_ARCHIVE"
    HASH_MISMATCH = "HASH_MISMATCH"
    PARSE_ERROR = "PARSE_ERROR"
    HTTP_EXHAUSTED = "HTTP_EXHAUSTED"


class PulsoEleitoralError(Exception):
    """Exceção base da plataforma Pulso Eleitoral.

    Args:
        message: Mensagem descritiva do erro técnico ou de domínio.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(self, message: str) -> None:
        """Inicializa a exceção base com mensagem descritiva.

        Args:
            message: Mensagem descritiva do erro.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        super().__init__(message)
        self.message = message


class SectionAuditError(PulsoEleitoralError):
    """Exceção recuperável isolada a uma seção eleitoral para registro em auditoria.

    Jamais deve abortar o processamento em lote; é convertida em registro na
    tabela `unprocessed_sections` e linha espelho em `raw_section_metrics`.

    Args:
        error_code: Código canônico da falha (`ErrorCode`).
        message: Descrição diagnóstica truncável a 500 caracteres.
        source_uri: URI ou caminho do artefato de origem, quando aplicável.
        sha512_expected: Hash SHA-512 esperado no manifesto `-aux.json`.
        sha512_actual: Hash SHA-512 efetivamente calculado sobre o payload.
        attempt_count: Número de tentativas realizadas antes da falha definitiva.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        *,
        source_uri: str | None = None,
        sha512_expected: str | None = None,
        sha512_actual: str | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Inicializa erro auditável de seção com metadados diagnósticos.

        Args:
            error_code: Código canônico da falha (`ErrorCode`).
            message: Descrição diagnóstica do problema encontrado.
            source_uri: URI ou caminho do artefato inspecionado.
            sha512_expected: Hash SHA-512 declarado pelo TSE.
            sha512_actual: Hash SHA-512 obtido na leitura.
            attempt_count: Quantidade de tentativas efetuadas.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        super().__init__(message)
        self.error_code = error_code
        self.source_uri = source_uri
        self.sha512_expected = sha512_expected
        self.sha512_actual = sha512_actual
        self.attempt_count = attempt_count


class MissingLogError(SectionAuditError):
    """Indica ausência de arquivo `.logjez` ou `logd.dat` para a seção (`MISSING_LOG`).

    Args:
        message: Detalhe diagnóstico da ausência do log.
        source_uri: URI ou pacote onde o log era esperado.
        attempt_count: Total de tentativas efetuadas.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        message: str,
        *,
        source_uri: str | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Inicializa erro de log ausente.

        Args:
            message: Detalhe diagnóstico da ausência do log.
            source_uri: URI ou pacote onde o log era esperado.
            attempt_count: Total de tentativas efetuadas.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        super().__init__(
            ErrorCode.MISSING_LOG,
            message,
            source_uri=source_uri,
            attempt_count=attempt_count,
        )


class CorruptArchiveError(SectionAuditError):
    """Indica pacote `.logjez` truncado ou com magic bytes inválidos (`FX-10`).

    Args:
        message: Detalhe diagnóstico da corrupção binária.
        source_uri: URI ou nome do arquivo corrompido.
        attempt_count: Total de tentativas efetuadas.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        message: str,
        *,
        source_uri: str | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Inicializa erro de pacote compactado corrompido.

        Args:
            message: Detalhe diagnóstico da corrupção binária.
            source_uri: URI ou nome do arquivo corrompido.
            attempt_count: Total de tentativas efetuadas.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        super().__init__(
            ErrorCode.CORRUPT_ARCHIVE,
            message,
            source_uri=source_uri,
            attempt_count=attempt_count,
        )


class HashMismatchError(SectionAuditError):
    """Indica divergência de integridade `SHA-512` frente ao manifesto (`FX-10`).

    Args:
        message: Detalhe diagnóstico da divergência criptográfica.
        source_uri: URI do artefato transferido.
        sha512_expected: Hash SHA-512 esperado segundo o manifesto.
        sha512_actual: Hash SHA-512 aferido nos bytes recebidos.
        attempt_count: Total de tentativas realizadas (incluindo retentativas).

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        message: str,
        *,
        source_uri: str | None = None,
        sha512_expected: str | None = None,
        sha512_actual: str | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Inicializa erro de divergência de hash criptográfico.

        Args:
            message: Detalhe diagnóstico da divergência criptográfica.
            source_uri: URI do artefato transferido.
            sha512_expected: Hash SHA-512 esperado segundo o manifesto.
            sha512_actual: Hash SHA-512 aferido nos bytes recebidos.
            attempt_count: Total de tentativas realizadas.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        super().__init__(
            ErrorCode.HASH_MISMATCH,
            message,
            source_uri=source_uri,
            sha512_expected=sha512_expected,
            sha512_actual=sha512_actual,
            attempt_count=attempt_count,
        )


class LogParseError(SectionAuditError):
    """Indica falha estrutural irrecuperável durante o parsing do `logd.dat`.

    Args:
        message: Detalhe diagnóstico do erro gramatical ou semântico.
        source_uri: Identificador do arquivo onde ocorreu o erro.
        attempt_count: Total de tentativas efetuadas.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        message: str,
        *,
        source_uri: str | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Inicializa erro estrutural de parsing do log.

        Args:
            message: Detalhe diagnóstico do erro gramatical ou semântico.
            source_uri: Identificador do arquivo onde ocorreu o erro.
            attempt_count: Total de tentativas efetuadas.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        super().__init__(
            ErrorCode.PARSE_ERROR,
            message,
            source_uri=source_uri,
            attempt_count=attempt_count,
        )


class HttpExhaustedError(SectionAuditError):
    """Indica esgotamento de retentativas HTTP/rede para obter a seção.

    Args:
        message: Detalhe do último erro HTTP ou timeout observado.
        source_uri: URL alvo da requisição esgotada.
        attempt_count: Quantidade total de tentativas disparadas.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        message: str,
        *,
        source_uri: str | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Inicializa erro de esgotamento de retentativas HTTP.

        Args:
            message: Detalhe do último erro HTTP ou timeout observado.
            source_uri: URL alvo da requisição esgotada.
            attempt_count: Quantidade total de tentativas disparadas.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        super().__init__(
            ErrorCode.HTTP_EXHAUSTED,
            message,
            source_uri=source_uri,
            attempt_count=attempt_count,
        )


class UnknownMunicipalityTimezoneError(PulsoEleitoralError):
    """Erro crítico disparado quando município de UF multi-fuso (`AM`/`PE`) é omitido.

    Cumpre a regra Fail-Fast de `REQ-ING-03` (`specs/01-ingestion-and-sources.md`),
    proibindo inferência silenciosa de fuso horário em estados com múltiplos fusos.

    Args:
        uf: Sigla da Unidade Federativa (ex.: `AM` ou `PE`).
        municipio_cod: Código TSE de 5 dígitos ausente do catálogo.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(self, uf: str, municipio_cod: int) -> None:
        """Inicializa erro Fail-Fast de município sem fuso cadastrado.

        Args:
            uf: Sigla da Unidade Federativa (`AM` ou `PE`).
            municipio_cod: Código TSE de 5 dígitos não localizado.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self.uf = uf.upper()
        self.municipio_cod = municipio_cod
        super().__init__(
            f"Município TSE {municipio_cod:05d} na UF multi-fuso '{self.uf}' "
            "não existe em resources/dim_municipio_fuso.csv. Atualize o catálogo "
            "antes de consolidar o lote."
        )


class InvariantViolationError(PulsoEleitoralError):
    """Erro crítico disparado quando qualquer invariante matemática (1..6) é violada.

    Args:
        message: Descrição exata da invariante violada e chaves afetadas.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """


class ContractValidationError(PulsoEleitoralError):
    """Erro crítico disparado em violações de contrato de exportação ou orçamento SLA.

    Args:
        message: Detalhe técnico da violação de schema ou tamanho máximo.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
