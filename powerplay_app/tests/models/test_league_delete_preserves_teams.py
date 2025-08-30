import pytest
from django.utils import timezone

from django.apps import apps

pytestmark = pytest.mark.django_db


def _mk_league(name="Liga X", season="2025/2026"):
    League = apps.get_model("powerplay_app", "League")
    return League.objects.create(
        name=name,
        season=season,
        date_start=timezone.now().date(),
        date_end=timezone.now().date(),
    )


def _mk_team(league, name):
    Team = apps.get_model("powerplay_app", "Team")
    return Team.objects.create(name=name, league=league)


def _mk_player(team, num, position="goalie"):
    Player = apps.get_model("powerplay_app", "Player")
    return Player.objects.create(
        first_name=f"P{num}",
        last_name="Test",
        jersey_number=num,
        position=position,
        team=team,
    )


def _mk_game(league, home, away):
    Game = apps.get_model("powerplay_app", "Game")
    from powerplay_app.models.games import GameCompetition
    # starts_at do dnešního dne, aby prošla validace sezóny
    dt = timezone.now().replace(hour=18, minute=0, second=0, microsecond=0)
    return Game.objects.create(
        starts_at=dt,
        home_team=home,
        away_team=away,
        competition=GameCompetition.LEAGUE,
        league=league,
        score_home=0,
        score_away=0,
    )


def test_delete_league_keeps_teams_and_nulls_fk():
    """Smazání ligy zachová týmy (league=NULL) a odstraní zápasy + jejich vazby."""
    # models
    League = apps.get_model("powerplay_app", "League")
    Team = apps.get_model("powerplay_app", "Team")
    Game = apps.get_model("powerplay_app", "Game")
    Line = apps.get_model("powerplay_app", "Line")
    LineAssignment = apps.get_model("powerplay_app", "LineAssignment")
    GameNomination = apps.get_model("powerplay_app", "GameNomination")

    # Arrange
    league = _mk_league("Liga DEL", "2025/2026")
    home = _mk_team(league, "HOME-KLUB")
    away = _mk_team(league, "AWAY-KLUB")

    g = _mk_game(league, home, away)

    # nominace (aby bylo co kaskádově mazat)
    ph = _mk_player(home, 1, position="goalie")
    pa = _mk_player(away, 2, position="goalie")
    GameNomination.objects.create(game=g, team=home, player=ph)
    GameNomination.objects.create(game=g, team=away, player=pa)

    # lajny + přiřazení
    ln_h0 = Line.objects.create(game=g, team=home, line_number=0)
    la_hg = LineAssignment.objects.create(line=ln_h0, player=ph, slot="G")
    ln_a0 = Line.objects.create(game=g, team=away, line_number=0)
    la_ag = LineAssignment.objects.create(line=ln_a0, player=pa, slot="G")

    # Sanity
    assert League.objects.count() == 1
    assert Team.objects.count() == 2
    assert Game.objects.count() == 1
    assert Line.objects.count() == 2
    assert LineAssignment.objects.count() == 2
    assert GameNomination.objects.count() == 2

    # Act — smažeme ligu
    league.delete()

    # Assert — TÝMY zůstávají, jen league=NULL
    assert Team.objects.count() == 2
    for t in Team.objects.all():
        assert t.league_id is None

    # Assert — VŠE navázané přes Game je pryč
    assert Game.objects.count() == 0
    assert Line.objects.count() == 0
    assert LineAssignment.objects.count() == 0
    assert GameNomination.objects.count() == 0
