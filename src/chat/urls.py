from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_dashboard, name='chat_dashboard'),
    path('private/<int:user_id>/', views.private_chat, name='private_chat'),
    path('route/<int:route_id>/', views.route_chat, name='route_chat'),
    path(
        'send_private_message/',
        views.send_private_message,
        name='send_private_message',
    ),
    path(
        'send_route_message/',
        views.send_route_message,
        name='send_route_message',
    ),
    path(
        'get_private_messages/<int:conversation_id>/',
        views.get_private_messages,
        name='get_private_messages',
    ),
    path(
        'get_route_messages/<int:route_id>/',
        views.get_route_messages,
        name='get_route_messages',
    ),
    path(
        'get_conversation_info/<int:conversation_id>/',
        views.get_conversation_info,
        name='get_conversation_info',
    ),
    path(
        'mark_read/<int:conversation_id>/',
        views.mark_conversation_as_read,
        name='mark_conversation_read',
    ),
    path(
        'mark_route_read/<int:route_id>/',
        views.mark_route_messages_as_read,
        name='mark_route_read',
    ),
    path(
        'get_unread_counts/', views.get_unread_counts, name='get_unread_counts'
    ),
    path(
        'delete_conversation/<int:conversation_id>/',
        views.delete_conversation,
        name='delete_conversation',
    ),
]
