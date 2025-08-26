# file: powerplay_app/templatetags/latest_match.py
"""Template tag: Poslední zápas (HOME vlevo, AWAY vpravo, shodný layout jako Next Game).

Použití v šabloně:
    {% load latest_match %}
    {% latest_match %}

Vyžaduje `primary_team` v kontextu (viz context processor).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from django import template
from django.db.models import Q
from django.utils import timezone

from powerplay_app.models.games import Game, GameCompetition

register = template.Library()


@dataclass(frozen=True)
class LatestVM:
    """Meta pro střední sloupec (datum, skóre, doplňková meta)."""

    datetime: datetime
    score_home: int
    score_away: int
    result: str  # "Výhra" | "Prohra" | "Remíza" (z pohledu primary_team)
    venue: Optional[str] = None
    location: Optional[str] = None  # město HOME týmu
    league: Optional[str] = None
    is_home: bool = False  # hrál primary_team doma?


# ---- helpers ---------------------------------------------------------------

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
    home_stadium = getattr(getattr(g, "home_team", None), "stadium", None)
    return getattr(home_stadium, "name", None)


def _city(g: Game) -> Optional[str]:
    return getattr(g.home_team, "city", None) or None


def _team_logo_url(team: Any) -> Optional[str]:
    if not team:
        return None
    # string url
    val = getattr(team, "logo_url", None)
    if isinstance(val, str) and val.strip():
        return val
    # ImageField
    img = getattr(team, "logo", None)
    if img is not None:
        try:
            url = img.url  # type: ignore[attr-defined]
            if isinstance(url, str) and url.strip():
                return url
        except Exception:
            pass
    # běžné aliasy
    for attr in ("emblem", "badge"):
        img2 = getattr(team, attr, None)
        if img2 is not None:
            try:
                url2 = img2.url  # type: ignore[attr-defined]
                if isinstance(url2, str) and url2.strip():
                    return url2
            except Exception:
                pass
    return None


def _team_region(team: Any) -> Optional[str]:
    return (
        getattr(team, "city", None)
        or getattr(team, "location", None)
        or getattr(team, "short_name", None)
        or None
    )


@register.inclusion_tag("site/_partials/latest_match.html", takes_context=True)
def latest_match(context: dict[str, Any]) -> dict[str, Any]:
    """Vrátí kontext pro POSLEDNÍ odehraný zápas (starts_at <= now).

    Vlevo se vždy vykresluje HOME tým, vpravo AWAY tým. Střed = datum + skóre.
    `result` je z pohledu `primary_team` (Výhra/Prohra/Remíza).
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

    is_home = g.home_team_id == getattr(primary_team, "id", None)

    # skóre ve směru HOME–AWAY (pro střední sloupec) + výsledek z pohledu primary
    s_home = int(g.score_home or 0)
    s_away = int(g.score_away or 0)
    us = s_home if is_home else s_away
    them = s_away if is_home else s_home
    if us > them:
        result = "Výhra"
    elif us < them:
        result = "Prohra"
    else:
        result = "Remíza"

    vm = LatestVM(
        datetime=g.starts_at,
        score_home=s_home,
        score_away=s_away,
        result=result,
        venue=_venue(g),
        location=_city(g),
        league=_league_label(g),
        is_home=is_home,
    )

    home_t = g.home_team
    away_t = g.away_team

    home = {
        "name": str(home_t.name),
        "region": _team_region(home_t),
        "logo_url": _team_logo_url(home_t),
        "is_us": is_home,
    }
    away = {
        "name": str(away_t.name),
        "region": _team_region(away_t),
        "logo_url": _team_logo_url(away_t),
        "is_us": not is_home,
    }

    return {
        "latest": vm,
        "primary_team": primary_team,
        "home": home,
        "away": away,
    }