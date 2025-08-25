# file: powerplay_app/templatetags/next_game_strip.py
"""Template tag for rendering the next scheduled game of the primary team.

Internal documentation is in English; all user-facing strings remain Czech.
Behavior preserved: only Google-style docstrings, type hints, and light
formatting added.

Usage:
    {% load next_game_strip %}
    {% next_game_strip %}

Context:
    Requires ``primary_team`` in the template context. See
    ``powerplay_app.context.primary_team`` context processor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, Optional, Any

from django import template
from django.db.models import Q
from django.utils import timezone

# Import explicitly from modules to avoid relying on models/__init__ exports
from powerplay_app.models.games import Game, GameCompetition

register = template.Library()


@dataclass(frozen=True)
class NextGameVM:
    """Immutable view model for the **next** game widget.

    Attributes:
        opponent: Opponent team name (Czech in UI).
        datetime: Match start datetime (timezone-aware).
        home_away: Literal flag indicating whether we play at home or away.
        venue: Optional venue name.
        location: Optional city (home team's city).
        league: Optional competition label.
        round_label: Optional round/phase label (not populated yet).
        stream_url: Optional streaming link (placeholder for future schema).
        tickets_url: Optional ticketing link (placeholder for future schema).
    """

    opponent: str
    datetime: datetime
    home_away: Literal["home", "away"]
    venue: Optional[str] = None
    location: Optional[str] = None
    league: Optional[str] = None
    round_label: Optional[str] = None
    stream_url: Optional[str] = None
    tickets_url: Optional[str] = None

    @property
    def is_home(self) -> bool:
        """Return ``True`` if the primary team is the home team."""
        return self.home_away == "home"


def _format_league_label(game: Game) -> Optional[str]:
    """Return a Czech label for the game's competition.

    Prefers concrete league/tournament names; falls back to a human-friendly
    type when it's a friendly game.
    """
    if game.competition == GameCompetition.LEAGUE and game.league:
        return str(game.league)
    if game.competition == GameCompetition.TOURNAMENT and game.tournament:
        return str(game.tournament)
    if game.competition == GameCompetition.FRIENDLY:
        return "Přátelské utkání"
    return None


def _venue_name(game: Game) -> Optional[str]:
    """Return the venue name.

    Prefers the explicit stadium field; otherwise falls back to the home
    team's stadium name when available.
    """
    if game.stadium:
        return game.stadium.name
    home_stadium = getattr(getattr(game, "home_team", None), "stadium", None)
    return getattr(home_stadium, "name", None)


def _location_city(game: Game) -> Optional[str]:
    """Return the home team's city when available."""
    return getattr(game.home_team, "city", None) or None


@register.inclusion_tag("site/_partials/next_game_strip.html", takes_context=True)
def next_game_strip(context: dict[str, Any]) -> dict[str, Any]:
    """Provide context for the next scheduled game of the primary team.

    Searches for the nearest future ``Game`` (``starts_at >= now``) where the
    primary team is either home or away. If none exists or ``primary_team`` is
    missing, the ``next_game`` key is set to ``None``.

    Args:
        context: Template context containing ``primary_team`` (Team or ``None``).

    Returns:
        dict[str, Any]: Context for ``site/_partials/next_game_strip.html`` with
        keys ``next_game`` (``NextGameVM | None``) and ``primary_team``.
    """
    primary_team = context.get("primary_team")
    now = timezone.now()

    if not primary_team:
        return {"next_game": None, "primary_team": None}

    game: Game | None = (
        Game.objects.select_related("home_team", "away_team", "league", "tournament", "stadium")
        .filter(Q(home_team=primary_team) | Q(away_team=primary_team), starts_at__gte=now)
        .order_by("starts_at")
        .first()
    )

    if not game:
        return {"next_game": None, "primary_team": primary_team}

    is_home = game.home_team_id == primary_team.id
    opponent = game.away_team.name if is_home else game.home_team.name

    vm = NextGameVM(
        opponent=opponent,
        datetime=game.starts_at,
        home_away="home" if is_home else "away",
        venue=_venue_name(game),
        location=_location_city(game),
        league=_format_league_label(game),
        round_label=None,  # not in the model yet; can be added later
        stream_url=None,   # placeholders for future schema
        tickets_url=None,
    )

    return {"next_game": vm, "primary_team": primary_team}
