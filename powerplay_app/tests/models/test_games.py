# file: powerplay_app/tests/games/test_games.py
"""Validation and constraint tests for Game-related models.

Coverage:
* ``Game.clean`` rules for teams, league/tournament coupling, and season bounds.
* Unique constraints for league and friendly competitions.
* ``GameNomination`` validation and autofill behavior.
* ``Line`` and ``LineAssignment`` validation rules and constraints.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from powerplay_app.models.games import GameCompetition, LineSlot

pytestmark = pytest.mark.django_db


def _aware(y: int, m: int, d: int, hh: int = 18, mm: int = 0) -> dt.datetime:
    """Create a timezone-aware datetime in the current timezone."""
    tz = timezone.get_current_timezone()
    return timezone.make_aware(dt.datetime(y, m, d, hh, mm), tz)


def _mk_game(
    Team: Any,
    league: Any,
    home_name: str = "HC A",
    away_name: str = "HC B",
    comp: GameCompetition = GameCompetition.LEAGUE,
) -> Any:
    """Construct an unsaved ``Game`` instance with two newly created teams.

    The league is attached only for league competition; otherwise left ``None``.
    """
    home = Team.objects.create(league=league, name=home_name)
    away = Team.objects.create(league=league, name=away_name)
    Game = apps.get_model("powerplay_app", "Game")
    return Game(
        starts_at=_aware(2025, 9, 1, 18, 0),
        home_team=home,
        away_team=away,
        competition=comp,
        league=league if comp == GameCompetition.LEAGUE else None,
    )


# --- Game.clean -----------------------------------------------------------


def test_game_teams_must_be_distinct(Team: Any, league_min: Any) -> None:
    """Reject games where home and away teams are identical."""
    Game = apps.get_model("powerplay_app", "Game")
    t = Team.objects.create(league=league_min, name="HC X")
    g = Game(
        starts_at=_aware(2025, 9, 1),
        home_team=t,
        away_team=t,
        competition=GameCompetition.LEAGUE,
        league=league_min,
    )
    with pytest.raises(ValidationError):
        g.full_clean()


def test_game_league_requires_league_and_forbids_tournament(
    Team: Any, league_min: Any
) -> None:
    """For league games, require ``league`` and forbid ``tournament``."""
    Game = apps.get_model("powerplay_app", "Game")
    home = Team.objects.create(league=league_min, name="HC H")
    away = Team.objects.create(league=league_min, name="HC A")

    g = Game(
        starts_at=_aware(2025, 9, 1),
        home_team=home,
        away_team=away,
        competition=GameCompetition.LEAGUE,
    )
    with pytest.raises(ValidationError):
        g.full_clean()

    Tournament = apps.get_model("powerplay_app", "Tournament")
    tour = Tournament.objects.create(name="Cup")
    g = Game(
        starts_at=_aware(2025, 9, 1),
        home_team=home,
        away_team=away,
        competition=GameCompetition.LEAGUE,
        league=league_min,
        tournament=tour,
    )
    with pytest.raises(ValidationError):
        g.full_clean()


def test_game_league_teams_must_belong_to_that_league(
    Team: Any, league_min: Any
) -> None:
    """Ensure both teams belong to the selected league for league games."""
    Game = apps.get_model("powerplay_app", "Game")
    OtherLeague = apps.get_model("powerplay_app", "League")
    other = OtherLeague.objects.create(
        name="Jiná Liga",
        season="2025/2026",
        date_start=dt.date(2025, 8, 1),
        date_end=dt.date(2026, 5, 1),
    )

    home = Team.objects.create(league=league_min, name="HC Home")
    away = Team.objects.create(league=other, name="HC Away")

    g = Game(
        starts_at=_aware(2025, 9, 1),
        home_team=home,
        away_team=away,
        competition=GameCompetition.LEAGUE,
        league=league_min,
    )
    with pytest.raises(ValidationError):
        g.full_clean()


def test_game_league_date_must_be_within_season(Team: Any, league_min: Any) -> None:
    """Validate that game date falls within the league season bounds."""
    g_in = _mk_game(Team, league_min)
    g_in.full_clean()  # should not raise

    Game = apps.get_model("powerplay_app", "Game")
    home = Team.objects.create(league=league_min, name="HC H2")
    away = Team.objects.create(league=league_min, name="HC A2")
    g_out = Game(
        starts_at=_aware(2025, 7, 1),
        home_team=home,
        away_team=away,
        competition=GameCompetition.LEAGUE,
        league=league_min,
    )
    with pytest.raises(ValidationError):
        g_out.full_clean()


def test_game_friendly_forbids_league_or_tournament(
    Team: Any, league_min: Any
) -> None:
    """For friendly games, forbid ``league`` and ``tournament`` fields."""
    Game = apps.get_model("powerplay_app", "Game")
    home = Team.objects.create(league=league_min, name="HC H3")
    away = Team.objects.create(league=league_min, name="HC A3")

    g = Game(
        starts_at=_aware(2025, 9, 1),
        home_team=home,
        away_team=away,
        competition=GameCompetition.FRIENDLY,
        league=league_min,
    )
    with pytest.raises(ValidationError):
        g.full_clean()

    Tournament = apps.get_model("powerplay_app", "Tournament")
    tour = Tournament.objects.create(name="Cup2")
    g = Game(
        starts_at=_aware(2025, 9, 1),
        home_team=home,
        away_team=away,
        competition=GameCompetition.FRIENDLY,
        tournament=tour,
    )
    with pytest.raises(ValidationError):
        g.full_clean()


# --- Game unique constraints ---------------------------------------------


def test_game_unique_league_constraint(Team: Any, league_min: Any) -> None:
    """Disallow duplicate league games with same teams and start time."""
    Game = apps.get_model("powerplay_app", "Game")
    home = Team.objects.create(league=league_min, name="HC UH1")
    away = Team.objects.create(league=league_min, name="HC UA1")
    when = _aware(2025, 9, 2)

    Game.objects.create(
        starts_at=when,
        home_team=home,
        away_team=away,
        competition=GameCompetition.LEAGUE,
        league=league_min,
    )
    with pytest.raises(IntegrityError):
        Game.objects.create(
            starts_at=when,
            home_team=home,
            away_team=away,
            competition=GameCompetition.LEAGUE,
            league=league_min,
        )


def test_game_unique_friendly_constraint(Team: Any, league_min: Any) -> None:
    """Disallow duplicate friendly games with same teams and start time."""
    Game = apps.get_model("powerplay_app", "Game")
    home = Team.objects.create(league=league_min, name="HC UH2")
    away = Team.objects.create(league=league_min, name="HC UA2")
    when = _aware(2025, 9, 3)

    Game.objects.create(
        starts_at=when,
        home_team=home,
        away_team=away,
        competition=GameCompetition.FRIENDLY,
    )
    with pytest.raises(IntegrityError):
        Game.objects.create(
            starts_at=when,
            home_team=home,
            away_team=away,
            competition=GameCompetition.FRIENDLY,
        )


# --- GameNomination -------------------------------------------------------


def _mk_game_basic(Team: Any, league_min: Any) -> tuple[Any, Any, Any]:
    """Create and save a league game with two teams; return game and teams."""
    Game = apps.get_model("powerplay_app", "Game")
    home = Team.objects.create(league=league_min, name="HC HN")
    away = Team.objects.create(league=league_min, name="HC AN")
    return (
        Game.objects.create(
            starts_at=_aware(2025, 9, 10),
            home_team=home,
            away_team=away,
            competition=GameCompetition.LEAGUE,
            league=league_min,
        ),
        home,
        away,
    )


def test_nomination_player_must_belong_to_team(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Reject nomination if player's team does not match the nomination team."""
    game, home, away = _mk_game_basic(Team, league_min)
    other_team = Team.objects.create(league=league_min, name="HC Other")
    p = Player.objects.create(
        first_name="A", last_name="B", jersey_number=1, position="forward", team=other_team
    )
    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    nom = GameNomination(game=game, player=p, team=home)
    with pytest.raises(ValidationError):
        nom.full_clean()


