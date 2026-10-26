"""Primitivas assíncronas de resiliência HTTP (`REQ-ING-02`).

Implementa Rate Limiter *Token Bucket*, *Retry Exponencial com Full Jitter*
(respeitando `Retry-After`) e *Circuit Breaker* para proteção frente a HTTP
`429` e falhas transitórias `5xx`.

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
import time
from enum import StrEnum

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})


class CircuitState(StrEnum):
    """Estados do disjuntor assíncrono de rede (`CircuitBreaker`).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


def compute_full_jitter_delay(
    attempt: int,
    *,
    retry_after_header: str | None = None,
    rng: random.Random | None = None,
) -> float:
    r"""Calcula o atraso de retry exponencial com *Full Jitter* (`specs/01` 2.1).

    Aplica a fórmula canônica $t_k = \text{Uniform}(0, \min(60.0, 0.5 \times 2^k))$
    e respeita `Retry-After` numérico caso o servidor solicite espera maior.

    Args:
        attempt: Índice da tentativa ($k \ge 1$).
        retry_after_header: Valor opcional do cabeçalho HTTP `Retry-After`.
        rng: Gerador pseudoaleatório opcional para testes determinísticos.

    Returns:
        Tempo de espera em segundos (`0.0` a `60.0`).

    Raises:
        Nenhum.
    """
    generator = rng or random
    cap = min(60.0, 0.5 * (2**attempt))
    jitter_delay = generator.uniform(0.0, cap)

    if retry_after_header is not None:
        try:
            server_wait = min(60.0, max(0.0, float(retry_after_header.strip())))
            return max(jitter_delay, server_wait)
        except ValueError:
            pass
    return jitter_delay


class TokenBucketRateLimiter:
    """Limitador assíncrono de taxa sustentada baseado em *Token Bucket*.

    Args:
        rate_per_sec: Taxa máxima sustentada de requisições por segundo.
        burst: Capacidade máxima de rajada inicial do balde.

    Returns:
        Nenhum.

    Raises:
        ValueError: Se `rate_per_sec <= 0`.
    """

    def __init__(
        self,
        rate_per_sec: float,
        *,
        burst: float | None = None,
    ) -> None:
        """Inicializa o balde de tokens com capacidade cheia.

        Args:
            rate_per_sec: Tokens adicionados por segundo (`> 0`).
            burst: Limite máximo de tokens acumulados.

        Returns:
            Nenhum.

        Raises:
            ValueError: Se `rate_per_sec` for menor ou igual a zero.
        """
        if rate_per_sec <= 0.0:
            raise ValueError("rate_per_sec deve ser estritamente positivo.")
        self._rate = rate_per_sec
        self._capacity = burst if burst is not None else max(1.0, rate_per_sec)
        self._tokens = self._capacity
        self._updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Aguarda até que pelo menos 1 token esteja disponível e o consome.

        Args:
            Nenhum.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = max(0.0, now - self._updated_at)
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._updated_at = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            needed = 1.0 - self._tokens
            wait_sec = needed / self._rate
            self._tokens = 0.0
            self._updated_at = now + wait_sec

        await asyncio.sleep(wait_sec)


class CircuitBreaker:
    """Disjuntor assíncrono para contenção de cascatas `429` / `5xx`.

    Args:
        failure_threshold: Falhas consecutivas necessárias para abrir o circuito.
        recovery_timeout_sec: Segundos em estado `OPEN` antes de testar `HALF_OPEN`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    def __init__(
        self,
        failure_threshold: int = 10,
        recovery_timeout_sec: float = 5.0,
    ) -> None:
        """Inicializa o disjuntor fechado (`CLOSED`).

        Args:
            failure_threshold: Limiar de falhas consecutivas (`>= 1`).
            recovery_timeout_sec: Pausa de resfriamento quando aberto (`>= 0`).

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        self._threshold = max(1, failure_threshold)
        self._recovery_sec = max(0.0, recovery_timeout_sec)
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Retorna o estado corrente do disjuntor (`CLOSED`, `OPEN`, `HALF_OPEN`).

        Args:
            Nenhum.

        Returns:
            Valor atual de `CircuitState`.

        Raises:
            Nenhum.
        """
        return self._state

    async def before_request(self) -> None:
        """Aguarda a janela de recuperação caso o circuito esteja `OPEN`.

        Args:
            Nenhum.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        wait_remaining = 0.0
        async with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self._recovery_sec:
                    self._state = CircuitState.HALF_OPEN
                else:
                    wait_remaining = self._recovery_sec - elapsed

        if wait_remaining > 0.0:
            await asyncio.sleep(wait_remaining)
            async with self._lock:
                if self._state == CircuitState.OPEN:
                    self._state = CircuitState.HALF_OPEN

    async def record_success(self) -> None:
        """Zera falhas consecutivas e fecha o circuito após resposta saudável.

        Args:
            Nenhum.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        async with self._lock:
            self._consecutive_failures = 0
            self._state = CircuitState.CLOSED

    async def record_failure(self) -> None:
        """Incrementa falhas consecutivas e abre o circuito ao atingir o limiar.

        Args:
            Nenhum.

        Returns:
            Nenhum.

        Raises:
            Nenhum.
        """
        async with self._lock:
            self._consecutive_failures += 1
            if (
                self._state == CircuitState.HALF_OPEN
                or self._consecutive_failures >= self._threshold
            ):
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
