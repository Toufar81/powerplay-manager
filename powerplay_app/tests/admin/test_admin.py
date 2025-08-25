# file: powerplay_app/tests/admin/test_admin.py
"""Admin-related test suite for Django admin customizations.

Guidelines for this repository:
- Docstrings, internal comments, and variable/method names are **English**.
- User-facing strings remain **Czech** (assertions keep CZ text where applicable).
- No behavior changes; this file focuses on cleanliness, hints, and docs.

Test coverage in this module:
* Registry presence of key models in the Django admin site.
* Player label helpers and custom choice field behavior.
* Queryset filtering helpers for game-side nominations.
* GameAdmin utilities for ensuring/generating default lines.
* GameAdminForm field labels and initial nomination population.
* Inlines (Goal/Penalty) foreign key queryset restrictions.
* Actions for regenerating calendar events and syncing league results.
* Custom admin list filter matching team or related game on TeamEvent.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.contrib import admin
from django.http import HttpRequest
from django.test import RequestFactory

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def make_request(path: str = "/admin/") -> HttpRequest:
    """Create a GET request with a dummy superuser for admin actions.

    The attached user satisfies permission checks (e.g., inlines calling
    ``request.user.has_perm``), ensuring admin formsets and actions can run.
    """
    req = RequestFactory().get(path)
    # Admin inlines call request.user.has_perm → attach a dummy superuser
    import types

    req.user = types.SimpleNamespace(
        has_perm=lambda perm: True,
        is_authenticated=True,
        is_active=True,
        is_staff=True,
        is_superuser=True,
    )
    return req


def setup_league_team_game() -> tuple[Any, Any, Any, Any]:
    """Create a minimal League, two Teams, and a Game linked to the league.

    Returns:
        tuple[Any, Any, Any, Any]: ``(league, home_team, away_team, game)``
        using dynamic models resolved via ``apps.get_model``.
    """
    League = apps.get_model("powerplay_app", "League")
    Team = apps.get_model("powerplay_app", "Team")
    Game = apps.get_model("powerplay_app", "Game")

    league = League.objects.create(
        name="Admin Liga", season="2025/2026", date_start="2025-08-01", date_end="2026-05-01"
    )
    home = Team.objects.create(league=league, name="HC Admin Home")
    away = Team.objects.create(league=league, name="HC Admin Away")
    game = Game.objects.create(
        starts_at="2025-09-01T18:00:00+00:00",
        home_team=home,
        away_team=away,
        competition=apps.get_model("powerplay_app", "Game")._meta.get_field("competition").choices[0][0],
        league=league,
    )
    return league, home, away, game


# --- Registry --------------------------------------------------------------


def test_admin_registry_contains_expected_models() -> None:
    """Ensure admin registry includes key models we expose in Django admin."""
    registry = admin.site._registry
    expected = [
        "League",
        "Stadium",
        "Team",
        "Country",
        "Player",
        "Game",
        "PlayerStats",
        "Tournament",
        "Staff",
        "TeamEvent",
        "PlayerSeasonTotals",
    ]
    for name in expected:
        model = apps.get_model("powerplay_app", name)
        assert model in registry


# --- _player_plain_label / PlayerChoiceField ------------------------------


def test_player_plain_label_and_choice_field_label() -> None:
    """Verify player label helper and custom choice field output (Czech)."""
    from powerplay_app.admin import _player_plain_label, PlayerChoiceField

    League = apps.get_model("powerplay_app", "League")
    Team = apps.get_model("powerplay_app", "Team")
    Player = apps.get_model("powerplay_app", "Player")

    league = League.objects.create(
        name="L-Label", season="2025/2026", date_start="2025-08-01", date_end="2026-05-01"
    )
    t = Team.objects.create(league=league, name="HC Label")
    p = Player.objects.create(
        first_name="Jan", last_name="Test", jersey_number=10, position="forward", team=t, nickname="Bomber"
    )
    assert _player_plain_label(p) == "10 Jan Test (Bomber)"

    field = PlayerChoiceField(queryset=Player.objects.all())
    assert field.label_from_instance(p) == "10 Jan Test (Bomber)"


# --- _players_qs_for_side -------------------------------------------------


def test_players_qs_for_side_filters_to_nominations() -> None:
    """Limit player queryset to those nominated for the given game's side."""
    from powerplay_app.admin import _players_qs_for_side

    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    Player = apps.get_model("powerplay_app", "Player")

    _, home, away, game = setup_league_team_game()

    hp = Player.objects.create(first_name="H", last_name="One", jersey_number=9, position="forward", team=home)
    ap = Player.objects.create(first_name="A", last_name="Two", jersey_number=8, position="forward", team=away)
    other_team = apps.get_model("powerplay_app", "Team").objects.create(league=home.league, name="HC Other")
    op = Player.objects.create(first_name="O", last_name="Other", jersey_number=7, position="forward", team=other_team)

    GameNomination.objects.create(game=game, team=home, player=hp)
    GameNomination.objects.create(game=game, team=away, player=ap)

    qs_home = _players_qs_for_side(game, home)
    qs_away = _players_qs_for_side(game, away)

    assert list(qs_home.values_list("id", flat=True)) == [hp.id]
    assert list(qs_away.values_list("id", flat=True)) == [ap.id]
    assert op.id not in list(qs_home.values_list("id", flat=True))


