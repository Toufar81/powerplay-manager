# file: powerplay_app/models/games.py
"""Game domain models: fixtures, nominations, lines, and assignments.

Contains:
* :class:`GameCompetition` – competition type enum.
* :class:`Game` – scheduled match with league/tournament/friendly rules.
* :class:`GameNomination` – player nominations for a given game.
* :class:`Line` – team formations per game (0 = goalie line).
* :class:`LineSlot` – positions within a line.
* :class:`LineAssignment` – player-to-slot assignment with domain validation.

Internal documentation is English; user-facing labels remain Czech. Behavior
and schema are unchanged.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .tournaments import Tournament
from .core import League
from django.urls import reverse
from django.utils.text import slugify


# --- Competition enum ------------------------------------------------------


class GameCompetition(models.TextChoices):
    """Type of competition the game belongs to (labels in Czech)."""

    LEAGUE = "league", "Ligový zápas"
    TOURNAMENT = "tournament", "Turnaj"
    FRIENDLY = "friendly", "Přátelský"


# --- Game ------------------------------------------------------------------


class Game(models.Model):
    """A scheduled game between two teams with optional competition context.

    Notes:
        * For ``LEAGUE`` games, ``league`` must be set and both teams must
          belong to that league; date must fall within the league season.
        * For ``TOURNAMENT`` games, ``tournament`` must be set; date must be
          within the tournament range when defined.
        * For ``FRIENDLY`` games, neither ``league`` nor ``tournament`` may be
          set.
    """

    starts_at = models.DateTimeField("Datum a čas zápasu")
    time_only = models.TimeField("Čas (volitelné)", blank=True, null=True)

    home_team = models.ForeignKey(
        "powerplay_app.Team",
        on_delete=models.CASCADE,
        related_name="games_home",
        verbose_name="Domácí tým",
    )
    away_team = models.ForeignKey(
        "powerplay_app.Team",
        on_delete=models.CASCADE,
        related_name="games_away",
        verbose_name="Hostující tým",
    )

    score_home = models.PositiveIntegerField("Skóre domácí", default=0)
    score_away = models.PositiveIntegerField("Skóre hosté", default=0)

    stadium = models.ForeignKey(
        "powerplay_app.Stadium",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Stadion",
    )

    competition = models.CharField(
        "Typ utkání",
        max_length=20,
        choices=GameCompetition.choices,
        default=GameCompetition.LEAGUE,
        help_text="Ligový / Turnaj / Přátelský",
    )
    league = models.ForeignKey(
        League,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Liga",
        help_text="Vyplň pouze u ligového zápasu.",
    )
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Turnaj",
        help_text="Vyplň pouze u turnajového zápasu.",
    )

    class Meta:
        verbose_name = "Zápas"
        verbose_name_plural = "Zápasy"
        constraints = [
            # League: unique across (league, starts_at, home, away)
            models.UniqueConstraint(
                fields=["competition", "league", "starts_at", "home_team", "away_team"],
                name="uniq_game_league",
                condition=Q(competition=GameCompetition.LEAGUE),
            ),
            # Tournament: unique across (tournament, starts_at, home, away)
            models.UniqueConstraint(
                fields=["competition", "tournament", "starts_at", "home_team", "away_team"],
                name="uniq_game_tournament",
                condition=Q(competition=GameCompetition.TOURNAMENT),
            ),
            # Friendly: unique across (competition, starts_at, home, away)
            models.UniqueConstraint(
                fields=["competition", "starts_at", "home_team", "away_team"],
                name="uniq_game_friendly",
                condition=Q(competition=GameCompetition.FRIENDLY),
            ),
        ]

    def clean(self) -> None:
        """Validate team distinctness and competition-specific rules.

        Raises:
            ValidationError: If any business rule is violated.
        """
        # Teams must be different
        if self.home_team_id and self.home_team_id == self.away_team_id:
            raise ValidationError("Domácí a hostující tým nesmí být stejný.")

        # Competition rules
        if self.competition == GameCompetition.LEAGUE:
            if not self.league_id:
                raise ValidationError({"league": "Ligový zápas musí mít vybranou ligu."})
            if self.tournament_id:
                raise ValidationError({"tournament": "Ligový zápas nesmí mít vyplněný turnaj."})

            # Both teams must belong to the selected league
            if self.home_team and self.home_team.league_id != self.league_id:
                raise ValidationError({"home_team": "Domácí tým nepatří do zvolené ligy."})
            if self.away_team and self.away_team.league_id != self.league_id:
                raise ValidationError({"away_team": "Hostující tým nepatří do zvolené ligy."})

            # Date must be within league season interval
            if (
                self.starts_at
                and self.league
                and self.league.date_start
                and self.league.date_end
            ):
                d = self.starts_at.date()
                if not (self.league.date_start <= d <= self.league.date_end):
                    raise ValidationError({"starts_at": "Termín zápasu je mimo rozmezí sezóny ligy."})

        elif self.competition == GameCompetition.TOURNAMENT:
            if not self.tournament_id:
                raise ValidationError({"tournament": "Turnajový zápas musí mít vybraný turnaj."})
            if self.league_id:
                raise ValidationError({"league": "Turnajový zápas nesmí mít vybranou ligu."})

            # Date must be within tournament interval (when present)
            if (
                self.starts_at
                and self.tournament
                and self.tournament.date_start
                and self.tournament.date_end
            ):
                d = self.starts_at.date()
                if not (self.tournament.date_start <= d <= self.tournament.date_end):
                    raise ValidationError({"starts_at": "Termín zápasu je mimo rozmezí turnaje."})

        else:  # FRIENDLY
            if self.league_id or self.tournament_id:
                raise ValidationError("Přátelský zápas nesmí mít vyplněnou ligu/turnaj.")

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Readable label: ``Home vs Away (YYYY-MM-DD HH:MM)``."""
        return f"{self.home_team} vs {self.away_team} ({self.starts_at:%Y-%m-%d %H:%M})"

    def canonical_slug(self) -> str:
        """Canonical human-readable slug: YYYY-MM-DD-home-vs-away."""
        date_part = self.starts_at.date().isoformat() if self.starts_at else "game"
        home = slugify(self.home_team.name) if self.home_team_id else "home"
        away = slugify(self.away_team.name) if self.away_team_id else "away"
        return f"{date_part}-{home}-vs-{away}"

    def get_absolute_url(self) -> str:  # pragma: no cover - simple helper
        """Site URL for public/portal detail (same view, forks by auth)."""
        return reverse("site:game_detail", args=[self.pk, self.canonical_slug()])

