# file: powerplay_app/site/views/calendar.py
"""Portal calendar view aggregating team events and near-future games.

Shows the next 30 days of items for the primary team, preferring
:class:`~powerplay_app.models.TeamEvent` and falling back to raw
:class:`~powerplay_app.models.games.Game` objects when no events are available.
Docstrings and internal comments are English; user-facing strings remain Czech.
Behavior is unchanged.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone
from django.views.generic import TemplateView

from powerplay_app.context import _resolve_primary_team
from powerplay_app.models import TeamEvent
from powerplay_app.models.games import Game


class CalendarView(TemplateView):
    """Calendar page for the portal.

    Strategy:
        1) Resolve the primary team (scopes the whole FE).
        2) Load team-bound events within a 30-day window starting "now".
        3) If no events exist yet (e.g., sync did not run), fall back to
           ``Game`` objects in the same window.

    Notes:
        - Time handling stays timezone-aware via ``timezone.now()`` and
          ``timezone.localtime`` in templates where needed.
        - QuerySets are left lazy; ``exists()`` is used explicitly for fallback
          branching.
    """

    template_name = "portal/calendar.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # override
        """Provide event lists and a fallback game list.

        Args:
            **kwargs: Extra context kwargs passed by Django.

        Returns:
            Template context with keys ``primary_team``, ``events``,
            ``fallback_games``, and date range markers.
        """
        ctx = super().get_context_data(**kwargs)

        team = _resolve_primary_team()
        start = timezone.now()
        end = start + timedelta(days=30)

        events = TeamEvent.objects.none()
        games_fallback = Game.objects.none()

        if team:
            # 1) Events directly bound to the team OR to games involving the team.
            events = (
                TeamEvent.objects
                .select_related(
                    "team",
                    "stadium",
                    "related_game",
                    "related_game__home_team",
                    "related_game__away_team",
                )
                .filter(
                    Q(team=team)
                    | Q(event_type=TeamEvent.EventType.GAME, related_game__home_team=team)
                    | Q(event_type=TeamEvent.EventType.GAME, related_game__away_team=team)
                )
                .filter(starts_at__gte=start, starts_at__lte=end)
                .order_by("starts_at")
            )

            # 2) Fallback: if TeamEvent sync hasn't created event rows yet,
            #    show upcoming games in the same 30-day window.
            if not events.exists():
                games_fallback = (
                    Game.objects
                    .select_related("home_team", "away_team", "stadium", "league", "tournament")
                    .filter(
                        (Q(home_team=team) | Q(away_team=team)),
                        starts_at__gte=start,
                        starts_at__lte=end,
                    )
                    .order_by("starts_at")
                )

        ctx.update(
            {
                "primary_team": team,
                "current": "calendar",
                "range_start": start,
                "range_end": end,
                "events": events,
                "fallback_games": games_fallback,
            }
        )
        return ctx
