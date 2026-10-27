"""Testes unitários para os componentes visuais do dashboard.

Valida a sanitização HTML via clean_html e a invocação dos componentes
principais de visualização no padrão Margem Eleitoral.
"""

from __future__ import annotations

import pandas as pd
from pytest_mock import MockerFixture

from pulso_eleitoral.dashboard.components.executive_story_cards import (
    render_executive_story_cards,
)
from pulso_eleitoral.dashboard.components.geography_tab import (
    render_geography_tab,
)
from pulso_eleitoral.dashboard.components.integrity_tab import (
    render_integrity_tab,
)
from pulso_eleitoral.dashboard.components.timeline_tab import (
    render_timeline_tab,
)
from pulso_eleitoral.dashboard.components.verdict_tab import (
    render_verdict_tab,
)
from pulso_eleitoral.dashboard.styles import apply_custom_styles, clean_html


def test_clean_html_strips_indents_and_comments() -> None:
    """Verifica se clean_html remove recuos e quebras para prevenir indent blocks."""
    raw_html = """
    <div class="test">
        <!-- Comentário ignorado -->
        <span>Conteúdo</span>
    </div>
    """
    cleaned = clean_html(raw_html)
    assert "\n" not in cleaned
    assert "<!--" not in cleaned
    assert cleaned == '<div class="test"><span>Conteúdo</span></div>'


def test_apply_custom_styles(mocker: MockerFixture) -> None:
    """Verifica se apply_custom_styles injeta o CSS no Streamlit via st.html."""
    mock_html = mocker.patch("streamlit.html")
    apply_custom_styles()
    mock_html.assert_called_once()


def test_render_executive_story_cards(mocker: MockerFixture) -> None:
    """Verifica a renderização dos cartões executivos da hero section."""
    mocker.patch("streamlit.html")
    mock_col = mocker.MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_col, mock_col, mock_col])

    kpis = {
        "total_votos_brasil": 127635809,
        "votos_pos_17h": 35972,
        "horario_ultimo_voto": "19:06:21",
        "local_ultimo_voto": "São Paulo / SP",
        "votos_h2": 3045,
        "pct_h2": 8.5,
        "pct_fila": 82.7,
        "votos_fila": 29738,
        "secoes_pos_17h": 30004,
        "total_secoes_analisadas": 497640,
    }
    render_executive_story_cards(kpis)


def test_render_timeline_tab(mocker: MockerFixture) -> None:
    """Verifica a renderização da aba de série temporal."""
    mocker.patch("streamlit.html")
    mocker.patch("streamlit.plotly_chart")
    mock_col = mocker.MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_col, mock_col, mock_col])

    df_timeline = pd.DataFrame(
        [
            {
                "minuto": "17:00",
                "votos": 12607,
                "pct_acumulado": 35.0,
                "fase": "1. Fila Inicial (Absorção Rápida)",
            },
            {
                "minuto": "18:00",
                "votos": 170,
                "pct_acumulado": 92.0,
                "fase": "3. Platô Atípico da Extensão",
            },
        ]
    )
    render_timeline_tab(df_timeline)


def test_render_geography_tab(mocker: MockerFixture) -> None:
    """Verifica a renderização da aba de análise geoespacial."""
    mocker.patch("streamlit.html")
    mocker.patch("streamlit.select_slider", return_value="19:06 (Janela Completa)")
    mocker.patch("streamlit.text_input", return_value="")
    mocker.patch("streamlit.pydeck_chart")
    mocker.patch("streamlit.caption")
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.plotly_chart")
    mock_col = mocker.MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_col, mock_col])

    df_map = pd.DataFrame(
        [
            {
                "municipio_nome": "SÃO PAULO",
                "uf": "SP",
                "latitude": -23.55,
                "longitude": -46.63,
                "votos_pos": 4492,
                "pct_apos_17h": 0.05,
                "ultimo_voto_str": "19:06:21",
            }
        ]
    )
    df_capitais = pd.DataFrame(
        [{"municipio_nome": "SÃO PAULO", "uf": "SP", "votos_pos": 4492}]
    )
    df_proporcao = pd.DataFrame(
        [{"municipio_nome": "BOCA DO ACRE", "uf": "AM", "pct_pos": 3.53}]
    )

    render_geography_tab(df_map, df_capitais, df_proporcao)


def test_render_integrity_tab(mocker: MockerFixture) -> None:
    """Verifica a renderização da aba de conformidade e integridade biométrica."""
    mocker.patch("streamlit.html")
    mocker.patch("streamlit.plotly_chart")
    mocker.patch("streamlit.markdown")
    mock_col = mocker.MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_col, mock_col])

    bio_data = {
        "ate_17h": {"pct_com_bio": 93.36, "pct_sem_bio": 6.64},
        "pos_17h": {"pct_com_bio": 92.21, "pct_sem_bio": 7.79},
        "delta_sem_bio": 1.15,
    }
    render_integrity_tab(bio_data)


def test_render_verdict_tab(mocker: MockerFixture) -> None:
    """Verifica a renderização da aba de veredito de auditoria e teste de estresse."""
    mocker.patch("streamlit.html")
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.latex")
    mocker.patch("streamlit.selectbox", return_value="Todas")
    mocker.patch("streamlit.text_input", return_value="")
    mocker.patch("streamlit.dataframe")
    mock_col = mocker.MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_col, mock_col])
    mocker.patch(
        "pulso_eleitoral.dashboard.components.verdict_tab.get_latest_sections",
        return_value=pd.DataFrame([{"municipio": "São Paulo", "votos": 10}]),
    )

    render_verdict_tab(db_path=":memory:")
