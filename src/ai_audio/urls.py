from django.urls import path

from . import views

app_name = 'ai_audio'

urlpatterns = [
    path(
        'generate/<int:point_id>/', views.generate_audio, name='generate_audio'
    ),
    path(
        'generate-location-description/<int:point_id>/',
        views.generate_location_description,
        name='generate_location_description',
    ),
    path(
        'status/<int:generation_id>/',
        views.get_audio_status,
        name='audio_status',
    ),
    path(
        'delete/<int:generation_id>/', views.delete_audio, name='delete_audio'
    ),
    path(
        'generate-temp-description/',
        views.generate_temp_description,
        name='generate_temp_description',
    ),
    path(
        'generate-temp-audio/',
        views.generate_temp_audio,
        name='generate_temp_audio',
    ),
]
