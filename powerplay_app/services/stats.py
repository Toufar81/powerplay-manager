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

from django.db.models import  F

from django.db.models.query import QuerySet

from django.core.cache import cache

from django.conf import settings

from django.db.models import F, Count, Sum, Value, Q, IntegerField, Subquery, OuterRef
from django.db.models.functions import Coalesce

from powerplay_app.models.games import GameNomination, GameCompetition
from powerplay_app.models.core import League  # pokud je League jinde, uprav import

CACHE_TTL = 5

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
    base_qs: QuerySet[PlayerSeasonTotals] = PlayerSeasonTotals.objects.filter(team=team)

    # GP z nominací (distinct game) – samostatný subdotaz
    gp_sq = (
        GameNomination.objects
        .filter(player=OuterRef("pk"))
        .values("player")
        .annotate(gp=Count("game", distinct=True))
        .values("gp")[:1]
    )

    # Agregace z PlayerStats – jeden „derived“ subquery, ze kterého si vytáhneme 4 hodnoty
    ps_sq = (
        PlayerStats.objects
        .filter(player=OuterRef("pk"))
        .values("player")
        .annotate(
            g=Coalesce(Sum("goals"), 0),
            a=Coalesce(Sum("assists"), 0),
            pim=Coalesce(Sum("penalty_minutes"), 0),
            ga=Coalesce(Sum("goals_against"), 0),
        )
    )

    qs = (
        base_qs
        .annotate(
            games_played=Coalesce(Subquery(gp_sq, output_field=IntegerField()), Value(0)),
            goals=Coalesce(Subquery(ps_sq.values("g")[:1], output_field=IntegerField()), Value(0)),
            assists=Coalesce(Subquery(ps_sq.values("a")[:1], output_field=IntegerField()), Value(0)),
            penalty_minutes=Coalesce(Subquery(ps_sq.values("pim")[:1], output_field=IntegerField()), Value(0)),
            goals_against=Coalesce(Subquery(ps_sq.values("ga")[:1], output_field=IntegerField()), Value(0)),
        )
        .annotate(points=F("goals") + F("assists"))
    )
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
    """Statistics helpers and recomputation routines.

    Provided utilities:
        - player_season_totals_qs – annotated totals for public FE.
        - games_for_team – helper to list a team's games (home/away).
        - recompute_game – recompute per-game PlayerStats from events; GAME SCORE
          IS NOT TOUCHED (score is the single source of truth).
    """

    home_id = game.home_team_id
    away_id = game.away_team_id

    # Reset existujících per-game stats
    PlayerStats.objects.filter(game=game).update(
        points=0, goals=0, assists=0, penalty_minutes=0, goals_against=0
    )

    # Góly
    for row in Goal.objects.filter(game=game).values("scorer").annotate(c=Count("id")):
        if row["scorer"] is None:
            continue
        stats, _ = PlayerStats.objects.get_or_create(player_id=row["scorer"], game=game)
        stats.goals = row["c"]
        stats.points = (stats.goals or 0) + (stats.assists or 0)
        stats.save(update_fields=["goals", "points"])

    # Asistence (primární + sekundární)
    for field in ("assist_1", "assist_2"):
        assist_qs = (
            Goal.objects.filter(game=game, **{f"{field}__isnull": False})
            .values(field)
            .annotate(c=Count("id"))
        )
        for row in assist_qs:
            pid = row[field]
            if pid is None:
                continue
            stats, _ = PlayerStats.objects.get_or_create(player_id=pid, game=game)
            stats.assists = (stats.assists or 0) + row["c"]
            stats.points = (stats.goals or 0) + (stats.assists or 0)
            stats.save(update_fields=["assists", "points"])

    # Trestné minuty
    for row in Penalty.objects.filter(game=game).values("penalized_player").annotate(mins=Sum("minutes")):
        pid = row["penalized_player"]
        if pid is None:
            continue
        stats, _ = PlayerStats.objects.get_or_create(player_id=pid, game=game)
        stats.penalty_minutes = int(row.get("mins") or 0)
        stats.save(update_fields=["penalty_minutes"])

    # Goals Against pro gólmany (line 0, slot G) – z RUČNÍHO skóre
    goalies = (
        LineAssignment.objects
        .filter(line__game=game, line__line_number=0, slot=LineSlot.G)
        .select_related("player", "line__team")
    )
    for la in goalies:
        player: Player | None = getattr(la, "player", None)
        if not player or player.position != "goalie":
            continue
        conceded = game.score_away if la.line.team_id == home_id else game.score_home
        stats, _ = PlayerStats.objects.get_or_create(player=player, game=game)
        stats.goals_against = int(conceded or 0)
        stats.save(update_fields=["goals_against"])

    # Invalidační úklid cache souhrnů (bezpečně pro dotčené hráče + možné ligy)
    affected_player_ids = list(PlayerStats.objects.filter(game=game).values_list("player_id", flat=True))
    possible_leagues = {
        game.league_id,
        getattr(game.home_team, "league_id", None),
        getattr(game.away_team, "league_id", None),
        None,
    }
    invalidate_player_totals_cache(affected_player_ids, possible_leagues)


