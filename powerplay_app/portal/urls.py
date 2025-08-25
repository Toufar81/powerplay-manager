# file: powerplay_app/portal/urls.py
"""URL configuration for the authenticated *Portal* section.

Internal documentation is **English**. Public slugs and names remain **Czech**
(as required by the product). Functionality remains unchanged.

Routes
------
- ``""`` → Dashboard (přehled)
- ``"ucet/"`` → Account (uživatelský účet)
- ``"kalendar/"`` → Calendar (týmový kalendář)
- ``"pokladna/"`` → Wallet (pokladna týmu)
- ``"pripominky/"`` → Feedback (připomínky)
"""

from __future__ import annotations

from django.urls import path
from django.urls.resolvers import URLPattern

from .views.dashboard import DashboardView
from .views.account import AccountView
from .views.calendar import CalendarView
from .views.wallet import WalletView
from .views.feedback import FeedbackView


app_name = "portal"

# Keep explicit type for clarity in IDEs and static analyzers.
urpatterns: list[URLPattern]  # alias for mypy friendliness

urlpatterns: list[URLPattern] = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("ucet/", AccountView.as_view(), name="account"),
    path("kalendar/", CalendarView.as_view(), name="calendar"),
    path("pokladna/", WalletView.as_view(), name="wallet"),
    path("pripominky/", FeedbackView.as_view(), name="feedback"),
]
