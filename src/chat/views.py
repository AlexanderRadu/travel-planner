import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from routes.models import Route
from routes.services.access import can_view_route

from .models import Conversation, PrivateMessage, RouteChat, RouteChatMessage

logger = logging.getLogger(__name__)


class ChatService:
    @staticmethod
    def get_user_conversations(user):
        conversations = (
            Conversation.objects.filter(participants=user)
            .prefetch_related(
                Prefetch(
                    'participants',
                    queryset=User.objects.only('id', 'username'),
                ),
                Prefetch(
                    'messages',
                    queryset=PrivateMessage.objects.filter(is_read=False)
                    .exclude(sender=user)
                    .only('id', 'is_read'),
                ),
            )
            .order_by('-updated_at')
        )

        for conv in conversations:
            conv.unread_count = (
                conv.messages.filter(is_read=False)
                .exclude(sender=user)
                .count()
            )

        return conversations

    @staticmethod
    def get_or_create_conversation(user1, user2):
        if user1 == user2:
            raise ValidationError(
                _('Cannot start a conversation with yourself')
            )
        conversation = (
            Conversation.objects.filter(participants=user1)
            .filter(participants=user2)
            .first()
        )
        if not conversation:
            with transaction.atomic():
                conversation = Conversation.objects.create()
                conversation.participants.add(user1, user2)
                logger.info(
                    f'Created new conversation between'
                    f' {user1.username} and {user2.username}'
                )
        return conversation

    @staticmethod
    def validate_message_content(content):
        if not content or not content.strip():
            raise ValidationError(_('Message cannot be empty'))
        content = content.strip()
        if len(content) > 1000:
            raise ValidationError(
                _('Message is too long (max 1000 characters)')
            )
        return content

    @staticmethod
    def get_route_chat_with_access_check(user, route_id):
        route = get_object_or_404(Route, id=route_id)
        if not can_view_route(user, route):
            raise PermissionDenied(_('You do not have access to this route'))
        route_chat = RouteChat.objects.get_or_create(route=route)[0]
        return route_chat, route

    @staticmethod
    def get_route_chats_with_unread(user):
        user_routes_chats = (
            RouteChat.objects.filter(route__author=user)
            .select_related('route')
            .order_by('-route__created_at')
        )

        participant_chats = (
            RouteChat.objects.filter(route__shared_with=user)
            .exclude(route__author=user)
            .select_related('route')
            .order_by('-route__created_at')
        )

        public_chats = (
            RouteChat.objects.filter(
                route__privacy='public', route__is_active=True
            )
            .select_related('route', 'route__author')
            .exclude(route__author=user)
            .order_by('-route__created_at')
        )

        for chat in user_routes_chats:
            chat.unread_count = (
                chat.messages.filter(is_read=False).exclude(user=user).count()
            )

        for chat in participant_chats:
            chat.unread_count = (
                chat.messages.filter(is_read=False).exclude(user=user).count()
            )

        for chat in public_chats:
            chat.unread_count = (
                chat.messages.filter(is_read=False).exclude(user=user).count()
            )

        return user_routes_chats, participant_chats, public_chats


class JSONResponseMixin:
    @staticmethod
    def success_response(data=None):
        response_data = {'success': True}
        if data:
            response_data.update(data)
        return JsonResponse(response_data)

    @staticmethod
    def error_response(message, status=400, error_code=None):
        response_data = {'success': False, 'error': message}
        if error_code:
            response_data['error_code'] = error_code
        return JsonResponse(response_data, status=status)

    @staticmethod
    def parse_json_request(request):
        if request.content_type != 'application/json':
            raise ValidationError('Invalid content type. Use application/json')
        try:
            return json.loads(request.body)
        except json.JSONDecodeError as e:
            raise ValidationError('Invalid JSON format') from e


