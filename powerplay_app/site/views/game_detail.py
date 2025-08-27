# file: powerplay_app/site/views/games.py
from __future__ import annotations

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView

from powerplay_app.models import Game, Team
from powerplay_app.models.games import GameCompetition, Line, LineAssignment, LineSlot
from powerplay_app.models.events import Goal, Penalty


def _competition_label(g: Game) -> str:
    if g.competition == GameCompetition.LEAGUE:
        return "Ligový zápas" + (f" • {g.league.name}" if g.league_id else "")
    if g.competition == GameCompetition.TOURNAMENT:
        return "Turnaj" + (f" • {g.tournament.name}" if g.tournament_id else "")
    return "Přátelské utkání"


def _resolve_primary_team() -> Team | None:
    tid = getattr(settings, "PRIMARY_TEAM_ID", None)
    if tid:
        return Team.objects.filter(id=int(tid)).first()
    tname = getattr(settings, "PRIMARY_TEAM_NAME", None)
    if tname:
        return Team.objects.filter(name=tname).first()
    return None


def _build_rink_lines(game: Game, team: Team):
    """
    Vrátí seznam lajn pro hřiště, ale SKRYJE prázdné lajny (bez bruslařů).
    Gólmanská lajna (#0) se sem vůbec nezařazuje.
    """
    lines = (
        Line.objects.filter(game=game, team=team)
        .exclude(line_number=0)
        .order_by("line_number")
        .prefetch_related("players__player")
    )
    out = []
    order = {LineSlot.LW: 0, LineSlot.C: 1, LineSlot.RW: 2, LineSlot.LD: 3, LineSlot.RD: 4}
    for ln in lines:
        slots = {s: None for s in ["LW", "C", "RW", "LD", "RD"]}
        for a in sorted(ln.players.all(), key=lambda x: order.get(x.slot, 99)):
            if a.player_id:
                slots[a.slot] = a.player
        # přidej jen lajny, kde je aspoň jeden bruslař
        if any(slots.values()):
            out.append({"number": ln.line_number, "slots": slots})
    return out


def _primary_goalie(game: Game, team: Team):
    gline = (
        Line.objects.filter(game=game, team=team, line_number=0)
        .prefetch_related("players__player")
        .first()
    )
    if not gline:
        return None
    a = gline.players.filter(slot=LineSlot.G).select_related("player").first()
    return a.player if a and a.player_id else None


class GameDetailView(DetailView):
    model = Game
    template_name = "site/game_detail.html"
    context_object_name = "game"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        game: Game = ctx["game"]

        # --- meta ---
        now = timezone.localtime()
        ctx["is_future"] = game.starts_at and timezone.localtime(game.starts_at) > now
        ctx["competition_label"] = _competition_label(game)
        ctx["admin_change_url"] = reverse("admin:powerplay_app_game_change", args=[game.pk])

        # --- liniové rozestavení pro „náš“ tým / fallback = domácí ---
        pteam = _resolve_primary_team()
        show_team = pteam if (pteam and pteam.id in (game.home_team_id, game.away_team_id)) else game.home_team
        ctx["PRIMARY_TEAM_NAME"] = getattr(settings, "PRIMARY_TEAM_NAME", show_team.name)
        ctx["rink_lines"] = _build_rink_lines(game, show_team)
        ctx["primary_goalie"] = _primary_goalie(game, show_team)

        # --- Góly a tresty (obě strany) ---
        qs_goals_home = Goal.objects.filter(game=game, team=game.home_team)\
            .select_related("scorer", "assist_1", "assist_2")\
            .order_by("period", "second_in_period")
        qs_goals_away = Goal.objects.filter(game=game, team=game.away_team)\
            .select_related("scorer", "assist_1", "assist_2")\
            .order_by("period", "second_in_period")
        qs_pens_home = Penalty.objects.filter(game=game, team=game.home_team)\
            .select_related("penalized_player")\
            .order_by("period", "second_in_period")
        qs_pens_away = Penalty.objects.filter(game=game, team=game.away_team)\
            .select_related("penalized_player")\
            .order_by("period", "second_in_period")

        ctx["goals_home"] = qs_goals_home
        ctx["goals_away"] = qs_goals_away
        ctx["pens_home"] = qs_pens_home
        ctx["pens_away"] = qs_pens_away

        # booleany pro šablonu – aby se nic prázdného nekreslilo
        has_home_goals = qs_goals_home.exists()
        has_away_goals = qs_goals_away.exists()
        has_home_pens = qs_pens_home.exists()
        has_away_pens = qs_pens_away.exists()

        ctx["show_home_col"] = has_home_goals or has_home_pens
        ctx["show_away_col"] = has_away_goals or has_away_pens
        ctx["has_any_events"] = ctx["show_home_col"] or ctx["show_away_col"]

        # nav highlight (volitelné)
        ctx["ns"] = "site"
        ctx["current"] = "game_detail"
        return ctx
