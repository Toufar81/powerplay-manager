from django.db import models

# 🏒 Tým
class Team(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    founded = models.DateField()
    coach = models.CharField(max_length=100)
    manager = models.CharField(max_length=100, blank=True, null=True)
    logo = models.ImageField(upload_to='team_logos/', blank=True, null=True)  # 🆕 logo týmu

    def __str__(self):
        return self.name

# 🧩 Typy pozic
POSITION_TYPES = [
    ('Offensive', 'Offensive'),
    ('Defensive', 'Defensive'),
    ('Goalkeeper', 'Goalkeeper'),
]

class PlayerPosition(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)
    position_type = models.CharField(max_length=20, choices=POSITION_TYPES, default='Offensive')
    can_score = models.BooleanField(default=True)
    can_concede = models.BooleanField(default=False)
    can_assist = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Player(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    nickname = models.CharField(max_length=30, blank=True, help_text="Jméno na dresu nebo přezdívka")
    birth_date = models.DateField()
    number = models.PositiveIntegerField()
    position = models.ForeignKey(PlayerPosition, on_delete=models.SET_NULL, null=True, blank=True, related_name='players')

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')

    photo = models.ImageField(upload_to='player_photos/', blank=True, null=True)

    matches_played = models.PositiveIntegerField(default=0)
    penalty_minutes = models.PositiveIntegerField(default=0)
    goals_scored = models.PositiveIntegerField(default=0)
    goals_conceded = models.PositiveIntegerField(default=0)
    assists = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.nickname or self.first_name} {self.last_name} ({self.number})"

    def is_goalkeeper(self):
        return self.position and self.position.code == 'GK'

    def has_scoring_stats(self):
        return self.position and self.position.can_score

# 🧑‍💼 Role týmu
class StaffRole(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

# 🧑‍💼 Vedení týmu
class StaffMember(models.Model):
    name = models.CharField(max_length=100)
    role = models.ForeignKey(StaffRole, on_delete=models.SET_NULL, null=True, related_name='members')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='staff')

    def __str__(self):
        return f"{self.role}: {self.name}"


# 🏆 Soutěž (liga, turnaj, přátelský zápas)
class Competition(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50, choices=[
        ('League', 'League'),
        ('Friendly', 'Friendly'),
        ('Tournament', 'Tournament'),
    ])
    season = models.CharField(max_length=20, blank=True, null=True)  # např. "2025/2026"
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.type})"


class Stadion(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=200)
    map_url = models.URLField(blank=True, null=True, help_text="Odkaz na mapu nebo Google Maps")

    def __str__(self):
        return self.name


# ⚔️ Zápas
class Match(models.Model):
    date = models.DateTimeField()
    stadion = models.ForeignKey(Stadion, on_delete=models.SET_NULL, null=True, blank=True)
    is_internal = models.BooleanField(default=False)
    competition = models.ForeignKey(Competition, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.stadion} – {self.date.strftime('%Y-%m-%d')}"


# 🧩 Strana zápasu (Black/White nebo skutečný tým)
class MatchTeam(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='sides')
    name = models.CharField(max_length=100)  # např. 'Black', 'White', 'HC Olomouc'
    players = models.ManyToManyField(Player, related_name='match_teams')

    def __str__(self):
        return f"{self.name} in {self.match}"

