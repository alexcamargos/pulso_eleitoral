"""Máquina de Estados Finita (FSM) determinística sobre `logd.dat` (`REQ-PAR-02`).

Executa pré-filtragem em nível de `bytes`, aritmética direta de timestamps sem
`datetime.strptime` no loop crítico, conversão exata de fuso horário para BRT e
transições de estado imunes a vazamento entre eleitores (`FX-01`..`FX-09`).

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from pulso_eleitoral.contracts.exceptions import LogParseError
from pulso_eleitoral.contracts.models import CutoffMode
from pulso_eleitoral.parser.patterns import CanonicalEvent, LogPatternProfile

SECONDS_07H: int = 7 * 3600
SECONDS_08H: int = 8 * 3600
SECONDS_17H: int = 17 * 3600
SECONDS_PER_DAY: int = 86_400
CLOCK_REGRESSION_TOLERANCE_SEC: int = 60


class VoterState(StrEnum):
    """Estados canônicos da FSM da seção eleitoral (`specs/02` Seção 4).

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    PRE_OPEN = "PRE_OPEN"
    IDLE_READY = "IDLE_READY"
    IDENTIFYING = "IDENTIFYING"
    IN_CABIN = "IN_CABIN"
    CLOSED = "CLOSED"


class BioMode(StrEnum):
    """Estado transitório do modo de habilitação do eleitor em atendimento.

    Args:
        Nenhum.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    UNKNOWN = "UNKNOWN"
    BIOMETRIC = "BIOMETRIC"
    MANUAL = "MANUAL"


@dataclass(slots=True, frozen=True)
class FsmExecutionResult:
    """Resultado bruto consolidado pela FSM antes da reconciliação com `.bu`.

    Args:
        aptos_from_log: Eleitores aptos identificados no cabeçalho do `logd.dat`.
        total_votos: Votos confirmados pela urna no dia oficial.
        votos_antes_08h: Votos confirmados antes das `08:00:00` no referencial `ts_ref`.
        votos_ate_17h: Votos na janela `< 17:00:00` no referencial `ts_ref`.
        votos_apos_17h: Votos na janela `>= 17:00:00` no referencial `ts_ref`.
        sem_bio_ate_17h: Votos manuais/biográficos `< 17:00:00`.
        sem_bio_apos_17h: Votos manuais/biográficos `>= 17:00:00`.
        bio_status_indefinido: Votos confirmados sem evento `BIO_*` prévio.
        tentativas_bio_falhas: Total de falhas de digital registradas.
        votos_cancelados_suspensos: Total de cancelamentos/suspensões pelo mesário.
        qtd_reinicializacoes: Reinicializações durante o expediente.
        horario_abertura_brt: Timestamp em BRT da abertura da seção.
        horario_primeiro_voto_brt: Menor timestamp em BRT de voto confirmado.
        horario_ultimo_voto_brt: Maior timestamp em BRT de voto confirmado.
        horario_encerramento_brt: Timestamp em BRT de encerramento da seção.
        relogio_suspeito: Flag de anomalia temporal/RTC.
        voto_apos_encerramento: Flag de voto confirmado após `SECTION_CLOSED`.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """

    aptos_from_log: int | None
    total_votos: int
    votos_antes_08h: int
    votos_ate_17h: int
    votos_apos_17h: int
    sem_bio_ate_17h: int
    sem_bio_apos_17h: int
    bio_status_indefinido: int
    tentativas_bio_falhas: int
    votos_cancelados_suspensos: int
    qtd_reinicializacoes: int
    horario_abertura_brt: datetime | None
    horario_primeiro_voto_brt: datetime | None
    horario_ultimo_voto_brt: datetime | None
    horario_encerramento_brt: datetime | None
    relogio_suspeito: bool
    voto_apos_encerramento: bool


def _parse_hhmmss_bytes(line: bytes) -> int | None:
    """Converte fatia ASCII `HH:MM:SS` (`line[11:19]`) diretamente em segundos.

    Args:
        line: Linha bruta em `bytes` com pelo menos 19 caracteres.

    Returns:
        Segundos desde `00:00:00` (`0..86399`) ou `None` se formato inválido.

    Raises:
        Nenhum.
    """
    if line[13] != 58 or line[16] != 58:
        return None
    b11, b12, b14, b15, b17, b18 = (
        line[11] - 48,
        line[12] - 48,
        line[14] - 48,
        line[15] - 48,
        line[17] - 48,
        line[18] - 48,
    )
    if (
        not (0 <= b11 <= 9 and 0 <= b12 <= 9)
        or not (0 <= b14 <= 9 and 0 <= b15 <= 9)
        or not (0 <= b17 <= 9 and 0 <= b18 <= 9)
    ):
        return None
    hh = b11 * 10 + b12
    mm = b14 * 10 + b15
    ss = b17 * 10 + b18
    if hh > 23 or mm > 59 or ss > 59:
        return None
    return hh * 3600 + mm * 60 + ss


def run_log_fsm(
    lines: list[bytes],
    *,
    election_date_iso: str,
    fuso_horario_offset_brt: int,
    cutoff_mode: str,
    profile: LogPatternProfile,
) -> FsmExecutionResult:
    """Executa a Máquina de Estados Finita sobre as linhas em `bytes` da seção.

    Args:
        lines: Lista de linhas brutas em `bytes` (`ISO-8859-1`) do `logd.dat`.
        election_date_iso: Data oficial do turno (`YYYY-MM-DD`).
        fuso_horario_offset_brt: Offset em horas vs Brasília (`-2`, `-1`, `0`, `+1`).
        cutoff_mode: `"UNIFIED_BRT"` ou `"LOCAL_TIME"`.
        profile: Perfil pré-compilado de expressões regulares.

    Returns:
        `FsmExecutionResult` com todos os contadores e timestamps normalizados em BRT.

    Raises:
        LogParseError: Se `election_date_iso` for inválida ou sem linhas TSV válidas.
    """
    try:
        election_day = date.fromisoformat(election_date_iso)
    except ValueError as exc:
        raise LogParseError(
            f"Data de eleição inválida '{election_date_iso}': {exc}"
        ) from exc

    next_day = election_day + timedelta(days=1)
    day_d_bytes = election_day.strftime("%d/%m/%Y").encode("ascii")
    day_d1_bytes = next_day.strftime("%d/%m/%Y").encode("ascii")
    midnight_dt = datetime(
        election_day.year,
        election_day.month,
        election_day.day,
        0,
        0,
        0,
    )

    aptos_from_log: int | None = None
    relogio_suspeito = False
    last_vota_sec_by_ue: dict[bytes, int] = {}
    parsed_events: list[tuple[int, CanonicalEvent]] = []
    valid_tsv_seen = False
    app_tokens = profile.vota_app_tokens_bytes
    primary_tok = app_tokens[0] if app_tokens else b"\tVOTA\t"
    extra_tokens = app_tokens[1:]
    aptos_re = profile.aptos_pattern
    classify_fn = profile.classify_message

    for line in lines:
        if len(line) < 25 or line[2] != 47 or line[5] != 47 or line[10] != 32:
            continue

        date_slice = line[:10]
        if date_slice == day_d_bytes:
            day_offset = 0
        elif date_slice == day_d1_bytes:
            day_offset = SECONDS_PER_DAY
        else:
            valid_tsv_seen = True
            if (
                aptos_from_log is None
                and aptos_re is not None
                and (b"aptos" in line or b"Aptos" in line or b"APTOS" in line)
            ):
                cols_pre = line.split(b"\t")
                if len(cols_pre) >= 6:
                    m_pre = aptos_re.search(cols_pre[4].decode("latin-1"))
                    if m_pre is not None:
                        aptos_from_log = int(m_pre.group(1))
            continue

        valid_tsv_seen = True
        if primary_tok not in line and not (
            extra_tokens and any(tok in line for tok in extra_tokens)
        ):
            continue

        cols = line.split(b"\t")
        if len(cols) < 6:
            continue

        intra_day_sec = _parse_hhmmss_bytes(line)
        if intra_day_sec is None:
            continue
        local_sec = day_offset + intra_day_sec

        if cols[3] == b"VOTA":
            ue_id = cols[2]
            prev_sec = last_vota_sec_by_ue.get(ue_id)
            if (
                prev_sec is not None
                and (prev_sec - local_sec) > CLOCK_REGRESSION_TOLERANCE_SEC
            ):
                relogio_suspeito = True
            last_vota_sec_by_ue[ue_id] = local_sec

        msg_text = cols[4].decode("latin-1")
        if (
            aptos_from_log is None
            and aptos_re is not None
            and (b"aptos" in cols[4] or b"Aptos" in cols[4] or b"APTOS" in cols[4])
        ):
            m_aptos = aptos_re.search(msg_text)
            if m_aptos is not None:
                aptos_from_log = int(m_aptos.group(1))

        ev = classify_fn(msg_text)
        if ev is not None:
            parsed_events.append((local_sec, ev))

    if not valid_tsv_seen:
        raise LogParseError("Arquivo logd.dat sem registros TSV válidos de 6 colunas.")

    return _evaluate_events_fsm(
        parsed_events,
        midnight_dt=midnight_dt,
        fuso_horario_offset_brt=fuso_horario_offset_brt,
        use_unified_brt=(cutoff_mode == CutoffMode.UNIFIED_BRT.value),
        aptos_from_log=aptos_from_log,
        initial_clock_suspect=relogio_suspeito,
    )


def _evaluate_events_fsm(
    events: list[tuple[int, CanonicalEvent]],
    *,
    midnight_dt: datetime,
    fuso_horario_offset_brt: int,
    use_unified_brt: bool,
    aptos_from_log: int | None,
    initial_clock_suspect: bool,
) -> FsmExecutionResult:
    """Aplica as transições determinísticas da FSM sobre os eventos classificados.

    Args:
        events: Sequência de `(local_sec, CanonicalEvent)` nos dias `D` e `D+1`.
        midnight_dt: Meia-noite (`00:00:00`) do dia oficial `D`.
        fuso_horario_offset_brt: Offset em horas frente a Brasília.
        use_unified_brt: `True` para `UNIFIED_BRT`, `False` para `LOCAL_TIME`.
        aptos_from_log: Valor de eleitores aptos capturado no cabeçalho, se houver.
        initial_clock_suspect: Estado inicial de `relogio_suspeito` por regressão RTC.

    Returns:
        `FsmExecutionResult` consolidado e aderente às invariantes 1..5.

    Raises:
        Nenhum.
    """
    offset_sec = fuso_horario_offset_brt * 3600
    has_explicit_open = any(
        ev == CanonicalEvent.VOTING_OPENED and lsec < SECONDS_PER_DAY
        for lsec, ev in events
    )

    state = VoterState.PRE_OPEN
    bio_mode = BioMode.UNKNOWN

    total_votos = 0
    votos_antes_08h = 0
    votos_ate_17h = 0
    votos_apos_17h = 0
    sem_bio_ate_17h = 0
    sem_bio_apos_17h = 0
    bio_status_indefinido = 0
    tentativas_bio_falhas = 0
    votos_cancelados_suspensos = 0
    qtd_reinicializacoes = 0

    abertura_brt_sec: int | None = None
    min_vote_brt_sec: int | None = None
    max_vote_brt_sec: int | None = None
    encerramento_brt_sec: int | None = None
    relogio_suspeito = initial_clock_suspect
    voto_apos_encerramento = False

    for local_sec, ev in events:
        brt_sec = local_sec - offset_sec
        ref_sec = brt_sec if use_unified_brt else local_sec

        if state == VoterState.PRE_OPEN:
            if ev == CanonicalEvent.VOTING_OPENED and local_sec < SECONDS_PER_DAY:
                state = VoterState.IDLE_READY
                bio_mode = BioMode.UNKNOWN
                if abertura_brt_sec is None:
                    abertura_brt_sec = brt_sec
                    if ref_sec < SECONDS_07H:
                        relogio_suspeito = True
            elif (
                not has_explicit_open
                and ev == CanonicalEvent.VOTER_SESSION_START
                and local_sec < SECONDS_PER_DAY
            ):
                # Fallback para log truncado no inicio do expediente (specs/02 4.1)
                state = VoterState.IDENTIFYING
                bio_mode = BioMode.UNKNOWN
            continue

        if ev == CanonicalEvent.VOTING_OPENED:
            if abertura_brt_sec is None:
                abertura_brt_sec = brt_sec
                if ref_sec < SECONDS_07H:
                    relogio_suspeito = True
            bio_mode = BioMode.UNKNOWN
            if state != VoterState.CLOSED:
                state = VoterState.IDLE_READY

        elif ev == CanonicalEvent.VOTER_SESSION_START:
            bio_mode = BioMode.UNKNOWN
            if state != VoterState.CLOSED:
                state = VoterState.IDENTIFYING

        elif ev == CanonicalEvent.BIO_FAIL:
            if state in (VoterState.IDLE_READY, VoterState.IDENTIFYING):
                tentativas_bio_falhas += 1
                state = VoterState.IDENTIFYING

        elif ev == CanonicalEvent.BIO_SUCCESS:
            if state != VoterState.CLOSED:
                bio_mode = BioMode.BIOMETRIC
                if state == VoterState.IDLE_READY:
                    state = VoterState.IDENTIFYING

        elif ev == CanonicalEvent.BIO_BYPASS:
            if state != VoterState.CLOSED:
                bio_mode = BioMode.MANUAL
                if state == VoterState.IDLE_READY:
                    state = VoterState.IDENTIFYING

        elif ev == CanonicalEvent.VOTER_ENABLED:
            if state in (VoterState.IDLE_READY, VoterState.IDENTIFYING):
                state = VoterState.IN_CABIN

        elif ev == CanonicalEvent.VOTER_ABORTED:
            if state in (VoterState.IDENTIFYING, VoterState.IN_CABIN):
                votos_cancelados_suspensos += 1
                state = VoterState.IDLE_READY
            bio_mode = BioMode.UNKNOWN

        elif ev == CanonicalEvent.SYSTEM_REBOOT:
            if state != VoterState.CLOSED:
                qtd_reinicializacoes += 1
                state = VoterState.IDLE_READY
            bio_mode = BioMode.UNKNOWN

        elif ev == CanonicalEvent.SECTION_CLOSED:
            encerramento_brt_sec = brt_sec
            bio_mode = BioMode.UNKNOWN
            state = VoterState.CLOSED

        elif ev == CanonicalEvent.VOTE_CONFIRMED:
            if state == VoterState.CLOSED:
                voto_apos_encerramento = True
            total_votos += 1
            if ref_sec < SECONDS_08H:
                votos_antes_08h += 1
                relogio_suspeito = True

            if ref_sec < SECONDS_17H:
                votos_ate_17h += 1
                if bio_mode == BioMode.MANUAL:
                    sem_bio_ate_17h += 1
                elif bio_mode == BioMode.UNKNOWN:
                    bio_status_indefinido += 1
            else:
                votos_apos_17h += 1
                if bio_mode == BioMode.MANUAL:
                    sem_bio_apos_17h += 1
                elif bio_mode == BioMode.UNKNOWN:
                    bio_status_indefinido += 1

            if min_vote_brt_sec is None or brt_sec < min_vote_brt_sec:
                min_vote_brt_sec = brt_sec
            if max_vote_brt_sec is None or brt_sec > max_vote_brt_sec:
                max_vote_brt_sec = brt_sec

            bio_mode = BioMode.UNKNOWN
            if state != VoterState.CLOSED:
                state = VoterState.IDLE_READY

    def _to_dt(sec_val: int | None) -> datetime | None:
        return midnight_dt + timedelta(seconds=sec_val) if sec_val is not None else None

    return FsmExecutionResult(
        aptos_from_log=aptos_from_log,
        total_votos=total_votos,
        votos_antes_08h=votos_antes_08h,
        votos_ate_17h=votos_ate_17h,
        votos_apos_17h=votos_apos_17h,
        sem_bio_ate_17h=sem_bio_ate_17h,
        sem_bio_apos_17h=sem_bio_apos_17h,
        bio_status_indefinido=bio_status_indefinido,
        tentativas_bio_falhas=tentativas_bio_falhas,
        votos_cancelados_suspensos=votos_cancelados_suspensos,
        qtd_reinicializacoes=qtd_reinicializacoes,
        horario_abertura_brt=_to_dt(abertura_brt_sec),
        horario_primeiro_voto_brt=_to_dt(min_vote_brt_sec),
        horario_ultimo_voto_brt=_to_dt(max_vote_brt_sec),
        horario_encerramento_brt=_to_dt(encerramento_brt_sec),
        relogio_suspeito=relogio_suspeito,
        voto_apos_encerramento=voto_apos_encerramento,
    )
