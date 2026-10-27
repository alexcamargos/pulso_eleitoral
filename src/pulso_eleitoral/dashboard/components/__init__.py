"""Componentes visuais e abas narrativas científicas do dashboard Streamlit."""

from __future__ import annotations

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
from pulso_eleitoral.dashboard.components.verdict_tab import render_verdict_tab

__all__ = [
    "render_executive_story_cards",
    "render_geography_tab",
    "render_integrity_tab",
    "render_timeline_tab",
    "render_verdict_tab",
]