# --- GameAdmin: ensure lines & generate action ----------------------------


def test_game_admin_ensure_default_lines_idempotent() -> None:
    """Confirm creating default lines is idempotent and totals 8 (2 teams × 4)."""
    Line = apps.get_model("powerplay_app", "Line")
    Game = apps.get_model("powerplay_app", "Game")
    _, _, _, game = setup_league_team_game()

    from powerplay_app.admin import GameAdmin

    ga = GameAdmin(Game, admin.site)
    ga._ensure_default_lines(game)
    ga._ensure_default_lines(game)

    counts = Line.objects.filter(game=game).count()
    # 2 teams * lines 0..3 = 8
    assert counts == 8


def test_game_admin_generate_default_lines_action_creates_missing() -> None:
    """Ensure the admin action generates missing default lines for a game."""
    Line = apps.get_model("powerplay_app", "Line")
    Game = apps.get_model("powerplay_app", "Game")
    _, _, _, g1 = setup_league_team_game()

    from powerplay_app.admin import GameAdmin

    ga = GameAdmin(Game, admin.site)

    # No existing lines initially
    assert Line.objects.filter(game=g1).count() == 0

    req = make_request()
    ga.message_user = lambda *a, **k: None  # Silence user messages during test
    ga.generate_default_lines(req, Game.objects.filter(pk=g1.pk))

    assert Line.objects.filter(game=g1).count() == 8


# --- GameAdminForm: labels and initial nominations ------------------------


def test_game_admin_form_labels_and_initials() -> None:
    """Verify Czech labels and initial nominations for admin form fields."""
    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    Player = apps.get_model("powerplay_app", "Player")
    _, home, away, game = setup_league_team_game()

    hp1 = Player.objects.create(first_name="H1", last_name="P", jersey_number=11, position="forward", team=home)
    ap1 = Player.objects.create(first_name="A1", last_name="P", jersey_number=21, position="forward", team=away)

    GameNomination.objects.create(game=game, team=home, player=hp1)
    GameNomination.objects.create(game=game, team=away, player=ap1)

    from powerplay_app.admin import GameAdminForm

    form = GameAdminForm(instance=game)

    assert form.fields["score_home"].label == "Skóre"
    assert form.fields["score_away"].label == "Skóre"

    # Home/away querysets prefilled
    assert list(form.fields["home_nominations"].queryset.values_list("id", flat=True)) == [hp1.id]
    assert list(form.fields["away_nominations"].queryset.values_list("id", flat=True)) == [ap1.id]

    # Initial preselects
    assert set(form.initial["home_nominations"]) == {hp1.id}
    assert set(form.initial["away_nominations"]) == {ap1.id}


