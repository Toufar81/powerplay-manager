# file: powerplay_app/dashboard.py
"""Django JET dashboards for the Powerplay admin.

This module defines:

* :class:`UpcomingEventsModule` – a dashboard module listing upcoming
  ``TeamEvent`` items for the next 14 days.
* :class:`CustomIndexDashboard` – the main admin index dashboard (3 columns)
  with quick links, recent actions, model lists, and the events module.
* :class:`CustomAppIndexDashboard` – per-app dashboard (2 columns) that
  displays the app's models and recent actions scoped to the app.

All user-visible labels are Czech; the code focuses on structure and data
fetching for dashboard widgets.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone
from django.utils.html import format_html
from jet.dashboard import modules
from jet.dashboard.dashboard import AppIndexDashboard, Dashboard
from jet.dashboard.modules import DashboardModule

from .models import TeamEvent
from .models.games import GameCompetition


# --- Upcoming events module ------------------------------------------------


class UpcomingEventsModule(DashboardModule):
    """List upcoming team events within the next 14 days.

    The module renders anchors to admin change pages. It prefetches related
    objects for performance and limits the number of displayed items.
    """

    title: str = "Nadcházející akce (14 dní)"
    template: str = "admin/dashboard/upcoming_events.html"
    limit: int = 10

    def init_with_context(self, context: dict[str, Any]) -> None:  # type: ignore[override]
        """Populate ``children`` with links for upcoming events.

        Args:
            context: Render context supplied by Django JET.
        """
        now = timezone.now()
        end_date = now + timedelta(days=14)

        events = (
            TeamEvent.objects.filter(starts_at__gte=now, starts_at__lte=end_date)
            .select_related(
                "team",
                "stadium",
                "related_game__home_team",
                "related_game__away_team",
                "related_game__league",
                "related_game__tournament",
            )
            .order_by("starts_at")[: self.limit]
        )

        def render_label(e: TeamEvent) -> str:
            """Build a human-readable label for one dashboard row."""
            if e.event_type == TeamEvent.EventType.GAME and e.related_game:
                g = e.related_game
                if g.competition == GameCompetition.LEAGUE and getattr(g, "league", None):
                    prefix = f"Liga {g.league}"
                elif g.competition == GameCompetition.TOURNAMENT and getattr(g, "tournament", None):
                    prefix = f"Turnaj {g.tournament.name}"
                elif g.competition == GameCompetition.FRIENDLY:
                    prefix = "Přátelský"
                else:
                    prefix = "Zápas"
                return f"{prefix} – Zápas: {g.home_team.name} vs {g.away_team.name}"
            if e.event_type == TeamEvent.EventType.TRAINING:
                return f"Trénink: {(e.team.name if e.team else '').strip()}"
            return e.title

        self.children = []  # list of HTML strings
        for e in events:
            admin_url = f"/admin/powerplay_app/teamevent/{e.id}/change/"
            local_dt = timezone.localtime(e.starts_at)  # align with admin timezone
            date_str = local_dt.strftime("%d.%m.%Y %H:%M")
            self.children.append(
                format_html('<a href="{}">{}</a> <small>{}</small>', admin_url, render_label(e), date_str)
            )


# --- Index dashboard (site-wide) ------------------------------------------


class CustomIndexDashboard(Dashboard):
    """Main admin index dashboard with quick navigation and summaries."""

    columns: int = 3

    def init_with_context(self, context: dict[str, Any]) -> None:  # type: ignore[override]
        """Assemble panels: quick links, recent actions, model lists, events."""
        self.children.append(
            modules.LinkList(
                title="Rychlé odkazy",
                children=[
                    {"title": "Přidat zápas", "url": "/admin/powerplay_app/game/add/", "external": False},
                    {"title": "Přidat tým", "url": "/admin/powerplay_app/team/add/", "external": False},
                    {"title": "Přidat hráče", "url": "/admin/powerplay_app/player/add/", "external": False},
                    {"title": "Události (kalendář)", "url": "/admin/powerplay_app/teamevent/", "external": False},
                ],
                column=0,
                collapsible=True,
            )
        )
        self.children.append(
            modules.RecentActions(title="Nedávné akce", limit=10, column=0, collapsible=True)
        )
        self.children.append(
            modules.AppList(
                title="PowerPlay – modely",
                models=("powerplay_app.*",),
                exclude=("django.contrib.*",),
                column=1,
                collapsible=True,
            )
        )
        self.children.append(
            modules.ModelList(
                title="Zápasy & Statistiky",
                models=("powerplay_app.models.Game", "powerplay_app.models.PlayerStats"),
                column=2,
                collapsible=True,
            )
        )
        self.children.append(
            modules.ModelList(
                title="Týmy & Hráči & Staff",
                models=(
                    "powerplay_app.models.Team",
                    "powerplay_app.models.Player",
                    "powerplay_app.models.Staff",
                ),
                column=2,
                collapsible=True,
            )
        )
        self.children.append(UpcomingEventsModule())


# --- App index dashboard (per app) ----------------------------------------


class CustomAppIndexDashboard(AppIndexDashboard):
    """Per-app dashboard listing models and recent actions for that app."""

    columns: int = 2

    def init_with_context(self, context: dict[str, Any]) -> None:  # type: ignore[override]
        """Assemble per-app model list and recent actions widgets."""
        self.children.append(
            modules.ModelList(title="Modely aplikace", models=(f"{self.app_label}.*",), column=0)
        )
        self.children.append(
            modules.RecentActions(
                title="Nedávné akce v aplikaci", include_list=(f"{self.app_label}.*",), limit=10, column=1
            )
        )
