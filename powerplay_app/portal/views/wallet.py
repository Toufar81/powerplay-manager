from __future__ import annotations

from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.views.generic import TemplateView

from powerplay_app.context import _resolve_primary_team
from powerplay_app.models.wallet import WalletTransaction


class WalletView(LoginRequiredMixin, TemplateView):
    template_name = "portal/wallet.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        ctx = super().get_context_data(**kwargs)
        team = _resolve_primary_team()

        qs = WalletTransaction.objects.none()
        total_in = Decimal("0")
        total_out = Decimal("0")
        balance = Decimal("0")

        if team:
            qs = (
                WalletTransaction.objects
                .filter(team=team)
                .select_related("category")
                .order_by("-date", "-id")
            )
            total_in = qs.filter(kind=WalletTransaction.Kind.INCOME).aggregate(
                s=Coalesce(Sum("amount"), Decimal("0"))
            )["s"]
            total_out = qs.filter(kind=WalletTransaction.Kind.EXPENSE).aggregate(
                s=Coalesce(Sum("amount"), Decimal("0"))
            )["s"]
            balance = (total_in or Decimal("0")) - (total_out or Decimal("0"))

        ctx.update({
            "primary_team": team,
            "current": "wallet",
            "tx": qs,
            "total_in": total_in,
            "total_out": total_out,
            "balance": balance,
        })
        return ctx