import re

from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from interactions.models import Favorite
from routes.models import Route, RouteFavorite
from users.models import Friendship, User, UserProfile


def get_friend_status(user, target):
    if user == target:
        return 'self'
    qs = Friendship.objects.filter(
        Q(from_user=user, to_user=target) | Q(from_user=target, to_user=user)
    )
    if not qs.exists():
        return 'none'
    obj = qs.first()
    if obj.status == 'accepted':
        return 'friend'
    if obj.from_user == user and obj.status == 'pending':
        return 'sent'
    if obj.to_user == user and obj.status == 'pending':
        return 'received'
    return 'none'


def get_friends_with_stats(user):
    friendships = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user), status='accepted'
    ).select_related('from_user', 'to_user')

    friends_list = []
    for f in friendships:
        friend = f.to_user if f.from_user == user else f.from_user
        count = Route.objects.filter(
            author=friend, privacy='public', is_active=True
        ).count()
        friend.public_active_route_count = count
        friends_list.append(friend)
    return friends_list


def get_pending_friend_requests(user, limit=5):
    return Friendship.objects.filter(
        to_user=user, status='pending'
    ).select_related('from_user')[:limit]


def remove_friendship(user, friend):
    friendship = Friendship.objects.filter(
        (
            Q(from_user=user, to_user=friend)
            | Q(from_user=friend, to_user=user)
        ),
        status='accepted',
    ).first()

    if friendship:
        friendship.delete()
        return True
    return False


def are_friends(user1, user2):
    return Friendship.objects.filter(
        (
            Q(from_user=user1, to_user=user2)
            | Q(from_user=user2, to_user=user1)
        ),
        status='accepted',
    ).exists()


def find_users_for_friendship(user, search_query, limit=20):
    users = User.objects.exclude(id=user.id)
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    user_data = []
    for u in users[:limit]:
        friendship = Friendship.objects.filter(
            Q(from_user=user, to_user=u) | Q(from_user=u, to_user=user)
        ).first()
        user_data.append(
            {
                'user': u,
                'friendship_status': friendship.status if friendship else None,
            }
        )
    return user_data


def process_friend_request(from_user, to_user):
    if from_user == to_user:
        return False, _('You cannot send a friend request to yourself')

    if Friendship.objects.filter(
        Q(from_user=from_user, to_user=to_user)
        | Q(from_user=to_user, to_user=from_user)
    ).exists():
        return False, _('A friend request already exists')

    Friendship.objects.create(from_user=from_user, to_user=to_user)
    return True, _('Friend request sent to %(username)s') % {
        'username': to_user.username
    }


def update_friend_request_status(friend_request, status):
    friend_request.status = status
    friend_request.save()


def get_username_change_status(profile):
    """Проверяет, можно ли сменить юзернейм и сколько дней осталось."""
    can_change_username = True
    username_change_days_left = None

    if profile.last_username_change:
        days_since = (timezone.now() - profile.last_username_change).days
        can_change_username = days_since >= 30
        if not can_change_username:
            username_change_days_left = 30 - days_since

    return can_change_username, username_change_days_left


def update_user_profile(user, data, files):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    can_change_username, _ = get_username_change_status(profile)

    username = data.get('username')
    username_changed = False

    if username and username != user.username:
        if not can_change_username:
            return False, _(
                'Имя пользователя можно менять только раз в 30 дней'
            )
        if User.objects.filter(username=username).exclude(id=user.id).exists():
            return False, _('Это имя пользователя уже занято')

        user.username = username
        username_changed = True

    email = data.get('email')
    if email and email != user.email:
        user.email = email
    user.first_name = data.get('first_name', '')
    user.last_name = data.get('last_name', '')
    user.save()

    profile.bio = data.get('bio', '')
    profile.location = data.get('location', '')
    profile.website = data.get('website', '')

    if username_changed:
        profile.last_username_change = timezone.now()

    if 'avatar' in files:
        profile.avatar = files['avatar']
    elif data.get('remove_avatar') == '1' and profile.avatar:
        profile.avatar.delete(save=False)
        profile.avatar = None

    profile.save()
    return True, _('Профиль успешно обновлен')


