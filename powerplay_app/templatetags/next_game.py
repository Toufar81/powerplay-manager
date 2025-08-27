# file: powerplay_app/templatetags/next_game.py
"""Template tag for rendering the next scheduled game (HOME left, AWAY right).

Public strings remain Czech; code comments/helpers in English.

Usage in templates:
    {% load next_game %}
    {% next_game_strip %}

Requires ``primary_team`` in context (provided by a context processor).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from django import template
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify

# Explicit import to avoid relying on packages' __init__ exports
from powerplay_app.models.games import Game, GameCompetition

register = template.Library()


@dataclass(frozen=True)
class NextGameVM:
    """Meta for the center column of the banner."""

    datetime: datetime
    venue: Optional[str] = None
    location: Optional[str] = None  # home team city
    league: Optional[str] = None
    round_label: Optional[str] = None
    stream_url: Optional[str] = None
    tickets_url: Optional[str] = None
    is_home: bool = False  # whether *primary_team* plays at home


# ---- helpers ---------------------------------------------------------------

def _format_league_label(game: Game) -> Optional[str]:
    if game.competition == GameCompetition.LEAGUE and game.league:
        return str(game.league)
    if game.competition == GameCompetition.TOURNAMENT and game.tournament:
        return str(game.tournament)
    if game.competition == GameCompetition.FRIENDLY:
        return "Přátelské utkání"
    return None


def _venue_name(game: Game) -> Optional[str]:
    if game.stadium:
        return game.stadium.name
    home_stadium = getattr(getattr(game, "home_team", None), "stadium", None)
    return getattr(home_stadium, "name", None)


def _home_city(game: Game) -> Optional[str]:
    return getattr(game.home_team, "city", None) or None


def _team_logo_url(team: Any) -> Optional[str]:
    """Resolve team logo URL from common fields; be defensive."""
    if not team:
        return None
    # direct string field
    val = getattr(team, "logo_url", None)
    if isinstance(val, str) and val.strip():
        return val
    # ImageField-like (may raise when storage is misconfigured, be safe)
    img = getattr(team, "logo", None)
    if img is not None:
        try:
            url = img.url  # type: ignore[attr-defined]
            if isinstance(url, str) and url.strip():
                return url
        except Exception:
            pass
    # Common aliases just in case
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


def _detail_url(game: Game) -> Optional[str]:
    """Prefer model's get_absolute_url(); fallback to reverse with slug."""
    if not game:
        return None
    # Try model helper
    get_abs = getattr(game, "get_absolute_url", None)
    if callable(get_abs):
        try:
            return get_abs()
        except Exception:
            pass
    # Fallback – construct from pk + slug
    date_part = game.starts_at.date().isoformat() if game.starts_at else "game"
    home = slugify(getattr(game.home_team, "name", "home"))
    away = slugify(getattr(game.away_team, "name", "away"))
    slug = f"{date_part}-{home}-vs-{away}"
    try:
        return reverse("site:game_detail", args=[game.pk, slug])
    except Exception:
        return None


@register.inclusion_tag("site/_partials/next_game_strip.html", takes_context=True)
def next_game_strip(context: dict[str, Any]) -> dict[str, Any]:
    """Return context for the next scheduled game of the primary team.

    LEFT is always HOME team, RIGHT is always AWAY team.
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

    is_home = game.home_team_id == getattr(primary_team, "id", None)

    vm = NextGameVM(
        datetime=game.starts_at,
        venue=_venue_name(game),
        location=_home_city(game),
        league=_format_league_label(game),
        round_label=None,
        stream_url=None,
        tickets_url=None,
        is_home=is_home,
    )

    home_team = game.home_team
    away_team = game.away_team

    home = {
        "name": str(home_team.name),
        "region": _team_region(home_team),
        "logo_url": _team_logo_url(home_team),
        "is_us": is_home,
    }
    away = {
        "name": str(away_team.name),
        "region": _team_region(away_team),
        "logo_url": _team_logo_url(away_team),
        "is_us": not is_home,
    }

    return {
        "next_game": vm,
        "primary_team": primary_team,
        "home": home,
        "away": away,
        "detail_url": _detail_url(game),
    }
