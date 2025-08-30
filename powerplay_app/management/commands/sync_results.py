# file: powerplay_app/management/commands/sync_results.py
"""Synchronize league matches into :class:`Game` via Playwright.

This management command imports matches from ``nocnihokejovaliga.cz`` by
launching a headless Chromium with Playwright and listening to the page's XHR
calls (teams, matches) against the observed API
``https://nhlliga.onrender.com/api``. Retrieved payloads are mapped to local
models and upserted into ``Game`` under the **LEAGUE** competition type.

High-level flow:
    1. Load the schedule page and capture XHR responses for teams and matches.
    2. Build ``{external_team_id: name}`` and a raw list of match dicts.
    3. Resolve the target :class:`League` (CLI args or fallback to the newest).
    4. Optionally expand ``League.date_start/date_end`` so imported games pass
       model validation.
    5. Upsert :class:`Game` rows keyed by ``(competition, league, starts_at,
       home_team, away_team)``; create missing :class:`Team`/:class:`Stadium`
       as needed (case-insensitive caches).

CLI options (Czech UX preserved):
    ``--league-id`` • ``--league-name`` • ``--league-season`` • ``--headful`` •
    ``--dry-run`` • ``--expand-league-dates`` (ON by default).

Assumptions & behavior:
    - All user-facing CLI strings remain Czech.
    - Time parsing converts ISO strings to **timezone-aware UTC** datetimes.
    - Transactions wrap the sync to keep partial imports from leaking.
    - ``--dry-run`` prints intended changes without touching the DB.

Internal documentation is English; schema and behavior are unchanged.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from playwright.sync_api import sync_playwright

from powerplay_app.models import League, Team, Stadium, Goal
from powerplay_app.services.stats import recompute_game

from powerplay_app.models.games import Game, GameCompetition


API_BASE = "https://nhlliga.onrender.com/api"  # kept from logs
SCHEDULE_URL = "https://nocnihokejovaliga.cz/schedule"


# ------------------------------- Playwright fetcher --------------------------------

def _iso_to_aware(dt_str: str) -> datetime:
    """Convert ISO string (e.g. ``"2025-09-01T21:30:00.000Z"``) to aware UTC datetime.

    Args:
        dt_str: ISO timestamp, optionally suffixed with ``Z``.

    Returns:
        Timezone-aware datetime in UTC.
    """
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.utc)
    return dt


def fetch_teams_and_matches(
    season_hint: str | None = None, *, headless: bool = True
) -> Tuple[Dict[int, str], List[dict]]:
    """Fetch teams and matches by listening to XHR calls on the schedule page.

    The page handles season selection internally; we only intercept network
    responses. ``season_hint`` is accepted for potential future use and is
    currently ignored.

    Args:
        season_hint: Optional free-form hint (unused for now).
        headless: Whether to run the browser headless.

    Returns:
        A tuple ``(teams_by_id, matches)`` where ``teams_by_id`` maps external
        team IDs to names and ``matches`` is the raw list of match dicts as
        returned by the remote API.
    """
    teams_by_id: Dict[int, str] = {}
    matches: List[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        def on_response(response: Any) -> None:
            url: str = response.url
            # Teams
            if url.startswith(f"{API_BASE}/teams"):
                try:
                    data = response.json()
                    items = data if isinstance(data, list) else data.get("teams", [])
                    for t in items:
                        name = (t.get("name") or t.get("title") or str(t.get("id"))).strip()
                        teams_by_id[int(t["id"])] = name
                except Exception:  # network / JSON errors are ignored
                    pass

            # Matches
            if re.search(r"/api/matches(\?|$)", url):
                try:
                    data = response.json()
                    if isinstance(data, list):
                        matches.extend(data)
                    elif isinstance(data, dict) and "matches" in data:
                        matches.extend(data["matches"])
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(SCHEDULE_URL, wait_until="domcontentloaded")
        # allow XHR calls to complete
        page.wait_for_timeout(7000)
        browser.close()

    return teams_by_id, matches


# ------------------------------------- Command -------------------------------------
class Command(BaseCommand):
    """Management command to sync league matches via Playwright.

    CLI is Czech; error messages and logs are kept user‑friendly for admins.
    """

    help = "Stáhne zápasy z nocnihokejovaliga.cz a synchronizuje je do tabulky Game."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:  # type: ignore[override]
        """Declare command‑line arguments for the sync command."""
        parser.add_argument("--league-id", type=int, help="ID ligy, do které se mají zápasy zařadit.")
        parser.add_argument("--league-name", type=str, help="Název ligy (pokud neexistuje, vytvoří se).")
        parser.add_argument("--league-season", type=str, help='Sezóna ve formátu např. "2025/2026".')
        parser.add_argument("--headful", action="store_true", help="Spustí Playwright s viditelným oknem.")
        parser.add_argument("--dry-run", action="store_true", help="Jen vypíše, neukládá změny.")
        parser.add_argument(
            "--expand-league-dates",
            action="store_true",
            default=True,
            help=(
                "Případně rozšíří date_start/date_end ligy tak, aby pokrývaly všechny "
                "importované zápasy (default ON)."
            ),
        )
        # Example: python manage.py sync_results --league-name "NHL" --league-season "2025/2026"

    # ---------- helpers ----------
    def _get_target_league(self, options: dict[str, Any]) -> League:
        """Resolve the target league using args or fallbacks.

        Priority:
            1) ``--league-id``
            2) ``--league-name`` + ``--league-season`` (create if missing)
            3) Most recent league by ``date_start``
        """
        # 1) league-id
        if options.get("league_id"):
            try:
                return League.objects.get(pk=options["league_id"])
            except League.DoesNotExist as exc:
                raise CommandError(f"Liga id={options['league_id']} neexistuje.") from exc

        # 2) league-name + season → create when missing
        name = options.get("league_name")
        season = options.get("league_season")
        if name and season:
            league, _ = League.objects.get_or_create(
                name=name,
                season=season,
                defaults={
                    # provisional dates; later expanded by imported matches
                    "date_start": timezone.now().date(),
                    "date_end": timezone.now().date(),
                },
            )
            return league

        # 3) fallback: the newest league
        league = League.objects.order_by("-date_start").first()
        if not league:
            raise CommandError(
                "Nebyla nalezena žádná Liga. Zadej --league-id nebo --league-name + --league-season."
            )
        return league

    def _maybe_expand_league_dates(
        self, league: League, matches: List[dict], expand: bool, dry: bool
    ) -> None:
        """Expand league date boundaries to include imported matches (optional)."""
        if not matches or not expand:
            return

        # compute min/max date from imported payloads
        dates: list[datetime.date] = []
        for m in matches:
            try:
                dates.append(_iso_to_aware(m["match_date"]).date())
            except Exception:
                continue
        if not dates:
            return

        min_d, max_d = min(dates), max(dates)

        # already covered?
        if (
            league.date_start
            and league.date_end
            and league.date_start <= min_d <= league.date_end
            and league.date_start <= max_d <= league.date_end
        ):
            return

        # gently expand by one day to avoid edge time mismatches
        new_start = min(league.date_start or min_d, min_d) - timedelta(days=1)
        new_end = max(league.date_end or max_d, max_d) + timedelta(days=1)

        self.stdout.write(
            f"ℹ️  Rozšiřuji rozsah ligy '{league.name} {league.season}' "
            f"z {league.date_start}–{league.date_end} na {new_start}–{new_end}"
        )
        if not dry:
            league.date_start = new_start
            league.date_end = new_end
            league.save(update_fields=["date_start", "date_end"])

    # ---------- main ----------
    def handle(self, *args: Any, **options: Any) -> None:  # type: ignore[override]
        """Entrypoint for the command; coordinates the sync routine."""
        dry: bool = bool(options.get("dry_run"))
        headless: bool = not bool(options.get("headful"))
        expand_dates: bool = bool(options.get("expand_league_dates"))

        self.stdout.write("🚀 Spouštím synchronizaci zápasů…")
        league = self._get_target_league(options)
        self.stdout.write(f"🎯 Cílová liga: {league}")

        self.stdout.write("🔍 Stahuji teams + matches přes Playwright…")
        teams_by_id, matches = fetch_teams_and_matches(headless=headless)

        self.stdout.write(f"📋 Nalezeno týmů: {len(teams_by_id)} | zápasů: {len(matches)}")

        # optionally expand league date range so ``Game.clean()`` passes
        self._maybe_expand_league_dates(league, matches, expand_dates, dry)

        created_games = 0
        updated_games = 0
        created_teams = 0
        created_stadiums = 0

        # Case-insensitive caches for quick lookup
        team_cache_by_name: Dict[str, Team] = {t.name.lower(): t for t in Team.objects.all()}
        stadium_cache_by_name: Dict[str, Stadium] = {s.name.lower(): s for s in Stadium.objects.all()}

        def get_team(ext_id: int) -> Team:
            """Resolve or create a ``Team`` in the target league by external id.

            If the team exists in another league, it is moved to the target
            league to keep data consistent across imports.
            """
            nonlocal created_teams
            ext_name = teams_by_id.get(int(ext_id)) or f"Team #{ext_id}"
            key = ext_name.lower()
            t = team_cache_by_name.get(key)
            if not t:
                # create the team in the target league
                t = Team.objects.create(name=ext_name, league=league)
                team_cache_by_name[key] = t
                created_teams += 1
            else:
                # move to the target league if needed
                if t.league_id != league.id:
                    t.league = league
                    if not dry:
                        t.save(update_fields=["league"])
            return t

        def get_stadium(venue: str | None) -> Stadium | None:
            """Resolve or create a ``Stadium`` by name (case‑insensitive)."""
            nonlocal created_stadiums
            if not venue:
                return None
            key = venue.strip().lower()
            if not key:
                return None
            s = stadium_cache_by_name.get(key)
            if not s:
                s = Stadium.objects.create(name=venue.strip()) if not dry else Stadium(name=venue.strip())
                stadium_cache_by_name[key] = s
                created_stadiums += 1
            return s

        @transaction.atomic
        def _sync() -> None:
            nonlocal created_games, updated_games

            def prune_goals_to_score(game: Game) -> None:
                """
                Delete extra Goal events if they exceed the manual score on the Game.
                Keeps the newest goals (dle period/second/id) a maže přebytky.
                """
                if not (game.home_team_id and game.away_team_id):
                    return

                def _delete_excess(goals_qs, target_count: int) -> int:
                    target = max(0, int(target_count or 0))
                    total = goals_qs.count()
                    extra = total - target
                    if extra <= 0:
                        return 0
                    # nelze goals_qs[:extra].delete() → získáme PK a smažeme přes pk__in
                    ids = list(goals_qs.values_list("id", flat=True)[:extra])
                    if ids:
                        Goal.objects.filter(id__in=ids).delete()
                    return extra

                # HOME: nejnovější góly jako přebytky
                qs_home = (
                    Goal.objects
                    .filter(game=game, team=game.home_team)
                    .order_by("-period", "-second_in_period", "-id")
                )
                _delete_excess(qs_home, game.score_home)

                # AWAY: dtto
                qs_away = (
                    Goal.objects
                    .filter(game=game, team=game.away_team)
                    .order_by("-period", "-second_in_period", "-id")
                )
                _delete_excess(qs_away, game.score_away)

            for m in matches:
                try:
                    starts_at = _iso_to_aware(m["match_date"])
                except Exception:
                    # skip bad dates
                    self.stdout.write(f"⚠️  Přeskakuji zápas s nevalidním datem: {m.get('match_date')}")
                    continue

                home_team = get_team(m["home_team_id"])
                away_team = get_team(m["away_team_id"])
                stadium = get_stadium(m.get("venue"))

                # None → 0 (DB NOT NULL)
                score_home = m.get("home_score") or 0
                score_away = m.get("away_score") or 0

                # UPSERT by unique constraint for league games
                lookups = dict(
                    competition=GameCompetition.LEAGUE,
                    league=league,
                    starts_at=starts_at,
                    home_team=home_team,
                    away_team=away_team,
                )
                defaults = dict(
                    score_home=score_home,
                    score_away=score_away,
                    stadium=stadium,
                )

                if dry:
                    # simulate upsert
                    exists = Game.objects.filter(**lookups).first()
                    if exists:
                        will_change = (
                            exists.score_home != score_home
                            or exists.score_away != score_away
                            or (stadium and exists.stadium_id != stadium.id)
                            or exists.competition != GameCompetition.LEAGUE
                            or exists.league_id != league.id
                        )
                        if will_change:
                            updated_games += 1
                    else:
                        created_games += 1
                    continue

                obj, created = Game.objects.update_or_create(defaults=defaults, **lookups)
                if created:
                    created_games += 1
                else:
                    # When stadium is None in both old/new values, Django won't mark as changed — that's fine.
                    updated_games += 1

                # Zarovnej počet Goal událostí na uložené skóre a přepočti PlayerStats
                prune_goals_to_score(obj)
                recompute_game(obj)

        _sync()

        self.stdout.write("")
        self.stdout.write("✅ Hotovo.")
        self.stdout.write(f"   🆕 Týmy vytvořeno:      {created_teams}")
        self.stdout.write(f"   🏟  Stadiony vytvořeno:  {created_stadiums}")
        self.stdout.write(f"   🆕 Zápasy vytvořeno:     {created_games}")
        self.stdout.write(f"   ♻️  Zápasy aktualizováno: {updated_games}")
        if dry:
            self.stdout.write("   (dry‑run: nic se neuložilo)")