def resolve_season_window(team: Team) -> tuple[League | None, Any | None, Any | None]:
    """Vrátí (liga, date_start, date_end) pro tým.
    - Primárně vezme team.league.
    - Fallback: poslední ligový zápas týmu → jeho liga.
    - Když nic, vrátí (None, None, None) – tzn. bez datového filtru.
    """
    if getattr(team, "league_id", None):
        lg = team.league
        return lg, getattr(lg, "date_start", None), getattr(lg, "date_end", None)

    last_league_game = (
        Game.objects
        .filter(Q(home_team=team) | Q(away_team=team), competition=GameCompetition.LEAGUE)
        .exclude(league__isnull=True)
        .select_related("league")
        .order_by("-starts_at")
        .first()
    )
    if last_league_game and last_league_game.league_id:
        lg = last_league_game.league
        return lg, getattr(lg, "date_start", None), getattr(lg, "date_end", None)

    return None, None, None


def get_player_totals_from_playerstats(
    player: Player,
    *,
    season_league: League | None,
    competitions: str = "league",  # 'league' | 'tournament' | 'friendly' | 'all'
) -> dict:
    """Souhrnné statistiky hráče z PlayerStats + GP z nominací.
    Respektuje soutěž (league/tournament/friendly/all) a (pokud známe) okno sezóny.

    Skater: {gp, g, a, pts, pim}
    Goalie: {gp, ga, g, a, pim}
    """
    comp = (competitions or "league").lower()
    if comp not in {"league", "tournament", "friendly", "all"}:
        comp = "league"

    # Filtry na hry (použijeme je jak pro GP, tak pro PlayerStats)
    game_filters = Q()
    if comp != "all":
        game_filters &= Q(game__competition=comp)

    # pro 'league' navíc fixujeme konkrétní ligu (když je)
    if comp == "league" and season_league:
        game_filters &= Q(game__league=season_league)

    # datové okno ligy – používáme pro vše, co není 'league', jen pokud ho známe
    # (tj. tournament/friendly/all se omezí na interval ligové sezóny, když máme ligu)
    # U 'league' to není nutné – liga je určena vazbou přes game__league.
    if comp != "league" and season_league and getattr(season_league, "date_start", None) and getattr(season_league, "date_end", None):
        game_filters &= Q(game__starts_at__date__gte=season_league.date_start,
                          game__starts_at__date__lte=season_league.date_end)

    # --- GP z nominací (distinct přes game)
    gp = (
        GameNomination.objects
        .filter(player=player)
        .filter(game_filters)
        .values("game")
        .distinct()
        .count()
    )

    # --- součty z PlayerStats
    ps_qs = PlayerStats.objects.filter(player=player).filter(game_filters)

    agg = ps_qs.aggregate(
        g=Coalesce(Sum("goals"), Value(0)),
        a=Coalesce(Sum("assists"), Value(0)),
        pim=Coalesce(Sum("penalty_minutes"), Value(0)),
        ga=Coalesce(Sum("goals_against"), Value(0)),
    )

    g = int(agg["g"] or 0)
    a = int(agg["a"] or 0)
    pim = int(agg["pim"] or 0)
    ga = int(agg["ga"] or 0)
    pts = g + a

    # výsledek podle pozice
    if getattr(player, "position", "") == "goalie":
        data = {"gp": gp, "ga": ga, "g": g, "a": a, "pim": pim}
    else:
        data = {"gp": gp, "g": g, "a": a, "pts": pts, "pim": pim}

    return data

# Klíčujeme podle hráče, ligy v sezónním okně a přepínače soutěže
_COMP_KEYS = ("league", "tournament", "friendly", "all")

def _totals_cache_key(player_id: int, league_id: int | str, cmp: str) -> str:
    return f"playerstats:totals:v1:{player_id}:{league_id}:{cmp}"

def invalidate_player_totals_cache(player_ids: list[int] | set[int],
                                   league_ids: list[int | None] | set[int | None] = (None,)) -> None:
    """
    Smaže cache pro zadané hráče a (možné) ligy. Pro jistotu pro všechny 'cmp'.
    league_id=None reprezentujeme řetězcem 'none'.
    """
    if not player_ids:
        return
    lids = [("none" if lid is None else int(lid)) for lid in league_ids]
    keys = []
    for pid in set(player_ids):
        for lid in set(lids):
            for cmp in _COMP_KEYS:
                keys.append(_totals_cache_key(pid, lid, cmp))
    cache.delete_many(keys)


def cached_player_totals(player: Player, *, season_league: League | None, competitions: str) -> dict:
    if getattr(settings, "DEBUG", False):
        return get_player_totals_from_playerstats(player, season_league=season_league, competitions=competitions)

    lid = getattr(season_league, "id", "none")
    key = _totals_cache_key(player.id, lid, (competitions or "league").lower())
    return cache.get_or_set(
        key,
        lambda: get_player_totals_from_playerstats(player, season_league=season_league, competitions=competitions),
        CACHE_TTL,
    )

