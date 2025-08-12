from django.core.management.base import BaseCommand
from datetime import date, datetime, timedelta
from django.utils import timezone
from powerplay_app.models import Competition, Stadium, Team, Player, Match

class Command(BaseCommand):
    help = "Naplní databázi testovacími daty"

    def handle(self, *args, **kwargs):
        # Vyčisti stará data
        Match.objects.all().delete()
        Player.objects.all().delete()
        Team.objects.all().delete()
        Stadium.objects.all().delete()
        Competition.objects.all().delete()

        # Stadiony
        stadium1 = Stadium.objects.create(name="Stadion Alfa", address="Ulice 1")
        stadium2 = Stadium.objects.create(name="Stadion Beta", address="Ulice 2")

        # Týmy
        team1 = Team.objects.create(name="Tým Červený", city="Město A", stadium=stadium1)
        team2 = Team.objects.create(name="Tým Modrý", city="Město B", stadium=stadium2)

        # Liga
        competition = Competition.objects.create(
            name="PowerPlay Liga",
            competition_type=Competition.CompetitionType.LEAGUE,
            season_start=date(2025, 8, 1),
            season_end=date(2026, 5, 31),
            rounds=30,
            status=Competition.Status.PLANNED
        )

        # Hráči pro každý tým
        for i in range(1, 11):
            Player.objects.create(
                first_name=f"Hráč{i}", last_name="Pole", jersey_number=i,
                position=Player.Position.FORWARD, birth_date=date(1990, 1, i),
                email=f"hrac{i}@cerveny.cz",
                phone_number=f"+4206000000{i:02}",
                current_team=team1
            )
            Player.objects.create(
                first_name=f"Hráč{i}", last_name="Pole", jersey_number=50 + i,
                position=Player.Position.DEFENSE, birth_date=date(1991, 2, i),
                email=f"hrac{i}@modry.cz",
                phone_number=f"+4207000000{i:02}",
                current_team=team2
            )

        for i in range(2):
            Player.objects.create(
                first_name=f"Brankář{i + 1}", last_name="Červený", jersey_number=90 + i,
                position=Player.Position.GOALKEEPER, birth_date=date(1988, 3, i + 1),
                email=f"brankar{i + 1}@cerveny.cz",
                phone_number=f"+4208000000{i + 1:02}",
                current_team=team1
            )
            Player.objects.create(
                first_name=f"Brankář{i + 1}", last_name="Modrý", jersey_number=99 + i,
                position=Player.Position.GOALKEEPER, birth_date=date(1989, 4, i + 1),
                email=f"brankar{i + 1}@modry.cz",
                phone_number=f"+4209000000{i + 1:02}",
                current_team=team2
            )

        # Zápasy
        for i in range(4):
            Match.objects.create(
                date_time=timezone.make_aware(datetime(2025, 9, 15 + i, 18, 0)),
                stadium=stadium1 if i % 2 == 0 else stadium2,
                competition=competition,
                home_team=team1 if i % 2 == 0 else team2,
                away_team=team2 if i % 2 == 0 else team1,
                home_score=2 + i,
                away_score=1 + i
            )

        self.stdout.write(self.style.SUCCESS("✅ Testovací data byla úspěšně nahrána."))