@login_required
def chat_dashboard(request):
    cache_key = f'chat_dashboard_{request.user.id}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return render(request, 'chat/dashboard.html', cached_data)

    try:
        conversations = ChatService.get_user_conversations(request.user)
        conversations_data = []
        total_unread_count = 0

        for conversation in conversations:
            other_user = conversation.get_other_participant(request.user)
            if other_user:
                last_message = conversation.messages.order_by(
                    '-created_at'
                ).first()
                unread_count = getattr(conversation, 'unread_count', 0)
                total_unread_count += unread_count
                conversations_data.append(
                    {
                        'conversation': conversation,
                        'other_user': other_user,
                        'unread_count': unread_count,
                        'last_message': last_message,
                        'is_online': getattr(other_user, 'is_online', False),
                    }
                )

        user_routes_chats, participant_chats, public_chats = (
            ChatService.get_route_chats_with_unread(request.user)
        )

        route_unread_total = 0
        for chat in user_routes_chats:
            route_unread_total += getattr(chat, 'unread_count', 0)
        for chat in participant_chats:
            route_unread_total += getattr(chat, 'unread_count', 0)
        for chat in public_chats:
            route_unread_total += getattr(chat, 'unread_count', 0)

        total_unread_count += route_unread_total

        friends = (
            User.objects.filter(
                Q(
                    friendship_requests_sent__to_user=request.user,
                    friendship_requests_sent__status='accepted',
                )
                | Q(
                    friendship_requests_received__from_user=request.user,
                    friendship_requests_received__status='accepted',
                )
            )
            .distinct()
            .only('id', 'username')
        )

        existing_ids = (
            {data['other_user'].id for data in conversations_data}
            if conversations_data
            else set()
        )
        friends_without_chats = friends.exclude(id__in=existing_ids)[:5]

        context = {
            'conversations_data': conversations_data,
            'user_routes_chats': user_routes_chats,
            'participant_chats': participant_chats,
            'public_chats': public_chats,
            'friends': friends,
            'friends_without_chats': friends_without_chats,
            'total_unread_count': total_unread_count,
        }

        cache.set(cache_key, context, 120)
        return render(request, 'chat/dashboard.html', context)

    except Exception as e:
        logger.error(
            f'Error in chat_dashboard for user {request.user.id}: {e}'
        )
        messages.error(request, _('An error occurred while loading chats'))
        return render(
            request,
            'chat/dashboard.html',
            {
                'conversations_data': [],
                'user_routes_chats': [],
                'participant_chats': [],
                'public_chats': [],
                'friends': [],
                'friends_without_chats': [],
                'total_unread_count': 0,
            },
        )


@login_required
def private_chat(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        messages.error(request, _('Cannot start a conversation with yourself'))
        return redirect('chat:chat_dashboard')

    conversation = ChatService.get_or_create_conversation(
        request.user, other_user
    )

    unread_messages = conversation.messages.filter(is_read=False).exclude(
        sender=request.user
    )
    if unread_messages.exists():
        with transaction.atomic():
            unread_messages.update(is_read=True)
        cache.delete(f'chat_dashboard_{request.user.id}')
        cache.delete(f'chat_dashboard_{other_user.id}')

    try:
        accepted_friends_count = other_user.friendship_requests_sent.filter(
            status='accepted'
        ).count()
    except AttributeError:
        accepted_friends_count = 0

    context = {
        'conversation': conversation,
        'other_user': other_user,
        'accepted_friends_count': accepted_friends_count,
    }
    return render(request, 'chat/private_chat.html', context)


@login_required
def route_chat(request, route_id):
    try:
        route_chat, route = ChatService.get_route_chat_with_access_check(
            request.user, route_id
        )

        unread_messages = route_chat.messages.filter(is_read=False).exclude(
            user=request.user
        )
        if unread_messages.exists():
            with transaction.atomic():
                unread_messages.update(is_read=True)
            cache.delete(f'chat_dashboard_{request.user.id}')

        chat_messages = route_chat.messages.select_related('user').order_by(
            '-timestamp'
        )[:100]
        return render(
            request,
            'chat/route_chat.html',
            {
                'route': route,
                'chat_messages': chat_messages,
                'route_chat': route_chat,
            },
        )
    except PermissionDenied:
        messages.error(request, _('You do not have access to this chat'))
        return redirect('routes:route_list')
    except Exception as e:
        logger.error(f'Error in route_chat for user {request.user.id}: {e}')
        messages.error(request, _('An error occurred while loading the chat'))
        return redirect('routes:route_list')


@login_required
@require_POST
def send_private_message(request):
    try:
        data = JSONResponseMixin.parse_json_request(request)
        user_id = data.get('user_id')
        message_content = data.get('message')

        if not user_id:
            return JSONResponseMixin.error_response(_('Missing user_id'))

        validated_content = ChatService.validate_message_content(
            message_content
        )
        other_user = get_object_or_404(User, id=user_id)

        if other_user == request.user:
            return JSONResponseMixin.error_response(
                _('Cannot send message to yourself')
            )

        with transaction.atomic():
            conversation = ChatService.get_or_create_conversation(
                request.user, other_user
            )
            message_obj = PrivateMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                content=validated_content,
            )
            conversation.updated_at = timezone.now()
            conversation.save()
            cache.delete(f'chat_dashboard_{request.user.id}')
            cache.delete(f'chat_dashboard_{other_user.id}')

        logger.info(f'User {request.user.id} sent message to {other_user.id}')
        return JSONResponseMixin.success_response(
            {
                'message_id': message_obj.id,
                'content': message_obj.content,
                'sender': message_obj.sender.username,
                'sender_id': message_obj.sender.id,
                'created_at': message_obj.created_at.strftime('%H:%M'),
                'created_at_iso': message_obj.created_at.isoformat(),
                'conversation_id': conversation.id,
            }
        )

    except ValidationError as e:
        return JSONResponseMixin.error_response(str(e))
    except Exception as e:
        logger.error(
            f'Error sending private message for user {request.user.id}: {e}'
        )
        return JSONResponseMixin.error_response(
            _('Internal server error'), status=500, error_code='server_error'
        )


