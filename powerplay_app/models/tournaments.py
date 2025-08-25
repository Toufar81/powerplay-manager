# file: powerplay_app/models/tournaments.py
"""Tournament model and on-demand standings computation.

Defines :class:`Tournament`, which groups games and exposes a computed table of
team standings using a 3‑point system (win=3, draw=1, loss=0). Goal totals and
penalty minutes are aggregated across related games.

Internal documentation is in English; user‑facing labels remain Czech. Behavior
and schema are unchanged.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.db.models import F, Sum


class Tournament(models.Model):
    """A tournament grouping multiple games with aggregate standings.

    Standings are computed across all related games using a simple 3‑point
    system and include goal difference and aggregated penalty minutes from
    :class:`powerplay_app.models.stats.PlayerStats`.
    """

    name = models.CharField("Název turnaje", max_length=255)
    date_start = models.DateField("Začátek", blank=True, null=True)
    date_end = models.DateField("Konec", blank=True, null=True)
    games = models.ManyToManyField(
        "powerplay_app.Game", blank=True, related_name="tournaments", verbose_name="Zápasy"
    )

    class Meta:
        verbose_name = "Turnaj"
        verbose_name_plural = "Turnaje"

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Readable label for admin lists (tournament name)."""
        return self.name

    # --- Aggregates ---------------------------------------------------------

    def standings(self) -> list[dict[str, Any]]:
        """Compute and return a sorted standings table for this tournament.

        The result is a list of dictionaries with keys:
        ``team``, ``points``, ``wins``, ``draws``, ``losses``, ``goals_for``,
        ``goals_against``, ``penalty_minutes``. Sorting is by points (desc) and
        then goal difference (desc).

        Notes:
            ``PlayerStats`` is imported lazily to avoid circular imports.
        """
        from .stats import PlayerStats  # lazy import to avoid circular dependency

        teams: set[Any] = set()
        for g in self.games.select_related("home_team", "away_team").all():
            teams.add(g.home_team)
            teams.add(g.away_team)

        table: list[dict[str, Any]] = []
        for team in teams:
            home = self.games.filter(home_team=team)
            away = self.games.filter(away_team=team)

            wins = home.filter(score_home__gt=F("score_away")).count() + away.filter(
                score_away__gt=F("score_home")
            ).count()
            draws = home.filter(score_home=F("score_away")).count() + away.filter(
                score_away=F("score_home")
            ).count()
            losses = home.filter(score_home__lt=F("score_away")).count() + away.filter(
                score_away__lt=F("score_home")
            ).count()
            points = wins * 3 + draws

            goals_for = (home.aggregate(s=Sum("score_home"))[
                "s"
            ] or 0) + (away.aggregate(s=Sum("score_away"))["s"] or 0)
            goals_against = (home.aggregate(s=Sum("score_away"))[
                "s"
            ] or 0) + (away.aggregate(s=Sum("score_home"))["s"] or 0)
            penalty_minutes = (
                PlayerStats.objects.filter(player__team=team, game__in=self.games.all()).aggregate(
                    s=Sum("penalty_minutes")
                )["s"]
                or 0
            )

            table.append(
                {
                    "team": team,
                    "points": points,
                    "wins": wins,
                    "draws": draws,
                    "losses": losses,
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "penalty_minutes": penalty_minutes,
                }
            )

        # Sort by points desc, then goal difference desc.
        return sorted(table, key=lambda x: (-x["points"], -(x["goals_for"] - x["goals_against"])) )
