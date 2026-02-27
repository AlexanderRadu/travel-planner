from users.models import Friendship


def navbar_context(request):
    if not request.user.is_authenticated:
        return {}
    pending_requests = list(
        Friendship.objects.filter(
            to_user=request.user, status='pending'
        ).select_related('from_user')[:5]
    )
    return {
        'pending_requests_count': len(pending_requests),
        'pending_friend_requests': pending_requests,
    }
