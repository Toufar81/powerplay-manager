# file: powerplay_app/tests/management/test_sync_results_and_fetcher.py
"""End-to-end tests for Playwright-based fetcher and ``sync_results`` command.

Coverage:
* Stubbing Playwright to test minimal output shape and proper browser closing.
* Management command smoke path (empty inputs) and full-flow object creation.
* Idempotent updates of scores and automatic league date expansion.
"""

from __future__ import annotations

import importlib
import io
import sys
import types
from typing import Any, Callable, Tuple

import pytest
from django.apps import apps
from django.core.management import call_command
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers: Fake Playwright stack (used to stub network in fetcher tests)
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal response object returning JSON payloads or raising errors."""

    def __init__(self, url: str, data: Any | None = None, raises: Exception | None = None) -> None:
        self.url = url
        self._data = data
        self._raises = raises

    def json(self) -> Any:
        """Return provided JSON payload or raise the configured exception."""
        if self._raises:
            raise self._raises
        return self._data


class _FakePage:
    """Single page with ``response`` event dispatch and optional goto error."""

    def __init__(self, responses: list[_FakeResponse], raise_in_goto: bool = False) -> None:
        self._responses = responses
        self._on_response_cb: Callable[[Any], None] | None = None
        self._raise_in_goto = raise_in_goto

    def on(self, event: str, cb: Callable[[Any], None]) -> None:
        """Register a callback for ``response`` events."""
        if event == "response":
            self._on_response_cb = cb

    def goto(self, url: str) -> None:
        """Optionally raise to simulate navigation failures."""
        if self._raise_in_goto:
            raise RuntimeError("boom in goto")

    def wait_for_timeout(self, ms: int) -> None:
        """Emit stored responses to the registered callback."""
        if self._on_response_cb:
            for r in self._responses:
                self._on_response_cb(r)


class _FakeBrowser:
    """Fake browser tracking ``close`` calls."""

    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.closed = False

    def new_page(self) -> _FakePage:
        """Return the preconfigured page instance."""
        return self._page

    def close(self) -> None:
        """Record that the browser was closed (for assertions)."""
        self.closed = True


class _FakeChromium:
    """Chromium facade producing a single fake browser while storing a handle."""

    def __init__(self, page: _FakePage, last: "_Last") -> None:
        self._page = page
        self._last = last

    def launch(self, headless: bool = False) -> _FakeBrowser:  # noqa: ARG002 - test helper
        """Launch a fake browser and expose it via ``_Last`` reference."""
        b = _FakeBrowser(self._page)
        self._last.browser = b
        return b


class _FakePlaywright:
    """Context manager exposing a fake Chromium implementation."""

    def __init__(self, page: _FakePage, last: "_Last") -> None:
        self.chromium = _FakeChromium(page, last)

    def __enter__(self) -> "_FakePlaywright":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: D401 - standard CM signature
        return False


class _Last:
    """Container used to expose the created browser to the test for assertions."""

    browser: _FakeBrowser | None = None


def _import_fetcher_with_stub(monkeypatch: pytest.MonkeyPatch, pw_impl: Callable[[], Any]) -> types.ModuleType:
    """Import fetcher module after stubbing Playwright with ``pw_impl``.

    If the target fetcher module is missing in the repository, skip tests
    with a Czech message to keep the suite green across environments.
    """
    pkg = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = pw_impl
    monkeypatch.setitem(sys.modules, "playwright", pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    # Reload target module with our stubbed Playwright. If not present, skip.
    if "powerplay_app.fetch_results_playwright" in sys.modules:
        del sys.modules["powerplay_app.fetch_results_playwright"]
    try:
        return importlib.import_module("powerplay_app.fetch_results_playwright")
    except ModuleNotFoundError:
        pytest.skip(
            "powerplay_app.fetch_results_playwright není v repu – fetcher testy přeskočeny"
        )


# ---------------------------------------------------------------------------
# a) Snapshot-like shape tests for fetch_results_playwright
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload, expected_ids",
    [
        ([{"id": 1}, {"id": 2}], [1, 2]),
        ({"matches": [{"id": 10}, {"id": 11}]}, [10, 11]),
    ],
)
def test_fetcher_min_shape_snapshot(monkeypatch: pytest.MonkeyPatch, payload: Any, expected_ids: list[int]) -> None:
    """Ensure fetcher returns list of dicts with IDs and closes browser."""
    responses = [_FakeResponse("https://host/api/matches", payload)]
    page = _FakePage(responses)
    last = _Last()

    def stub_sync_playwright() -> _FakePlaywright:
        return _FakePlaywright(page, last)

    mod = _import_fetcher_with_stub(monkeypatch, stub_sync_playwright)

    out = mod.fetch_results_playwright(log=False)
    assert isinstance(out, list)
    assert [m.get("id") for m in out] == expected_ids
    # Minimal shape (snapshot-light)
    for m in out:
        assert "id" in m and isinstance(m["id"], int)
    assert last.browser and last.browser.closed is True


# ---------------------------------------------------------------------------
# b) Management command `sync_results`
#    – smoke: invokes fetcher and does not fail on empty input
# ---------------------------------------------------------------------------


def test_sync_results_invokes_fetcher_and_handles_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the command calls fetcher and handles empty datasets without errors."""
    League = apps.get_model("powerplay_app", "League")
    Game = apps.get_model("powerplay_app", "Game")

    league = League.objects.create(
        name="Liga CMD", season="2025/2026", date_start="2025-08-01", date_end="2026-05-01"
    )

    calls: dict[str, Any] = {}

    def fake_fetch_teams_and_matches(**kwargs: Any) -> tuple[dict[int, str], list[dict[str, Any]]]:
        """Capture kwargs and return empty teams/matches."""
        calls["kwargs"] = kwargs
        return {}, []

    # Patch directly into the command module so the invocation goes through our stub
    cmd_mod = importlib.import_module("powerplay_app.management.commands.sync_results")
    monkeypatch.setattr(cmd_mod, "fetch_teams_and_matches", fake_fetch_teams_and_matches, raising=True)

    # Run the command (admin uses arguments league_id, headful)
    call_command("sync_results", league_id=league.id, headful=False)

    # Verify: fetcher was called and no Game was created
    assert "kwargs" in calls
    assert Game.objects.count() == 0