def get_user_statistics(user):
    user_routes = Route.objects.filter(author=user)
    total_distance = (
        user_routes.aggregate(
            total=Sum('total_distance', filter=Q(total_distance__isnull=False))
        )['total']
        or 0
    )

    friends_count = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user), status='accepted'
    ).count()

    favorites_count = RouteFavorite.objects.filter(user=user).count()

    return {
        'routes_count': user_routes.count(),
        'total_distance': total_distance,
        'friends_count': friends_count,
        'favorites_count': favorites_count,
        'recent_routes': user_routes.order_by('-created_at')[:5],
    }


def get_public_profile_data(target_user, requesting_user):
    routes_qs = Route.objects.filter(author=target_user, is_active=True)
    total_distance = (
        routes_qs.aggregate(
            total=Sum('total_distance', filter=Q(total_distance__isnull=False))
        )['total']
        or 0
    )

    public_routes = routes_qs.filter(privacy='public').order_by('-created_at')

    friendships = Friendship.objects.filter(
        Q(from_user=target_user) | Q(to_user=target_user), status='accepted'
    ).select_related('from_user', 'to_user')

    friends = [
        f.to_user if f.from_user == target_user else f.from_user
        for f in friendships
    ]

    is_friend = friend_request_sent = friend_request_received = False
    user_favorites_ids = []

    if requesting_user.is_authenticated:
        user_favorites_ids = list(
            Favorite.objects.filter(user=requesting_user).values_list(
                'route_id', flat=True
            )
        )
        if requesting_user != target_user:
            status = get_friend_status(requesting_user, target_user)
            if status == 'friend':
                is_friend = True
            elif status == 'sent':
                friend_request_sent = True
            elif status == 'received':
                friend_request_received = True

    private_routes = (
        Route.objects.filter(author=target_user, privacy='private')
        if requesting_user == target_user
        else []
    )

    return {
        'total_distance': total_distance,
        'public_routes': public_routes,
        'friends': friends[:12],
        'user_favorites_ids': user_favorites_ids,
        'is_friend': is_friend,
        'friend_request_sent': friend_request_sent,
        'friend_request_received': friend_request_received,
        'private_routes': private_routes,
    }


def create_notification(user, title, message, obj_type, obj_id):
    try:
        from notifications.models import Notification

        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=obj_type,
            related_object_id=obj_id,
            related_object_type='route',
        )
    except ImportError:
        pass


def share_route_with_friend(user, route, friend_id):
    if route.author != user and not user.is_staff:
        return False, _('You do not have permission to share this route')

    if not friend_id:
        return False, _('No friend selected')

    try:
        friend = User.objects.get(id=friend_id)
    except User.DoesNotExist:
        return False, _('User not found')

    if not are_friends(user, friend):
        return False, _('This user is not your friend')

    route.shared_with.add(friend)

    create_notification(
        user=friend,
        title=_('Route shared with you'),
        message=_('%(sender)s has shared the route "%(route_name)s" with you')
        % {'sender': user.username, 'route_name': route.name},
        obj_type='route_shared',
        obj_id=route.id,
    )

    friend_name = friend.get_full_name() or friend.username
    return True, _('Route "%(route_name)s" has been shared with %(name)s') % {
        'route_name': route.name,
        'name': friend_name,
    }


def get_simple_friends_list(user):
    friendships = Friendship.objects.filter(
        Q(from_user=user, status='accepted')
        | Q(to_user=user, status='accepted')
    ).select_related('from_user', 'to_user')

    friends = []
    for f in friendships:
        friend = f.to_user if f.from_user == user else f.from_user
        friends.append(
            {
                'id': friend.id,
                'username': friend.username,
                'first_name': friend.first_name,
                'last_name': friend.last_name,
                'email': friend.email,
            }
        )
    return friends


def check_username(user, username):
    if not username:
        return {'error': _('Имя пользователя не может быть пустым')}

    user_exists = (
        User.objects.filter(username=username).exclude(id=user.id).exists()
    )

    pattern = re.compile(r'^[a-zA-Z0-9_]+$')
    is_valid = bool(pattern.match(username))

    return {'exists': user_exists, 'is_valid': is_valid, 'username': username}
