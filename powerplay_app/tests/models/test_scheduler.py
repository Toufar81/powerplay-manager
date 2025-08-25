# file: powerplay_app/tests/events/test_team_events.py
"""Tests for ``TeamEvent`` model meta, validation, and constraints.

Coverage:
* Model meta/verbose names and ordering.
* Validation rules: end after start, related game must use ``game`` type,
  non-game events require a team, and game events normalize ``team`` to ``None``.
* Uniqueness constraint: single event per related game.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Tuple

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def _aware(y: int, m: int, d: int, hh: int = 18, mm: int = 0) -> dt.datetime:
    """Create a timezone-aware datetime in the current timezone."""
    tz = timezone.get_current_timezone()
    return timezone.make_aware(dt.datetime(y, m, d, hh, mm), tz)


def _mk_game_basic(Team: Any, league: Any) -> Tuple[Any, Any, Any]:
    """Create a league game with two fresh teams; return ``(game, home, away)``."""
    Game = apps.get_model("powerplay_app", "Game")
    # Create two teams in the given league
    home = Team.objects.create(league=league, name="HC HN")
    away = Team.objects.create(league=league, name="HC AN")

    competition = Game._meta.get_field("competition").choices[0][0]  # league
    game = Game.objects.create(
        starts_at=_aware(2025, 9, 10, 18, 0),
        home_team=home,
        away_team=away,
        competition=competition,
        league=league,
    )
    return game, home, away


# --- Meta ------------------------------------------------------------------


def test_teamevent_meta_and_indexes() -> None:
    """Validate verbose names and default ordering for ``TeamEvent``."""
    TeamEvent = apps.get_model("powerplay_app", "TeamEvent")
    assert TeamEvent._meta.verbose_name == "Událost týmu"
    assert TeamEvent._meta.verbose_name_plural == "Události týmů"
    assert TeamEvent._meta.ordering == ("starts_at",)


# --- Validation ------------------------------------------------------------


def test_ends_after_starts_validation(Team: Any, league_min: Any) -> None:
    """Reject events whose ``ends_at`` is earlier than ``starts_at``."""
    TeamEvent = apps.get_model("powerplay_app", "TeamEvent")
    ev = TeamEvent(
        team=Team.objects.create(league=league_min, name="HC X"),
        event_type="training",
        title="Trénink",
        starts_at=_aware(2025, 9, 1, 19, 0),
        ends_at=_aware(2025, 9, 1, 18, 0),  # ends before start
    )
    with pytest.raises(ValidationError):
        ev.full_clean()


def test_related_game_requires_type_game(Team: Any, league_min: Any) -> None:
    """Require ``event_type='game'`` when ``related_game`` is set."""
    TeamEvent = apps.get_model("powerplay_app", "TeamEvent")
    Game = apps.get_model("powerplay_app", "Game")
    game, home, _ = _mk_game_basic(Team, league_min)
    # Remove any auto-created event for this game
    TeamEvent.objects.filter(related_game=game).delete()

    ev = TeamEvent(
        team=home,
        event_type="training",  # invalid type
        title="Napojená, ale ne zápas",
        starts_at=_aware(2025, 9, 12, 18, 0),
        ends_at=_aware(2025, 9, 12, 19, 0),
        related_game=game,
    )
    with pytest.raises(ValidationError):
        ev.full_clean()


def test_non_game_requires_team(Team: Any, league_min: Any) -> None:
    """Require explicit ``team`` for non-game events."""
    TeamEvent = apps.get_model("powerplay_app", "TeamEvent")
    ev = TeamEvent(
        # team missing
        event_type="training",
        title="Bez týmu",
        starts_at=_aware(2025, 9, 5, 18, 0),
        ends_at=_aware(2025, 9, 5, 19, 0),
    )
    with pytest.raises(ValidationError):
        ev.full_clean()


def test_game_event_normalizes_team_to_none(Team: Any, league_min: Any) -> None:
    """Normalize ``team`` to ``None`` for ``event_type='game'`` during cleaning."""
    TeamEvent = apps.get_model("powerplay_app", "TeamEvent")
    game, home, _ = _mk_game_basic(Team, league_min)
    # Remove any auto-created event for this game
    TeamEvent.objects.filter(related_game=game).delete()

    ev = TeamEvent(
        team=home,  # will be nullified in clean()
        event_type="game",
        title="Zápas",
        starts_at=_aware(2025, 9, 23, 18, 0),
        ends_at=_aware(2025, 9, 23, 20, 0),
        related_game=game,
    )
    ev.full_clean()  # should not raise
    assert ev.team is None


# --- Constraint ------------------------------------------------------------


def test_unique_event_per_game(Team: Any, league_min: Any) -> None:
    """Enforce one ``TeamEvent`` per ``related_game``."""
    TeamEvent = apps.get_model("powerplay_app", "TeamEvent")
    game, home, _ = _mk_game_basic(Team, league_min)
    # Remove any auto-created event for this game
    TeamEvent.objects.filter(related_game=game).delete()

    TeamEvent.objects.create(
        event_type="game",
        title="Zápas 1",
        starts_at=_aware(2025, 9, 24, 18, 0),
        ends_at=_aware(2025, 9, 24, 20, 0),
        related_game=game,
    )

    with pytest.raises(IntegrityError):
        TeamEvent.objects.create(
            event_type="game",
            title="Zápas 2",
            starts_at=_aware(2025, 9, 25, 18, 0),
            ends_at=_aware(2025, 9, 25, 20, 0),
            related_game=game,
        )
