from django.contrib import admin

from routes.models import Route, RoutePoint


class RoutePointInline(admin.TabularInline):
    model = RoutePoint
    extra = 0
    fields = ('order', 'name', 'latitude', 'longitude')
    ordering = ('order',)


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'privacy', 'is_active', 'created_at')
    list_filter = ('privacy', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    inlines = [RoutePointInline]
    readonly_fields = ('created_at', 'updated_at')
