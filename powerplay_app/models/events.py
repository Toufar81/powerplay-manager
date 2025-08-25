# file: powerplay_app/models/events.py
"""Game event models attached to a :class:`Game`.

This module defines domain objects that capture what happens during a match:

- **Enumerations**
  - :class:`Period` – periods 1–3, overtime, shootout.
  - :class:`Strength` – game strength at the moment of a goal (EV/PP/OS/EN/PS).
  - :class:`PenaltyType` – penalty types (2/5/10/20).

- **Abstract base**
  - :class:`GameEventBase` – shared fields (``game``, ``team``, ``period``,
    ``second_in_period``) and validation that the selected team participates in the game.

- **Concrete events**
  - :class:`Goal` – a goal with a scorer, up to two assists, and a
    :class:`Strength` value. Validation requires all involved players to belong
    to the scoring team and to be nominated for the game via
    :class:`powerplay_app.models.games.GameNomination`. Assists must not
    duplicate the scorer or each other.
  - :class:`Penalty` – a penalty referencing the offending player, duration, and type.
    Validation requires the player to belong to the penalized team and to be
    nominated for the game.

UI labels (``verbose_name`` etc.) are in Czech; internal documentation is in English.
The module only applies validation rules to stored data.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from .games import GameNomination


# --- Enums -----------------------------------------------------------------


class Period(models.IntegerChoices):
    """Enumeration of game periods (labels in Czech)."""

    FIRST = 1, "1. třetina"
    SECOND = 2, "2. třetina"
    THIRD = 3, "3. třetina"
    OT = 4, "Prodloužení"
    SO = 5, "Nájezdy"


class Strength(models.TextChoices):
    """Enumeration of strength states at the moment of a goal (labels in Czech)."""

    EV = "EV", "Plný počet"
    PP = "PP", "Přesilovka"
    SH = "OS", "Oslabení"
    EN = "EN", "Do prázdné"
    PS = "PS", "Trestné střílení"


class PenaltyType(models.TextChoices):
    """Enumeration of penalty categories and their nominal durations (labels in Czech)."""

    MINOR = "2", "Malý trest (2)"
    MAJOR = "5", "Velký trest (5)"
    MISCONDUCT = "10", "Osobní trest (10)"
    GAME = "20", "Do konce utkání (20)"


# --- Base ------------------------------------------------------------------


class GameEventBase(models.Model):
    """Abstract base for timestamped, team‑bound game events.

    Attributes:
        game: Game to which the event belongs.
        team: Team credited with the event (must participate in the game).
        period: Game period when the event occurred.
        second_in_period: Seconds elapsed within the period.
    """

    game = models.ForeignKey(
        "powerplay_app.Game", on_delete=models.CASCADE, verbose_name="Zápas"
    )
    team = models.ForeignKey(
        "powerplay_app.Team", on_delete=models.CASCADE, verbose_name="Tým"
    )
    period = models.IntegerField("Třetina", choices=Period.choices)
    second_in_period = models.PositiveIntegerField("Čas")

    class Meta:
        abstract = True

    def clean(self) -> None:
        """Ensure the selected team participates in the given game.

        Raises:
            ValidationError: If the team is not either the home or away team.
        """
        if (
            self.game_id
            and self.team_id
            and self.team_id
            not in (self.game.home_team_id, self.game.away_team_id)
        ):
            raise ValidationError(
                "Událost může být jen pro tým účastnící se zápasu."
            )


# --- Concrete events -------------------------------------------------------


class Goal(GameEventBase):
    """Scored goal with optional primary/secondary assists.

    Validation ensures scorer and assistants belong to the scoring team and are
    nominated for the game.
    """

    scorer = models.ForeignKey(
        "powerplay_app.Player",
        on_delete=models.CASCADE,
        related_name="goals_scored",
        verbose_name="Střelec",
    )
    assist_1 = models.ForeignKey(
        "powerplay_app.Player",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assists_primary",
        verbose_name="Asistence 1",
    )
    assist_2 = models.ForeignKey(
        "powerplay_app.Player",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assists_secondary",
        verbose_name="Asistence 2",
    )
    strength = models.CharField(
        "Síla hry", max_length=2, choices=Strength.choices, default=Strength.EV
    )

    class Meta:
        verbose_name = "Gól"
        verbose_name_plural = "Góly"

    def clean(self) -> None:
        """Run base validation and goal-specific domain rules.

        Rules:
            * Team must participate in the game (base rule).
            * Scorer/assistants must belong to the scoring team.
            * Scorer/assistants must be nominated for the game.
            * Assistant 1 cannot be the scorer.
            * Assistant 2 cannot be the scorer nor equal to Assistant 1.

        Raises:
            ValidationError: If any rule is violated.
        """
        super().clean()

        players = [self.scorer, self.assist_1, self.assist_2]
        for player in filter(None, players):
            if player.team_id != self.team_id:
                raise ValidationError(
                    "Střelec i asistenti musí být z týmu, který gól vstřelil."
                )
            if self.game_id and not GameNomination.objects.filter(
                game_id=self.game_id, player_id=player.id
            ).exists():
                raise ValidationError(
                    "Střelec/asistenti musí být nominováni do tohoto zápasu."
                )

        if self.assist_1 and self.assist_1_id == self.scorer_id:
            raise ValidationError("Asistent 1 nesmí být zároveň střelcem.")

        if self.assist_2 and (
            self.assist_2_id == self.scorer_id
            or self.assist_2_id == self.assist_1_id
        ):
            raise ValidationError(
                "Asistent 2 nesmí být střelcem ani shodný s Asistentem 1."
            )


class Penalty(GameEventBase):
    """Penalty assigned to a player within a specific game/team context.

    Validation ensures the player belongs to the penalized team and is
    nominated for the game.
    """

    penalized_player = models.ForeignKey(
        "powerplay_app.Player", on_delete=models.CASCADE, verbose_name="Faulující hráč"
    )
    minutes = models.PositiveSmallIntegerField("Délka trestu (min)")
    penalty_type = models.CharField(
        "Typ trestu", max_length=3, choices=PenaltyType.choices, default=PenaltyType.MINOR
    )
    reason = models.CharField("Důvod", max_length=200, blank=True)

    class Meta:
        verbose_name = "Trest"
        verbose_name_plural = "Tresty"

    def clean(self) -> None:
        """Run base validation and penalty-specific rules.

        Raises:
            ValidationError: If the player is not from the penalized team or was
            not nominated for the game.
        """
        super().clean()

        if self.penalized_player and self.penalized_player.team_id != self.team_id:
            raise ValidationError(
                "Trest musí být připsán týmu, za který faulující hráč hraje v zápase."
            )

        if (
            self.game_id
            and self.penalized_player_id
            and not GameNomination.objects.filter(
                game_id=self.game_id, player_id=self.penalized_player_id
            ).exists()
        ):
            raise ValidationError(
                "Faulující hráč musí být nominován do tohoto zápasu."
            )
