# file: powerplay_app/site/urls.py
"""Public *Site* URL configuration.

Internal documentation is **English**. Public paths and route names remain in
**Czech** as required by the product. No behavior change.

Routes
------
- ``""`` → Home (Domů)
- ``"prihlasit/"`` → Login (Přihlášení)
- ``"odhlasit/"`` → Logout (Odhlášení)
- ``"liga/"`` → League overview (Liga)
- ``"hraci/"`` → Players list (Hráči)
- ``"hraci/<int:pk>/"`` → Player detail
- ``"vedeni/"`` → Staff list (Vedení)
- ``"vedeni/<int:pk>/"`` → Staff detail
- ``"kontakt/"`` → Contact (Kontakt)
"""

from __future__ import annotations

from django.urls import path
from django.urls.resolvers import URLPattern

from .views.home import HomeView
from .views.league import LeagueView
from .views.players import PlayersListView, PlayerDetailView
from .views.staff import StaffListView, StaffDetailView
from .views.contact import ContactView
from .views.auth import SiteLoginView, SiteLogoutView  # custom authentication views


app_name = "site"

# Keep explicit typing for IDEs/mypy.
urpatterns: list[URLPattern]

urlpatterns: list[URLPattern] = [
    # Domů
    path("", HomeView.as_view(), name="home"),

    # Přihlášení / Odhlášení
    path("prihlasit/", SiteLoginView.as_view(), name="login"),
    path("odhlasit/", SiteLogoutView.as_view(), name="logout"),

    # Liga
    path("liga/", LeagueView.as_view(), name="league"),

    # Hráči
    path("hraci/", PlayersListView.as_view(), name="players"),
    path("hraci/<int:pk>/", PlayerDetailView.as_view(), name="player_detail"),

    # Vedení
    path("vedeni/", StaffListView.as_view(), name="staff"),
    path("vedeni/<int:pk>/", StaffDetailView.as_view(), name="staff_detail"),

    # Kontakt
    path("kontakt/", ContactView.as_view(), name="contact"),
]
