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

# 👤 Hráč
class Player(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    birth_date = models.DateField()
    position = models.CharField(max_length=30, choices=[
        ('GK', 'Goalkeeper'),
        ('DF', 'Defender'),
        ('MF', 'Midfielder'),
        ('FW', 'Forward'),
    ])
    number = models.PositiveIntegerField()
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.number})"

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

