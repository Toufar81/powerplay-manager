from django.db import models
from django.utils.translation import gettext_lazy as _

# ===== 1. SOUTĚŽE =====
class Competition(models.Model):
    class CompetitionType(models.TextChoices):
        LEAGUE = 'league', _('Liga')
        TOURNAMENT = 'tournament', _('Turnaj')
        FRIENDLY = 'friendly', _('Přátelský zápas')

    class Status(models.TextChoices):
        PLANNED = 'planned', _('Plánována')
        ONGOING = 'ongoing', _('Probíhá')
        FINISHED = 'finished', _('Ukončena')

    name = models.CharField(max_length=100)
    competition_type = models.CharField(max_length=20, choices=CompetitionType.choices)
    season_start = models.DateField()
    season_end = models.DateField()
    rounds = models.PositiveIntegerField(default=0)
    playoff_format = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)

    def __str__(self):
        return f"{self.name} ({self.season_start.year}/{self.season_end.year})"


# ===== 2. TÝMY & STADIONY =====
class Stadium(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    map_url = models.URLField(blank=True, null=True)
    photo = models.ImageField(upload_to='stadiums/', blank=True, null=True)

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='team_logos/', blank=True, null=True)
    stadium = models.ForeignKey(Stadium, on_delete=models.SET_NULL, null=True, blank=True)
    competitions = models.ManyToManyField(Competition, blank=True)

    def __str__(self):
        return self.name


# ===== 3. HRÁČI =====
class Player(models.Model):
    class Position(models.TextChoices):
        GOALKEEPER = 'GK', _('Brankář')
        DEFENSE = 'DF', _('Obránce')
        FORWARD = 'FW', _('Útočník')

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    jersey_number = models.PositiveIntegerField()
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    position = models.CharField(max_length=2, choices=Position.choices)
    birth_date = models.DateField()
    photo = models.ImageField(upload_to='players/', blank=True, null=True)
    current_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} #{self.jersey_number}"


# ===== 4. ZÁPASY & STATISTIKY =====
class Match(models.Model):
    date_time = models.DateTimeField()
    stadium = models.ForeignKey(Stadium, on_delete=models.SET_NULL, null=True, blank=True)
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    home_team = models.ForeignKey(Team, related_name='home_matches', on_delete=models.CASCADE)
    away_team = models.ForeignKey(Team, related_name='away_matches', on_delete=models.CASCADE)
    home_score = models.PositiveIntegerField(default=0)
    away_score = models.PositiveIntegerField(default=0)

    report_text = models.TextField(blank=True, null=True)
    photos = models.ImageField(upload_to='match_reports/photos/', blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} - {self.date_time.strftime('%d.%m.%Y')}"


class MatchLineup(models.Model):
    class Line(models.IntegerChoices):
        FIRST = 1, "1. lajna"
        SECOND = 2, "2. lajna"
        THIRD = 3, "3. lajna"
        SUBSTITUTES = 4, "Náhradníci"

    class PositionDetail(models.TextChoices):
        LW = "LW", "Levé křídlo"
        C = "C", "Střed"
        RW = "RW", "Pravé křídlo"
        LD = "LD", "Levý obránce"
        RD = "RD", "Pravý obránce"
        G = "G", "Brankář"

    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, editable=False)
    is_starting = models.BooleanField(default=True)
    line_number = models.IntegerField(choices=Line.choices, blank=True, null=True)
    position_detail = models.CharField(max_length=2, choices=PositionDetail.choices, blank=True, null=True)

    goals = models.PositiveIntegerField(default=0, blank=True)
    assists = models.PositiveIntegerField(default=0, blank=True)
    penalty_minutes = models.PositiveIntegerField(default=0, blank=True)
    goals_conceded = models.PositiveIntegerField(default=0, blank=True)

    def save(self, *args, **kwargs):
        if self.match and self.player:
            if self.player.current_team == self.match.home_team:
                self.team = self.match.home_team
            elif self.player.current_team == self.match.away_team:
                self.team = self.match.away_team
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.player} ({self.get_line_number_display()} - {self.get_position_detail_display()})"


# ===== 5. ROLE A VEDENÍ =====
class StaffRole(models.Model):
    ROLES = [
        ('coach', 'Trenér'),
        ('assistant', 'Asistent trenéra'),
        ('manager', 'Manažer'),
        ('physio', 'Fyzioterapeut'),
    ]
    role = models.CharField(max_length=20, choices=ROLES)
    name = models.CharField(max_length=100)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.get_role_display()} - {self.name}"
