from django.contrib import admin
from .models import Team, Player, StaffMember, Competition, Match, MatchTeam,PlayerPosition
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

@admin.register(PlayerPosition)
class PlayerPositionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'position_type', 'can_score', 'can_concede', 'can_assist')
    list_filter = ('position_type',)
    search_fields = ('code', 'name')

# 👤 Hráč
@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        'first_name', 'last_name', 'number', 'position', 'position_type_display',
        'team', 'matches_played', 'penalty_minutes', 'goals_display', 'assists_display', 'photo_preview'
    )

    list_filter = ('position', 'position__position_type', 'team')
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

    def position_type_display(self, obj):
        if obj.position:
            color = {
                'Goalkeeper': 'blue',
                'Defensive': 'green',
                'Offensive': 'orange'
            }.get(obj.position.position_type, 'gray')
            return format_html(
                '<span style="color:{};">{}</span>',
                color,
                obj.position.position_type
            )
        return "-"
    position_type_display.short_description = "Typ pozice"

    def assists_display(self, obj):
        if obj.has_scoring_stats():
            return f"Asistence: {obj.assists}"
        return "-"
    assists_display.short_description = "Asistence"


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
from .models import Stadion

# Stadion
@admin.register(Stadion)
class StadionAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')
    search_fields = ('name', 'address')

# ⚔️ Zápas
@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('date', 'stadion', 'is_internal', 'competition')
    list_filter = ('is_internal', 'competition', 'stadion')
    search_fields = ('stadion__name', 'stadion__address')

# 🧩 Strana zápasu
@admin.register(MatchTeam)
class MatchTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'match')
    list_filter = ('match',)
    search_fields = ('name',)
