"""Testes baseados em propriedades (`hypothesis`) da FSM e invariantes (`REQ-QA-01`).

Gera estocasticamente sequências arbitrárias de eventos canônicos, fusos
horários (`-2` a `+1`), modos de corte e regressões de relógio para provar que
100% das execuções respeitam as Invariantes Matemáticas 1 a 5.

Args:
    Nenhum.

Returns:
    Nenhum.

Raises:
    Nenhum.
"""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from pulso_eleitoral.contracts.models import CutoffMode, ParsedSectionMetrics
from pulso_eleitoral.parser.fsm import _evaluate_events_fsm
from pulso_eleitoral.parser.patterns import CanonicalEvent


@given(
    events=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=120_000),
            st.sampled_from(list(CanonicalEvent)),
        ),
        min_size=0,
        max_size=120,
    ),
    offset_brt=st.sampled_from([-2, -1, 0, 1]),
    use_unified_brt=st.booleans(),
    initial_clock_suspect=st.booleans(),
)
@settings(max_examples=200, deadline=None)
def test_fsm_always_preserves_mathematical_invariants_1_to_5(
    events: list[tuple[int, CanonicalEvent]],
    offset_brt: int,
    use_unified_brt: bool,
    initial_clock_suspect: bool,
) -> None:
    """Prova que qualquer sequência arbitrária de eventos satisfaz as invariantes 1..5.

    Args:
        events: Lista arbitrária de `(segundos_locais, CanonicalEvent)`.
        offset_brt: Offset em horas frente a Brasília (`-2`, `-1`, `0`, `+1`).
        use_unified_brt: Flag alternando entre `UNIFIED_BRT` e `LOCAL_TIME`.
        initial_clock_suspect: Flag inicial de suspeita de relógio.

    Returns:
        Nenhum.

    Raises:
        Nenhum.
    """
    fsm_res = _evaluate_events_fsm(
        events,
        midnight_dt=datetime(2022, 10, 2, 0, 0, 0),
        fuso_horario_offset_brt=offset_brt,
        use_unified_brt=use_unified_brt,
        aptos_from_log=400,
        initial_clock_suspect=initial_clock_suspect,
    )
    metrics = ParsedSectionMetrics(
        ano_eleicao=2022,
        turno=1,
        pleito_id=406,
        uf="AM" if offset_brt < 0 else "SP",
        municipio_cod=2550 if offset_brt < 0 else 71072,
        municipio_ibge=None,
        municipio_nome="TESTE",
        zona=1,
        secao=1,
        fuso_horario_offset_brt=offset_brt,
        cutoff_mode=(
            CutoffMode.UNIFIED_BRT.value
            if use_unified_brt
            else CutoffMode.LOCAL_TIME.value
        ),
        qtd_arquivos_log=1,
        total_aptos=fsm_res.aptos_from_log,
        comparecimento_bu=None,
        total_votos=fsm_res.total_votos,
        divergencia_bu_log=None,
        votos_antes_08h=fsm_res.votos_antes_08h,
        votos_ate_17h=fsm_res.votos_ate_17h,
        votos_apos_17h=fsm_res.votos_apos_17h,
        sem_bio_ate_17h=fsm_res.sem_bio_ate_17h,
        sem_bio_apos_17h=fsm_res.sem_bio_apos_17h,
        bio_status_indefinido=fsm_res.bio_status_indefinido,
        tentativas_bio_falhas=fsm_res.tentativas_bio_falhas,
        votos_cancelados_suspensos=fsm_res.votos_cancelados_suspensos,
        qtd_reinicializacoes=fsm_res.qtd_reinicializacoes,
        horario_abertura_brt=fsm_res.horario_abertura_brt,
        horario_primeiro_voto_brt=fsm_res.horario_primeiro_voto_brt,
        horario_ultimo_voto_brt=fsm_res.horario_ultimo_voto_brt,
        horario_encerramento_brt=fsm_res.horario_encerramento_brt,
        relogio_suspeito=fsm_res.relogio_suspeito,
        voto_apos_encerramento=fsm_res.voto_apos_encerramento,
    )
    metrics.validate_invariants()
    assert (
        metrics.sem_bio_ate_17h
        + metrics.sem_bio_apos_17h
        + metrics.bio_status_indefinido
        <= metrics.total_votos
    )
