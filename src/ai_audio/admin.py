from django.contrib import admin

from .models import AudioGeneration


@admin.register(AudioGeneration)
class AudioGenerationAdmin(admin.ModelAdmin):
    list_display = (
        'point',
        'user',
        'status',
        'language',
        'voice_type',
        'created_at',
    )
    list_filter = ('status', 'language', 'voice_type', 'created_at')
    search_fields = ('text_content', 'point__name')
    readonly_fields = ('created_at', 'completed_at', 'processing_time')
