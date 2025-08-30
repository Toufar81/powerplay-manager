import io
import types

import pytest
from django.apps import apps
from django.core.management import call_command
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _run_sync_with_stub(monkeypatch, league, teams_by_id, matches):
    """
    Patchne fetcher uvnitř management commandu a spustí `sync_results`
    pro zadanou ligu. Vrací zachycený stdout (jen pro debug).
    """
    cmd_mod = __import__("powerplay_app.management.commands.sync_results", fromlist=["*"])

    def fake_fetch_teams_and_matches(**kwargs):
        return teams_by_id, matches

    monkeypatch.setattr(cmd_mod, "fetch_teams_and_matches", fake_fetch_teams_and_matches, raising=True)
    out = io.StringIO()
    call_command("sync_results", league_id=league.id, headful=False, stdout=out)
    return out.getvalue()


def _mk_league(name, season):
    League = apps.get_model("powerplay_app", "League")
    # Rozsah sezóny, aby pokryl testovací zápasy
    return League.objects.create(
        name=name,
        season=season,
        date_start=timezone.datetime(2025, 8, 1).date(),
        date_end=timezone.datetime(2026, 5, 1).date(),
    )


def test_delete_one_league_preserves_other_league_and_resync_relinks_teams(monkeypatch):
    League = apps.get_model("powerplay_app", "League")
    Team = apps.get_model("powerplay_app", "Team")
    Game = apps.get_model("powerplay_app", "Game")

    # --- Arrange: 2 ligy ---
    liga_a = _mk_league("Liga A", "2025/2026")
    liga_b = _mk_league("Liga B", "2025/2026")

    # Data pro import do ligy A
    teams_a = {2: "HC A", 6: "HC B"}
    matches_a = [
        {
            "id": 101,
            "season_id": 1,
            "home_team_id": 2,
            "away_team_id": 6,
            "home_score": 3,
            "away_score": 2,
            "match_date": "2026-02-13T18:00:00.000Z",
            "status": "finished",
            "venue": "PORUBA",
            "record_image": None,
        }
    ]

    # Data pro import do ligy B
    teams_b = {3: "HC C", 4: "HC D"}
    matches_b = [
        {
            "id": 202,
            "season_id": 2,
            "home_team_id": 3,
            "away_team_id": 4,
            "home_score": 1,
            "away_score": 1,
            "match_date": "2026-03-10T19:30:00.000Z",
            "status": "finished",
            "venue": None,
            "record_image": None,
        }
    ]

    # --- Import do ligy A i B ---
    _run_sync_with_stub(monkeypatch, liga_a, teams_a, matches_a)
    _run_sync_with_stub(monkeypatch, liga_b, teams_b, matches_b)

    assert Game.objects.count() == 2
    assert Team.objects.filter(name__in=["HC A", "HC B"], league=liga_a).count() == 2
    assert Team.objects.filter(name__in=["HC C", "HC D"], league=liga_b).count() == 2

    # --- Act: smažeme pouze ligu A ---
    liga_a.delete()

    # TÝMY z ligy A zůstávají, ale mají league=NULL
    assert Team.objects.filter(name__in=["HC A", "HC B"]).count() == 2
    assert Team.objects.filter(name__in=["HC A", "HC B"], league__isnull=True).count() == 2

    # Zápasy ligy B zůstávají nedotčeny
    assert Game.objects.count() == 1
    g_b = Game.objects.get()
    assert g_b.league_id == liga_b.id

    # --- Act: znovu importujeme do (nově vytvořené) ligy A a ověříme re-link týmů ---
    # Vytvoříme „novou“ ligu A se stejným jménem/sezónou (simulace nové sezónní entity po smazání)
    liga_a2 = _mk_league("Liga A", "2025/2026")

    # re-sync: stejné názvy týmů → příkaz by měl existující záznamy týmů přesunout do ligy A
    _run_sync_with_stub(monkeypatch, liga_a2, teams_a, matches_a)

    # Týmy HC A / HC B jsou znovu přirazeny do (nové) ligy A
    assert Team.objects.filter(name__in=["HC A", "HC B"], league=liga_a2).count() == 2

    # Je znovu vytvořen i zápas ligy A
    assert Game.objects.filter(league=liga_a2).count() == 1

    # A zápas ligy B stále existuje
    assert Game.objects.filter(league=liga_b).count() == 1
