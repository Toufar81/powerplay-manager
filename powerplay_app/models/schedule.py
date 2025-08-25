# file: powerplay_app/models/scheduler.py
"""Scheduling models for team events in the Powerplay domain.

Provides :class:`TeamEvent`, a calendar entry that may stand alone (training,
camp, meeting, etc.) or reference a specific
:class:`~powerplay_app.models.Game`. The model validates temporal and structural
invariants in :meth:`clean`, orders by ``starts_at``, and enforces at most one
event per linked game via a unique constraint.

UI labels (``verbose_name`` etc.) are Czech; internal documentation is English.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


# --- Model -----------------------------------------------------------------


class TeamEvent(models.Model):
    """Calendar event associated with a team or derived from a game.

    Notes:
        - ``event_type`` drives validation rules in :meth:`clean`.
        - When ``event_type`` is ``GAME``, ``team`` is not required and is
          normalized to ``None`` during validation to avoid ambiguity.
        - For all other types, a ``team`` is required.
    """

    class EventType(models.TextChoices):
        """Supported event categories (labels in Czech)."""

        GAME = "game", "Zápas"
        TRAINING = "training", "Trénink"
        CAMP = "camp", "Kemp"
        MEETING = "meeting", "Porada"
        OTHER = "other", "Jiné"

    class Source(models.TextChoices):
        """Origin of the event (labels in Czech)."""

        MANUAL = "manual", "Ručně"
        GAME = "game", "Ze zápasu"

    # ``team`` is optional for GAME but required otherwise.
    team = models.ForeignKey(
        "powerplay_app.Team",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Tým",
        null=True,
        blank=True,
    )
    event_type = models.CharField("Typ události", max_length=20, choices=EventType.choices)
    title = models.CharField(
        "Název",
        max_length=200,
        help_text="Krátký popis (např. Trénink A-tým / Zápas …).",
    )
    starts_at = models.DateTimeField("Začátek")
    ends_at = models.DateTimeField("Konec", help_text="Musí být po začátku.")
    stadium = models.ForeignKey(
        "powerplay_app.Stadium",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Stadion",
    )
    location_text = models.CharField("Místo (textem)", max_length=200, blank=True)
    related_game = models.ForeignKey(
        "powerplay_app.Game",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Související zápas",
    )
    is_canceled = models.BooleanField("Zrušeno", default=False)
    note = models.TextField("Poznámka", blank=True)

    source = models.CharField("Zdroj", max_length=20, choices=Source.choices, default=Source.MANUAL)
    auto_synced = models.BooleanField("Automaticky synchronizováno", default=False)

    class Meta:
        verbose_name = "Událost týmu"
        verbose_name_plural = "Události týmů"
        ordering = ("starts_at",)
        indexes = [
            models.Index(fields=("team", "starts_at")),
            models.Index(fields=("starts_at",)),
        ]
        constraints = [
            # Exactly one TeamEvent per related Game (globally), when set.
            models.UniqueConstraint(
                fields=["related_game"],
                name="uniq_event_per_game",
                condition=Q(related_game__isnull=False),
            )
        ]

    # --- Validation ---------------------------------------------------------

    def clean(self) -> None:
        """Validate temporal order and team/competition invariants.

        Rules:
            * ``ends_at`` must be after ``starts_at``.
            * If ``related_game`` is set, ``event_type`` must be ``GAME``.
            * Non-``GAME`` events require a ``team``.
            * ``GAME`` events should not carry a team reference; it is
              normalized to ``None`` to keep the source of truth on the Game.

        Raises:
            ValidationError: When any rule above is violated.
        """
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValidationError("Konec události musí být po začátku.")

        if self.related_game_id and self.event_type != self.EventType.GAME:
            raise ValidationError({"event_type": "Událost propojená se zápasem musí mít typ 'Zápas'."})

        # All non-game events require a team selection.
        if self.event_type != self.EventType.GAME and not self.team_id:
            raise ValidationError({"team": "U této události je nutné vybrat tým."})

        # For GAME events we keep team unset to avoid duplicating association.
        if self.event_type == self.EventType.GAME:
            self.team = None

    # --- Display ------------------------------------------------------------

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Readable label with type, title, and start datetime."""
        return f"{self.get_event_type_display()}: {self.title} ({self.starts_at:%Y-%m-%d %H:%M})"
