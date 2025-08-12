from django.test import TestCase
from datetime import date, datetime
from django.utils import timezone
from powerplay_app.models import (
    Competition, Stadium, Team, Player, Match, MatchLineup, StaffRole
)

class ModelsTestCase(TestCase):
    def setUp(self):
        self.stadium = Stadium.objects.create(
            name="Na Stínadlech",
            address="Teplice",
            map_url="https://example.com/map"
        )

        self.competition = Competition.objects.create(
            name="1. Liga",
            competition_type=Competition.CompetitionType.LEAGUE,
            season_start=date(2025, 8, 1),
            season_end=date(2026, 5, 31),
            rounds=30,
            playoff_format="Playoff 8 týmů",
            status=Competition.Status.PLANNED
        )

        self.team_home = Team.objects.create(
            name="FK Teplice",
            city="Teplice",
            stadium=self.stadium
        )
        self.team_away = Team.objects.create(
            name="Slavia Praha",
            city="Praha",
            stadium=self.stadium
        )

        self.team_home.competitions.add(self.competition)
        self.team_away.competitions.add(self.competition)

        self.player = Player.objects.create(
            first_name="Libor",
            last_name="Novák",
            jersey_number=10,
            nickname="Liby",
            email="libor@example.com",
            phone_number="+420123456789",
            position=Player.Position.FORWARD,
            birth_date=date(2000, 1, 1),
            current_team=self.team_home
        )

        self.match = Match.objects.create(
            date_time=timezone.make_aware(datetime(2025, 9, 15, 18, 0)),
            stadium=self.stadium,
            competition=self.competition,
            home_team=self.team_home,
            away_team=self.team_away,
            home_score=2,
            away_score=1,
            report_text="Skvělý zápas!",
            video_url="https://example.com/video"
        )

    # === COMPETITION ===
    def test_competition_str(self):
        self.assertEqual(str(self.competition), "1. Liga (2025/2026)")
        self.assertEqual(self.competition.get_status_display(), "Plánována")
        self.assertEqual(self.competition.get_competition_type_display(), "Liga")

    # === STADIUM ===
    def test_stadium_str_and_map(self):
        self.assertEqual(str(self.stadium), "Na Stínadlech")
        self.assertEqual(self.stadium.map_url, "https://example.com/map")

    # === TEAM ===
    def test_team_str_and_logo(self):
        self.assertEqual(str(self.team_home), "FK Teplice")
        self.assertEqual(self.team_home.logo.name, None)


    # === PLAYER ===
    def test_player_str_and_position(self):
        self.assertEqual(str(self.player), "Libor Novák #10")
        self.assertEqual(self.player.get_position_display(), "Útočník")
        self.assertEqual(self.player.nickname, "Liby")

    # === MATCH ===
    def test_match_str_and_report(self):
        self.assertIn("FK Teplice vs Slavia Praha", str(self.match))
        self.assertIn("15.09.2025", str(self.match))
        self.assertEqual(self.match.report_text, "Skvělý zápas!")
        self.assertEqual(self.match.video_url, "https://example.com/video")

    # === MATCH LINEUP ===
    def test_match_lineup_creation_and_team_assignment(self):
        lineup = MatchLineup.objects.create(
            match=self.match,
            player=self.player,
            line_number=MatchLineup.Line.FIRST,
            position_detail=MatchLineup.PositionDetail.C,
            goals=2,
            assists=1,
            penalty_minutes=4,
            goals_conceded=0
        )
        lineup.save()
        self.assertEqual(lineup.team, self.team_home)
        self.assertEqual(lineup.get_line_number_display(), "1. lajna")
        self.assertEqual(lineup.get_position_detail_display(), "Střed")
        self.assertEqual(str(lineup), "Libor Novák #10 (1. lajna - Střed)")

    def test_match_lineup_boolean_and_stats(self):
        lineup = MatchLineup.objects.create(
            match=self.match,
            player=self.player,
            line_number=MatchLineup.Line.SECOND,
            position_detail=MatchLineup.PositionDetail.RW,
            is_starting=False,
            goals=1,
            assists=2,
            penalty_minutes=0,
            goals_conceded=1
        )
        lineup.save()
        self.assertFalse(lineup.is_starting)
        self.assertEqual(lineup.goals, 1)
        self.assertEqual(lineup.assists, 2)
        self.assertEqual(lineup.goals_conceded, 1)

    # === STAFF ROLE ===
    def test_staff_role_str_and_display(self):
        staff = StaffRole.objects.create(
            role="coach",
            name="Petr Rada",
            team=self.team_home,
            email="rada@example.com",
            phone_number="+420777777777"
        )
        self.assertEqual(str(staff), "Trenér - Petr Rada")
        self.assertEqual(staff.get_role_display(), "Trenér")
