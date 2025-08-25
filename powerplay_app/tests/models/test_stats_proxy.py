# file: powerplay_app/tests/models/test_player_season_totals.py
"""Tests for the ``PlayerSeasonTotals`` proxy model behavior.

Coverage:
* Proxy model meta flags and Czech verbose names.
* Queryset access via proxy reads from the same table as ``Player``.
* Creating and updating through the proxy persists on the base model.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps

pytestmark = pytest.mark.django_db


def test_player_season_totals_is_proxy_and_verbose_names() -> None:
    """Validate proxy flag and Czech verbose names for the proxy model."""
    PlayerSeasonTotals = apps.get_model("powerplay_app", "PlayerSeasonTotals")
    assert PlayerSeasonTotals._meta.proxy is True
    assert PlayerSeasonTotals._meta.verbose_name == "Souhrnná statistika hráče"
    assert (
        PlayerSeasonTotals._meta.verbose_name_plural
        == "Souhrnné statistiky hráčů"
    )


def test_proxy_queryset_reads_same_table(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Ensure proxy queryset returns rows mapped to the same DB table as ``Player``."""
    team = Team.objects.create(league=league_min, name="HC Proxy")
    p = Player.objects.create(
        first_name="Jan",
        last_name="Proxy",
        jersey_number=77,
        position="forward",
        team=team,
    )

    PlayerSeasonTotals = apps.get_model("powerplay_app", "PlayerSeasonTotals")
    p_proxy = PlayerSeasonTotals.objects.get(pk=p.pk)

    assert p_proxy.pk == p.pk
    assert p_proxy.first_name == "Jan"
    # The proxy class instance is both PlayerSeasonTotals and Player
    assert isinstance(p_proxy, PlayerSeasonTotals)
    assert isinstance(p_proxy, Player)


def test_proxy_can_create_and_updates_persist_on_player(
    Player: Any, Team: Any, league_min: Any
) -> None:
    """Creating via proxy stores a ``Player`` row; updates via proxy persist on base."""
    PlayerSeasonTotals = apps.get_model("powerplay_app", "PlayerSeasonTotals")
    team = Team.objects.create(league=league_min, name="HC Proxy 2")

    # Create via proxy writes into the Player table
    p_proxy = PlayerSeasonTotals.objects.create(
        first_name="Eva",
        last_name="Totals",
        jersey_number=88,
        position="defense",
        team=team,
    )

    PlayerModel = apps.get_model("powerplay_app", "Player")
    p_base = PlayerModel.objects.get(pk=p_proxy.pk)

    assert p_base.first_name == "Eva"

    # Updating through the proxy reflects in the base model
    p_proxy.last_name = "Totalsova"
    p_proxy.save()
    p_base.refresh_from_db()
    assert p_base.last_name == "Totalsova"
