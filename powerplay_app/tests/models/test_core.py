# file: powerplay_app/tests/models/test_models.py
"""Model behavior tests for core entities (League, Stadium, Team, Country, Player).

Coverage:
* League: season autofill, date validation, unique constraints, string format.
* Stadium/Team/Country: string representation and relationships.
* Player: jersey number uniqueness per team and photo URL behavior.

Docstrings and internal comments are in English; user-facing strings remain
Czech where present. No behavior changes.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# --- League ---------------------------------------------------------------


def test_league_autofills_season_when_blank(League: Any) -> None:
    """Ensure ``season`` is auto-filled when left blank based on date range."""
    league = League(
        name="Liga",
        season="",
        date_start=dt.date(2025, 8, 1),
        date_end=dt.date(2026, 5, 1),
    )
    league.save()
    assert league.season == "2025/2026"


def test_league_clean_rejects_end_before_start(League: Any) -> None:
    """Reject leagues where ``date_end`` is earlier than ``date_start``."""
    league = League(
        name="Liga",
        season="2025/2026",
        date_start=dt.date(2026, 5, 1),
        date_end=dt.date(2025, 8, 1),
    )
    with pytest.raises(ValidationError):
        league.full_clean()


def test_league_unique_name_season(League: Any) -> None:
    """Enforce uniqueness of (name, season)."""
    League.objects.create(
        name="Praha Liga",
        season="2024/2025",
        date_start=dt.date(2024, 8, 1),
        date_end=dt.date(2025, 5, 1),
    )
    with pytest.raises(IntegrityError):
        League.objects.create(
            name="Praha Liga",
            season="2024/2025",
            date_start=dt.date(2024, 8, 1),
            date_end=dt.date(2025, 5, 1),
        )


def test_league_str_includes_name_and_season(League: Any) -> None:
    """Return ``"<name> <season>"`` in ``__str__``."""
    l = League(
        name="NHL",
        season="2025/2026",
        date_start=dt.date(2025, 8, 1),
        date_end=dt.date(2026, 5, 1),
    )
    assert str(l) == "NHL 2025/2026"


# --- Stadium --------------------------------------------------------------


def test_stadium_str_is_name(Stadium: Any) -> None:
    """Return stadium ``name`` in ``__str__``."""
    s = Stadium.objects.create(name="O2 Arena")
    assert str(s) == "O2 Arena"


# --- Team -----------------------------------------------------------------


def test_team_unique_name(Team: Any, league_min: Any) -> None:
    """Enforce team name uniqueness within a league."""
    Team.objects.create(league=league_min, name="HC Flames")
    with pytest.raises(IntegrityError):
        Team.objects.create(league=league_min, name="HC Flames")


def test_league_related_name_teams(Team: Any, league_min: Any) -> None:
    """Expose reverse relation ``league.teams`` including created team."""
    t = Team.objects.create(league=league_min, name="HC Vary")
    assert t in league_min.teams.all()


def test_team_str_is_name(Team: Any, league_min: Any) -> None:
    """Return team ``name`` in ``__str__``."""
    t = Team.objects.create(league=league_min, name="HC Python")
    assert str(t) == "HC Python"


# --- Country --------------------------------------------------------------


def test_country_str_format(Country: Any) -> None:
    """Return ``"<name> (<iso_code>)"`` in ``__str__``."""
    c = Country.objects.create(name="Česko", iso_code="CZE")
    assert str(c) == "Česko (CZE)"


# --- Player ---------------------------------------------------------------


def test_player_unique_jersey_per_team(Player: Any, team_min: Any) -> None:
    """Enforce jersey number uniqueness per team."""
    Player.objects.create(
        first_name="Jan",
        last_name="Novák",
        jersey_number=10,
        position="forward",
        team=team_min,
    )
    with pytest.raises(IntegrityError):
        Player.objects.create(
            first_name="Petr",
            last_name="Svoboda",
            jersey_number=10,
            position="forward",
            team=team_min,
        )


def test_player_same_jersey_allowed_different_team(
    Player: Any, Team: Any, league_min: Any, team_min: Any
) -> None:
    """Allow the same jersey number across different teams."""
    team2 = Team.objects.create(league=league_min, name="HC Django")
    Player.objects.create(
        first_name="Jan",
        last_name="Novák",
        jersey_number=10,
        position="forward",
        team=team_min,
    )
    # Should not raise
    Player.objects.create(
        first_name="Pavel",
        last_name="Horák",
        jersey_number=10,
        position="forward",
        team=team2,
    )


def test_player_photo_url_fallback_without_photo(Player: Any, team_min: Any) -> None:
    """Provide default player photo URL when no photo is uploaded."""
    p = Player.objects.create(
        first_name="Anna",
        last_name="Kovářová",
        jersey_number=9,
        position="defense",
        team=team_min,
    )
    url = p.photo_url()
    assert url.endswith("powerplay_app/img/default_player.png")


def test_player_photo_url_when_photo_present(
    Player: Any, team_min: Any, tmp_path: Any, settings: Any
) -> None:
    """Return MEDIA-based URL when a player photo is present."""
    settings.MEDIA_ROOT = tmp_path.as_posix()
    settings.MEDIA_URL = "/media/"
    image_content = b"testimg"
    f = SimpleUploadedFile("p.jpg", image_content, content_type="image/jpeg")
    p = Player.objects.create(
        first_name="Lukas",
        last_name="Sedlak",
        jersey_number=20,
        position="forward",
        team=team_min,
        photo=f,
    )
    url = p.photo_url()
    assert url.startswith("/media/")
    assert "player_photos/" in url
