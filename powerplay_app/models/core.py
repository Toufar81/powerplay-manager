# file: powerplay_app/models.py
"""Core domain models for the hockey team management app.

Contains foundational entities:
- :class:`League` with season range and auto-filled season label.
- :class:`Stadium` as an arena/venue.
- :class:`Team` participating in a league (globally unique name).
- :class:`Country` of birth (unique ISO code).
- :class:`Player` with per-team jersey uniqueness and photo URL helper.

Internal documentation is English; user-facing labels stay Czech. Behavior and
schema are unchanged.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.db import models
from django.templatetags.static import static


# --- League ----------------------------------------------------------------


class League(models.Model):
    """A hockey league/competition and its season timeframe.

    The ``season`` label can be provided manually (e.g., "2025/2026"). If it is
    left empty, it is derived from ``date_start`` and ``date_end`` during save.
    """

    name = models.CharField("Název ligy", max_length=255)
    season = models.CharField("Sezóna", max_length=20, blank=True)
    logo = models.ImageField("Logo", upload_to="liga_loga/", blank=True, null=True)
    date_start = models.DateField("Začátek sezóny")
    date_end = models.DateField("Konec sezóny")

    class Meta:
        verbose_name = "Liga"
        verbose_name_plural = "Ligy"
        constraints = [
            # Stejný název ligy se může opakovat, ale ne ve stejné sezóně
            models.UniqueConstraint(fields=["name", "season"], name="uniq_league_name_season"),
        ]

    def clean(self) -> None:
        """Validate model state before saving.

        Raises:
            ValidationError: If ``date_end`` is before ``date_start``.
        """
        if self.date_end and self.date_start and self.date_end < self.date_start:
            # User-facing validation message remains in Czech.
            raise ValidationError("Konec sezóny musí být po začátku.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist the league and auto-fill ``season`` when empty.

        If ``season`` is empty and both dates are present, it is derived from the
        years of ``date_start`` and ``date_end`` (e.g., ``2025/2026``).
        """
        if not self.season and self.date_start and self.date_end:
            y1 = self.date_start.year
            y2 = self.date_end.year
            self.season = f"{y1}/{y2}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Compact label combining league name and season."""
        return f"{self.name} {self.season}".strip()


# --- Stadium ---------------------------------------------------------------


class Stadium(models.Model):
    """Ice hockey stadium or arena where matches are played."""

    name = models.CharField("Název stadionu", max_length=255)
    address = models.CharField("Adresa", max_length=255, blank=True, null=True)
    map_url = models.URLField("Mapa", blank=True, null=True)

    class Meta:
        verbose_name = "Stadion"
        verbose_name_plural = "Stadiony"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name

    # --- helper for safe embed ------------------------------------------------
    def embed_url(self) -> str | None:
        """Return a Google Maps *embed* URL when possible.

        Logic:
        - If ``map_url`` already looks like an embeddable link (contains
          "embed" or "output=embed"), use it as-is.
        - Else, if we have at least an address (fallback to name), construct
          a generic Google query embed URL.
        - Otherwise return ``None`` to indicate there is nothing to embed.
        """
        if self.map_url and ("embed" in self.map_url or "output=embed" in self.map_url):
            return self.map_url
        query = self.address or self.name
        if query:
            return f"https://www.google.com/maps?q={quote(query)}&output=embed"
        return None


# --- Team ------------------------------------------------------------------


class Team(models.Model):
    """A hockey team participating in a league.

    Notes:
        ``name`` is globally unique among teams.
    """

    league = models.ForeignKey(
        "powerplay_app.League", on_delete=models.CASCADE, related_name="teams", verbose_name="Liga"
    )
    name = models.CharField("Název týmu", max_length=255, unique=True)
    city = models.CharField("Město", max_length=255, blank=True, null=True)
    coach = models.CharField("Trenér", max_length=255, blank=True, null=True)
    stadium = models.ForeignKey(
        "powerplay_app.Stadium", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Stadion"
    )
    logo = models.ImageField("Logo týmu", upload_to="team_loga/", blank=True, null=True)
    staff_notes = models.TextField("Poznámky k realizačnímu týmu", blank=True, null=True)

    class Meta:
        verbose_name = "Tým"
        verbose_name_plural = "Týmy"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


# --- Country ---------------------------------------------------------------


class Country(models.Model):
    """Country of birth with a unique ISO code."""

    name = models.CharField("Stát", max_length=100)
    iso_code = models.CharField("ISO kód", max_length=3, unique=True)

    class Meta:
        verbose_name = "Stát"
        verbose_name_plural = "Státy narození"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} ({self.iso_code})"


# --- Player ----------------------------------------------------------------


class Player(models.Model):
    """Player entity associated with a specific team.

    The jersey number is unique per team (enforced by a DB constraint). The
    :meth:`photo_url` helper returns a URL or a static fallback if the photo is
    not available.
    """

    class Position(models.TextChoices):
        """Supported hockey player positions (UI labels in Czech)."""

        FORWARD = "forward", "Útočník"
        DEFENSE = "defense", "Obránce"
        GOALIE = "goalie", "Brankář"

    first_name = models.CharField("Jméno", max_length=255)
    last_name = models.CharField("Příjmení", max_length=255)
    birth_date = models.DateField("Datum narození", blank=True, null=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Stát")
    nickname = models.CharField("Přezdívka", max_length=50, blank=True, null=True)
    phone = models.CharField("Telefon", max_length=20, blank=True, null=True)
    email = models.EmailField("E-mail", blank=True, null=True)
    jersey_number = models.PositiveIntegerField("Číslo dresu")
    position = models.CharField("Pozice", max_length=50, choices=Position.choices)
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, related_name="players", verbose_name="Tým"
    )
    photo = models.ImageField(
        "Profilová fotka", upload_to="player_photos/", blank=True, null=True, help_text="Doporučeno 300×300 px."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "jersey_number"], name="uniq_jersey_per_team")
        ]
        verbose_name = "Hráč"
        verbose_name_plural = "Hráči"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.first_name} {self.last_name}"

    def photo_url(self) -> str:
        """Return a public URL for the player's photo or a static fallback.

        If the stored image URL cannot be resolved or the photo is not set, a
        static fallback path is returned. Broad exception handling is
        intentional to avoid breaking templates when storage backends raise
        unexpected runtime errors.
        """
        if self.photo:
            try:
                return self.photo.url
            except Exception:  # noqa: BLE001 - keep broad to match original behavior
                pass
        return static("powerplay_app/img/default_player.png")
