# file: powerplay_app/tests/events/test_events.py
"""Event model enums and validation tests.

Coverage:
* Abstract base class flag for ``GameEventBase``.
* Enum choices (``Period``, ``Strength``, ``PenaltyType``) values and labels.
* Field defaults and verbose names for ``Goal`` and ``Penalty``.
* Model ``_meta`` verbose names for ``Goal``/``Penalty``.
* Validation rules requiring team participation and game nominations.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from powerplay_app.models.events import GameEventBase, PenaltyType, Period, Strength
from powerplay_app.models.games import GameCompetition

pytestmark = pytest.mark.django_db


# --- Base enums and meta ---------------------------------------------------


def test_game_event_base_is_abstract() -> None:
    """Ensure ``GameEventBase`` is an abstract model.

    The ORM should not create a concrete table for this base class.
    """
    assert GameEventBase._meta.abstract is True


def test_period_choices_values_and_labels() -> None:
    """Verify ``Period`` enum choices and Czech labels."""
    assert list(Period.choices) == [
        (1, "1. třetina"),
        (2, "2. třetina"),
        (3, "3. třetina"),
        (4, "Prodloužení"),
        (5, "Nájezdy"),
    ]


def test_strength_choices_values_and_labels() -> None:
    """Verify ``Strength`` enum choices and Czech labels."""
    assert list(Strength.choices) == [
        ("EV", "Plný počet"),
        ("PP", "Přesilovka"),
        ("OS", "Oslabení"),
        ("EN", "Do prázdné"),
        ("PS", "Trestné střílení"),
    ]


def test_penalty_type_choices_values_and_labels() -> None:
    """Verify ``PenaltyType`` enum choices and Czech labels."""
    assert list(PenaltyType.choices) == [
        ("2", "Malý trest (2)"),
        ("5", "Velký trest (5)"),
        ("10", "Osobní trest (10)"),
        ("20", "Do konce utkání (20)"),
    ]


def test_goal_strength_field_default_and_labels() -> None:
    """Check default and label of ``Goal.strength`` field."""
    Goal = apps.get_model("powerplay_app", "Goal")
    f = Goal._meta.get_field("strength")
    assert f.default == Strength.EV
    assert f.verbose_name == "Síla hry"


def test_penalty_defaults_and_labels() -> None:
    """Check defaults and labels for ``Penalty`` relevant fields."""
    Penalty = apps.get_model("powerplay_app", "Penalty")
    f_type = Penalty._meta.get_field("penalty_type")
    f_minutes = Penalty._meta.get_field("minutes")
    assert f_type.default == PenaltyType.MINOR
    assert f_type.verbose_name == "Typ trestu"
    assert f_minutes.verbose_name == "Délka trestu (min)"


def test_goal_meta_verbose_names() -> None:
    """Validate Czech verbose names for ``Goal`` model."""
    Goal = apps.get_model("powerplay_app", "Goal")
    assert Goal._meta.verbose_name == "Gól"
    assert Goal._meta.verbose_name_plural == "Góly"


def test_penalty_meta_verbose_names() -> None:
    """Validate Czech verbose names for ``Penalty`` model."""
    Penalty = apps.get_model("powerplay_app", "Penalty")
    assert Penalty._meta.verbose_name == "Trest"
    assert Penalty._meta.verbose_name_plural == "Tresty"


# --- Validation rules with Game/GameNomination -----------------------------


def _aware(y: int, m: int, d: int, hh: int = 18, mm: int = 0) -> dt.datetime:
    """Create a timezone-aware datetime in the current timezone."""
    tz = timezone.get_current_timezone()
    return timezone.make_aware(dt.datetime(y, m, d, hh, mm), tz)


def _mk_game_basic(Team: Any, league_min: Any) -> tuple[Any, Any, Any]:
    """Create a minimal game with home/away teams within a league.

    Args:
        Team: Team model class fixture.
        league_min: Precreated League instance fixture.

    Returns:
        tuple[Any, Any, Any]: ``(game, home_team, away_team)``.
    """
    Game = apps.get_model("powerplay_app", "Game")
    home = Team.objects.create(league=league_min, name="HC Evt H")
    away = Team.objects.create(league=league_min, name="HC Evt A")
    return (
        Game.objects.create(
            starts_at=_aware(2025, 9, 12),
            home_team=home,
            away_team=away,
            competition=GameCompetition.LEAGUE,
            league=league_min,
        ),
        home,
        away,
    )


def test_base_clean_team_must_participate_in_game(Team: Any, Player: Any, league_min: Any) -> None:
    """Reject events referencing a team that does not play in the game."""
    game, home, away = _mk_game_basic(Team, league_min)
    third = Team.objects.create(league=league_min, name="HC Third EVT")
    p = Player.objects.create(first_name="S", last_name="1", jersey_number=11, position="forward", team=third)
    Goal = apps.get_model("powerplay_app", "Goal")
    goal = Goal(game=game, team=third, period=1, second_in_period=10, scorer=p)
    with pytest.raises(ValidationError):
        goal.full_clean()


def test_goal_requires_players_from_scoring_team_and_nomination(
    Team: Any, Player: Any, league_min: Any
) -> None:
    """Require scorer/assists to be nominated and belong to the scoring team."""
    game, home, away = _mk_game_basic(Team, league_min)
    scorer = Player.objects.create(first_name="A", last_name="S", jersey_number=9, position="forward", team=home)
    a1 = Player.objects.create(first_name="B", last_name="A1", jersey_number=12, position="forward", team=home)

    Goal = apps.get_model("powerplay_app", "Goal")

    g = Goal(game=game, team=home, period=1, second_in_period=15, scorer=scorer, assist_1=a1)
    with pytest.raises(ValidationError):
        g.full_clean()

    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    GameNomination.objects.create(game=game, player=scorer, team=home)
    GameNomination.objects.create(game=game, player=a1, team=home)
    g = Goal(game=game, team=home, period=1, second_in_period=16, scorer=scorer, assist_1=a1)
    g.full_clean()  # should not raise

    bad_scorer = Player.objects.create(first_name="X", last_name="Bad", jersey_number=30, position="forward", team=away)
    GameNomination.objects.create(game=game, player=bad_scorer, team=away)
    g2 = Goal(game=game, team=home, period=1, second_in_period=20, scorer=bad_scorer)
    with pytest.raises(ValidationError):
        g2.full_clean()


def test_goal_assist_conflicts(Team: Any, Player: Any, league_min: Any) -> None:
    """Disallow scorer to be listed as an assist and duplicate assists."""
    game, home, _ = _mk_game_basic(Team, league_min)
    scorer = Player.objects.create(first_name="A", last_name="S", jersey_number=13, position="forward", team=home)
    a1 = Player.objects.create(first_name="B", last_name="A1", jersey_number=14, position="forward", team=home)
    a2 = Player.objects.create(first_name="C", last_name="A2", jersey_number=15, position="forward", team=home)

    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    for p in (scorer, a1, a2):
        GameNomination.objects.create(game=game, player=p, team=home)

    Goal = apps.get_model("powerplay_app", "Goal")

    g1 = Goal(game=game, team=home, period=1, second_in_period=30, scorer=scorer, assist_1=scorer)
    with pytest.raises(ValidationError):
        g1.full_clean()

    g2 = Goal(game=game, team=home, period=1, second_in_period=31, scorer=scorer, assist_2=scorer)
    with pytest.raises(ValidationError):
        g2.full_clean()

    g3 = Goal(game=game, team=home, period=1, second_in_period=32, scorer=scorer, assist_1=a1, assist_2=a1)
    with pytest.raises(ValidationError):
        g3.full_clean()


def test_penalty_requires_player_from_team_and_nomination(
    Team: Any, Player: Any, league_min: Any
) -> None:
    """Require penalized player to be nominated and belong to the penalty team."""
    game, home, away = _mk_game_basic(Team, league_min)
    skater = Player.objects.create(first_name="P", last_name="X", jersey_number=16, position="forward", team=home)

    Penalty = apps.get_model("powerplay_app", "Penalty")

    p = Penalty(game=game, team=home, period=1, second_in_period=40, penalized_player=skater, minutes=2)
    with pytest.raises(ValidationError):
        p.full_clean()

    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    GameNomination.objects.create(game=game, player=skater, team=home)
    p_ok = Penalty(game=game, team=home, period=1, second_in_period=41, penalized_player=skater, minutes=2)
    p_ok.full_clean()  # should not raise

    other = Player.objects.create(first_name="O", last_name="Y", jersey_number=17, position="forward", team=away)
    GameNomination.objects.create(game=game, player=other, team=away)
    p_bad = Penalty(game=game, team=home, period=1, second_in_period=42, penalized_player=other, minutes=2)
    with pytest.raises(ValidationError):
        p_bad.full_clean()
