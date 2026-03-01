from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.translation import gettext as _

from users.models import Friendship, User


def get_accepted_friends_for_user(user):
    friends = Friendship.objects.filter(
        Q(from_user=user, status='accepted')
        | Q(to_user=user, status='accepted')
    ).select_related('from_user', 'to_user')

    friends_list = []
    for friendship in friends:
        friend = (
            friendship.to_user
            if friendship.from_user == user
            else friendship.from_user
        )
        friends_list.append(
            {
                'id': friend.id,
                'username': friend.username,
                'first_name': friend.first_name,
                'last_name': friend.last_name,
                'email': friend.email,
            }
        )
    return friends_list


def share_route_with_user(route, current_user, target_email: str):

    email = target_email.strip() if target_email else ''

    if not email:
        raise ValueError(_('Email not provided.'))

    target_user = User.objects.get(email=email)

    if target_user == current_user:
        raise ValueError(_('You cannot share access with yourself.'))

    route.privacy = 'personal'
    route.shared_with.add(target_user)

    route.save(update_fields=['privacy'])

    return target_user


def grant_route_access(route, requesting_user, email: str):

    if route.author != requesting_user and not requesting_user.is_staff:
        raise PermissionDenied(
            _('You do not have permission to share access to this route.')
        )

    if not email:
        raise ValueError(_('Email not provided.'))

    try:
        target_user = User.objects.get(email=email)
    except User.DoesNotExist as e:
        raise ValueError(_('No user registered with this email.')) from e

    if target_user == requesting_user:
        raise ValueError(_('You cannot share access with yourself.'))

    route.privacy = 'personal'
    route.shared_with.add(target_user)
    route.save()

    return target_user


def share_route_with_friend(route, requesting_user, friend_id):

    if route.author != requesting_user and not requesting_user.is_staff:
        raise PermissionDenied(
            _('You do not have permission to send this route.')
        )

    if not friend_id:
        raise ValueError(_('Friend not selected.'))

    try:
        friend = User.objects.get(id=friend_id)
    except User.DoesNotExist as e:
        raise ValueError(_('Friend not found.')) from e

    friendship = Friendship.objects.filter(
        (
            Q(from_user=requesting_user, to_user=friend)
            | Q(from_user=friend, to_user=requesting_user)
        ),
        status='accepted',
    ).first()

    if not friendship:
        raise ValueError(_('The user is not your friend.'))

    route.shared_with.add(friend)
    route.save()

    return friend
