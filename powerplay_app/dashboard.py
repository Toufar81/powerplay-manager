# file: powerplay_manager/dashboard.py
from jet.dashboard import modules
from jet.dashboard.dashboard import Dashboard
from django.urls import reverse

class CustomIndexDashboard(Dashboard):
    columns = 2  # přehledný 2‑sloupcový layout

    def init_with_context(self, context):
        # Blok s modely naší appky
        self.children.append(
            modules.ModelList(
                title="Hokej – modely",
                models=[
                    "powerplay_app.models.League",
                    "powerplay_app.models.Team",
                    "powerplay_app.models.Player",
                    "powerplay_app.models.Game",
                    "powerplay_app.models.Goal",
                    "powerplay_app.models.Penalty",
                    "powerplay_app.models.PlayerStats",
                    "powerplay_app.models.Tournament",
                    "powerplay_app.models.Staff",
                ],
            )
        )
        # Rychlé odkazy
        self.children.append(
            modules.LinkList(
                title="Rychlé akce",
                children=[
                    {"title": "Zápasy", "url": reverse("admin:powerplay_app_game_changelist")},
                    {"title": "Týmy", "url": reverse("admin:powerplay_app_team_changelist")},
                    {"title": "Hráči", "url": reverse("admin:powerplay_app_player_changelist")},
                    {"title": "Turnaje", "url": reverse("admin:powerplay_app_tournament_changelist")},
                ],
            )
        )
        # Poslední akce
        self.children.append(
            modules.RecentActions(
                title="Poslední akce",
                limit=10,
            )
        )
