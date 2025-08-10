from django.contrib import admin
from .models import Team, Player, StaffMember, Competition, Match, MatchTeam
from django.utils.html import format_html

# 🏒 Tým
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'coach', 'logo_preview')

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="50" height="50" />', obj.logo.url)
        return "-"
    logo_preview.short_description = "Logo"



# 👤 Hráč
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        'first_name', 'last_name', 'number', 'position', 'team',
        'matches_played', 'penalty_minutes', 'goals_display', 'photo_preview'
    )
    list_filter = ('position', 'team')
    search_fields = ('first_name', 'last_name')

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />',
                obj.photo.url
            )
        return "-"
    photo_preview.short_description = "Foto"

    def goals_display(self, obj):
        if obj.is_goalkeeper():
            return f"Inkasováno: {obj.goals_conceded}"
        elif obj.has_scoring_stats():
            return f"Vstřeleno: {obj.goals_scored}"
        return "-"
    goals_display.short_description = "Góly"
from .models import StaffRole

# 🧑‍💼 Role týmu
@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


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
