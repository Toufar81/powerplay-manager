# file: powerplay_app/tests/tournaments/test_tournament.py
"""Tournament model standings and meta behavior tests.

Coverage:
* Czech verbose names and ``__str__`` for ``Tournament``.
* Empty standings when no games are attached.
* Points and sorting logic across attached games (win=3, draw=1, loss=0).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.apps import apps
from django.utils import timezone

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def _aware(y: int, m: int, d: int, hh: int = 18, mm: int = 0) -> dt.datetime:
    """Create a timezone-aware datetime in the current timezone."""
    tz = timezone.get_current_timezone()
    return timezone.make_aware(dt.datetime(y, m, d, hh, mm), tz)


def _mk_game(
    Team: Any,
    league: Any,
    home_name: str,
    away_name: str,
    when: dt.datetime,
    sh: int,
    sa: int,
) -> Any:
    """Create (or reuse) teams by unique ``Team.name`` and persist a game.

    The competition is taken from the first choice of the ``Game.competition``
    field and ``league`` is set accordingly.
    """
    Game = apps.get_model("powerplay_app", "Game")
    home, _ = Team.objects.get_or_create(league=league, name=home_name)
    away, _ = Team.objects.get_or_create(league=league, name=away_name)
    return Game.objects.create(
        starts_at=when,
        home_team=home,
        away_team=away,
        score_home=sh,
        score_away=sa,
        competition=apps.get_model("powerplay_app", "Game")._meta.get_field("competition").choices[0][0],
        league=league,
    )


# --- Tournament meta & basics ---------------------------------------------


def test_tournament_meta_and_str() -> None:
    """Validate Czech verbose names and string representation."""
    Tournament = apps.get_model("powerplay_app", "Tournament")
    t = Tournament.objects.create(name="Podzimní pohár")
    assert str(t) == "Podzimní pohár"
    assert Tournament._meta.verbose_name == "Turnaj"
    assert Tournament._meta.verbose_name_plural == "Turnaje"


def test_standings_no_games_returns_empty() -> None:
    """Return an empty list when no games are attached to the tournament."""
    Tournament = apps.get_model("powerplay_app", "Tournament")
    t = Tournament.objects.create(name="Prázdno Cup")
    assert t.standings() == []


def test_standings_points_and_sorting(Team: Any, league_min: Any) -> None:
    """Compute points and sort by points, then goal difference, then goals for."""
    Tournament = apps.get_model("powerplay_app", "Tournament")
    t = Tournament.objects.create(name="Mini Cup")

    # Distinct datetimes avoid unique constraints
    g1 = _mk_game(Team, league_min, "HC A", "HC B", _aware(2025, 9, 1, 10, 0), 3, 1)  # A win
    g2 = _mk_game(Team, league_min, "HC A", "HC C", _aware(2025, 9, 2, 10, 0), 2, 2)  # draw
    g3 = _mk_game(Team, league_min, "HC B", "HC C", _aware(2025, 9, 3, 10, 0), 0, 1)  # C win

    t.games.add(g1, g2, g3)

    table = t.standings()

    # Expected order: A(4, GD +2), C(4, GD +1), B(0)
    assert [row["team"].name for row in table] == ["HC A", "HC C", "HC B"]

    rows = {row["team"].name: row for row in table}

    assert rows["HC A"]["points"] == 4
    assert rows["HC A"]["wins"] == 1
    assert rows["HC A"]["draws"] == 1
    assert rows["HC A"]["losses"] == 0
    assert rows["HC A"]["goals_for"] == 5
    assert rows["HC A"]["goals_against"] == 3

    assert rows["HC C"]["points"] == 4
    assert rows["HC C"]["wins"] == 1
    assert rows["HC C"]["draws"] == 1
    assert rows["HC C"]["losses"] == 0
    assert rows["HC C"]["goals_for"] == 3
    assert rows["HC C"]["goals_against"] == 2

    assert rows["HC B"]["points"] == 0
    assert rows["HC B"]["wins"] == 0
    assert rows["HC B"]["draws"] == 0
    assert rows["HC B"]["losses"] == 2
    assert rows["HC B"]["goals_for"] == 1
    assert rows["HC B"]["goals_against"] == 4

    # Aggregation for penalty_minutes via PlayerStats is not required → expect 0
    assert isinstance(rows["HC A"]["penalty_minutes"], int)
    assert rows["HC A"]["penalty_minutes"] == 0
