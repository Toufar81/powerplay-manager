from django import forms
from .models import MatchLineup

class MatchLineupForm(forms.ModelForm):
    class Meta:
        model = MatchLineup
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
