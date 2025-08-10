from django.db import models

# 🏒 Tým
class Team(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    founded = models.DateField()
    coach = models.CharField(max_length=100)
    manager = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name


class Player(models.Model):
    POSITION_CHOICES = [
        ('GK', 'Goalkeeper'),
        ('DF', 'Defender'),
        ('MF', 'Midfielder'),
        ('FW', 'Forward'),
    ]

    # 🧍‍♂️ Základní údaje
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    nickname = models.CharField(
        max_length=30,
        blank=True,
        help_text="Jméno na dresu nebo přezdívka"
    )
    birth_date = models.DateField()
    number = models.PositiveIntegerField()
    position = models.CharField(max_length=30, choices=POSITION_CHOICES)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')

    # 📸 Fotka hráče
    photo = models.ImageField(upload_to='player_photos/', blank=True, null=True)

    # 📊 Statistiky
    matches_played = models.PositiveIntegerField(default=0)
    penalty_minutes = models.PositiveIntegerField(default=0)

    # Pro MF, FW, DF
    goals_scored = models.PositiveIntegerField(default=0)

    # Pro GK
    goals_conceded = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.nickname or self.first_name} {self.last_name} ({self.number})"

    def is_goalkeeper(self):
        return self.position == 'GK'

    def has_scoring_stats(self):
        return self.position in ['FW', 'MF', 'DF']

# 🧑‍💼 Vedení týmu
class StaffMember(models.Model):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=50, choices=[
        ('Coach', 'Coach'),
        ('Manager', 'Manager'),
        ('Physio', 'Physiotherapist'),
    ])
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

# ⚔️ Zápas
class Match(models.Model):
    date = models.DateTimeField()
    location = models.CharField(max_length=100)
    is_internal = models.BooleanField(default=False)
    competition = models.ForeignKey(Competition, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Match on {self.date.strftime('%Y-%m-%d')}"

# 🧩 Strana zápasu (Black/White nebo skutečný tým)
class MatchTeam(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='sides')
    name = models.CharField(max_length=100)  # např. 'Black', 'White', 'HC Olomouc'
    players = models.ManyToManyField(Player, related_name='match_teams')

    def __str__(self):
        return f"{self.name} in {self.match}"

