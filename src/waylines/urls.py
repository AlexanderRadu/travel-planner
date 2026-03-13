from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

import routes.views

urlpatterns = [
    path('', routes.views.home),
    path('admin/', admin.site.urls),
    path('routes/', include('routes.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('chat/', include('chat.urls')),
    path('interactions/', include('interactions.urls')),
    path('users/', include('users.urls')),
    path('api/ai-audio/', include('ai_audio.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