@login_required
@require_POST
def send_route_message(request):
    try:
        data = JSONResponseMixin.parse_json_request(request)
        route_id = data.get('route_id')
        message_content = data.get('message')

        if not route_id:
            return JSONResponseMixin.error_response(_('Missing route_id'))

        validated_content = ChatService.validate_message_content(
            message_content
        )

        with transaction.atomic():
            route_chat, route = ChatService.get_route_chat_with_access_check(
                request.user, route_id
            )
            message_obj = RouteChatMessage.objects.create(
                route_chat=route_chat,
                user=request.user,
                message=validated_content,
            )
            participants = [route.author, *list(route.shared_with.all())]
            for participant in participants:
                cache.delete(f'chat_dashboard_{participant.id}')

        logger.info(
            f'User {request.user.id} sent message to route chat {route_id}'
        )
        return JSONResponseMixin.success_response(
            {
                'message_id': message_obj.id,
                'content': message_obj.message,
                'sender': message_obj.user.username,
                'sender_id': message_obj.user.id,
                'created_at': message_obj.timestamp.strftime('%H:%M'),
                'route_id': route.id,
            }
        )

    except (ValidationError, PermissionDenied) as e:
        return JSONResponseMixin.error_response(str(e))
    except Exception as e:
        logger.error(
            f'Error sending route message for user {request.user.id}: {e}'
        )
        return JSONResponseMixin.error_response(
            _('Failed to send message'), status=500
        )


@login_required
@require_http_methods(['GET'])
def get_private_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return JSONResponseMixin.error_response(_('Access denied'), status=403)

    last_message_id = request.GET.get('last_message_id')
    limit = int(request.GET.get('limit', 100))

    messages_qs = conversation.messages.select_related('sender').order_by(
        '-created_at'
    )
    if last_message_id:
        messages_qs = messages_qs.filter(id__gt=last_message_id)
    messages_qs = messages_qs[:limit]
    messages_list = list(reversed(messages_qs))

    messages_data = [
        {
            'id': msg.id,
            'content': msg.content,
            'sender': msg.sender.username,
            'sender_id': msg.sender.id,
            'created_at': msg.created_at.strftime('%H:%M'),
            'created_at_full': msg.created_at.strftime('%d.%m.%Y %H:%M'),
            'is_own': msg.sender == request.user,
            'is_read': msg.is_read,
        }
        for msg in messages_list
    ]

    return JSONResponseMixin.success_response(
        {
            'messages': messages_data,
            'conversation_id': conversation.id,
            'has_more': len(messages_list) == limit,
        }
    )


@login_required
@require_http_methods(['GET'])
def get_route_messages(request, route_id):
    route_chat, route = ChatService.get_route_chat_with_access_check(
        request.user, route_id
    )

    last_message_id = request.GET.get('last_id')
    limit = int(request.GET.get('limit', 100))

    messages_qs = route_chat.messages.select_related('user').order_by(
        '-timestamp'
    )
    if last_message_id:
        messages_qs = messages_qs.filter(id__gt=last_message_id)
    messages_qs = messages_qs[:limit]
    messages_list = list(reversed(messages_qs))

    messages_data = [
        {
            'id': msg.id,
            'content': msg.message,
            'sender': msg.user.username,
            'sender_id': msg.user.id,
            'created_at': msg.timestamp.strftime('%H:%M'),
            'is_own': msg.user == request.user,
            'is_read': msg.is_read,
        }
        for msg in messages_list
    ]

    return JSONResponseMixin.success_response(
        {
            'messages': messages_data,
            'route_id': route.id,
            'has_more': len(messages_list) == limit,
        }
    )


