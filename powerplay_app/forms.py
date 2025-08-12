from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import MatchLineup

class MatchLineupForm(forms.ModelForm):
    class Meta:
        model = MatchLineup
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


class MatchLineupInlineFormSet(BaseInlineFormSet):
    def save_new(self, form, commit=True):
        obj = form.save(commit=False)
        match = self.instance
        player = form.cleaned_data.get('player')

        if player and match:
            current_team = getattr(player, 'current_team', None)
            if current_team == match.home_team:
                obj.team = match.home_team
            elif current_team == match.away_team:
                obj.team = match.away_team
            else:
                raise ValidationError(
                    f"Hráč {player} není v žádném týmu tohoto zápasu ({match.home_team} vs {match.away_team})."
                )

        if commit:
            obj.save()
        return obj

    def clean(self):
        super().clean()

        seen_players = set()
        line_data = {}
        position_counts = {}

        match_instance = self.instance
        home_goals_by_players = 0
        away_goals_by_players = 0

        for i, form in enumerate(self.forms):
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            player = form.cleaned_data.get('player')
            match = form.cleaned_data.get('match')
            line = form.cleaned_data.get('line_number')
            position = form.cleaned_data.get('position_detail')
            goals = form.cleaned_data.get('goals', 0)

            if not player or not match:
                continue

            # 1️⃣ Chybějící lajna
            if line is None:
                form.add_error('line_number', f"Hráč {player} nemá vyplněnou lajnu.")
                continue

            # 2️⃣ Chybějící pozice
            if not position:
                form.add_error('position_detail', f"Hráč {player} nemá vyplněnou pozici.")
                continue

            player_id = getattr(player, 'pk', None)
            if not player_id:
                continue

            # 3️⃣ Duplicitní hráč
            if player_id in seen_players:
                form.add_error('player', f"Hráč {player} je v sestavě vícekrát.")
                continue
            seen_players.add(player_id)

            # 4️⃣ Počet hráčů v lajně
            key = (match.id, line)
            if key not in line_data:
                line_data[key] = {'G': 0, 'F': 0}
            if position == 'G':
                line_data[key]['G'] += 1
            else:
                line_data[key]['F'] += 1

            # 5️⃣ Unikátní pozice v lajně
            if key not in position_counts:
                position_counts[key] = set()
            if position in position_counts[key]:
                label = MatchLineup.PositionDetail(position).label
                form.add_error('position_detail', f"V lajně {line} už je obsazená pozice {label}.")
                continue
            position_counts[key].add(position)

            # 6️⃣ Týmová příslušnost
            current_team = getattr(player, 'current_team', None)
            if current_team == match_instance.home_team:
                home_goals_by_players += goals
            elif current_team == match_instance.away_team:
                away_goals_by_players += goals
            else:
                form.add_error('player', f"Hráč {player} není v žádném týmu tohoto zápasu.")
                continue

        # 7️⃣ Validace počtu hráčů v lajně
        for (match_id, line), counts in line_data.items():
            if counts['G'] > 1:
                self._add_line_error(line, f"Lajna {line} má více než jednoho brankáře.")
            if counts['F'] > 5:
                self._add_line_error(line, f"Lajna {line} má více než 5 hráčů v poli.")

        # 8️⃣ Validace součtu gólů vs. týmové skóre
        if match_instance.home_score is not None and home_goals_by_players > match_instance.home_score:
            raise ValidationError(
                f"Součet gólů hráčů domácího týmu ({home_goals_by_players}) "
                f"překračuje týmové skóre ({match_instance.home_score})."
            )

        if match_instance.away_score is not None and away_goals_by_players > match_instance.away_score:
            raise ValidationError(
                f"Součet gólů hráčů hostujícího týmu ({away_goals_by_players}) "
                f"překračuje týmové skóre ({match_instance.away_score})."
            )

    def _add_line_error(self, line_number, message):
        """Pomocná metoda pro přidání chyby ke všem hráčům v dané lajně."""
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            if form.cleaned_data.get('line_number') == line_number:
                form.add_error('line_number', message)


