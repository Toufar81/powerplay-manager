from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, datetime
from random import choice, randint

from powerplay_app.models import (
    League, Stadium, Team, Player, Game, Line, LineAssignment, LineSlot,
    Goal, Penalty, PenaltyType, Period, PlayerStats, _recompute_game
)

class Command(BaseCommand):
    help = "Naplní databázi realistickými testovacími daty pro ligu, týmy, hráče a zápasy (včetně postů v lajnách)."

    def handle(self, *args, **options):
        self.stdout.write("⚙️  Resetuji stávající testovací data…")
        # Smazat v bezpečném pořadí kvůli FK
        Goal.objects.all().delete()
        Penalty.objects.all().delete()
        LineAssignment.objects.all().delete()
        Line.objects.all().delete()
        PlayerStats.objects.all().delete()
        Game.objects.all().delete()
        Player.objects.all().delete()
        Team.objects.all().delete()
        Stadium.objects.all().delete()
        League.objects.all().delete()

        # --- League ---
        league = League.objects.create(
            name="PowerPlay League",
            season="2025/26",
            date_start=date(2025, 8, 1),
            date_end=date(2026, 5, 31),
        )

        # --- Stadiums ---
        stadium1 = Stadium.objects.create(name="Stadion Alfa", address="Ulice 1")
        stadium2 = Stadium.objects.create(name="Stadion Beta", address="Ulice 2")

        # --- Teams ---
        team1 = Team.objects.create(name="Tým Červený", city="Město A", league=league, stadium=stadium1)
        team2 = Team.objects.create(name="Tým Modrý", city="Město B", league=league, stadium=stadium2)

        # --- Players ---
        def create_team_players(team: Team):
            jersey = 1
            players = []
            for i in range(8):
                players.append(Player(
                    first_name=f"Hráč{jersey}", last_name=team.name.split()[-1],
                    jersey_number=jersey, position="forward", team=team,
                    birth_date=date(1996, (i % 12) + 1, min((i % 28) + 1, 28)),
                    email=f"hrac{jersey}@{team.name.split()[1].lower()}.cz",
                ))
                jersey += 1
            for i in range(6):
                players.append(Player(
                    first_name=f"Hráč{jersey}", last_name=team.name.split()[-1],
                    jersey_number=jersey, position="defense", team=team,
                    birth_date=date(1995, (i % 12) + 1, min((i % 28) + 1, 28)),
                    email=f"hrac{jersey}@{team.name.split()[1].lower()}.cz",
                ))
                jersey += 1
            players.append(Player(first_name="Brankář1", last_name=team.name.split()[-1], jersey_number=90, position="goalie", team=team))
            players.append(Player(first_name="Brankář2", last_name=team.name.split()[-1], jersey_number=91, position="goalie", team=team))
            Player.objects.bulk_create(players)
            return list(Player.objects.filter(team=team).order_by('jersey_number'))

        players_t1 = create_team_players(team1)
        players_t2 = create_team_players(team2)

        # --- Games ---
        self.stdout.write("📅 Zakládám zápasy…")
        games = []
        base_day = 15
        for i in range(4):
            dt = timezone.make_aware(datetime(2025, 9, base_day + i, 18, 0))
            home = team1 if i % 2 == 0 else team2
            away = team2 if i % 2 == 0 else team1
            stadium = stadium1 if home == team1 else stadium2
            games.append(Game(starts_at=dt, stadium=stadium, home_team=home, away_team=away))
        Game.objects.bulk_create(games)
        games = list(Game.objects.order_by('starts_at'))

        # --- Lines & Assignments (se sloty) ---
        self.stdout.write("📋 Tvořím lajny a sestavy se sloty…")
        slot_order = [LineSlot.LW, LineSlot.C, LineSlot.RW, LineSlot.LD, LineSlot.RD]

        for g in games:
            for t in (g.home_team, g.away_team):
                l0 = Line.objects.create(game=g, team=t, line_number=0)
                l1 = Line.objects.create(game=g, team=t, line_number=1)
                l2 = Line.objects.create(game=g, team=t, line_number=2)
                l3 = Line.objects.create(game=g, team=t, line_number=3)

                team_players = players_t1 if t == team1 else players_t2

                # brankář do lajny 0
                goalie = next((p for p in team_players if p.position == 'goalie'), None)
                if goalie:
                    LineAssignment.objects.create(line=l0, player=goalie, slot=LineSlot.G)

                # rozdělit bruslaře do lajn 1–3 po pěti slotech
                skaters = [p for p in team_players if p.position != 'goalie']
                for idx, p in enumerate(skaters[:15]):  # 3 lajny × 5 postů
                    line_obj = [l1, l2, l3][idx // 5]
                    slot = slot_order[idx % 5]
                    LineAssignment.objects.create(line=line_obj, player=p, slot=slot)

        # --- Events ---
        self.stdout.write("🥅 Generuji góly a tresty…")
        for g in games:
            home_goals = randint(2, 4)
            away_goals = randint(1, 3)

            def rand_scorer(team: Team):
                return choice(Player.objects.filter(team=team, position__in=["forward", "defense"]))

            def rand_assist(team: Team):
                return choice(Player.objects.filter(team=team, position__in=["forward", "defense"])) if randint(0, 1) else None

            sec = 120
            for _ in range(home_goals):
                Goal.objects.create(
                    game=g, team=g.home_team, period=Period.FIRST, second_in_period=sec,
                    scorer=rand_scorer(g.home_team), assist_1=rand_assist(g.home_team), assist_2=rand_assist(g.home_team)
                )
                sec += randint(60, 180)
            for _ in range(away_goals):
                Goal.objects.create(
                    game=g, team=g.away_team, period=Period.SECOND, second_in_period=sec,
                    scorer=rand_scorer(g.away_team), assist_1=rand_assist(g.away_team), assist_2=rand_assist(g.away_team)
                )
                sec += randint(60, 180)

            for _ in range(randint(1, 3)):
                team = choice([g.home_team, g.away_team])
                Penalty.objects.create(
                    game=g, team=team, period=Period.THIRD, second_in_period=randint(30, 900),
                    penalized_player=choice(Player.objects.filter(team=team)),
                    minutes=choice([2, 2, 5]), penalty_type=PenaltyType.MINOR,
                    reason="Hákování"
                )

            _recompute_game(g)

        self.stdout.write(self.style.SUCCESS("✅ Testovací data byla úspěšně nahrána (se sloty v lajnách)."))
