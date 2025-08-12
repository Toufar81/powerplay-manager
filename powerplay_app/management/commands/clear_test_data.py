from django.core.management.base import BaseCommand
from powerplay_app.models import Match, Player, Team, Stadium, Competition

class Command(BaseCommand):
    help = "Vyčistí testovací data z databáze"

    def handle(self, *args, **kwargs):
        Match.objects.all().delete()
        Player.objects.all().delete()
        Team.objects.all().delete()
        Stadium.objects.all().delete()
        Competition.objects.all().delete()

        self.stdout.write(self.style.WARNING("🧹 Testovací data byla odstraněna."))
