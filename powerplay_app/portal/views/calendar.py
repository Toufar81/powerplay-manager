from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Iterable

from django.db.models import Q

from django.views.generic import TemplateView

from powerplay_app.models import Game, TeamEvent, Team
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse, NoReverseMatch

TYPE_LABELS = {
    "game": "Zápas",
    "training": "Trénink",
    "camp": "Kemp",
    "meeting": "Porada",
    "other": "Jiné",
}

# Pomocná funkce: jaký tým je „náš“ (stejné chování jako v admine)
def _resolve_primary_team_id() -> Optional[int]:
    tid = getattr(settings, "PRIMARY_TEAM_ID", None)
    if tid:
        return int(tid)
    name = getattr(settings, "PRIMARY_TEAM_NAME", None)
    if not name:
        return None
    return Team.objects.filter(name=name).values_list("id", flat=True).first()

def _team_logo_url(t: Optional[Team]) -> Optional[str]:
    if not t:
        return None
    try:
        f = getattr(t, "logo", None)
        if f and getattr(f, "url", None):
            return f.url
    except Exception:
        pass
    return None

def _public_game_url(g) -> str | None:
    # 1) preferuj get_absolute_url(), pokud existuje a funguje
    try:
        if hasattr(g, "get_absolute_url"):
            url = g.get_absolute_url()
            if url:
                return url
    except Exception:
        pass

    # 2) reverz na site:game_detail vyžaduje <pk> i <slug>
    #    - vezmeme g.slug, public_slug… nebo vytvoříme „bezpečný“ fallback
    slug = getattr(g, "slug", None) or getattr(g, "public_slug", None)
    if not slug:
        dt = timezone.localtime(g.starts_at).strftime("%Y-%m-%d-%H%M")
        slug = slugify(f"{g.home_team.name} vs {g.away_team.name} {dt}")[:60]

    try:
        return reverse("site:game_detail", kwargs={"pk": g.pk, "slug": slug})
    except NoReverseMatch:
        # 3) poslední nouzový pokus – libovolný slug (většina view ho nevaliduje)
        try:
            return reverse("site:game_detail", kwargs={"pk": g.pk, "slug": "detail"})
        except NoReverseMatch:
            return None



@dataclass
class CalItem:
    kind: str                   # "game" | "event"
    type: str                   # klíč do TYPE_LABELS
    starts_at: timezone.datetime
    type_label: str
    # Společné
    title: str
    stadium_name: Optional[str] = None
    # Pro zápas
    url: Optional[str] = None
    home_name: Optional[str] = None
    away_name: Optional[str] = None
    home_logo: Optional[str] = None
    away_logo: Optional[str] = None
    # Pro jednostranné akce
    single_logo: Optional[str] = None


class CalendarView(TemplateView):
    template_name = "portal/calendar.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        primary_team_id = _resolve_primary_team_id()
        now = timezone.now()
        horizon_days = int(self.request.GET.get("days") or 45)
        to_ts = now + timezone.timedelta(days=horizon_days)

        # --- ZÁPASY (Game) ---
        game_qs = (
            Game.objects
            .filter(
                Q(home_team_id=primary_team_id) | Q(away_team_id=primary_team_id),
                starts_at__gte=now,
                starts_at__lte=to_ts,
            )
            .select_related("home_team", "away_team", "stadium", "league", "tournament")
            .order_by("starts_at")
        )

        games: list[CalItem] = []
        for g in game_qs:
            home = g.home_team
            away = g.away_team
            games.append(CalItem(
                kind="game",
                type="game",
                type_label=TYPE_LABELS["game"],
                starts_at=g.starts_at,
                title=f"{home.name} vs {away.name}",
                stadium_name=getattr(getattr(g, "stadium", None), "name", None),
                url=_public_game_url(g),
                home_name=home.name,
                away_name=away.name,
                home_logo=_team_logo_url(home),
                away_logo=_team_logo_url(away),
            ))

        # --- TEAM EVENTS (mimo zápasy) ---
        show_canceled = self.request.GET.get("canceled") == "1"
        ev_filter = Q(team_id=primary_team_id) | Q(related_game__home_team_id=primary_team_id) | Q(related_game__away_team_id=primary_team_id)
        ev_qs = (
            TeamEvent.objects
            .filter(ev_filter, starts_at__gte=now, starts_at__lte=to_ts)
            .select_related("team", "stadium", "related_game", "related_game__home_team", "related_game__away_team")
            .order_by("starts_at")
        )
        if not show_canceled:
            ev_qs = ev_qs.filter(is_canceled=False)

        # Budeme deduplikovat eventy navázané na zápas, protože zápas bereme z Game
        game_ids = {g.starts_at.replace(second=0, microsecond=0): set() for g in game_qs}  # jen pro rychlý lookup
        game_pk_set = {getattr(getattr(e, "related_game", None), "pk", None) for e in ev_qs if e.related_game_id}
        game_pk_set.discard(None)

        events: list[CalItem] = []
        for e in ev_qs:
            if e.related_game_id and e.related_game_id in game_pk_set:
                continue  # necháme jen "zápasovou" kartu z Game

            etype = (e.event_type or "other").lower()
            type_label = TYPE_LABELS.get(etype, TYPE_LABELS["other"])
            single_logo = _team_logo_url(e.team) or (
                _team_logo_url(getattr(getattr(e, "related_game", None), "home_team", None))
                if e.related_game_id else None
            )

            title = e.title or type_label
            events.append(CalItem(
                kind="event",
                type=etype,
                type_label=type_label,
                starts_at=e.starts_at,
                title=title,
                stadium_name=getattr(getattr(e, "stadium", None), "name", None),
                single_logo=single_logo,
            ))

        # --- MERGE + FILTR DLE TAB ---
        merged: list[CalItem] = sorted([*games, *events], key=lambda x: x.starts_at)

        tab = (self.request.GET.get("tab") or "all").lower()
        if tab != "all":
            tabmap = {
                "games": {"game"},
                "training": {"training"},
                "camp": {"camp"},
                "meeting": {"meeting"},
                "other": {"other"},
            }
            allowed = tabmap.get(tab, {"__none__"})
            merged = [it for it in merged if it.type in allowed]

        # Počty pro pilulky
        def count_of(kinds: Iterable[str]) -> int:
            s = set(kinds)
            return sum(1 for it in games if it.type in s) + sum(1 for it in events if it.type in s)

        pills = [
            ("all", "Vše", len(games) + len(events)),
            ("games", "Zápasy", count_of({"game"})),
            ("training", "Tréninky", count_of({"training"})),
            ("camp", "Kempy", count_of({"camp"})),
            ("meeting", "Porady", count_of({"meeting"})),
            ("other", "Jiné", count_of({"other"})),
        ]

        ctx.update({
            "items": merged,
            "pills": pills,
            "selected_tab": tab,
        })
        return ctx
