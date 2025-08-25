# file: powerplay_app/admin.py
"""Django admin configuration for leagues, teams, players, games and events.

Internal documentation (docstrings, comments) is in **English**. All
user-facing labels/descriptions remain **Czech** to match the target market.

"""

from __future__ import annotations

from typing import Any
from functools import lru_cache

import nested_admin
from django import forms
from django.conf import settings
from .models.wallet import WalletCategory, WalletTransaction
from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.core.management import call_command
from django.db.models import (
    Count,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db import transaction  # noqa: F401  # kept if used by other modules via import side-effects
from django.db.models.functions import Coalesce
from django.forms.models import BaseInlineFormSet
from .models.feedback import GameFeedback
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Country,
    Game,
    Goal,
    League,
    Line,
    LineAssignment,
    Penalty,
    Player,
    PlayerStats,
    Staff,
    Stadium,
    Team,
    TeamEvent,
    Tournament,
    _recompute_game,
)
from .models.games import GameNomination, LineSlot, Game as GameModel, GameCompetition
from .models.stats_proxy import PlayerSeasonTotals


# ------------------------------------------------------------
# Safe unregistration (idempotent)
# ------------------------------------------------------------
for model in (
    League,
    Stadium,
    Team,
    Country,
    Player,
    Game,
    PlayerStats,
    Tournament,
    Line,
    LineAssignment,
    Goal,
    Penalty,
    Staff,
    TeamEvent,
):
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass


# ------------------------------------------------------------
# Global admin actions
# ------------------------------------------------------------
@admin.action(description="Znovu vygenerovat kalendářové události (1 událost / zápas)")
def regenerate_calendar_events(modeladmin: Any, request: Any, queryset: Any) -> None:
    """Re-sync calendar events for selected games.

    Notes:
        UI text remains Czech; action reuses the app's sync helper.
    """
    from .signals import _sync_event_for_game

    for g in queryset.select_related("home_team", "away_team"):
        _sync_event_for_game(g, create_if_missing=True)
    modeladmin.message_user(request, f"Hotovo. Zpracováno {queryset.count()} zápasů.")


# ------------------------------------------------------------
# Simple registries
# ------------------------------------------------------------
@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    """Admin for league with a convenience action to sync results."""

    list_display = ("name", "season", "date_start", "date_end")
    search_fields = ("name", "season")
    actions = ["sync_results_for_league"]

    @admin.action(description="Načíst/aktualizovat zápasy z webu (Playwright)")
    def sync_results_for_league(self, request: Any, queryset: Any) -> None:
        """Fetch/update league matches using the custom management command."""
        if queryset.count() != 1:
            self.message_user(request, "Vyber přesně jednu ligu.", level=messages.ERROR)
            return
        league = queryset.first()
        try:
            call_command("sync_results", league_id=league.id, headful=False)
            self.message_user(request, f"✅ Synchronizace dokončena pro ligu: {league}.")
        except Exception as e:  # pragma: no cover - operational path
            self.message_user(
                request, f"❌ Synchronizace selhala: {e}", level=messages.ERROR
            )


@admin.register(Stadium)
class StadiumAdmin(admin.ModelAdmin):
    """Admin for stadiums."""

    list_display = ("name", "address")
    search_fields = ("name", "address")


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    """Admin for countries of birth."""

    list_display = ("name", "iso_code")
    search_fields = ("name", "iso_code")


# ------------------------------------------------------------
# Team + Staff
# ------------------------------------------------------------
class StaffInline(admin.TabularInline):
    """Inline for staff members under a team form."""

    model = Staff
    extra = 0
    can_delete = True
    fields = (
        "first_name",
        "last_name",
        "role",
        "phone",
        "email",
        "address",
        "photo",
        "photo_preview",
        "is_active",
        "order",
    )
    readonly_fields = ("photo_preview",)
    ordering = ("order", "last_name")

    def photo_preview(self, obj: Staff) -> str:
        """Render a small thumbnail preview for staff photo in admin."""
        if obj and getattr(obj, "photo", None):
            return format_html(
                '<img src="{}" style="height:40px;border-radius:4px;" />', obj.photo.url
            )
        return "—"

    photo_preview.short_description = "Náhled"


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Admin for team with embedded staff management."""

    list_display = ("name", "league", "city", "coach")
    list_filter = ("league",)
    search_fields = ("name", "city", "coach")
    inlines = [StaffInline]

    # Classic selects (no autocomplete) for league and stadium
    def formfield_for_foreignkey(self, db_field: Any, request: Any, **kwargs: Any):
        if db_field.name == "league":
            kwargs["queryset"] = League.objects.order_by("name", "season")
        elif db_field.name == "stadium":
            kwargs["queryset"] = Stadium.objects.order_by("name")
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name in {"league", "stadium"}:
            field.empty_label = "— vyberte —"
            field.widget.attrs.update({"style": "min-width:260px;"})
        return field


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    """Admin for staff entries with simple filters and ordering."""

    list_display = (
        "first_name",
        "last_name",
        "role",
        "team",
        "phone",
        "email",
        "is_active",
        "order",
    )
    list_filter = ("is_active", "team__league", "team", "role")
    search_fields = (
        "first_name",
        "last_name",
        "role",
        "team__name",
        "email",
        "phone",
        "address",
    )
    ordering = ("team", "order", "last_name")

    def formfield_for_foreignkey(self, db_field: Any, request: Any, **kwargs: Any):
        """Classic select for team with ordering and wider widget."""
        if db_field.name == "team":
            kwargs["queryset"] = Team.objects.order_by("name")
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "team":
            field.empty_label = "— vyberte tým —"
            field.widget.attrs.update({"style": "min-width:260px;"})
        return field


# ------------------------------------------------------------
# Player
# ------------------------------------------------------------
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    """Admin for players with photo preview helpers."""

    list_display = (
        "first_name",
        "last_name",
        "team",
        "position",
        "jersey_number",
        "photo_thumb",
    )
    list_filter = ("position", "team__league")
    search_fields = ("first_name", "last_name", "nickname", "email")
    readonly_fields = ("photo_preview",)

    def formfield_for_foreignkey(self, db_field: Any, request: Any, **kwargs: Any):
        """Classic selects for team and country with ordering and wider widget."""
        if db_field.name == "team":
            kwargs["queryset"] = Team.objects.order_by("name")
        elif db_field.name == "country":
            kwargs["queryset"] = Country.objects.order_by("name")
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name in {"team", "country"}:
            field.empty_label = "— vyberte —"
            field.widget.attrs.update({"style": "min-width:260px;"})
        return field

    # Photos
    def photo_thumb(self, obj: Player) -> str:
        """Small avatar used in list_display."""
        return format_html(
            '<img src="{}" style="height:40px;width:auto;border-radius:4px;" />',
            obj.photo_url(),
        )

    photo_thumb.short_description = "Foto"

    def photo_preview(self, obj: Player) -> str:
        """Larger preview for the change form sidebar."""
        return format_html(
            '<img src="{}" style="max-height:300px;width:auto;border-radius:8px;" />',
            obj.photo_url(),
        )

    photo_preview.short_description = "Náhled fotky"


# ------------------------------------------------------------
# Helpers: select <option> labels for players
# ------------------------------------------------------------

def _player_plain_label(p: Player) -> str:
    """Return a concise player label for selects (number + name + nickname)."""
    num = p.jersey_number if p.jersey_number is not None else ""
    nick = f" ({p.nickname})" if p.nickname else ""
    return f"{num} {p.first_name} {p.last_name}{nick}".strip()


class PlayerChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that uses a custom label renderer for players."""

    def label_from_instance(self, obj: Player) -> str:
        return _player_plain_label(obj)


