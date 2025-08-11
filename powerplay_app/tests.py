from django.test import TestCase
from datetime import date, datetime
from .models import Competition, Team, Stadium, Player, Match, MatchLineup, StaffRole

class ModelsTestCase(TestCase):
    def setUp(self):
        self.stadium = Stadium.objects.create(name="Na Stínadlech", address="Teplice")
        self.competition = Competition.objects.create(
            name="1. Liga",
            competition_type=Competition.CompetitionType.LEAGUE,
            season_start=date(2025, 8, 1),
            season_end=date(2026, 5, 31),
            rounds=30,
            status=Competition.Status.PLANNED
        )
        self.team_home = Team.objects.create(name="FK Teplice", city="Teplice", stadium=self.stadium)
        self.team_away = Team.objects.create(name="Slavia Praha", city="Praha", stadium=self.stadium)
        self.team_home.competitions.add(self.competition)

        self.player = Player.objects.create(
            first_name="Libor",
            last_name="Novák",
            jersey_number=10,
            position=Player.Position.FORWARD,
            birth_date=date(2000, 1, 1),
            current_team=self.team_home
        )

        self.match = Match.objects.create(
            date_time=datetime(2025, 9, 15, 18, 0),
            stadium=self.stadium,
            competition=self.competition,
            home_team=self.team_home,
            away_team=self.team_away,
            home_score=2,
            away_score=1
        )

    def test_competition_str(self):
        self.assertEqual(str(self.competition), "1. Liga (2025/2026)")

    def test_team_str(self):
        self.assertEqual(str(self.team_home), "FK Teplice")

    def test_player_str(self):
        self.assertEqual(str(self.player), "Libor Novák #10")

    def test_match_str(self):
        self.assertIn("FK Teplice vs Slavia Praha", str(self.match))

    def test_match_lineup_creation(self):
        lineup = MatchLineup.objects.create(
            match=self.match,
            team=self.team_home,
            player=self.player,
            is_starting=True,
            goals=1,
            assists=0,
            penalty_minutes=2,
            goals_conceded=0
        )
        self.assertEqual(lineup.goals, 1)
        self.assertEqual(lineup.get_display_name(), f"{self.player} - {self.match}")


    def test_staff_role_str(self):
        staff = StaffRole.objects.create(role="coach", name="Petr Rada", team=self.team_home)
        self.assertEqual(str(staff), "Trenér - Petr Rada")
