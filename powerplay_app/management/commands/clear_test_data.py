"""Remove all test data from the application's database.

This management command irreversibly deletes objects used for local
testing such as matches, players, teams, stadiums and competitions.
**WARNING:** Running this command will permanently purge those records
and should only be done in a non-production environment.
"""

from django.core.management.base import BaseCommand
from powerplay_app.models import Match, Player, Team, Stadium, Competition

class Command(BaseCommand):
    help = "Vyčistí testovací data z databáze"

    def handle(self, *args, **kwargs):
        """Execute the command.

        No arguments are expected. The method sequentially deletes all
        records for ``Match``, ``Player``, ``Team``, ``Stadium`` and
        ``Competition`` models, then outputs a warning to ``stdout``.
        This action cannot be undone and will empty the associated
        tables.
        """
        Match.objects.all().delete()
        Player.objects.all().delete()
        Team.objects.all().delete()
        Stadium.objects.all().delete()
        Competition.objects.all().delete()

        self.stdout.write(self.style.WARNING("🧹 Testovací data byla odstraněna."))
