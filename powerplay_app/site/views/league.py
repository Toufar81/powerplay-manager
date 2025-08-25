# file: powerplay_app/views/league.py
"""Public league page view.

Exposes :class:`LeagueView`, a lightweight template view that renders
``site/league.html`` and provides the league of the *primary* team to the
template. The primary team is injected by a global context processor; this view
only reads that context and derives ``league`` accordingly. No database queries
are issued.

Internal documentation is in English; user-facing strings remain Czech.
Behavior is unchanged.
"""

from __future__ import annotations

from typing import Any

from django.views.generic import TemplateView


class LeagueView(TemplateView):
    """Render the league page using the primary team's league reference."""

    template_name = "site/league.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Return template context with the league of the primary team.

        Returns:
            Template context including ``league`` resolved from ``primary_team``
            (if present).
        """
        ctx = super().get_context_data(**kwargs)
        # ``primary_team`` is injected by the context processor.
        team = ctx.get("primary_team")
        ctx["league"] = getattr(team, "league", None)
        return ctx
