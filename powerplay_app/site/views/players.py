# file: powerplay_app/views/players.py
"""Players listing and detail views for the public Site.

- PlayersListView  — list players of the primary team with position filters.
- PlayerDetailView — show one player, computed age, cached season totals,
  and a per-game table sourced from PlayerStats.

Notes
-----
* Competition filter uses ?cmp=league|tournament|friendly|all
* Season window is taken from resolve_season_window(team) if a league exists
* PIM in per-game rows is taken from PlayerStats.minutes; when empty/0 we
  fallback to sum of Penalty.minutes for that player in the game.
* GA in per-game rows supports `ga` or `goals_against` field names
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from django.db.models import Count, Sum
from django.views.generic import DetailView, TemplateView

from powerplay_app.context import _resolve_primary_team
from powerplay_app.models import Player, PlayerStats
from powerplay_app.services.stats import resolve_season_window, cached_player_totals


# Czech UI labels by position value
POS_LABELS: Final[dict[str, str]] = {
    "forward": "Útočníci",
    "defense": "Obránci",
    "goalie": "Brankáři",
}


def _age(born: date | None) -> int | None:
    """Return age in years for a given birth date or ``None`` when unknown."""
    if not born:
        return None
    today = date.today()
    years = today.year - born.year - (
        (today.month, today.day) < (born.month, born.day)
    )
    return years


class PlayersListView(TemplateView):
    """Render a list of players for the primary team with position filters."""

    template_name = "site/players.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        ctx = super().get_context_data(**kwargs)
        team = _resolve_primary_team()
        selected = self.request.GET.get("pos")

        qs = Player.objects.none()
        pos_counts: dict[str, int] = {}
        total_count = 0

        if team:
            base = Player.objects.filter(team=team)
            qs = base.order_by("jersey_number", "last_name")
            if selected in POS_LABELS:
                qs = qs.filter(position=selected)

            # counts for filter badges
            counts = base.values("position").annotate(c=Count("id"))
            pos_counts = {row["position"]: row["c"] for row in counts}
            total_count = base.count()

        # prepared list for template (label + count)
        pos_list = [
            {"key": key, "label": label, "count": pos_counts.get(key, 0)}
            for key, label in POS_LABELS.items()
        ]

        ctx.update(
            {
                "players": qs,
                "pos_labels": POS_LABELS,
                "pos_counts": pos_counts,
                "pos_list": pos_list,
                "selected_pos": selected if selected in POS_LABELS else None,
                "total_count": total_count,
            }
        )
        return ctx


class PlayerDetailView(DetailView):
    """Player detail view with computed age, totals and per-game rows."""

    model = Player
    template_name = "site/player_detail.html"
    context_object_name = "player"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        ctx = super().get_context_data(**kwargs)
        p: Player = ctx["player"]

        # competition switch from URL (?cmp=league|tournament|friendly|all)
        cmp = (self.request.GET.get("cmp") or "all").lower()
        if cmp not in {"league", "tournament", "friendly", "all"}:
            cmp = "league"

        # season window (league may be missing → no date limit)
        season_league, d1, d2 = resolve_season_window(p.team) if p.team_id else (None, None, None)

        # season totals (cached)
        totals = cached_player_totals(p, season_league=season_league, competitions=cmp)

        # per-game rows (PlayerStats -> Game)
        game_rows: list[dict[str, Any]] = []
        if p.pk:
            qs = (
                PlayerStats.objects
                .filter(player=p)
                .select_related("game", "game__home_team", "game__away_team")
                .order_by("-game__starts_at")
            )
            if d1 and d2:
                qs = qs.filter(game__starts_at__date__gte=d1, game__starts_at__date__lte=d2)
            if cmp != "all":
                qs = qs.filter(game__competition=cmp)

            for st in qs:
                g = st.game
                if not g:
                    continue

                home_is_us = (p.team_id and g.home_team_id == p.team_id)
                opponent = g.away_team if home_is_us else g.home_team

                # result letter (W/L/D); future games → None
                letter: str | None = None
                if g.score_home is not None and g.score_away is not None:
                    if g.score_home == g.score_away:
                        letter = "D"
                    else:
                        us_score = g.score_home if home_is_us else g.score_away
                        them_score = g.score_away if home_is_us else g.score_home
                        letter = "W" if (us_score or 0) > (them_score or 0) else "L"

                g_val = getattr(st, "goals", 0) or 0
                a_val = getattr(st, "assists", 0) or 0

                # --- PIM: prefer PlayerStats.minutes; if empty/0, sum Penalty.minutes for this game/player
                minutes = getattr(st, "minutes", None)
                pim_val = minutes if minutes not in (None, 0) else (
                    g.penalty_set.filter(
                        penalized_player_id=p.id,
                        team_id=p.team_id,
                    ).aggregate(total=Sum("minutes"))["total"] or 0
                )

                # --- GA může být `ga` nebo `goals_against`
                ga_val = getattr(st, "ga", None)
                if ga_val is None:
                    ga_val = getattr(st, "goals_against", 0)
                ga_val = ga_val or 0

                pts_val = getattr(st, "points", None)
                if pts_val is None:
                    pts_val = g_val + a_val

                game_rows.append(
                    {
                        "game": g,
                        "opponent": opponent,
                        "is_away": (not home_is_us),
                        "result_letter": letter,  # W/L/D/None
                        "g": g_val,
                        "a": a_val,
                        "pts": pts_val,
                        "pim": pim_val,          # ← minutes or fallback from Penalty
                        "ga": ga_val,            # for goalies
                    }
                )

        ctx.update(
            {
                "age": _age(p.birth_date),
                "is_goalie": (p.position == "goalie"),
                "stats": totals,
                "season_meta": {
                    "league": season_league,
                    "date_start": d1,
                    "date_end": d2,
                    "cmp": cmp,
                },
                "game_rows": game_rows,
            }
        )
        return ctx
