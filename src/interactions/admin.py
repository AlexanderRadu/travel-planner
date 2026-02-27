from django.contrib import admin

from interactions.models import Favorite, Rating


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'route', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'route__name')
    date_hierarchy = 'created_at'


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'route', 'score', 'created_at')
    list_filter = ('score', 'created_at')
    search_fields = ('user__username', 'route__name')
    date_hierarchy = 'created_at'
