from django.contrib import admin
from .models import Competition, Stadium, Team, Player, Match, MatchLineup, StaffRole

@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'competition_type', 'season_start', 'season_end', 'status')
    list_filter = ('competition_type', 'status')
    search_fields = ('name',)


@admin.register(Stadium)
class StadiumAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'stadium')
    search_fields = ('name', 'city')
    filter_horizontal = ('competitions',)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'jersey_number', 'position', 'current_team')
    list_filter = ('position', 'current_team')
    search_fields = ('first_name', 'last_name')


class MatchLineupInline(admin.TabularInline):
    model = MatchLineup
    extra = 5
    fields = ('player', 'team', 'is_starting', 'goals', 'assists', 'penalty_minutes', 'goals_conceded')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('date_time', 'competition', 'home_team', 'away_team', 'home_score', 'away_score')
    list_filter = ('competition', 'date_time')
    inlines = [MatchLineupInline]
    search_fields = ('home_team__name', 'away_team__name')


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ('role', 'name', 'team')
    list_filter = ('role', 'team')
