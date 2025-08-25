from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django import template
from django.db.models import Q
from django.utils import timezone

from powerplay_app.models.games import Game, GameCompetition

register = template.Library()


@dataclass(frozen=True)
class LatestMatchVM:
    opponent: str
    datetime: timezone.datetime
    home_away: str  # "home" | "away"
    score_us: int
    score_them: int
    result: str  # "Výhra" | "Prohra" | "Remíza"
    league: Optional[str] = None
    venue: Optional[str] = None
    location: Optional[str] = None


_DEF_RESULT_LABELS = {
    "win": "Výhra",
    "loss": "Prohra",
    "draw": "Remíza",
}


def _league_label(g: Game) -> Optional[str]:
    if g.competition == GameCompetition.LEAGUE and g.league:
        return str(g.league)
    if g.competition == GameCompetition.TOURNAMENT and g.tournament:
        return str(g.tournament)
    if g.competition == GameCompetition.FRIENDLY:
        return "Přátelský zápas"
    return None


def _venue(g: Game) -> Optional[str]:
    if g.stadium:
        return g.stadium.name
    return getattr(getattr(g, "home_team", None), "stadium", None).name if getattr(getattr(g, "home_team", None), "stadium", None) else None


def _city(g: Game) -> Optional[str]:
    return getattr(g.home_team, "city", None) or None


@register.inclusion_tag("site/_partials/latest_match.html", takes_context=True)
def latest_match(context):
    primary_team = context.get("primary_team")
    if not primary_team:
        return {"latest": None, "primary_team": None}

    now = timezone.now()
    g = (
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
