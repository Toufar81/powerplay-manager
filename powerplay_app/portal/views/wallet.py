# file: powerplay_app/portal/views/wallet.py
"""Wallet (cashbox) portal view.

Exposes :class:`WalletView`, a login-protected template view that renders
``portal/wallet.html``. The page summarizes a team's cashflow for a selected
period (month or year) based on :class:`powerplay_app.models.wallet.WalletTransaction`.
The *primary* team is resolved via the context service; when absent, the view
returns stable defaults.

Flow:
    1. Read GET params ``period`` (``"year"`` or ``"month"``), ``year``, and
       ``month``. Fallbacks use ``timezone.now()`` and available years for the
       team (computed via ``.dates('date', 'year')``).
    2. Compute an **inclusive** date window with ``_range_for``.
    3. Build a base queryset for the team and compute aggregates:
       - ``balance_all`` across **all** transactions (team-scoped).
       - Window totals ``total_in`` / ``total_out`` and ``balance``.
       Aggregations use ``Coalesce`` to preserve ``Decimal('0')`` semantics.
    4. Derive top categories (up to 5) for expenses and incomes.

Context keys provided to the template:
    - ``primary_team`` – resolved team or ``None``.
    - ``current`` – menu marker ``"wallet"``.
    - ``period``, ``year``, ``month`` – current filter values.
    - ``year_choices`` – list of available years for the dropdown.
    - ``months`` – Czech month choices for the UI.
    - ``range_from`` / ``range_to`` – inclusive window bounds.
    - ``tx`` – filtered transaction queryset ordered by ``-date``, ``-id``.
    - ``total_in`` / ``total_out`` / ``balance`` – window aggregates.
    - ``balance_all`` – aggregate across all data regardless of the filter.
    - ``top_exp`` / ``top_inc`` – top 5 categories by amount.

Internal documentation is in English; user-facing strings remain Czech.
Behavior is unchanged.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any, TYPE_CHECKING

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.views.generic import TemplateView

from powerplay_app.context import _resolve_primary_team
from powerplay_app.models.wallet import WalletTransaction

if TYPE_CHECKING:  # import only for typing to avoid runtime coupling
    from powerplay_app.models import Team


# Month choices displayed in the UI (Czech labels)
CZ_MONTHS = [
    (1, "leden"), (2, "únor"), (3, "březen"), (4, "duben"),
    (5, "květen"), (6, "červen"), (7, "červenec"), (8, "srpen"),
    (9, "září"), (10, "říjen"), (11, "listopad"), (12, "prosinec"),
]


class WalletView(LoginRequiredMixin, TemplateView):
    """Team wallet overview for authenticated users.

    Context keys:
        - ``primary_team``: The current team in scope (or ``None``).
        - ``period``/``year``/``month``: Current filter selection.
        - ``range_from``/``range_to``: Inclusive date window for the listing.
        - ``tx``: Filtered queryset of transactions.
        - ``total_in``/``total_out``/``balance``: Aggregates for the window.
        - ``balance_all``: Aggregate across *all* data regardless of filter.
        - ``top_exp``/``top_inc``: Top categories (up to 5) by amount.
    """

    template_name = "portal/wallet.html"

    # ---- helpers -----------------------------------------------------------
    def _years_for_team(self, team: "Team" | None) -> list[int]:
        """Return all years with any transactions; fallback to current year.

        The query uses ``.dates('date', 'year')`` to keep it database-side, then
        extracts unique years for the filter dropdown.
        """
        if not team:
            return [timezone.now().year]
        years = [d.year for d in WalletTransaction.objects.filter(team=team).dates("date", "year")]
        return years or [timezone.now().year]

    def _range_for(self, period: str, year: int, month: int) -> tuple[date, date]:
        """Compute an inclusive date range for the given selection.

        Args:
            period: ``"month"`` for a monthly range; any other value yields yearly.
            year: Target year.
            month: Target month (1–12); caller clamps to sane bounds.
        """
        if period == "month":
            last = monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, last)
        # default = whole year
        return date(year, 1, 1), date(year, 12, 31)

    # ---- view --------------------------------------------------------------
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Assemble filter values, compute aggregates, and provide lists.

        Notes:
            - Keeps defaults stable even if there is no team yet.
            - Uses explicit fallbacks to ``Decimal('0')`` to simplify templates.
        """
        ctx = super().get_context_data(**kwargs)
        team = _resolve_primary_team()

        # ---- read filter ----------------------------------------------------
        years = self._years_for_team(team)
        now = timezone.now()
        period = self.request.GET.get("period", "year")
        try:
            year = int(self.request.GET.get("year", years[-1]))
        except Exception:
            year = years[-1]
        try:
            month = int(self.request.GET.get("month", now.month))
        except Exception:
            month = now.month
        # keep sane values
        if year not in years:
            years.append(year)
            years = sorted(set(years))
        month = 1 if month < 1 else (12 if month > 12 else month)

        since, until = self._range_for(period, year, month)

        # ---- base queryset --------------------------------------------------
        tx_all = WalletTransaction.objects.none()
        tx_filtered = WalletTransaction.objects.none()
        total_in = total_out = balance = Decimal("0")
        top_exp: list[dict[str, Any]] = []
        top_inc: list[dict[str, Any]] = []

        if team:
            tx_all = WalletTransaction.objects.filter(team=team).select_related("category")

            # independent total balance (across all records)
            all_in = tx_all.filter(kind=WalletTransaction.Kind.INCOME).aggregate(
                s=Coalesce(Sum("amount"), Decimal("0"))
            )["s"]
            all_out = tx_all.filter(kind=WalletTransaction.Kind.EXPENSE).aggregate(
                s=Coalesce(Sum("amount"), Decimal("0"))
            )["s"]
            balance_all = (all_in or Decimal("0")) - (all_out or Decimal("0"))

            # filtered window (list + aggregates + TOP)
            tx_filtered = tx_all.filter(date__gte=since, date__lte=until).order_by("-date", "-id")

            total_in = tx_filtered.filter(kind="in").aggregate(s=Coalesce(Sum("amount"), Decimal("0")))["s"]
            total_out = tx_filtered.filter(kind="out").aggregate(s=Coalesce(Sum("amount"), Decimal("0")))["s"]
            balance = (total_in or Decimal("0")) - (total_out or Decimal("0"))

            # TOP categories (expenses / incomes) – top 5
            top_exp = (
                tx_filtered.filter(kind="out", category__isnull=False)
                .values("category__name")
                .annotate(s=Sum("amount"))
                .order_by("-s")[:5]
            )
            top_inc = (
                tx_filtered.filter(kind="in", category__isnull=False)
                .values("category__name")
                .annotate(s=Sum("amount"))
                .order_by("-s")[:5]
            )
        else:
            balance_all = Decimal("0")

        ctx.update({
            "primary_team": team,
            "current": "wallet",
            # filter UI
            "period": period,
            "year": year,
            "month": month,
            "year_choices": years,
            "months": CZ_MONTHS,
            "range_from": since,
            "range_to": until,
            # data
            "tx": tx_filtered,
            "total_in": total_in,
            "total_out": total_out,
            "balance": balance,
            # independent of filter
            "balance_all": balance_all,
            "top_exp": top_exp,
            "top_inc": top_inc,
        })
        return ctx
