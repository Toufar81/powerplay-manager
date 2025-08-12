from django.test import TestCase
from datetime import date, datetime
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.utils import timezone
from powerplay_app.models import Match, MatchLineup, Player, Team, Stadium, Competition
from powerplay_app.forms import MatchLineupForm, MatchLineupInlineFormSet

class MatchLineupFormSetTest(TestCase):
    def setUp(self):
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

        self.player1 = Player.objects.create(
            first_name="Libor", last_name="Novák", jersey_number=10,
            position=Player.Position.FORWARD, birth_date=date(2000, 1, 1),
            email="libor.novak@example.com",
            phone_number="+420123456789",
            current_team=self.team_home
        )

        self.player2 = Player.objects.create(
            first_name="Jan", last_name="Brankář", jersey_number=1,
            position=Player.Position.GOALKEEPER, birth_date=date(1999, 5, 5),
            email="jan.brankar@example.com",
            phone_number="+420987654321",
            current_team=self.team_home
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

        self.FormSet = inlineformset_factory(
            Match,
            MatchLineup,
            form=MatchLineupForm,
            formset=MatchLineupInlineFormSet,
            extra=0,
            can_delete=False
        )

    def get_formset_data(self, overrides=None):
        data = {
            'matchlineup_set-TOTAL_FORMS': '2',
            'matchlineup_set-INITIAL_FORMS': '0',
            'matchlineup_set-MIN_NUM_FORMS': '0',
            'matchlineup_set-MAX_NUM_FORMS': '1000',

            'matchlineup_set-0-player': self.player1.pk,
            'matchlineup_set-0-line_number': 1,
            'matchlineup_set-0-position_detail': 'LW',
            'matchlineup_set-0-goals': 1,
            'matchlineup_set-0-match': self.match.pk,

            'matchlineup_set-1-player': self.player2.pk,
            'matchlineup_set-1-line_number': 1,
            'matchlineup_set-1-position_detail': 'G',
            'matchlineup_set-1-goals': 1,
            'matchlineup_set-1-match': self.match.pk,
        }
        if overrides:
            data.update(overrides)
        return data

    def test_valid_lineup(self):
        formset = self.FormSet(data=self.get_formset_data(), instance=self.match)
        self.assertTrue(formset.is_valid())

    def test_missing_line_number(self):
        data = self.get_formset_data({'matchlineup_set-0-line_number': ''})
        formset = self.FormSet(data=data, instance=self.match)
        self.assertFalse(formset.is_valid())
        self.assertIn("nemá vyplněnou lajnu", str(formset.errors))

    def test_missing_position(self):
        data = self.get_formset_data({'matchlineup_set-0-position_detail': ''})
        formset = self.FormSet(data=data, instance=self.match)
        self.assertFalse(formset.is_valid())
        self.assertIn("nemá vyplněnou pozici", str(formset.errors))

    def test_duplicate_player(self):
        data = self.get_formset_data({'matchlineup_set-1-player': self.player1.pk})
        formset = self.FormSet(data=data, instance=self.match)
        self.assertFalse(formset.is_valid())
        self.assertIn("je v sestavě vícekrát", str(formset.errors))

    def test_too_many_goalkeepers(self):
        player_extra = Player.objects.create(
            first_name="Extra", last_name="Brankář", jersey_number=99,
            position=Player.Position.GOALKEEPER, birth_date=date(1997, 7, 7),
            current_team=self.team_home
        )
        data = self.get_formset_data({
            'matchlineup_set-TOTAL_FORMS': '3',
            'matchlineup_set-2-player': player_extra.pk,
            'matchlineup_set-2-line_number': 1,
            'matchlineup_set-2-position_detail': 'G',
            'matchlineup_set-2-goals': 0,
            'matchlineup_set-2-match': self.match.pk,
        })
        formset = self.FormSet(data=data, instance=self.match)
        self.assertFalse(formset.is_valid())
        self.assertIn("více než jednoho brankáře", str(formset.errors))

    def test_too_many_field_players(self):
        extra_players = []
        for i in range(3, 9):
            player = Player.objects.create(
                first_name=f"Hráč{i}", last_name="Pole", jersey_number=100 + i,
                position=Player.Position.FORWARD, birth_date=date(1990, 1, i),
                current_team=self.team_home,
                email = f"hrac{i}@example.com",
                phone_number = f"+4206000000{i}",

            )
            extra_players.append(player)

        data = self.get_formset_data()
        for idx, player in enumerate(extra_players, start=2):
            data[f'matchlineup_set-{idx}-player'] = player.pk
            data[f'matchlineup_set-{idx}-line_number'] = 1
            data[f'matchlineup_set-{idx}-position_detail'] = 'RW'
            data[f'matchlineup_set-{idx}-goals'] = 0
            data[f'matchlineup_set-{idx}-match'] = self.match.pk

        data['matchlineup_set-TOTAL_FORMS'] = str(2 + len(extra_players))
        formset = self.FormSet(data=data, instance=self.match)
        self.assertFalse(formset.is_valid())
        self.assertIn("více než 5 hráčů v poli", str(formset.errors))

    def test_goals_exceed_team_score(self):
        data = self.get_formset_data({'matchlineup_set-0-goals': 3})
        formset = self.FormSet(data=data, instance=self.match)
        with self.assertRaises(ValidationError) as context:
            formset.clean()
        self.assertIn("překračuje týmové skóre", str(context.exception))
