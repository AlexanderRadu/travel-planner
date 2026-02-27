from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/routes/', views.RouteCreateView.as_view(), name='route_create'),
    path(
        'api/routes/<int:pk>/',
        views.RouteUpdateView.as_view(),
        name='route_update',
    ),
    path(
        'api/routes/<int:route_id>/share/',
        views.share_route,
        name='share_route',
    ),
    path('api/points/', views.save_point, name='save_point'),
    path('api/points/<int:point_id>/', views.save_point, name='update_point'),
    path('all/', views.all_routes, name='all_routes'),
    path('my/', views.my_routes, name='my_routes'),
    path('shared/', views.shared_routes, name='shared_routes'),
    path('create/', views.create_route, name='create_route'),
    path('walking/', views.walking_routes, name='walking_routes'),
    path('driving/', views.driving_routes, name='driving_routes'),
    path('cycling/', views.cycling_routes, name='cycling_routes'),
    path('adventure/', views.adventure_routes, name='adventure_routes'),
    path('<int:route_id>/', views.route_detail, name='route_detail'),
    path('<int:route_id>/edit/', views.edit_route, name='edit_route'),
    path(
        '<int:route_id>/toggle-active/',
        views.toggle_route_active,
        name='toggle_route_active',
    ),
    path('<int:route_id>/rate/', views.rate_route, name='rate_route'),
    path(
        '<int:route_id>/favorite/',
        views.toggle_favorite,
        name='toggle_favorite',
    ),
    path(
        '<int:route_id>/comment/',
        views.add_route_comment,
        name='add_route_comment',
    ),
    path(
        'points/<int:point_id>/comment/',
        views.add_point_comment,
        name='add_point_comment',
    ),
    path(
        '<int:route_id>/generate-qr/',
        views.generate_qr_code,
        name='generate_qr_code',
    ),
    path('<int:route_id>/qr-code/', views.route_qr_code, name='route_qr_code'),
    path(
        '<int:route_id>/share-access/',
        views.share_route_access,
        name='share_route_access',
    ),
    path(
        '<int:route_id>/send-to-friend/',
        views.send_to_friend,
        name='send_to_friend',
    ),
    path('api/friends/', views.get_friends_list, name='get_friends_list'),
    path('search/', views.search_routes, name='search'),
    path(
        'api/routes/<int:route_id>/delete/',
        views.delete_route,
        name='delete_route',
    ),
    path('<int:route_id>/export/gpx/', views.export_gpx, name='export_gpx'),
    path('<int:route_id>/export/kml/', views.export_kml, name='export_kml'),
    path(
        '<int:route_id>/export/geojson/',
        views.export_geojson,
        name='export_geojson',
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
