# File: powerplay_app/tests/models/test_wallet.py
"""Tests for wallet models: categories and transactions.

Covers two guarantees:

- ``WalletCategory`` names are unique **per team**.
- ``WalletTransaction.signed_amount()`` returns ``+amount`` for incomes and
  ``-amount`` for expenses.

Docstrings and internal comments are English. Czech is kept in any user-facing
strings when present (none here).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction
from django.utils import timezone

if TYPE_CHECKING:  # typing-only imports to avoid hard runtime coupling
    from powerplay_app.models import League, Team

pytestmark = pytest.mark.django_db


def _mk_team(name: str, league: "League") -> "Team":
    """Create a ``Team`` in the given league for test isolation."""
    Team = apps.get_model("powerplay_app", "Team")
    return Team.objects.create(league=league, name=name)


def test_wallet_category_unique_per_team(league_min: "League") -> None:
    """Categories must be unique within the same team, but may repeat across teams."""
    WalletCategory = apps.get_model("powerplay_app", "WalletCategory")

    t1 = _mk_team("HC Wallet A", league_min)
    t2 = _mk_team("HC Wallet B", league_min)

    WalletCategory.objects.create(team=t1, name="Členské")

    # Expect duplicate to fail; wrap in atomic to leave transaction clean.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            WalletCategory.objects.create(team=t1, name="Členské")

    # Same name in a different team is valid.
    WalletCategory.objects.create(team=t2, name="Členské")


def test_wallet_transaction_signed_amount_income_expense(league_min: "League") -> None:
    """``signed_amount()`` returns positive for income and negative for expense."""
    WalletTransaction = apps.get_model("powerplay_app", "WalletTransaction")

    t = _mk_team("HC Wallet E", league_min)

    inc = WalletTransaction.objects.create(
        team=t,
        kind="in",
        date=timezone.now().date(),
        amount=Decimal("123.45"),
        note="platba",
    )
    exp = WalletTransaction.objects.create(
        team=t,
        kind="out",
        date=timezone.now().date(),
        amount=Decimal("50.00"),
        note="dresy",
    )

    assert inc.signed_amount() == Decimal("123.45")
    assert exp.signed_amount() == Decimal("-50.00")