# --- GoalInline / PenaltyInline filtering --------------------------------


def test_goal_inline_foreignkeys_filtered() -> None:
    """Limit GoalInline foreign keys to teams/players relevant to the game."""
    Player = apps.get_model("powerplay_app", "Player")
    _, home, away, game = setup_league_team_game()
    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    Goal = apps.get_model("powerplay_app", "Goal")

    hp = Player.objects.create(first_name="H", last_name="One", jersey_number=9, position="forward", team=home)
    ap = Player.objects.create(first_name="A", last_name="Two", jersey_number=8, position="forward", team=away)

    GameNomination.objects.create(game=game, team=home, player=hp)
    GameNomination.objects.create(game=game, team=away, player=ap)

    from powerplay_app.admin import GoalInline

    inline = GoalInline(parent_model=apps.get_model("powerplay_app", "Game"), admin_site=admin.site)
    # Bind current game via get_formset
    inline.get_formset(make_request(), obj=game)

    # Team field limited to game participants
    team_field = inline.formfield_for_foreignkey(Goal._meta.get_field("team"), make_request())
    teams = set(team_field.queryset.values_list("name", flat=True))
    assert teams == {home.name, away.name}

    # Scorer limited to nominated players from both sides
    sc_field = inline.formfield_for_foreignkey(Goal._meta.get_field("scorer"), make_request())
    ids = set(sc_field.queryset.values_list("id", flat=True))
    assert ids == {hp.id, ap.id}


def test_penalty_inline_foreignkeys_filtered() -> None:
    """Limit PenaltyInline foreign keys to teams/players relevant to the game."""
    Player = apps.get_model("powerplay_app", "Player")
    _, home, away, game = setup_league_team_game()
    GameNomination = apps.get_model("powerplay_app", "GameNomination")
    Penalty = apps.get_model("powerplay_app", "Penalty")

    hp = Player.objects.create(first_name="H", last_name="One", jersey_number=9, position="forward", team=home)
    ap = Player.objects.create(first_name="A", last_name="Two", jersey_number=8, position="forward", team=away)

    GameNomination.objects.create(game=game, team=home, player=hp)
    GameNomination.objects.create(game=game, team=away, player=ap)

    from powerplay_app.admin import PenaltyInline

    inline = PenaltyInline(parent_model=apps.get_model("powerplay_app", "Game"), admin_site=admin.site)
    inline.get_formset(make_request(), obj=game)

    team_field = inline.formfield_for_foreignkey(Penalty._meta.get_field("team"), make_request())
    teams = set(team_field.queryset.values_list("name", flat=True))
    assert teams == {home.name, away.name}

    pp_field = inline.formfield_for_foreignkey(Penalty._meta.get_field("penalized_player"), make_request())
    ids = set(pp_field.queryset.values_list("id", flat=True))
    assert ids == {hp.id, ap.id}


# --- regenerate_calendar_events action -----------------------------------


def test_regenerate_calendar_events_calls_sync(monkeypatch: Any) -> None:
    """Verify admin action calls the game→calendar sync with ``create_if_missing``.
    """
    _, _, _, game = setup_league_team_game()
    Game = apps.get_model("powerplay_app", "Game")

    calls: list[tuple[int, bool]] = []

    def fake_sync(g: Any, create_if_missing: bool = False) -> None:
        """Collect call arguments to assert invocation happened as expected."""
        calls.append((g.pk, create_if_missing))

    # Imported inside action from powerplay_app.signals
    monkeypatch.setattr("powerplay_app.signals._sync_event_for_game", fake_sync)

    from powerplay_app.admin import regenerate_calendar_events, GameAdmin

    # Need a ModelAdmin with message_user
    ga = GameAdmin(Game, admin.site)
    ga.message_user = lambda *a, **k: None  # Silence user messages

    regenerate_calendar_events(ga, make_request(), Game.objects.filter(pk=game.pk))

    assert calls == [(game.pk, True)]


