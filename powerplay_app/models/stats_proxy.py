# file: powerplay_app/models/stats_proxy.py
"""Proxy model exposing seasonal totals for players.

This module defines a Django **proxy model** that reuses the underlying
``Player`` database table while allowing a distinct admin/view layer focused on
per‑season totals. No database schema changes are introduced by a proxy model.

Notes:
    - All internal documentation is in English; user‑facing labels remain Czech.
    - Aggregations for totals should be implemented via querysets/services that
      operate on ``Player.stats`` (``PlayerStats``) and optionally filtered by
      season/league, not by adding fields here.
"""

from __future__ import annotations

from django.db import models

from .core import Player  # ``Player`` is defined in core.py


class PlayerSeasonTotals(Player):
    """Read‑only view of a player intended for seasonal totals in admin/UI.

    This is a proxy to ``Player``—it does not create a new table. Use it to
    register separate Django admin screens or specialized views without altering
    the base ``Player`` model or its schema.
    """

    class Meta:
        proxy = True
        verbose_name = "Souhrnná statistika hráče"
        verbose_name_plural = "Souhrnné statistiky hráčů"
