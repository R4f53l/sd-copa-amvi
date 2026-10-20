from django import forms
from django.utils.translation import gettext_lazy as _

from apps.teams.models import City


class PublicMatchFilterForm(forms.Form):
    round_number = forms.TypedChoiceField(
        label=_("Round"),
        choices=(),
        coerce=int,
        empty_value=None,
        required=False,
    )
    city = forms.ModelChoiceField(
        label=_("City"),
        queryset=City.objects.none(),
        required=False,
        empty_label=_("All cities"),
    )

    def __init__(self, *args, round_numbers=(), cities=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["round_number"].choices = [
            ("", _("All rounds")),
            *((number, number) for number in round_numbers),
        ]
        if cities is not None:
            self.fields["city"].queryset = cities
