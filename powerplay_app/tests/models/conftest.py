# file: powerplay_app/tests/conftest.py
"""Common pytest fixtures for powerplay_app tests.

Provides convenient accessors for core models (resolved dynamically via
``apps.get_model``) and minimal data builders used across test modules.

Fixtures:
    - ``League``, ``Stadium``, ``Team``, ``Country``, ``Player``: Model classes.
    - ``league_min``: Minimal league with a fixed 2025/2026 season date range.
    - ``team_min``: Minimal team bound to ``league_min``.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

import pytest
from django.apps import apps

APP: str = "powerplay_app"


@pytest.fixture
def League() -> Any:
    """Return the League model class."""
    return apps.get_model(APP, "League")


@pytest.fixture
def Stadium() -> Any:
    """Return the Stadium model class."""
    return apps.get_model(APP, "Stadium")


@pytest.fixture
def Team() -> Any:
    """Return the Team model class."""
    return apps.get_model(APP, "Team")


@pytest.fixture
def Country() -> Any:
    """Return the Country model class."""
    return apps.get_model(APP, "Country")


@pytest.fixture
def Player() -> Any:
    """Return the Player model class."""
    return apps.get_model(APP, "Player")


@pytest.fixture
def league_min(League: Any) -> Any:
    """Create a minimal league with a stable season date range.

    Ensures consistent season bounds for dependent tests.
    """
    return League.objects.create(
        name="Test League",
        season="2025/2026",
        date_start=_dt.date(2025, 8, 1),
        date_end=_dt.date(2026, 5, 1),
    )


@pytest.fixture
def team_min(Team: Any, league_min: Any) -> Any:
    """Create a minimal team bound to ``league_min``."""
    return Team.objects.create(league=league_min, name="HC Python")
