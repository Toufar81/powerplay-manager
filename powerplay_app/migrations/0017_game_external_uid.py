# file: powerplay_app/migrations/0017_game_external_uid.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("powerplay_app", "0016_stadium_photo_team_public_email_team_website_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="external_uid",
            field=models.CharField(
                "Externí UID",
                max_length=80,
                null=True,
                blank=True,
                unique=True,
                help_text="Stabilní externí identifikátor (např. nhlliga:<season_id>:<id>).",
            ),
        ),
    ]
