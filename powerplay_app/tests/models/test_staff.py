# file: powerplay_app/tests/staff/test_staff.py
"""Tests for the ``Staff`` model meta, relations, defaults, and validation.

Coverage:
* Model verbose names and default ordering.
* Reverse relation from ``Team`` via ``staff_members``.
* Required fields and default values.
* Phone number validator acceptance and rejection cases.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def _mk_team(Team: Any, league_min: Any, name: str = "HC Staff") -> Any:
    """Create and return a minimal team in ``league_min`` with the given name."""
    return Team.objects.create(league=league_min, name=name)


# --- Meta ------------------------------------------------------------------


def test_staff_meta_verbose_and_ordering() -> None:
    """Validate Czech verbose names and default ordering on ``Staff`` model."""
    Staff = apps.get_model("powerplay_app", "Staff")
    assert Staff._meta.verbose_name == "Člen realizačního týmu"
    assert Staff._meta.verbose_name_plural == "Realizační tým"
    assert Staff._meta.ordering == ("team", "order", "last_name")


# --- Relations -------------------------------------------------------------


def test_staff_related_name_on_team(Team: Any, league_min: Any) -> None:
    """Ensure ``team.staff_members`` includes created staff record."""
    Staff = apps.get_model("powerplay_app", "Staff")
    team = _mk_team(Team, league_min)
    s = Staff.objects.create(team=team, first_name="Jan", last_name="Novák", role="Trenér")
    assert s in team.staff_members.all()


# --- Defaults & Required fields -------------------------------------------


def test_staff_required_fields_and_defaults(Team: Any, league_min: Any) -> None:
    """Allow optional fields to be empty; defaults ``is_active=True``, ``order=0``."""
    Staff = apps.get_model("powerplay_app", "Staff")
    team = _mk_team(Team, league_min)
    s = Staff(team=team, first_name="Eva", last_name="Svobodová", role="Manažer")
    s.full_clean()
    s.save()
    assert s.is_active is True
    assert s.order == 0


# --- Validators ------------------------------------------------------------


def test_staff_phone_validator_accepts_valid_and_rejects_invalid(
    Team: Any, league_min: Any
) -> None:
    """Accept common numeric phone formats; reject non-numeric/too-long values."""
    Staff = apps.get_model("powerplay_app", "Staff")
    team = _mk_team(Team, league_min)

    # valid examples
    ok = Staff(team=team, first_name="Ok", last_name="Phone", role="Asistent", phone="+420 123 456 789")
    ok.full_clean()  # should not raise

    ok2 = Staff(team=team, first_name="Ok2", last_name="Phone2", role="Asistent", phone="123-456-789")
    ok2.full_clean()  # should not raise

    # invalid: contains letters
    bad = Staff(team=team, first_name="Bad", last_name="Phone", role="Asistent", phone="abc123")
    with pytest.raises(ValidationError):
        bad.full_clean()

    # invalid: too long (>20 chars allowed by regex)
    long_number = "123456789012345678901"  # 21 chars
    bad2 = Staff(team=team, first_name="Bad2", last_name="Phone2", role="Asistent", phone=long_number)
    with pytest.raises(ValidationError):
        bad2.full_clean()