def test_nomination_team_must_participate(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Reject nomination if the nominated team does not play in the game."""
    game, home, away = _mk_game_basic(Team, league_min)
    third = Team.objects.create(league=league_min, name="HC Third2")
    p = Player.objects.create(first_name="A", last_name="B", jersey_number=2, position="forward", team=home)
    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    nom = GameNomination(game=game, player=p, team=third)
    with pytest.raises(ValidationError):
        nom.full_clean()


def test_nomination_autofills_team_from_player_on_save(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Autofill missing ``team`` from the player's team on save."""
    game, home, _ = _mk_game_basic(Team, league_min)
    p = Player.objects.create(first_name="A", last_name="B", jersey_number=3, position="forward", team=home)
    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    nom = GameNomination(game=game, player=p)
    # Do not call full_clean before save — ``team`` is required but set in ``save``.
    nom.save()
    nom.refresh_from_db()
    assert nom.team_id == p.team_id
    # After team is assigned, the object is valid
    nom.full_clean()


def test_nomination_unique_game_player(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Enforce unique (game, player) nominations."""
    game, home, _ = _mk_game_basic(Team, league_min)
    p = Player.objects.create(first_name="A", last_name="B", jersey_number=4, position="forward", team=home)
    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    GameNomination.objects.create(game=game, player=p, team=home)
    with pytest.raises(IntegrityError):
        GameNomination.objects.create(game=game, player=p, team=home)


# --- Line -----------------------------------------------------------------


def test_line_team_must_participate_in_game(Team: Any, league_min: Any) -> None:
    """Reject lines created for teams not participating in the game."""
    game, home, _ = _mk_game_basic(Team, league_min)
    third = Team.objects.create(league=league_min, name="HC Third2")
    Line = apps.get_model("powerplay_app", "Line")
    line = Line(game=game, team=third, line_number=1)
    with pytest.raises(ValidationError):
        line.full_clean()


def test_line_unique_together(Team: Any, league_min: Any) -> None:
    """Enforce unique (game, team, line_number) for lines."""
    game, home, _ = _mk_game_basic(Team, league_min)
    Line = apps.get_model("powerplay_app", "Line")
    Line.objects.create(game=game, team=home, line_number=1)
    with pytest.raises(IntegrityError):
        Line.objects.create(game=game, team=home, line_number=1)


# --- LineAssignment -------------------------------------------------------


def test_assignment_player_must_be_from_line_team(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Reject assignments where player's team differs from the line's team."""
    game, home, away = _mk_game_basic(Team, league_min)
    Line = apps.get_model("powerplay_app", "Line")
    line = Line.objects.create(game=game, team=home, line_number=1)
    p = Player.objects.create(first_name="X", last_name="Y", jersey_number=6, position="forward", team=away)
    LineAssignment = apps.get_model("powerplay_app", "LineAssignment")
    la = LineAssignment(line=line, player=p, slot=LineSlot.LW)
    with pytest.raises(ValidationError):
        la.full_clean()


def test_assignment_goalie_line_rules(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Enforce goalie line number and goalie-only slot for goalies."""
    game, home, _ = _mk_game_basic(Team, league_min)
    Line = apps.get_model("powerplay_app", "Line")
    goalie_line = Line.objects.create(game=game, team=home, line_number=0)
    LineAssignment = apps.get_model("powerplay_app", "LineAssignment")

    la = LineAssignment(line=goalie_line, slot=LineSlot.LW)
    with pytest.raises(ValidationError):
        la.full_clean()

    skater = apps.get_model("powerplay_app", "Player").objects.create(
        first_name="S", last_name="K", jersey_number=7, position="forward", team=home
    )
    la2 = LineAssignment(line=goalie_line, slot=LineSlot.G, player=skater)
    with pytest.raises(ValidationError):
        la2.full_clean()

    goalie = apps.get_model("powerplay_app", "Player").objects.create(
        first_name="G", last_name="K", jersey_number=1, position="goalie", team=home
    )
    la3 = LineAssignment(line=goalie_line, slot=LineSlot.G, player=goalie)
    la3.full_clean()  # should not raise


def test_assignment_same_player_cannot_be_in_multiple_lines_in_same_game(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Disallow the same player to appear in multiple lines within a game."""
    game, home, _ = _mk_game_basic(Team, league_min)
    Line = apps.get_model("powerplay_app", "Line")
    line1 = Line.objects.create(game=game, team=home, line_number=1)
    line2 = Line.objects.create(game=game, team=home, line_number=2)
    p = Player.objects.create(first_name="U", last_name="V", jersey_number=8, position="forward", team=home)

    LineAssignment = apps.get_model("powerplay_app", "LineAssignment")
    LineAssignment.objects.create(line=line1, player=p, slot=LineSlot.LW)

    la = LineAssignment(line=line2, player=p, slot=LineSlot.C)
    with pytest.raises(ValidationError):
        la.full_clean()
