# file: powerplay_app/models/wallet.py
"""Wallet (cashbox) models for team income/expense tracking.

Provides :class:`WalletCategory` for per-team categorization and
:class:`WalletTransaction` for recording individual entries. Monetary values are
stored as :class:`decimal.Decimal`. Validation logic lives in forms/services;
these models focus on structure and display. UI labels are Czech; internal
documentation is English.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models


# --- Categories ------------------------------------------------------------


class WalletCategory(models.Model):
    """Category for wallet transactions scoped per team.

    The combination ``(team, name)`` is unique, preventing duplicate category
    names within the same team. Ordering by team, explicit order, and name keeps
    UI lists stable.
    """

    team = models.ForeignKey(
        "powerplay_app.Team",
        on_delete=models.CASCADE,
        related_name="wallet_categories",
        verbose_name="Tým",
    )
    name = models.CharField("Název", max_length=80)
    is_active = models.BooleanField("Aktivní", default=True)
    order = models.PositiveSmallIntegerField("Pořadí", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kategorie pokladny"
        verbose_name_plural = "Kategorie pokladny"
        ordering = ("team", "order", "name")
        unique_together = ("team", "name")

    def __str__(self) -> str:  # pragma: no cover
        """Human-readable label used in admin and selects."""
        return f"{self.team.name} • {self.name}"


# --- Transactions ----------------------------------------------------------


class WalletTransaction(models.Model):
    """Single wallet entry (income/expense)."""

    class Kind(models.TextChoices):
        """Transaction direction (labels in Czech)."""

        INCOME = "in", "Příjem"
        EXPENSE = "out", "Výdaj"

    team = models.ForeignKey(
        "powerplay_app.Team",
        on_delete=models.CASCADE,
        related_name="wallet_transactions",
        verbose_name="Tým",
    )
    category = models.ForeignKey(
        WalletCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="Kategorie",
    )
    kind = models.CharField("Typ", max_length=4, choices=Kind.choices)
    date = models.DateField("Datum")
    amount = models.DecimalField("Částka", max_digits=10, decimal_places=2)
    note = models.CharField("Poznámka", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Položka pokladny"
        verbose_name_plural = "Položky pokladny"
        ordering = ("-date", "-id")
        indexes = [models.Index(fields=("team", "date"))]

    def signed_amount(self) -> Decimal:
        """Return amount with sign according to transaction kind.

        Returns:
            ``+amount`` for income, ``-amount`` for expense.
        """
        return self.amount if self.kind == self.Kind.INCOME else -self.amount

    def __str__(self) -> str:  # pragma: no cover
        """Concise summary label for lists and admin."""
        sign = "+" if self.kind == self.Kind.INCOME else "−"
        return f"{self.date} {sign}{self.amount} {self.category or ''}"