# --- Game nomination -------------------------------------------------------


class GameNomination(models.Model):
    """Nomination binding a player to a particular game (with team shortcut).

    ``team`` duplicates the player's team for efficient filtering and
    validation. When ``team`` is not provided, it is auto-filled from the
    player on save.
    """

    game = models.ForeignKey(
        "powerplay_app.Game",
        on_delete=models.CASCADE,
        related_name="nominations",
        verbose_name="Zápas",
    )
    player = models.ForeignKey(
        "powerplay_app.Player",
        on_delete=models.CASCADE,
        related_name="nominations",
        verbose_name="Hráč",
    )
    team = models.ForeignKey("powerplay_app.Team", on_delete=models.CASCADE, verbose_name="Tým")

    class Meta:
        verbose_name = "Nominace do zápasu"
        verbose_name_plural = "Nominace do zápasu"
        constraints = [
            models.UniqueConstraint(fields=("game", "player"), name="uniq_nomination_game_player"),
        ]

    def clean(self) -> None:
        """Validate team membership and game participation.

        Raises:
            ValidationError: If the player is not from the selected team or the
            team is not participating in the game.
        """
        # Player must belong to the selected team
        if self.player_id and self.team_id and self.player.team_id != self.team_id:
            raise ValidationError("Hráč nepatří do vybraného týmu.")

        # Team must participate in the game
        if (
            self.game_id
            and self.team_id
            and self.team_id not in (self.game.home_team_id, self.game.away_team_id)
        ):
            raise ValidationError("Tým v nominaci není účastníkem tohoto zápasu.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Fill ``team`` from player's current team if missing, then persist."""
        if not self.team_id and self.player_id:
            self.team_id = self.player.team_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Readable label with game and player."""
        return f"{self.game} – {self.player}"


# --- Line ------------------------------------------------------------------


class Line(models.Model):
    """A line (formation) for a team in a specific game.

    ``line_number`` enumerates formations (1, 2, 3, …). Number ``0`` denotes
    the goalie line.
    """

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="lines", verbose_name="Zápas")
    team = models.ForeignKey("powerplay_app.Team", on_delete=models.CASCADE, verbose_name="Tým")
    line_number = models.PositiveIntegerField("Číslo lajny", help_text="1, 2, 3 …; 0 = gólman")

    class Meta:
        unique_together = ("game", "team", "line_number")
        verbose_name = "Lajna"
        verbose_name_plural = "Lajny"

    def clean(self) -> None:
        """Ensure the line belongs to a team participating in the game."""
        if (
            self.game_id
            and self.team_id
            and self.team_id not in (self.game.home_team_id, self.game.away_team_id)
        ):
            raise ValidationError(
                "Lajna může patřit jen domácímu nebo hostujícímu týmu daného zápasu."
            )

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Readable label with team name and line number."""
        return f"{self.team} - Lajna {self.line_number}"


# --- Line slot enum --------------------------------------------------------


class LineSlot(models.TextChoices):
    """Positions available within a line (labels in Czech)."""

    LW = "LW", "Levé křídlo"
    C = "C", "Střed"
    RW = "RW", "Pravé křídlo"
    LD = "LD", "Levá obrana"
    RD = "RD", "Pravá obrana"
    G = "G", "Brankář"


# --- Line assignment -------------------------------------------------------


class LineAssignment(models.Model):
    """Assignment of a player to a line and specific slot within a game.

    The player field is optional to allow explicit empty slots.

    Domain rules enforced in ``clean``:
        * Player must belong to the same team as the line.
        * Line ``0`` is goalie-only: only slot ``G`` is allowed and, if filled,
          the player's position must be goalie.
        * A player cannot appear in multiple lines for the same game.
    """

    line = models.ForeignKey(Line, on_delete=models.CASCADE, related_name="players", verbose_name="Lajna")
    player = models.ForeignKey(
        "powerplay_app.Player",
        on_delete=models.CASCADE,
        verbose_name="Hráč",
        null=True,
        blank=True,  # Slot may be intentionally empty
    )
    slot = models.CharField("Post", max_length=2, choices=LineSlot.choices)

    class Meta:
        unique_together = (("line", "slot"),)
        verbose_name = "Hráč v lajně"
        verbose_name_plural = "Hráči v lajně"

    def clean(self) -> None:
        """Validate team consistency, goalie rules, and uniqueness per game."""
        # Player must be from the same team as the line
        if self.line_id and self.player_id:
            if self.player.team_id != self.line.team_id:
                raise ValidationError("Hráč v lajně musí patřit do stejného týmu jako lajna.")

        # Goalie line (0) → only slot G; if player set, must be a goalie
        if self.line and self.line.line_number == 0:
            if self.slot != LineSlot.G:
                raise ValidationError("V brankářské lajně (0) je povolen pouze post Brankář.")
            if self.player_id and self.player.position != "goalie":
                raise ValidationError("Do brankářské lajny lze přiřadit jen hráče s pozicí Brankář.")

        # Player cannot be assigned to another line in the same game
        if self.player_id and self.line_id:
            game_id = self.line.game_id
            exists_elsewhere = (
                LineAssignment.objects.filter(player_id=self.player_id, line__game_id=game_id)
                .exclude(pk=self.pk)
                .exists()
            )
            if exists_elsewhere:
                raise ValidationError("Hráč už je přiřazen v jiné lajně v tomto zápase.")

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Readable label with player (or placeholder), slot, and line."""
        player_txt = str(self.player) if self.player_id else "—"
        return f"{player_txt} – {self.get_slot_display()} ({self.line})"