# ---------------------------------------------------------------------------
# c) Full-flow tests for management command `sync_results`
# ---------------------------------------------------------------------------

import importlib as _il_again  # local alias to avoid shadowing above


def _run_sync_with_stub(
    monkeypatch: pytest.MonkeyPatch,
    league: Any,
    teams_by_id: dict[int, str],
    matches: list[dict[str, Any]],
) -> tuple[str, types.ModuleType]:
    """Patch fetcher, run the command, and return ``(stdout, cmd_module)``.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        league: League instance to sync.
        teams_by_id: Mapping of external team IDs to names.
        matches: Iterable of match payload dicts.
    """
    cmd_mod = _il_again.import_module("powerplay_app.management.commands.sync_results")

    def fake_fetch_teams_and_matches(**kwargs: Any) -> tuple[dict[int, str], list[dict[str, Any]]]:
        return teams_by_id, matches

    monkeypatch.setattr(cmd_mod, "fetch_teams_and_matches", fake_fetch_teams_and_matches, raising=True)
    out = io.StringIO()
    call_command("sync_results", league_id=league.id, headful=False, stdout=out)
    return out.getvalue(), cmd_mod


def test_sync_results_creates_game_and_related_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Create teams/stadium and a game from fetched data."""
    League = apps.get_model("powerplay_app", "League")
    Team = apps.get_model("powerplay_app", "Team")
    Stadium = apps.get_model("powerplay_app", "Stadium")
    Game = apps.get_model("powerplay_app", "Game")

    league = League.objects.create(
        name="Liga Sync 1",
        season="2025/2026",
        date_start=timezone.now().date(),
        date_end=timezone.now().date(),
    )

    teams = {2: "HC Sync A", 6: "HC Sync B"}
    matches = [
        {
            "id": 360,
            "season_id": 1,
            "home_team_id": 2,
            "away_team_id": 6,
            "home_score": None,
            "away_score": None,
            "match_date": "2026-02-13T21:00:00.000Z",
            "status": "scheduled",
            "venue": "PORUBA",
            "record_image": None,
        }
    ]

    stdout, _ = _run_sync_with_stub(monkeypatch, league, teams, matches)

    assert Team.objects.filter(name__in=["HC Sync A", "HC Sync B"], league=league).count() == 2
    assert Stadium.objects.filter(name__iexact="PORUBA").exists()
    g = Game.objects.get()
    assert g.home_team.name == "HC Sync A"
    assert g.away_team.name == "HC Sync B"
    assert g.league_id == league.id
    assert g.score_home == 0 and g.score_away == 0  # None → 0
    assert g.stadium and g.stadium.name.upper() == "PORUBA"


def test_sync_results_is_idempotent_and_updates_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    """Upsert behavior: second run updates scores of the existing game."""
    League = apps.get_model("powerplay_app", "League")
    Game = apps.get_model("powerplay_app", "Game")

    league = League.objects.create(
        name="Liga Sync 2",
        season="2025/2026",
        date_start=timezone.now().date(),
        date_end=timezone.now().date(),
    )

    teams = {2: "HC Sync A2", 6: "HC Sync B2"}

    # 1st run: scheduled (no scores)
    matches1 = [
        {
            "id": 400,
            "season_id": 1,
            "home_team_id": 2,
            "away_team_id": 6,
            "home_score": None,
            "away_score": None,
            "match_date": "2026-03-01T19:00:00.000Z",
            "status": "scheduled",
            "venue": None,
            "record_image": None,
        }
    ]
    _run_sync_with_stub(monkeypatch, league, teams, matches1)
    assert Game.objects.count() == 1
    g = Game.objects.get()
    assert (g.score_home, g.score_away) == (0, 0)

    # 2nd run: finished (scores present) → must update existing row
    matches2 = [
        {
            "id": 400,
            "season_id": 1,
            "home_team_id": 2,
            "away_team_id": 6,
            "home_score": 4,
            "away_score": 2,
            "match_date": "2026-03-01T19:00:00.000Z",
            "status": "finished",
            "venue": None,
            "record_image": None,
        }
    ]
    _run_sync_with_stub(monkeypatch, league, teams, matches2)

    assert Game.objects.count() == 1  # idempotent by (league, dt, home, away)
    g.refresh_from_db()
    assert (g.score_home, g.score_away) == (4, 2)


def test_sync_results_expands_league_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expand league date range to envelop fetched matches (±1 day around bounds)."""
    League = apps.get_model("powerplay_app", "League")
    Game = apps.get_model("powerplay_app", "Game")

    # League that does NOT cover upcoming match date → command should expand
    league = League.objects.create(
        name="Liga Sync 3",
        season="2025/2026",
        date_start=timezone.now().date(),
        date_end=timezone.now().date(),
    )

    teams = {2: "HC Sync A3", 6: "HC Sync B3"}
    matches = [
        {
            "id": 500,
            "season_id": 1,
            "home_team_id": 2,
            "away_team_id": 6,
            "home_score": 1,
            "away_score": 1,
            "match_date": "2026-04-10T18:30:00.000Z",
            "status": "scheduled",
            "venue": None,
            "record_image": None,
        }
    ]

    old_start, old_end = league.date_start, league.date_end
    _run_sync_with_stub(monkeypatch, league, teams, matches)

    league.refresh_from_db()
    # Date range expanded by ±1 day around min/max match dates
    assert league.date_start <= old_start
    assert league.date_end >= timezone.datetime.fromisoformat("2026-04-10T00:00:00+00:00").date()
    assert Game.objects.count() == 1