# --- LeagueAdmin.sync_results_for_league ----------------------------------


def test_league_admin_sync_results_invokes_command(monkeypatch: Any) -> None:
    """Ensure action runs ``sync_results`` for the selected league (headless)."""
    League = apps.get_model("powerplay_app", "League")
    league = League.objects.create(name="L1", season="2025/2026", date_start="2025-08-01", date_end="2026-05-01")

    called: dict[str, Any] = {}

    def fake_call_command(cmd: str, **kwargs: Any) -> None:
        """Capture management command invocation for assertion."""
        called["cmd"] = cmd
        called["kwargs"] = kwargs

    monkeypatch.setattr("powerplay_app.admin.call_command", fake_call_command)

    from powerplay_app.admin import LeagueAdmin

    la = LeagueAdmin(League, admin.site)
    la.message_user = lambda *a, **k: None

    la.sync_results_for_league(make_request(), League.objects.filter(pk=league.pk))

    assert called["cmd"] == "sync_results"
    assert called["kwargs"]["league_id"] == league.id
    assert called["kwargs"]["headful"] is False


def test_league_admin_sync_results_requires_single_selection() -> None:
    """Show a Czech error message unless exactly one league is selected."""
    League = apps.get_model("powerplay_app", "League")
    l1 = League.objects.create(name="L1", season="2025/2026", date_start="2025-08-01", date_end="2026-05-01")
    l2 = League.objects.create(name="L2", season="2025/2026", date_start="2025-08-01", date_end="2026-05-01")

    from powerplay_app.admin import LeagueAdmin

    la = LeagueAdmin(League, admin.site)

    # Capture error path via message_user; should not raise
    msgs: list[tuple[str, Any | None]] = []
    la.message_user = lambda request, msg, level=None: msgs.append((msg, level))

    la.sync_results_for_league(make_request(), League.objects.filter(pk__in=[l1.pk, l2.pk]))

    assert msgs and "Vyber přesně jednu ligu" in msgs[0][0]


# --- TeamEventAdmin.TeamAnyFilter ----------------------------------------


def test_team_event_admin_any_filter_matches_team_or_related_game() -> None:
    """Filter returns events by explicit team or by related game's teams."""
    TeamEvent = apps.get_model("powerplay_app", "TeamEvent")
    _, home, away, game = setup_league_team_game()
    # Defensive: ensure no auto-generated event from signals exists for game
    TeamEvent.objects.filter(related_game=game).delete()

    # Event without explicit team but with related_game
    ev1 = TeamEvent.objects.create(
        event_type="game",
        title="E1",
        starts_at="2025-09-10T18:00:00+00:00",
        ends_at="2025-09-10T20:00:00+00:00",
        related_game=game,
    )
    # Event with explicit team
    ev2 = TeamEvent.objects.create(
        team=home,
        event_type="training",
        title="E2",
        starts_at="2025-09-11T18:00:00+00:00",
        ends_at="2025-09-11T19:00:00+00:00",
    )

    from powerplay_app.admin import TeamEventAdmin

    tea = TeamEventAdmin(TeamEvent, admin.site)

    # Filtering by home.id must return both (ev2 via team, ev1 via related_game.home)
    class DummyReq:
        """Minimal request-like object providing GET for admin filters."""

        GET = {"team_any": str(home.id)}

    qs = tea.get_queryset(DummyReq())  # Base queryset from the admin
    filtered = TeamEventAdmin.TeamAnyFilter(DummyReq(), {}, TeamEvent, tea).queryset(DummyReq(), qs)
    assert set(filtered.values_list("id", flat=True)) == {ev1.id, ev2.id}
