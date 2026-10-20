from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.shared.forms import BootstrapFormMixin

from .models import City, Player, Stadium, Team

DATE_FORMAT = "%Y-%m-%d"


# gera slug automatico quando omitido e valida unicidade
class AutoSlugModelForm(BootstrapFormMixin, forms.ModelForm):
    slug_source_field = "name"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        if not slug:
            source = self.cleaned_data.get(self.slug_source_field, "")
            slug = slugify(source)
        return slug


class CityForm(AutoSlugModelForm):
    class Meta:
        model = City
        fields = ("name", "state", "slug")

    def clean_state(self):
        state = self.cleaned_data.get("state", "")
        return state.strip().upper()


class StadiumForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Stadium
        fields = (
            "name",
            "city",
            "address",
            "capacity",
            "latitude",
            "longitude",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.order_by("name")


class TeamForm(AutoSlugModelForm):
    class Meta:
        model = Team
        fields = (
            "name",
            "short_name",
            "slug",
            "city",
            "home_stadium",
            "crest",
            "primary_color",
            "secondary_color",
            "founded_year",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.order_by("name")
        # carrega cidade junto com estadio em consulta unica
        self.fields["home_stadium"].queryset = (
            Stadium.objects.filter(is_active=True)
            .select_related("city")
            .order_by("name")
        )

    def clean_short_name(self):
        short_name = self.cleaned_data.get("short_name", "")
        return short_name.strip().upper()


class PlayerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Player
        fields = (
            "full_name",
            "nickname",
            "document_number",
            "birth_date",
            "position",
            "preferred_foot",
            "photo",
            "is_active",
        )
        widgets = {
            "birth_date": forms.DateInput(
                attrs={"type": "date"},
                format=DATE_FORMAT,
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].input_formats = [DATE_FORMAT]

    def clean_document_number(self):
        # converte string vazia em nulo para respeitar restricao unique
        doc = (self.cleaned_data.get("document_number") or "").strip()
        if not doc:
            return None
        clash = Player.objects.filter(document_number=doc).exclude(
            pk=self.instance.pk
        )
        if clash.exists():
            raise ValidationError(
                _("A player with this document number already exists.")
            )
        return doc
