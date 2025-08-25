# file: powerplay_app/services/stats.py
"""Statistics helpers and recomputation routines.

Internal documentation is in English; user-facing strings remain Czech
(there are none here). Behavior is preserved. This module adds
Google-style docstrings, type hints, and light formatting.

Provided utilities:
    - :func:`player_season_totals_qs` – annotated totals for public FE, based on
      the ``PlayerSeasonTotals`` proxy.
    - :func:`games_for_team` – helper to list a team's games (home/away).
    - :func:`recompute_game` – recompute game score and per-game ``PlayerStats``
      from ``Goal``/``Penalty`` events and goalie assignments.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Sum, Value, F, Q
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet

from powerplay_app.models import (
    Game,
    Goal,
    Penalty,
    Player,
    PlayerStats,
    LineAssignment,
    LineSlot,
    Team,
)
from powerplay_app.models.stats_proxy import PlayerSeasonTotals


__all__ = [
    "player_season_totals_qs",
    "games_for_team",
    "recompute_game",
]


def player_season_totals_qs(team: Team) -> QuerySet[PlayerSeasonTotals]:
    """Return annotated season totals for players of a given team.

    The query mirrors the admin proxy aggregations so it can be reused on the
    public frontend without duplicating logic.

    Annotations:
        - ``games_played``: distinct count of nominated games.
        - ``goals`` / ``assists`` / ``points`` / ``penalty_minutes``.
        - ``goals_against``: computed from game scores for goalies assigned to
          line 0 (slot ``G``), split by home/away side.

    Args:
        team (Team): Team whose players should be aggregated.

    Returns:
        QuerySet[PlayerSeasonTotals]: Players with additional annotation fields.

    Side Effects:
        None. The returned queryset is lazily evaluated and does not modify the
        database until acted upon.

    Raises:
        None.
    """
    qs: QuerySet[PlayerSeasonTotals] = PlayerSeasonTotals.objects.filter(team=team)

    qs = qs.annotate(
        games_played=Coalesce(Count("nominations__game", distinct=True), Value(0)),
        goals=Coalesce(Count("goals_scored"), Value(0)),
        assists=Coalesce(Count("assists_primary") + Count("assists_secondary"), Value(0)),
        penalty_minutes=Coalesce(Sum("penalty__minutes"), Value(0)),
    ).annotate(points=F("goals") + F("assists"))

    ga_home = Coalesce(
        Sum(
            "lineassignment__line__game__score_away",
            filter=Q(
                lineassignment__slot=LineSlot.G,
                lineassignment__line__line_number=0,
                lineassignment__line__game__home_team=F("team"),
            ),
        ),
        Value(0),
    )
    ga_away = Coalesce(
        Sum(
            "lineassignment__line__game__score_home",
            filter=Q(
                lineassignment__slot=LineSlot.G,
                lineassignment__line__line_number=0,
                lineassignment__line__game__away_team=F("team"),
            ),
        ),
        Value(0),
    )
    qs = qs.annotate(goals_against=ga_home + ga_away)
    return qs


def games_for_team(team: Team) -> QuerySet[Game]:
    """Return all games where the team is home or away.

    Args:
        team (Team): Team whose games should be listed.

    Returns:
        QuerySet[Game]: Lazily evaluated queryset of the team's games with
        related ``home_team`` and ``away_team`` preloaded.

    Side Effects:
        None. The function only constructs a queryset and does not hit the
        database until the queryset is evaluated.

    Raises:
        None.
    """
    return (
        Game.objects.select_related("home_team", "away_team")
        .filter(Q(home_team=team) | Q(away_team=team))
    )


def recompute_game(game: Game) -> None:
    """Recompute a game's score and per-player stats from atomic events.

    What is recomputed:
        - Game score (from ``Goal`` events per team).
        - ``PlayerStats`` for the given game: goals, assists, points,
          penalty minutes, and goals against for goalies on line 0.

    Constraints/assumptions:
        - Goalie GA is assigned to players occupying slot ``G`` in line 0 for
          that game. Empty slots are ignored.
        - If a player appears multiple times as goalie for the same game
          (misconfiguration), the last save wins but the value is identical.

    Args:
        game (Game): Game instance whose statistics should be recomputed.

    Returns:
        None: The function updates the database in place.

    Side Effects:
        Persists updated ``Game`` scores and ``PlayerStats`` records to the
        database.

    Raises:
        None.
    """
    home_id = game.home_team_id
    away_id = game.away_team_id

    # --- Score ---
    goals_per_team = (
        Goal.objects.filter(game=game).values("team").annotate(cnt=Count("id"))
    )
    score_map: dict[int | None, int] = {row["team"]: row["cnt"] for row in goals_per_team}
    game.score_home = score_map.get(home_id, 0)
    game.score_away = score_map.get(away_id, 0)
    game.save(update_fields=["score_home", "score_away"])

    # --- Reset per-game stats ---
    PlayerStats.objects.filter(game=game).update(
        points=0, goals=0, assists=0, penalty_minutes=0, goals_against=0
    )

    # --- Goals ---
    for row in Goal.objects.filter(game=game).values("scorer").annotate(c=Count("id")):
        stats, _ = PlayerStats.objects.get_or_create(player_id=row["scorer"], game=game)
        stats.goals = row["c"]
        stats.points = (stats.goals or 0) + (stats.assists or 0)
        stats.save(update_fields=["goals", "points"])

    # --- Assists (primary + secondary) ---
    for field in ("assist_1", "assist_2"):
        assist_qs = (
            Goal.objects.filter(game=game, **{f"{field}__isnull": False})
            .values(field)
            .annotate(c=Count("id"))
        )
        for row in assist_qs:
            stats, _ = PlayerStats.objects.get_or_create(player_id=row[field], game=game)
            stats.assists = (stats.assists or 0) + row["c"]
            stats.points = (stats.goals or 0) + (stats.assists or 0)
            stats.save(update_fields=["assists", "points"])

    # --- Penalty minutes ---
    for row in Penalty.objects.filter(game=game).values("penalized_player").annotate(mins=Sum("minutes")):
        stats, _ = PlayerStats.objects.get_or_create(player_id=row["penalized_player"], game=game)
        stats.penalty_minutes = row.get("mins") or 0
        stats.save(update_fields=["penalty_minutes"])

    # --- Goals against for goalies on line 0 (slot G) ---
    goalies = (
        LineAssignment.objects.filter(line__game=game, line__line_number=0, slot=LineSlot.G)
        .select_related("player", "line__team")
    )

    for la in goalies:
        player: Player | None = getattr(la, "player", None)
        if not player or player.position != "goalie":
            # Empty slot or non-goalie assigned; ignore to avoid crashes.
            continue
        conceded = game.score_away if la.line.team_id == home_id else game.score_home
        stats, _ = PlayerStats.objects.get_or_create(player=player, game=game)
        stats.goals_against = conceded
        stats.save(update_fields=["goals_against"])
