from django.conf import settings
from powerplay_app.models import Team

def get_primary_team() -> Team:
    slug = getattr(settings, "PRIMARY_TEAM_SLUG", None)
    if slug:
        return Team.objects.select_related("league").get(slug=slug)
    tid = getattr(settings, "PRIMARY_TEAM_ID", None)
    if tid:
        return Team.objects.select_related("league").get(pk=int(tid))
    raise RuntimeError("PRIMARY_TEAM_SLUG / PRIMARY_TEAM_ID není nastaven.")
