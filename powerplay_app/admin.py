from django.contrib import admin
from .models import Competition, Stadium, Team, Player, Match, MatchLineup, StaffRole
from .forms import MatchLineupForm, MatchLineupInlineFormSet

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
    list_display = ('first_name', 'last_name', 'nickname','jersey_number', 'position', 'current_team')
    list_filter = ('position', 'current_team')
    search_fields = ('first_name', 'last_name')


class MatchLineupInline(admin.TabularInline):
    model = MatchLineup
    extra = 5
    list_display = ('player', 'team', 'match', 'line_number', 'position_detail', 'goals', 'assists')
    readonly_fields = ('team',)

class HomeLineupInline(admin.TabularInline):
    model = MatchLineup
    form = MatchLineupForm
    formset = MatchLineupInlineFormSet
    extra = 0
    fields = (
        'player', 'is_starting',
        'line_number', 'position_detail',
        'goals', 'assists', 'penalty_minutes', 'goals_conceded'
    )

    verbose_name = "Hráč domácího týmu"
    verbose_name_plural = "Sestava domácího týmu"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        obj_id = request.resolver_match.kwargs.get('object_id')
        if obj_id:
            match = Match.objects.get(pk=obj_id)
            return qs.filter(team=match.home_team)
        return qs.none()

    def get_formset(self, request, obj=None, **kwargs):
        self.parent_object = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "player" and hasattr(self, 'parent_object') and self.parent_object:
            kwargs["queryset"] = Player.objects.filter(current_team=self.parent_object.home_team)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)



class AwayLineupInline(admin.TabularInline):
    model = MatchLineup
    form = MatchLineupForm
    formset = MatchLineupInlineFormSet
    extra = 0
    fields = (
        'player', 'is_starting',
        'line_number', 'position_detail',
        'goals', 'assists', 'penalty_minutes', 'goals_conceded'
    )

    verbose_name = "Hráč hostujícího týmu"
    verbose_name_plural = "Sestava hostujícího týmu"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        obj_id = request.resolver_match.kwargs.get('object_id')
        if obj_id:
            match = Match.objects.get(pk=obj_id)
            return qs.filter(team=match.away_team)

    def get_formset(self, request, obj=None, **kwargs):
        self.parent_object = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "player" and hasattr(self, 'parent_object') and self.parent_object:
            kwargs["queryset"] = Player.objects.filter(current_team=self.parent_object.away_team)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('date_time', 'competition', 'home_team', 'away_team', 'home_score', 'away_score')
    list_filter = ('competition', 'date_time')
    search_fields = ('home_team__name', 'away_team__name')
    inlines = [HomeLineupInline, AwayLineupInline]

    def get_inline_instances(self, request, obj=None):
        inline_instances = []
        for inline_class in self.inlines:
            inline = inline_class(self.model, self.admin_site)
            if obj:
                if isinstance(inline, HomeLineupInline):
                    inline.verbose_name_plural = f"Sestava domácího týmu – {obj.home_team.name}"
                elif isinstance(inline, AwayLineupInline):
                    inline.verbose_name_plural = f"Sestava hostujícího týmu – {obj.away_team.name}"
            inline_instances.append(inline)
        return inline_instances



@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ('role', 'name', 'team')
    list_filter = ('role', 'team')

