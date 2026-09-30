"""Django admin configuration for the championships app."""
from django.contrib import admin
from .models import Championship, ChampionshipTeam, PlayerRegistration

admin.site.register(Championship)
admin.site.register(ChampionshipTeam)
admin.site.register(PlayerRegistration)
