# file: powerplay_app/models/stats.py
"""Per‑game statistics model for players in the Powerplay domain.

Defines :class:`PlayerStats`, a single-row summary of a player's performance in
one game (points, goals, assists, shots, PIM, GA). Uniqueness is enforced per
``(player, game)`` to prevent duplicates.

Internal documentation is English; user‑facing labels remain Czech. Behavior and
schema are unchanged.
"""

from __future__ import annotations

from django.db import models


# --- Model -----------------------------------------------------------------


class PlayerStats(models.Model):
    """Aggregated statistics for a single player in a single game.

    Notes:
        - Uniqueness is enforced per (player, game) to avoid duplicate rows.
        - ``goals_against`` is primarily meaningful for goalies but stored for
          all players to keep the schema simple.
        - ``points`` is stored explicitly (not derived) to allow custom league
          rules or manual corrections.
    """

    player = models.ForeignKey(
        "powerplay_app.Player",
        on_delete=models.CASCADE,
        related_name="stats",
        verbose_name="Hráč",
    )
    game = models.ForeignKey(
        "powerplay_app.Game",
        on_delete=models.CASCADE,
        related_name="stats",
        verbose_name="Zápas",
    )

    points = models.PositiveIntegerField("Body", default=0)
    goals = models.PositiveIntegerField("Góly", default=0)
    assists = models.PositiveIntegerField("Asistence", default=0)
    shots = models.PositiveIntegerField("Střely", default=0)
    penalty_minutes = models.PositiveIntegerField("Trestné minuty", default=0)
    goals_against = models.PositiveIntegerField("Obdržené góly (gólmani)", default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "game"], name="uniq_stats_player_game")
        ]
        verbose_name = "Statistika hráče"
        verbose_name_plural = "Statistiky hráčů"

    @property
    def pim(self) -> int:
        return getattr(self, "minutes", 0) or 0

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Readable label combining player and game."""
        return f"{self.player} - {self.game}"
