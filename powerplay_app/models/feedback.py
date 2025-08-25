# file: powerplay_app/models/feedback.py
"""Feedback models attached to teams.

This module provides :class:`GameFeedback` for collecting user-submitted
feedback scoped to a team. Each entry may optionally reference an individual
:class:`~powerplay_app.models.Game` or a calendar
:class:`~powerplay_app.models.TeamEvent`. Author information is stored both as
an FK (``created_by``) and as a denormalized snapshot (``created_by_name``) so
that labels remain stable if accounts change later.

UI labels (``verbose_name`` etc.) are Czech; internal documentation is English.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


# --- Model -----------------------------------------------------------------


class GameFeedback(models.Model):
    """User-submitted feedback for a team.

    Entries may optionally link to a specific game or a team calendar event.
    The author is stored as a user FK and as a denormalized display name
    snapshot to keep labels stable over time.
    """

    team = models.ForeignKey(
        "powerplay_app.Team",
        on_delete=models.CASCADE,
        related_name="feedbacks",
        verbose_name="Tým",
    )

    # Feedback may reference a game or an event (or neither).
    related_game = models.ForeignKey(
        "powerplay_app.Game",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
        verbose_name="Zápas",
    )
    related_event = models.ForeignKey(
        "powerplay_app.TeamEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
        verbose_name="Událost",
    )

    subject = models.CharField("Předmět", max_length=120, blank=True)
    message = models.TextField("Zpráva")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_feedbacks",
        verbose_name="Vytvořil (uživatel)",
    )
    created_by_name = models.CharField(
        "Jméno autora (snapshot)", max_length=120, blank=True
    )

    class Meta:
        verbose_name = "Připomínka"
        verbose_name_plural = "Připomínky"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("team", "created_at"))]

    def __str__(self) -> str:  # pragma: no cover
        """Short label for admin lists (team, subject preview, and target)."""
        target = self.related_event or self.related_game or "bez vazby"
        return f"[{self.team}] {self.subject or self.message[:25]}… → {target}"
