from django.urls import path

import interactions.views

app_name = 'interactions'

urlpatterns = [
    path(
        'favorite/<int:route_id>/',
        interactions.views.toggle_favorite,
        name='toggle_favorite',
    ),
    path(
        'rating/<int:route_id>/',
        interactions.views.add_rating,
        name='add_rating',
    ),
    path(
        'comment/<int:route_id>/',
        interactions.views.add_comment,
        name='add_comment',
    ),
    path(
        'comment/delete/<int:comment_id>/',
        interactions.views.delete_comment,
        name='delete_comment',
    ),
]
