from django.contrib import admin
from .models import Team, Player, StaffMember, Competition, Match, MatchTeam

# 🏒 Tým
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'founded', 'coach', 'manager')
    search_fields = ('name', 'city')

# 👤 Hráč
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'number', 'position', 'team')
    list_filter = ('position', 'team')
    search_fields = ('first_name', 'last_name')

# 🧑‍💼 Vedení týmu
@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'team')
    list_filter = ('role', 'team')
    search_fields = ('name',)

# 🏆 Soutěž
@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'season', 'start_date', 'end_date')
    list_filter = ('type', 'season')
    search_fields = ('name',)

# ⚔️ Zápas
@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('date', 'location', 'is_internal', 'competition')
    list_filter = ('is_internal', 'competition')
    search_fields = ('location',)

# 🧩 Strana zápasu
@admin.register(MatchTeam)
class MatchTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'match')
    list_filter = ('match',)
    search_fields = ('name',)
