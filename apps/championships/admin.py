"""Django admin configuration for the championships app."""

from django.contrib import admin

from .models import Championship, ChampionshipTeam, PlayerRegistration

#cria o inline de ChampionshipTeam
class ChampionshipTeamInline(admin.TabularInline):
    model = ChampionshipTeam
    extra = 1

class ChampionshipAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'season', 'start_date', 'end_date')
    search_fields = ('name', 'season')
    inlines = [ChampionshipTeamInline]

    fieldsets = (
        ('Geral', {
            'fields': ('name', 'season', 'slug', 'description', 'status', 'start_date', 'end_date')
        }),
        ('Regulamento', {
            'fields': ('regulation', 'regulation_file')
        }),
        ('Regras', {
            'fields': (
                'points_per_win',
                'points_per_draw',
                'points_per_loss',
                'yellow_cards_for_suspension',
                'max_players_per_team',
            )
        }),
    )
    prepopulated_fields = {'slug': ('name',)}

class ChampionshipPlayerInline(admin.TabularInline):
    model = PlayerRegistration
    extra = 1

class ChampionshipTeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'championship', 'team', 'points', 'rank') #caso seja necessario
    search_fields = ('championship__name', 'team__name')
    
    inlines = [ChampionshipPlayerInline]
    readonly_fields = (
        'played',         
        'wins',            
        'draws',           
        'losses',         
        'goals_for',       
        'goals_against',   
        'points',          
        'yellow_cards',   
        'red_cards',       
        'rank',            
    )


admin.site.register(Championship, ChampionshipAdmin)
admin.site.register(ChampionshipTeam, ChampionshipTeamAdmin)