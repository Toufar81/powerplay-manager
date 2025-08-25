# File: powerplay_app/tests/models/test_feedback.py
"""Tests for feedback model behavior and invariants.

Covers:
- Basic creation with/without links to ``Game`` or ``TeamEvent``.
- ``team`` is required at the DB layer.
- Author display name snapshot remains stable when the user changes.
- ``__str__`` includes team, subject preview, and a fallback target label.

Internal docs are English; Czech strings remain in assertions where applicable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

if TYPE_CHECKING:  # typing-only to avoid runtime coupling
    from powerplay_app.models import League, Team

pytestmark = pytest.mark.django_db


def _mk_team(name: str, league: "League") -> "Team":
    """Create a ``Team`` helper for tests in a given league."""
    Team = apps.get_model("powerplay_app", "Team")
    return Team.objects.create(name=name, league=league)


def test_feedback_basic_create_with_game_or_event_or_none(league_min: "League") -> None:
    """Feedback can be stored standalone or linked to a game/event."""
    Game = apps.get_model("powerplay_app", "Game")
    TeamEvent = apps.get_model("powerplay_app", "TeamEvent")
    GameFeedback = apps.get_model("powerplay_app", "GameFeedback")

    team = _mk_team("HC FB", league_min)

    # bez vazby
    fb0 = GameFeedback.objects.create(team=team, subject="A", message="M0")
    assert fb0.related_game_id is None and fb0.related_event_id is None

    # s friendly zápasem
    away = _mk_team("HC X", league_min)
    g = Game.objects.create(
        starts_at=timezone.now(),
        home_team=team,
        away_team=away,
        competition="friendly",
    )
    fb1 = GameFeedback.objects.create(team=team, related_game=g, message="M1")
    assert fb1.related_game_id == g.id

    # s tréninkem
    ev = TeamEvent.objects.create(
        team=team,
        event_type="training",
        title="Trénink",
        starts_at=timezone.now(),
        ends_at=timezone.now(),
    )
    fb2 = GameFeedback.objects.create(team=team, related_event=ev, message="M2")
    assert fb2.related_event_id == ev.id


def test_feedback_requires_team() -> None:
    """DB constraint requires a team for every feedback entry."""
    GameFeedback = apps.get_model("powerplay_app", "GameFeedback")
    with pytest.raises(IntegrityError):
        GameFeedback.objects.create(message="Bez týmu")


def test_feedback_author_snapshot_stable(league_min: "League") -> None:
    """Changing the user does not alter the stored author snapshot."""
    GameFeedback = apps.get_model("powerplay_app", "GameFeedback")
    team = _mk_team("HC FB2", league_min)
    User = get_user_model()
    u = User.objects.create(username="fbuser", first_name="Jan", last_name="Novák")

    fb = GameFeedback.objects.create(
        team=team,
        message="msg",
        created_by=u,
        created_by_name="Jan Novák",
    )

    # změna uživatele neovlivní uložený snapshot
    u.first_name = "Pepa"
    u.save()
    fb.refresh_from_db()
    assert fb.created_by_id == u.id
    assert fb.created_by_name == "Jan Novák"


def test_feedback_str_contains_team_subject_and_target(league_min: "League") -> None:
    """``__str__`` should include team name, subject preview, and fallback target label."""
    GameFeedback = apps.get_model("powerplay_app", "GameFeedback")
    team = _mk_team("HC FB3", league_min)

    fb = GameFeedback.objects.create(team=team, subject="Dotaz", message="Dlouhá zpráva…")
    s = str(fb)
    assert team.name in s
    assert "Dotaz" in s
    assert "bez vazby" in s  # fallback když není game ani event
