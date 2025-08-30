# file: powerplay_app/models/staff.py
"""Team staff (coaches and support roles) linked to teams.

Defines the :class:`Staff` model used to store non-player personnel for a team
(e.g., coaches, physios, managers). Phone numbers are validated by a reusable
regex validator. All user-facing labels remain Czech.
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

# Validator is defined at module scope for reuse and easier testing.
phone_validator: RegexValidator = RegexValidator(
    regex=r"^\+?[0-9\- ]{7,20}$",
    message="Zadej platné telefonní číslo (např. +420 123 456 789).",
)


# --- Model -----------------------------------------------------------------


class Staff(models.Model):
    """Member of a team's staff (coach, physiotherapist, manager, etc.).

    Notes:
        - ``staff_members`` reverse accessor on ``Team`` is explicit.
        - ``order`` enables custom ordering within the team section.
        - Phone and email are optional; ``phone`` is validated by
          :data:`phone_validator`.
    """

    team = models.ForeignKey(
        "powerplay_app.Team",
        on_delete=models.CASCADE,
        related_name="staff_members",  # explicit, avoids ambiguity
        verbose_name="Tým",
    )
    first_name = models.CharField("Jméno", max_length=100)
    last_name = models.CharField("Příjmení", max_length=100)
    role = models.CharField("Funkce", max_length=255)

    # NEW: delší popis role/funkce
    role_description = models.TextField("Popis funkce", blank=True)

    phone = models.CharField(
        "Telefon", max_length=30, blank=True, null=True, validators=[phone_validator]
    )
    email = models.EmailField("E-mail", blank=True, null=True)
    photo = models.ImageField("Fotografie", upload_to="staff_photos/", blank=True, null=True)
    address = models.CharField("Adresa", max_length=255, blank=True, null=True)
    is_active = models.BooleanField("Aktivní", default=True)
    order = models.PositiveIntegerField("Pořadí", default=0)

    class Meta:
        verbose_name = "Člen realizačního týmu"
        verbose_name_plural = "Realizační tým"
        ordering = ("team", "order", "last_name")

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Readable label: full name, role, and team."""
        return f"{self.first_name} {self.last_name} – {self.role} ({self.team})"
