from django.test import TestCase, RequestFactory
from django.contrib import admin
from datetime import date, datetime
from django.utils import timezone

from powerplay_app.models import (
    Competition, Stadium, Team, Player, Match, MatchLineup, StaffRole
)
from powerplay_app.admin import (
    MatchAdmin, HomeLineupInline, AwayLineupInline,
    CompetitionAdmin, StadiumAdmin, TeamAdmin, PlayerAdmin, StaffRoleAdmin
)


class AdminRegistrationTest(TestCase):
    def test_models_registered(self):
        self.assertIn(Competition, admin.site._registry)
        self.assertIsInstance(admin.site._registry[Competition], CompetitionAdmin)

        self.assertIn(Stadium, admin.site._registry)
        self.assertIsInstance(admin.site._registry[Stadium], StadiumAdmin)

        self.assertIn(Team, admin.site._registry)
        self.assertIsInstance(admin.site._registry[Team], TeamAdmin)

        self.assertIn(Player, admin.site._registry)
        self.assertIsInstance(admin.site._registry[Player], PlayerAdmin)

        self.assertIn(Match, admin.site._registry)
        self.assertIsInstance(admin.site._registry[Match], MatchAdmin)

        self.assertIn(StaffRole, admin.site._registry)
        self.assertIsInstance(admin.site._registry[StaffRole], StaffRoleAdmin)


class MatchAdminInlineTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.stadium = Stadium.objects.create(name="Test Stadium", address="Test Street")
        self.team_home = Team.objects.create(name="Domácí", city="Město", stadium=self.stadium)
        self.team_away = Team.objects.create(name="Hosté", city="Jinde", stadium=self.stadium)

        self.competition = Competition.objects.create(
            name="Test Liga",
            competition_type=Competition.CompetitionType.LEAGUE,
            season_start=date(2025, 8, 1),
            season_end=date(2026, 5, 31),
            rounds=30,
            status=Competition.Status.PLANNED
        )

        self.match = Match.objects.create(
            date_time=timezone.make_aware(datetime(2025, 9, 15, 18, 0)),
            stadium=self.stadium,
            competition=self.competition,
            home_team=self.team_home,
            away_team=self.team_away,
            home_score=2,
            away_score=1
        )

        self.admin = MatchAdmin(Match, admin.site)

    def test_inline_verbose_names(self):
        request = self.factory.get(f'/admin/powerplay_app/match/{self.match.pk}/change/')
        inlines = self.admin.get_inline_instances(request, obj=self.match)

        home_inline = next(i for i in inlines if isinstance(i, HomeLineupInline))
        away_inline = next(i for i in inlines if isinstance(i, AwayLineupInline))

        self.assertIn(self.match.home_team.name, home_inline.verbose_name_plural)
        self.assertIn(self.match.away_team.name, away_inline.verbose_name_plural)


class HomeLineupInlineTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.stadium = Stadium.objects.create(name="Test Stadium", address="Test Street")
        self.team_home = Team.objects.create(name="Domácí", city="Město", stadium=self.stadium)
        self.team_away = Team.objects.create(name="Hosté", city="Jinde", stadium=self.stadium)

        self.player_home = Player.objects.create(
            first_name="Libor", last_name="Novák", jersey_number=10,
            position=Player.Position.FORWARD, birth_date=date(2000, 1, 1),
            current_team=self.team_home
        )
        self.player_away = Player.objects.create(
            first_name="Jan", last_name="Host", jersey_number=11,
            position=Player.Position.DEFENSE, birth_date=date(1999, 5, 5),
            current_team=self.team_away
        )

        self.competition = Competition.objects.create(
            name="Test Liga",
            competition_type=Competition.CompetitionType.LEAGUE,
            season_start=date(2025, 8, 1),
            season_end=date(2026, 5, 31),
            rounds=30,
            status=Competition.Status.PLANNED
        )

        self.match = Match.objects.create(
            date_time=timezone.make_aware(datetime(2025, 9, 15, 18, 0)),
            stadium=self.stadium,
            competition=self.competition,
            home_team=self.team_home,
            away_team=self.team_away,
            home_score=2,
            away_score=1
        )

        self.inline = HomeLineupInline(MatchLineup, admin.site)
        self.inline.parent_object = self.match

    def test_player_queryset_filtered_by_home_team(self):
        field = self.inline.formfield_for_foreignkey(
            db_field=MatchLineup._meta.get_field('player'),
            request=self.factory.get('/admin/')
        )
        self.assertIn(self.player_home, field.queryset)
        self.assertNotIn(self.player_away, field.queryset)