# ------------------------------------------------------------
# Line / LineAssignment – forms & formsets
# ------------------------------------------------------------
class LineForm(forms.ModelForm):
    """Simple line form exposing the line number field only."""

    class Meta:
        model = Line
        fields = ("line_number",)
        labels = {"line_number": "Číslo lajny"}
        widgets = {
            "line_number": forms.NumberInput(attrs={"min": 0, "step": 1, "style": "max-width:90px"})
        }


SKATER_ORDER = [LineSlot.LW, LineSlot.C, LineSlot.RW, LineSlot.LD, LineSlot.RD]
SKATER_LABELS = {
    LineSlot.LW: "Levé křídlo",
    LineSlot.C: "Střed",
    LineSlot.RW: "Pravé křídlo",
    LineSlot.LD: "Levá obrana",
    LineSlot.RD: "Pravá obrana",
}


class LineAssignmentInlineFormSet(BaseInlineFormSet):
    """Inline formset that enforces fixed slots and nomination-based player pool.

    Rules:
        - Goalies (line 0): only goalies allowed; max 1 row.
        - Skaters: exactly 5 visible rows (LW, C, RW, LD, RD).
        - Player may be empty (slot intentionally blank).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        line = self.instance
        team_id = getattr(line, "team_id", None)
        game_id = getattr(line, "game_id", None)

        if team_id and game_id:
            pids = (
                GameNomination.objects.filter(game_id=game_id, team_id=team_id).values_list("player_id", flat=True)
            )
            base_qs = Player.objects.filter(id__in=pids).order_by("jersey_number", "last_name")
        else:
            base_qs = Player.objects.none()

        if getattr(line, "line_number", None) == 0:
            goalie_code = getattr(getattr(Player, "Position", None), "GOALIE", None)
            goalie_filter = {"position": goalie_code} if goalie_code is not None else {
                "position__in": ["goalie", "G", "GK", "GOALIE"]
            }
            qs = base_qs.filter(**goalie_filter)
            self.max_num = 1
            self.extra = max(0, 1 - self.initial_form_count())
        else:
            goalie_code = getattr(getattr(Player, "Position", None), "GOALIE", None)
            not_goalie_filter = ~Q(position=goalie_code) if goalie_code is not None else ~Q(
                position__in=["goalie", "G", "GK", "GOALIE"]
            )
            qs = base_qs.filter(not_goalie_filter)
            self.max_num = 5
            self.extra = max(0, 5 - self.initial_form_count())

        if "player" in self.form.base_fields:
            self.form.base_fields["player"] = PlayerChoiceField(queryset=qs, required=False)

    def add_fields(self, form: forms.ModelForm, index: int | None) -> None:
        """Inject hidden ``slot`` and optional read-only label field."""
        super().add_fields(form, index)
        line = self.instance
        is_goalie_line = getattr(line, "line_number", None) == 0

        if is_goalie_line:
            slot_value = LineSlot.G
        else:
            slot_order = [LineSlot.LW, LineSlot.C, LineSlot.RW, LineSlot.LD, LineSlot.RD]
            slot_value = (
                slot_order[index] if isinstance(index, int) and 0 <= index < len(slot_order) else slot_order[-1]
            )

        form.fields["slot"] = forms.CharField(widget=forms.HiddenInput(), required=False)
        form.initial["slot"] = slot_value
        form.instance.slot = slot_value  # required for validation

        if not is_goalie_line and isinstance(index, int) and 0 <= index < 5:
            form.fields["slot_label"] = forms.CharField(label="Štítek slotu", required=False, disabled=True)
            form.initial["slot_label"] = {
                LineSlot.LW: "Levé křídlo",
                LineSlot.C: "Střed",
                LineSlot.RW: "Pravé křídlo",
                LineSlot.LD: "Levá obrana",
                LineSlot.RD: "Pravá obrana",
            }[slot_value]

    def save(self, commit: bool = True):  # type: ignore[override]
        """Persist created/changed/deleted inline objects preserving slot order."""
        self.new_objects = []
        self.changed_objects = []
        self.deleted_objects = []

        line = self.instance
        is_goalie_line = getattr(line, "line_number", None) == 0
        order = [LineSlot.LW, LineSlot.C, LineSlot.RW, LineSlot.LD, LineSlot.RD]

        for idx, form in enumerate(self.forms):
            if not hasattr(form, "cleaned_data"):
                continue

            want_delete = form.cleaned_data.get("DELETE")
            player = form.cleaned_data.get("player")

            if not is_goalie_line and idx >= 5:
                continue

            instance = getattr(form, "instance", None)
            existed = bool(getattr(instance, "pk", None))

            if want_delete:
                if existed and commit:
                    instance.delete()
                    self.deleted_objects.append(instance)
                continue

            if not player and not existed:
                continue

            obj = form.save(commit=False)
            obj.line = line
            obj.slot = getattr(obj, "slot", None) or (
                LineSlot.G if is_goalie_line else order[min(idx, 4)]
            )

            if existed:
                changed = list(getattr(form, "changed_data", []))
                if "slot" not in changed and getattr(instance, "slot", None) != obj.slot:
                    changed.append("slot")
                if changed:
                    if commit:
                        obj.save()
                    self.changed_objects.append((obj, changed))
                else:
                    if commit and getattr(instance, "slot", None) != obj.slot:
                        obj.save()
            else:
                if commit:
                    obj.save()
                self.new_objects.append(obj)

        return self.new_objects + [o for (o, _) in self.changed_objects]


class SkaterLineAssignmentForm(forms.ModelForm):
    """Inline form for skaters adding a non-model, read-only ``slot_label``."""

    slot_label = forms.CharField(
        label="Štítek slotu",
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={"readonly": "readonly"}),
    )

    class Meta:
        model = LineAssignment
        fields = ("slot_label", "player")


# ------------------------------------------------------------
# Inlines — display
# ------------------------------------------------------------
class GoalieLineAssignmentInline(nested_admin.NestedTabularInline):
    """Inline for goalie assignment within the goalie line (line 0)."""

    model = LineAssignment
    formset = LineAssignmentInlineFormSet
    extra = 0
    fields = ("player",)
    can_delete = False

    def has_delete_permission(self, request: Any, obj: Any | None = None) -> bool:
        return False


class SkaterLineAssignmentInline(nested_admin.NestedTabularInline):
    """Exactly 5 fixed rows: read-only slot label + player selector."""

    model = LineAssignment
    form = SkaterLineAssignmentForm
    formset = LineAssignmentInlineFormSet
    extra = 0
    fields = ("slot_label", "player")
    can_delete = False

    def has_add_permission(self, request: Any, obj: Any | None = None) -> bool:
        return True

    def has_delete_permission(self, request: Any, obj: Any | None = None) -> bool:
        return False


# ------------------------------------------------------------
# Nested inlines – Goalie (0) and Skater lines (1–3)
# ------------------------------------------------------------
class BaseGameLineInline(nested_admin.NestedTabularInline):
    """Base inline for lines bound to one of the game teams.

    ``team_side`` controls whether the inline manages home or away team lines.
    """

    model = Line
    form = LineForm
    extra = 0
    show_change_link = True
    can_delete = True
    team_side: str | None = None

    def get_queryset(self, self_request: Any):  # type: ignore[override]
        qs = super().get_queryset(self_request)
        game = getattr(self_request, "_current_game", None)
        if not game or self.team_side is None:
            return qs.none()
        team_id = game.home_team_id if self.team_side == "home" else game.away_team_id
        return qs.filter(game=game, team_id=team_id)

    def get_formset(self, request: Any, obj: Any | None = None, **kwargs: Any):  # type: ignore[override]
        request._current_game = obj
        return super().get_formset(request, obj, **kwargs)

    def save_new(self, form: Any, commit: bool = True):  # type: ignore[override]
        obj = super().save_new(form, commit=False)
        game = form.instance.game
        obj.team = game.home_team if self.team_side == "home" else game.away_team
        if commit:
            obj.save()
        return obj


class GoalieLineInline(BaseGameLineInline):
    """Inline manager for the goalie line (line_number=0)."""

    inlines = [GoalieLineAssignmentInline]
    can_delete = False
    max_num = 1

    def has_add_permission(self, request: Any, obj: Any | None = None) -> bool:
        return False

    def get_queryset(self, request: Any):  # type: ignore[override]
        return super().get_queryset(request).filter(line_number=0)

    def get_formset(self, request: Any, obj: Any | None = None, **kwargs: Any):  # type: ignore[override]
        formset = super().get_formset(request, obj, **kwargs)
        orig_init = formset.form.__init__

        def _init(fself: Any, *a: Any, **kw: Any) -> None:
            orig_init(fself, *a, **kw)
            if "line_number" in fself.fields:
                fself.fields["line_number"].widget = forms.HiddenInput()
            if "DELETE" in fself.fields:
                fself.fields["DELETE"].widget = forms.HiddenInput()

        formset.form.__init__ = _init
        return formset


class SkaterLinesInline(BaseGameLineInline):
    """Inline manager for non-goalie lines (1–3)."""

    inlines = [SkaterLineAssignmentInline]

    def get_queryset(self, request: Any):  # type: ignore[override]
        return super().get_queryset(request).exclude(line_number=0).order_by("line_number")


class HomeGoalieLineInline(GoalieLineInline):
    team_side = "home"
    classes = ("line-col-left", "line-goalie")
    verbose_name_plural = "Gólman – Domácí tým"

    def get_formset(self, request: Any, obj: Any | None = None, **kwargs: Any):  # type: ignore[override]
        self.verbose_name_plural = (
            f"Gólman – {obj.home_team.name}" if obj and obj.home_team_id else "Gólman – Domácí tým"
        )
        return super().get_formset(request, obj, **kwargs)


class HomeSkaterLinesInline(SkaterLinesInline):
    team_side = "home"
    classes = ("line-col-left", "line-skaters")
    verbose_name_plural = "Sestava – Domácí tým"

    def get_formset(self, request: Any, obj: Any | None = None, **kwargs: Any):  # type: ignore[override]
        self.verbose_name_plural = (
            f"Sestava – {obj.home_team.name}" if obj and obj.home_team_id else "Sestava – Domácí tým"
        )
        return super().get_formset(request, obj, **kwargs)


class AwayGoalieLineInline(GoalieLineInline):
    team_side = "away"
    classes = ("line-col-right", "line-goalie")
    verbose_name_plural = "Gólman – Hostující tým"

    def get_formset(self, request: Any, obj: Any | None = None, **kwargs: Any):  # type: ignore[override]
        self.verbose_name_plural = (
            f"Gólman – {obj.away_team.name}" if obj and obj.away_team_id else "Gólman – Hostující tým"
        )
        return super().get_formset(request, obj, **kwargs)


class AwaySkaterLinesInline(SkaterLinesInline):
    team_side = "away"
    classes = ("line-col-right", "line-skaters")
    verbose_name_plural = "Sestava – Hostující tým"

    def get_formset(self, request: Any, obj: Any | None = None, **kwargs: Any):  # type: ignore[override]
        self.verbose_name_plural = (
            f"Sestava – {obj.away_team.name}" if obj and obj.away_team_id else "Sestava – Hostující tým"
        )
        return super().get_formset(request, obj, **kwargs)


# ------------------------------------------------------------
# Goals / Penalties – foreign key choices limited to nominations
# ------------------------------------------------------------

def _players_qs_for_side(game: GameModel, team: Team):
    """Return eligible players (nominated for the game) for a given team."""
    if not (game and team):
        return Player.objects.none()
    ids = GameNomination.objects.filter(game=game, team=team).values_list("player_id", flat=True)
    return Player.objects.filter(id__in=ids).order_by("jersey_number", "last_name")


class GoalInline(nested_admin.NestedTabularInline):
    """Inline to edit goals within a game admin page."""

    model = Goal
    extra = 0

    def get_formset(self, request: Any, obj: Any | None = None, **kwargs: Any):  # type: ignore[override]
        self._game = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field: Any, request: Any, **kwargs: Any):  # type: ignore[override]
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        g = getattr(self, "_game", None)
        if g:
            valid_teams = Team.objects.filter(id__in=[g.home_team_id, g.away_team_id])
            if db_field.name == "team":
                field.queryset = valid_teams
            if db_field.name in {"scorer", "assist_1", "assist_2"}:
                field.queryset = _players_qs_for_side(g, g.home_team) | _players_qs_for_side(
                    g, g.away_team
                )
        return field


class PenaltyInline(nested_admin.NestedTabularInline):
    """Inline to edit penalties within a game admin page."""

    model = Penalty
    extra = 0

    def get_formset(self, request: Any, obj: Any | None = None, **kwargs: Any):  # type: ignore[override]
        self._game = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field: Any, request: Any, **kwargs: Any):  # type: ignore[override]
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        g = getattr(self, "_game", None)
        if g:
            valid_teams = Team.objects.filter(id__in=[g.home_team_id, g.away_team_id])
            if db_field.name == "team":
                field.queryset = valid_teams
            if db_field.name == "penalized_player":
                field.queryset = _players_qs_for_side(g, g.home_team) | _players_qs_for_side(
                    g, g.away_team
                )
        return field


# ------------------------------------------------------------
# Quick nominations (checkbox grid)
# ------------------------------------------------------------

def _player_badge(p: Player) -> str:
    """Return HTML badge for a player used in checkbox grid labels."""
    num = p.jersey_number if p.jersey_number is not None else "—"
    name = f"{p.first_name} {p.last_name}".strip()
    nick_html = f' <span class="nick">({p.nickname})</span>' if p.nickname else ""
    return (
        '<span class="meta">'
        f'  <span class="num">{num}</span>'
        f'  <span class="name">{name}</span>'
        f"{nick_html}"
        "</span>"
    )


class PlayerChoicesField(forms.ModelMultipleChoiceField):
    """ModelMultipleChoiceField that renders players with rich labels (HTML)."""

    def label_from_instance(self, obj: Player) -> str:  # type: ignore[override]
        return mark_safe(_player_badge(obj))


class GameAdminForm(forms.ModelForm):
    """Custom form for games adding two nomination grids (home/away)."""

    home_nominations = PlayerChoicesField(
        queryset=Player.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "player-grid"}),
        required=False,
        label="",
    )
    away_nominations = PlayerChoicesField(
        queryset=Player.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "player-grid"}),
        required=False,
        label="",
    )

    class Meta:
        model = Game
        fields = "__all__"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        inst: Game | None = self.instance if getattr(self.instance, "pk", None) else None

        # Re-label both score fields to a unified Czech label
        if "score_home" in self.fields:
            self.fields["score_home"].label = "Skóre"
        if "score_away" in self.fields:
            self.fields["score_away"].label = "Skóre"

        if inst and inst.home_team_id:
            self.fields["home_nominations"].queryset = (
                Player.objects.filter(team_id=inst.home_team_id).order_by("jersey_number", "last_name")
            )
            self.initial["home_nominations"] = list(
                GameNomination.objects.filter(game=inst, team_id=inst.home_team_id).values_list(
                    "player_id", flat=True
                )
            )

        if inst and inst.away_team_id:
            self.fields["away_nominations"].queryset = (
                Player.objects.filter(team_id=inst.away_team_id).order_by("jersey_number", "last_name")
            )
            self.initial["away_nominations"] = list(
                GameNomination.objects.filter(game=inst, team_id=inst.away_team_id).values_list(
                    "player_id", flat=True
                )
            )


# ------------------------------------------------------------
# Game admin
# ------------------------------------------------------------
@admin.register(Game)
class GameAdmin(nested_admin.NestedModelAdmin):
    """Rich admin for games with nested inlines and nomination helpers."""

    form = GameAdminForm

    list_display = (
        "id",
        "starts_at",
        "competition",
        "league",
        "tournament",
        "home_team",
        "away_team",
        "score_home",
        "score_away",
    )
    list_filter = (
        "competition",
        "league",
        "tournament",
        "home_team__league",
        "home_team",
        "away_team",
    )
    date_hierarchy = "starts_at"
    search_fields = ("home_team__name", "away_team__name")

    inlines = [
        HomeGoalieLineInline,
        HomeSkaterLinesInline,
        AwayGoalieLineInline,
        AwaySkaterLinesInline,
        GoalInline,
        PenaltyInline,
    ]
    actions = ["recompute_selected_games", "generate_default_lines", regenerate_calendar_events]

    def get_fieldsets(self, request: Any, obj: Game | None = None):  # type: ignore[override]
        """Group fields and dynamically label nomination sections by team names."""
        home_name = obj.home_team.name if (obj and obj.home_team_id) else "Domácí tým"
        away_name = obj.away_team.name if (obj and obj.away_team_id) else "Hostující tým"
        return (
            ("Info", {"fields": ("starts_at", "stadium", "competition", "league", "tournament")}),
            ("Týmy", {"fields": (("home_team", "score_home"), ("away_team", "score_away"))}),
            (f"Nominace – {home_name}", {"fields": ("home_nominations",)}),
            (f"Nominace – {away_name}", {"fields": ("away_nominations",)}),
        )

    class Media:
        css = {"all": ("powerplay_app/admin_nominations.css",)}

    def changeform_view(self, request: Any, object_id: str | None = None, form_url: str = "", extra_context: dict | None = None):  # type: ignore[override]
        """Inject small CSS tweaks to align score fields and inline styling."""
        css_inline = """
        <style>
          .change-form .module.aligned .form-row .field-score_home,
          .change-form .module.aligned .form-row .field-score_away {
            display: flex !important; align-items: center !important; gap: 8px !important;
          }
          .change-form .module.aligned .form-row .field-score_home label,
          .change-form .module.aligned .form-row .field-score_away label {
            margin: 0 6px 0 0 !important; line-height: 1 !important; float: none !important; width: auto !important; padding: 0 !important;
          }
          #id_score_home, #id_score_away { margin-top: 0 !important; vertical-align: middle !important; }
          .inline-group .inline-related { border: 1px solid #e5e5e5; background: #fafafa; border-radius: 6px; padding: 12px; margin-bottom: 14px; }
        </style>
        """
        extra_context = extra_context or {}
        extra_context["extrahead"] = (extra_context.get("extrahead", "") or "") + css_inline
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)

    @staticmethod
    def _ensure_default_lines(game: Game) -> None:
        """Create default lines 0–3 for both teams when missing (idempotent)."""
        if not (game.home_team_id and game.away_team_id):
            return
        for team in (game.home_team, game.away_team):
            for num in (0, 1, 2, 3):
                Line.objects.get_or_create(game=game, team=team, line_number=num)

    def get_form(self, request: Any, obj: Game | None = None, **kwargs: Any):  # type: ignore[override]
        """Ensure default lines exist before rendering the form."""
        request._current_game = obj
        if obj:
            self._ensure_default_lines(obj)
        return super().get_form(request, obj, **kwargs)

    @admin.action(description="Přepočítat skóre a statistiky pro vybrané zápasy")
    def recompute_selected_games(self, request: Any, queryset: Any) -> None:
        """Recompute score and statistics for selected games using app service."""
        for g in queryset:
            _recompute_game(g)
        self.message_user(request, f"Přepočítáno: {queryset.count()} zápasů")

    @admin.action(description="Vygenerovat výchozí lajny 0–3 pro domácí/hosty (pokud chybí)")
    def generate_default_lines(self, request: Any, queryset: Any) -> None:
        """Create missing default lines for each selected game (both teams)."""
        created = 0
        for g in queryset.select_related("home_team", "away_team"):
            for team in (g.home_team, g.away_team):
                for num in (0, 1, 2, 3):
                    _, was_created = Line.objects.get_or_create(game=g, team=team, line_number=num)
                    created += 1 if was_created else 0
        self.message_user(request, f"Vytvořeno {created} lajn (pokud chyběly).")

    def save_related(self, request: Any, form: forms.ModelForm, formsets: list[Any], change: bool) -> None:  # type: ignore[override]
        """After saving inlines, sync quick nomination checkboxes to DB rows."""
        super().save_related(request, form, formsets, change)
        game: Game = form.instance
        if not game.pk:
            return

        def sync_side(team: Team | None, selected_ids: list[int] | None) -> None:
            if not team:
                return
            selected = set(map(int, selected_ids or []))
            existing = set(
                GameNomination.objects.filter(game=game, team=team).values_list("player_id", flat=True)
            )
            to_add = selected - existing
            if to_add:
                GameNomination.objects.bulk_create(
                    [GameNomination(game=game, team=team, player_id=pid) for pid in to_add],
                    ignore_conflicts=True,
                )
            to_del = existing - selected
            if to_del:
                GameNomination.objects.filter(game=game, team=team, player_id__in=to_del).delete()

        home_sel = form.cleaned_data.get("home_nominations") or []
        away_sel = form.cleaned_data.get("away_nominations") or []
        sync_side(game.home_team, [p.id for p in home_sel])
        sync_side(game.away_team, [p.id for p in away_sel])

        _debug_print_lineups(game)


# ------------------------------------------------------------
# PlayerStats
# ------------------------------------------------------------
@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    """Admin for per-game player statistics."""

    list_display = (
        "player",
        "game",
        "points",
        "goals",
        "assists",
        "penalty_minutes",
        "goals_against",
    )
    list_filter = ("player__team", "game__home_team__league")
    search_fields = ("player__first_name", "player__last_name")


# ------------------------------------------------------------
# Tournament
# ------------------------------------------------------------
@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    """Admin for tournaments with a horizontal selector for games."""

    list_display = ("name", "date_start", "date_end")
    filter_horizontal = ("games",)
    search_fields = ("name",)


# ------------------------------------------------------------
# TeamEvent
# ------------------------------------------------------------
@admin.register(TeamEvent)
class TeamEventAdmin(admin.ModelAdmin):
    """Admin for scheduler events with a custom filter across related games."""

    list_display = ("title", "team_display", "event_type", "starts_at", "ends_at", "is_canceled")
    list_filter = ("event_type", "is_canceled", "source", "auto_synced")
    search_fields = (
        "title",
        "note",
        "location_text",
        "stadium__name",
        "team__name",
        "related_game__home_team__name",
        "related_game__away_team__name",
    )
    raw_id_fields = ("related_game",)
    ordering = ("starts_at",)
    date_hierarchy = "starts_at"
    fieldsets = (
        (None, {"fields": ("team", "event_type", "title", "starts_at", "ends_at", "is_canceled")}),
        ("Místo", {"fields": ("stadium", "location_text")}),
        ("Napojení", {"fields": ("related_game", "source", "auto_synced")}),
        ("Poznámka", {"fields": ("note",)}),
    )

    class TeamAnyFilter(admin.SimpleListFilter):
        """Filter that matches explicit team or either participant of the related game."""

        title = "Tým (včetně zápasů)"
        parameter_name = "team_any"

        def lookups(self, request: Any, model_admin: Any):  # type: ignore[override]
            return [(str(t.id), t.name) for t in Team.objects.order_by("name")]

        def queryset(self, request: Any, queryset: Any):  # type: ignore[override]
            if not self.value():
                return queryset
            team_id = int(self.value())
            return queryset.filter(
                Q(team_id=team_id)
                | Q(related_game__home_team_id=team_id)
                | Q(related_game__away_team_id=team_id)
            )

    def get_list_filter(self, request: Any):  # type: ignore[override]
        return (self.TeamAnyFilter,) + tuple(super().get_list_filter(request))

    def team_display(self, obj: TeamEvent) -> str:
        """Human-readable team column that falls back to the related game teams."""
        if obj.team:
            return obj.team.name
        if obj.related_game_id:
            return f"{obj.related_game.home_team.name} / {obj.related_game.away_team.name}"
        return "—"

    team_display.short_description = "Tým"


# --- DEBUG: print lineups after save (developer visibility only) ---

def _debug_print_lineups(game: Game) -> None:
    """Print home/away lineups for the given game in the server console.

    Why:
        Helps developers quickly verify the nested inline behavior and slot
        assignments when saving a game in admin. Kept as a debug helper.
    """
    try:
        from .models.games import Line, LineAssignment

        order = {"G": 0, "LW": 1, "C": 2, "RW": 3, "LD": 4, "RD": 5}

        print("\n=== LINEUP DEBUG ===")
        print(f"Game #{game.pk}: {game.home_team} vs {game.away_team} @ {game.starts_at}")

        lines = (
            Line.objects.filter(game=game)
            .select_related("team")
            .prefetch_related("players__player")
            .order_by("team__name", "line_number")
        )

        for line in lines:
            print(f"[{line.team.name}] Lajna {line.line_number}:")
            assignments = sorted(line.players.all(), key=lambda a: order.get(a.slot, 99))
            for a in assignments:
                player_txt = f"{a.player.first_name} {a.player.last_name}" if a.player_id else "(prázdné)"
                print(f"  - {a.slot}: {player_txt}")

        print("=== /LINEUP DEBUG ===\n")
    except Exception as e:  # pragma: no cover - debug path
        print(f"[LINEUP DEBUG] Chyba při tisku sestav: {e}")


# ------------------------------------------------------------
# PlayerSeasonTotals (proxy)
# ------------------------------------------------------------
@admin.register(PlayerSeasonTotals)
class PlayerSeasonTotalsAdmin(admin.ModelAdmin):
    """Proxy-based aggregated totals for players shown in list view.

    Totals are computed via annotations to avoid row multiplication; GA values
    are obtained using subqueries scoped to goalie line (line 0) assignments on
    home/away sides.
    """

    list_display = (
        "player_name",
        "team_name",
        "league_name",
        "games_played",
        "goals",
        "assists",
        "points",
        "penalty_minutes",
        "goals_against",
    )
    list_select_related = ("team", "team__league")
    search_fields = ("first_name", "last_name", "nickname", "team__name")
    list_filter = ("team__league", "team")
    actions = ["debug_totals", "debug_ga"]

    def get_queryset(self, request: Any):  # type: ignore[override]
        """Annotate queryset with totals without duplicating rows."""
        qs = super().get_queryset(request)

        # GP, G, A, PIM using correct reverse names
        qs = qs.annotate(
            games_played=Coalesce(Count("nominations__game", distinct=True), Value(0)),
            goals=Coalesce(Count("goals_scored"), Value(0)),
            assists=Coalesce(Count("assists_primary") + Count("assists_secondary"), Value(0)),
            penalty_minutes=Coalesce(Sum("penalty__minutes"), Value(0)),
        ).annotate(points=F("goals") + F("assists"))

        # GA via subqueries to avoid multiplication across other joins
        sq_ga_home = (
            LineAssignment.objects.filter(
                player_id=OuterRef("pk"),
                slot="G",
                line__line_number=0,
                line__game__home_team_id=OuterRef("team_id"),
            )
            .values("player")
            .annotate(s=Sum("line__game__score_away"))
            .values("s")[:1]
        )

        sq_ga_away = (
            LineAssignment.objects.filter(
                player_id=OuterRef("pk"),
                slot="G",
                line__line_number=0,
                line__game__away_team_id=OuterRef("team_id"),
            )
            .values("player")
            .annotate(s=Sum("line__game__score_home"))
            .values("s")[:1]
        )

        qs = qs.annotate(
            goals_against=Coalesce(Subquery(sq_ga_home, output_field=IntegerField()), Value(0))
            + Coalesce(Subquery(sq_ga_away, output_field=IntegerField()), Value(0))
        )

        return qs

    # ---- list_display helpers ----
    @admin.display(ordering="last_name", description="Hráč")
    def player_name(self, obj: Player) -> str:  # type: ignore[override]
        num = f"{obj.jersey_number} " if obj.jersey_number is not None else ""
        return f"{num}{obj.first_name} {obj.last_name}".strip()

    @admin.display(ordering="team__name", description="Tým")
    def team_name(self, obj: Player) -> str:  # type: ignore[override]
        return obj.team.name if obj.team_id else "—"

    @admin.display(ordering="team__league__name", description="Liga")
    def league_name(self, obj: Player) -> str:  # type: ignore[override]
        return obj.team.league.name if obj.team_id and obj.team.league_id else "—"

    @admin.display(ordering="games_played", description="Games played")
    def games_played(self, obj: Any) -> int:  # type: ignore[override]
        return getattr(obj, "games_played", 0)

    @admin.display(ordering="goals", description="Goals")
    def goals(self, obj: Any) -> int:  # type: ignore[override]
        return getattr(obj, "goals", 0)

    @admin.display(ordering="assists", description="Assists")
    def assists(self, obj: Any) -> int:  # type: ignore[override]
        return getattr(obj, "assists", 0)

    @admin.display(ordering="points", description="Points")
    def points(self, obj: Any) -> int:  # type: ignore[override]
        return getattr(obj, "points", 0)

    @admin.display(ordering="penalty_minutes", description="Penalty minutes")
    def penalty_minutes(self, obj: Any) -> int:  # type: ignore[override]
        return getattr(obj, "penalty_minutes", 0)

    @admin.display(ordering="goals_against", description="Goals against")
    def goals_against(self, obj: Any) -> int:  # type: ignore[override]
        return getattr(obj, "goals_against", 0)

    # ---- DEBUG actions ----
    @admin.action(description="DEBUG: vypsat součty do konzole")
    def debug_totals(self, request: Any, queryset: Any) -> None:
        """Print quick totals for selected players to the server console."""
        print("\n==== DEBUG PlayerSeasonTotals (proxy) ====")
        for p in queryset[:20]:
            gp = GameNomination.objects.filter(player=p).values("game").distinct().count()
            g = Goal.objects.filter(scorer=p).count()
            a = Goal.objects.filter(assist_1=p).count() + Goal.objects.filter(assist_2=p).count()
            try:
                pim = Penalty.objects.filter(penalized_player=p).aggregate(Sum("minutes"))["minutes__sum"] or 0
            except Exception:  # pragma: no cover - debug path
                pim = "(?)"
            ga = (
                (p.lineassignment_set.filter(
                    slot="G", line__line_number=0, line__game__home_team=p.team
                ).aggregate(s=Coalesce(Sum("line__game__score_away"), 0))["s"]
                 or 0)
                + (
                    p.lineassignment_set.filter(
                        slot="G", line__line_number=0, line__game__away_team=p.team
                    ).aggregate(s=Coalesce(Sum("line__game__score_home"), 0))["s"]
                    or 0
                )
            )
            print(f"- {p} | GP={gp} G={g} A={a} PTS={g+a} PIM={pim} GA={ga}")
        print("==== /DEBUG =================================\n")
        self.message_user(request, "Výpočet vypsán do konzole (runserver).")

    @admin.action(description="DEBUG: rozpad GA (per zápas) do konzole")
    def debug_ga(self, request: Any, queryset: Any) -> None:
        """Print per-game GA (score-based vs event-based) for selected players."""
        from .models import Goal as GoalModel
        from .models.games import Line as LineModel

        print("\n==== DEBUG GA (per player, per game) ====")
        for p in queryset[:10]:  # limit to avoid noisy console
            print(f"\n--- {p}  [team={p.team}] ---")
            goalie_lines = (
                LineModel.objects.filter(line_number=0, players__player=p)
                .select_related("game", "team")
                .order_by("game_id")
            )

            ga_score_total = 0
            ga_goals_total = 0
            seen_games: set[int] = set()

            for ln in goalie_lines:
                g = ln.game
                opp_score = g.score_away if g.home_team_id == ln.team_id else g.score_home
                goals_against_by_goals = GoalModel.objects.filter(game=g).exclude(team_id=ln.team_id).count()

                dup = ""
                if g.id in seen_games:
                    dup = "  <-- DUPLAJNA pro tento zápas (dvakrát gólman?)"
                else:
                    seen_games.add(g.id)

                print(
                    f"  Game #{g.id}: {g.home_team} {g.score_home}–{g.score_away} {g.away_team} | "
                    f"opp_score={opp_score} | goals_count={goals_against_by_goals}{dup}"
                )

                ga_score_total += opp_score
                ga_goals_total += goals_against_by_goals

            print(f"  TOTAL: GA_from_score={ga_score_total}  |  GA_from_goals={ga_goals_total}")
        print("==== /DEBUG GA ====\n")

        self.message_user(request, "Výpis je v konzoli (runserver).")


@lru_cache(maxsize=1)
def _resolve_default_team_id() -> int | None:
    """Resolve default team id from settings.


    Resolution order:
    1. ``PRIMARY_TEAM_ID`` – if set, return it (as ``int``).
    2. ``PRIMARY_TEAM_NAME`` – if set, look up a team by exact name and
    return its database id.
    3. Otherwise ``None``.


    Returns:
    int | None: Database id of the resolved team or ``None`` if not found.


    Notes:
    Result is cached via :func:`functools.lru_cache` to avoid repeated
    queries. Clear Django caches or restart the process to refresh.
    """
    tid = getattr(settings, "PRIMARY_TEAM_ID", None)
    if tid:
        return int(tid)
    name = getattr(settings, "PRIMARY_TEAM_NAME", None)
    if not name:
        return None
    return Team.objects.filter(name=name).values_list("id", flat=True).first()


class _DefaultTeamMixin:
    """Bind admin to a single *default* team.


    Behavior:
    - List view shows records only for the default team.
    - Change form pre-fills and hides the ``team`` field.
    - Save enforces ``team`` to be set to the default when missing.
    """

    def get_queryset(self, request):
        """Restrict queryset to the resolved default team when available."""
        qs = super().get_queryset(request)
        dtid = _resolve_default_team_id()
        return qs.filter(team_id=dtid) if dtid else qs

    def get_changeform_initial_data(self, request):
        """Pre-fill ``team`` with the default team id in the form initial data."""
        initial = super().get_changeform_initial_data(request)
        dtid = _resolve_default_team_id()
        if dtid:
            initial.setdefault("team", dtid)
        return initial

    def get_form(self, request, obj=None, **kwargs):
        """Hide ``team`` and lock its queryset to the default team only."""
        form = super().get_form(request, obj, **kwargs)
        dtid = _resolve_default_team_id()
        if dtid and "team" in form.base_fields:
            fld = form.base_fields["team"]
            fld.initial = dtid
            fld.queryset = fld.queryset.filter(id=dtid)
            fld.widget = forms.HiddenInput()
        return form

    def save_model(self, request, obj, form, change):
        """Ensure ``team`` is set to the default when not provided."""
        if not getattr(obj, "team_id", None):
            dtid = _resolve_default_team_id()
            if dtid:
                obj.team_id = dtid
        return super().save_model(request, obj, form, change)


@admin.register(WalletCategory)
class WalletCategoryAdmin(_DefaultTeamMixin, admin.ModelAdmin):
    """Admin for wallet categories (scoped to the default team)."""

    list_display = ("name", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("order", "name")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(_DefaultTeamMixin, admin.ModelAdmin):
    """Admin for wallet transactions (scoped to the default team)."""

    list_display = ("date", "category", "kind", "amount", "note")
    list_filter = ("kind", "category")
    search_fields = ("note",)
    date_hierarchy = "date"
    ordering = ("-date", "-id")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit category choices to the default team only."""
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "category" and hasattr(field, "queryset"):
            dtid = _resolve_default_team_id()
            if dtid:
                field.queryset = field.queryset.filter(team_id=dtid)
        return field


# --- Feedback (Připomínky) ---

@admin.register(GameFeedback)
class GameFeedbackAdmin(admin.ModelAdmin):
    """Admin for feedback items (no non-existent ``status`` field).


    Adds a handy filter to distinguish feedback with/without a linked game.
    """

    class HasGameFilter(admin.SimpleListFilter):
        """Filter by presence of a related game."""
        title = "Vazba na zápas"
        parameter_name = "has_game"

        def lookups(self, request, model_admin):
            return [
                ("with", "Má přiřazený zápas"),
                ("without", "Bez zápasu"),
            ]

        def queryset(self, request, queryset):
            if self.value() == "with":
                return queryset.exclude(related_game__isnull=True)
            if self.value() == "without":
                return queryset.filter(related_game__isnull=True)
            return queryset

    list_display = (
        "created_at",
        "team",
        "related_game",
        "subject",
        "created_by_display",
    )
    list_filter = ("team", HasGameFilter)  # ← žádné 'status'
    search_fields = (
        "subject",
        "message",
        "created_by_name",
        "created_by__username",
        "related_game__home_team__name",
        "related_game__away_team__name",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(description="Autor")
    def created_by_display(self, obj: GameFeedback) -> str:
        """Prefer stored author name; otherwise fall back to username."""
        return obj.created_by_name or (getattr(obj.created_by, "username", "") or "—")

