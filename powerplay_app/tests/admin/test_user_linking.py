import pytest
from django.contrib.auth import get_user_model
from powerplay_app.models import Player, Staff, Team
from powerplay_app.admin import (
    _norm_name, _norm_pair, link_users_by_name_for_players, create_users_for_players,
)
from django.contrib import admin
from django.test import RequestFactory

@pytest.mark.django_db
def test_norm_name_strips_and_accent_insensitive():
    assert _norm_name("  Ján   Novák  ") == "jannovak".replace(" ", "")
    assert _norm_name("Novák") == "novak"
    assert _norm_pair("Jan", "Novák") == ("jan", "novak")

class _DummyMA:
    def __init__(self):
        self.messages = []
    def message_user(self, request, msg, level=None):
        self.messages.append((level, msg))

@pytest.mark.django_db
def test_link_by_name_exact_one_match(player_factory, team_factory):
    User = get_user_model()
    t = team_factory()
    p = Player.objects.create(first_name="Jan", last_name="Novák", jersey_number=10, position="forward", team=t)
    u = User.objects.create(username="j.novak", first_name="Jan", last_name="Novak")
    ma = _DummyMA()
    link_users_by_name_for_players(ma, RequestFactory().get("/"), Player.objects.filter(id=p.id))
    p.refresh_from_db()
    assert p.user_id == u.id

@pytest.mark.django_db
def test_create_user_for_player_creates_and_links(player_factory, team_factory):
    User = get_user_model()
    t = team_factory()
    p = Player.objects.create(first_name="Karel", last_name="Vomáčka", jersey_number=22, position="forward", team=t)
    ma = _DummyMA()
    create_users_for_players(ma, RequestFactory().get("/"), Player.objects.filter(id=p.id))
    p.refresh_from_db()
    assert p.user_id
    u = User.objects.get(id=p.user_id)
    assert u.first_name == "Karel"
    assert u.last_name == "Vomáčka"
    assert u.is_staff is False