@login_required
@require_http_methods(['GET'])
def get_conversation_info(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return JSONResponseMixin.error_response(_('Access denied'), status=403)

    other_user = conversation.get_other_participant(request.user)
    if not other_user:
        return JSONResponseMixin.error_response(
            _('Conversation not found'), status=404
        )

    unread_count = (
        conversation.messages.filter(is_read=False)
        .exclude(sender=request.user)
        .count()
    )

    return JSONResponseMixin.success_response(
        {
            'conversation': {
                'id': conversation.id,
                'updated_at': conversation.updated_at.isoformat(),
                'unread_count': unread_count,
            },
            'other_user': {
                'id': other_user.id,
                'username': other_user.username,
                'is_online': getattr(other_user, 'is_online', False),
                'last_seen': getattr(other_user, 'last_seen', None),
                'routes_count': other_user.routes.count(),
            },
        }
    )


@login_required
@require_POST
def mark_conversation_as_read(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return JSONResponseMixin.error_response(_('Access denied'), status=403)

    with transaction.atomic():
        updated_count = (
            conversation.messages.filter(is_read=False)
            .exclude(sender=request.user)
            .update(is_read=True)
        )
        cache.delete(f'chat_dashboard_{request.user.id}')

    logger.info(
        f'User {request.user.id} marked conversation {conversation_id} as read'
    )
    return JSONResponseMixin.success_response({'updated_count': updated_count})


@login_required
@require_http_methods(['GET'])
def get_unread_counts(request):
    try:
        private_unread = (
            PrivateMessage.objects.filter(
                conversation__participants=request.user, is_read=False
            )
            .exclude(sender=request.user)
            .count()
        )

        my_routes_unread = (
            RouteChatMessage.objects.filter(
                route_chat__route__author=request.user, is_read=False
            )
            .exclude(user=request.user)
            .count()
        )

        shared_routes_unread = (
            RouteChatMessage.objects.filter(
                route_chat__route__shared_with=request.user, is_read=False
            )
            .exclude(user=request.user)
            .count()
        )

        public_routes_unread = (
            RouteChatMessage.objects.filter(
                route_chat__route__privacy='public',
                route_chat__route__is_active=True,
                is_read=False,
            )
            .exclude(route_chat__route__author=request.user)
            .exclude(user=request.user)
            .count()
        )

        total_unread = (
            private_unread
            + my_routes_unread
            + shared_routes_unread
            + public_routes_unread
        )

        conversations_unread = []
        conversations = Conversation.objects.filter(participants=request.user)
        for conv in conversations:
            unread = (
                conv.messages.filter(is_read=False)
                .exclude(sender=request.user)
                .count()
            )
            if unread > 0:
                conversations_unread.append(
                    {'id': conv.id, 'unread_count': unread}
                )

        return JSONResponseMixin.success_response(
            {
                'success': True,
                'total_unread': total_unread,
                'private_unread': private_unread,
                'my_routes_unread': my_routes_unread,
                'shared_routes_unread': shared_routes_unread,
                'public_routes_unread': public_routes_unread,
                'conversations': conversations_unread,
            }
        )

    except Exception as e:
        logger.error(
            f'Error in get_unread_counts for user {request.user.id}: {e}'
        )
        return JSONResponseMixin.error_response(
            _('Failed to get unread counts'), status=500
        )


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return JSONResponseMixin.error_response(_('Access denied'), status=403)

    with transaction.atomic():
        conversation.participants.remove(request.user)
        if conversation.participants.count() == 0:
            conversation.delete()
        cache.delete(f'chat_dashboard_{request.user.id}')

    logger.info(
        f'User {request.user.id} deleted conversation {conversation_id}'
    )
    return JSONResponseMixin.success_response(
        {'message': _('Conversation deleted')}
    )


@login_required
@require_POST
def mark_route_messages_as_read(request, route_id):
    try:
        route_chat = ChatService.get_route_chat_with_access_check(
            request.user, route_id
        )[0]

        with transaction.atomic():
            updated_count = (
                route_chat.messages.filter(is_read=False)
                .exclude(user=request.user)
                .update(is_read=True)
            )
            cache.delete(f'chat_dashboard_{request.user.id}')

        logger.info(
            f'User {request.user.id} marked route messages'
            f' for route {route_id} as read'
        )
        return JSONResponseMixin.success_response(
            {'success': True, 'updated_count': updated_count}
        )

    except PermissionDenied as e:
        return JSONResponseMixin.error_response(str(e), status=403)
    except Exception as e:
        logger.error(
            f'Error marking route messages as read for user'
            f' {request.user.id}: {e}'
        )
        return JSONResponseMixin.error_response(
            _('Failed to mark messages as read'), status=500
        )
