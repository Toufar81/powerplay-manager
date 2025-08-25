# file: powerplay_app/templatetags/latest_match.py
"""Template tags for rendering the latest non-future match of the primary team.

Provides two pieces:

- :class:`LatestMatchVM` – an immutable view model used by the partial template
  to render opponent, datetime, home/away, score, result (Czech label), and
  optional competition/venue/city.
- ``{% latest_match %}`` inclusion tag – expects ``primary_team`` in the
  template context and supplies ``latest`` (``LatestMatchVM | None``) along with
  ``primary_team``. It selects the most recent :class:`~powerplay_app.models.games.Game`
  whose ``starts_at`` is not in the future and where the team appears as either
  home or away; related objects are prefetched via ``select_related``.

Usage::

    {% load latest_match %}
    {% latest_match %}

Requirements:
    ``primary_team`` must be present in the template context (see
    ``powerplay_app.context.primary_team`` context processor). UI labels remain
    Czech; internal documentation is English. Behavior is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, Optional, Any

from django import template
from django.db.models import Q
from django.utils import timezone

from powerplay_app.models.games import Game, GameCompetition

register = template.Library()


@dataclass(frozen=True)
class LatestMatchVM:
    """Immutable view model for the latest finished match widget.

    Attributes:
        opponent: Opponent team name (Czech in UI).
        datetime: Match start datetime (timezone-aware).
        home_away: Literal flag indicating whether the primary team was home or away.
        score_us: Goals scored by the primary team.
        score_them: Goals conceded by the primary team.
        result: Czech label: "Výhra" | "Prohra" | "Remíza".
        league: Optional competition label (e.g., "NHL 2025/2026" or tournament name).
        venue: Optional venue name.
        location: Optional city (home team's city).
    """

    opponent: str
    datetime: datetime
    home_away: Literal["home", "away"]
    score_us: int
    score_them: int
    result: str
    league: Optional[str] = None
    venue: Optional[str] = None
    location: Optional[str] = None


# Fixed Czech result labels for UI output.
_DEF_RESULT_LABELS: Final[dict[str, str]] = {
    "win": "Výhra",
    "loss": "Prohra",
    "draw": "Remíza",
}


def _league_label(g: Game) -> Optional[str]:
    """Return a Czech label describing the competition for the given game."""
    if g.competition == GameCompetition.LEAGUE and g.league:
        return str(g.league)
    if g.competition == GameCompetition.TOURNAMENT and g.tournament:
        return str(g.tournament)
    if g.competition == GameCompetition.FRIENDLY:
        return "Přátelský zápas"
    return None


def _venue(g: Game) -> Optional[str]:
    """Return the venue name.

    Prefers the game's explicit stadium; falls back to the home team's stadium
    name if available.
    """
    if g.stadium:
        return g.stadium.name
    home_stadium = getattr(getattr(g, "home_team", None), "stadium", None)
    return getattr(home_stadium, "name", None)


def _city(g: Game) -> Optional[str]:
    """Return the home team's city when available."""
    return getattr(g.home_team, "city", None) or None


@register.inclusion_tag("site/_partials/latest_match.html", takes_context=True)
def latest_match(context: dict[str, Any]) -> dict[str, Any]:
    """Render context for the latest finished match of the primary team.

    Looks up the most recent game (``starts_at`` <= ``now``) involving the
    primary team and returns a view model for display. If no game is found or
    the team is missing, returns ``latest=None``.

    Args:
        context: Template context containing ``primary_team``.

    Returns:
        Context with keys ``latest`` (``LatestMatchVM | None``) and
        ``primary_team`` for the partial template.
    """
    primary_team = context.get("primary_team")
    if not primary_team:
        return {"latest": None, "primary_team": None}

    now = timezone.now()
    g: Game | None = (
        Game.objects.select_related("home_team", "away_team", "league", "tournament", "stadium")
        .filter(Q(home_team=primary_team) | Q(away_team=primary_team), starts_at__lte=now)
        .order_by("-starts_at")
        .first()
    )

    if not g:
        return {"latest": None, "primary_team": primary_team}

    is_home = g.home_team_id == primary_team.id
    us = g.score_home if is_home else g.score_away
    them = g.score_away if is_home else g.score_home

    if us > them:
        result = _DEF_RESULT_LABELS["win"]
    elif us < them:
        result = _DEF_RESULT_LABELS["loss"]
    else:
        result = _DEF_RESULT_LABELS["draw"]

    vm = LatestMatchVM(
        opponent=(g.away_team.name if is_home else g.home_team.name),
        datetime=g.starts_at,
        home_away=("home" if is_home else "away"),
        score_us=us,
        score_them=them,
        result=result,
        league=_league_label(g),
        venue=_venue(g),
        location=_city(g),
    )

    return {"latest": vm, "primary_team": primary_team}
