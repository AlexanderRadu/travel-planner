from django.db.models import Avg, Count, Q

from interactions.models import Favorite
from routes.models import Route
from users.models import Friendship, User


def get_general_stats() -> dict:

    active_routes = Route.objects.filter(is_active=True)

    total_routes = active_routes.count()
    total_users = User.objects.count()

    total_countries = active_routes.values('country').distinct().count()

    walking_count = active_routes.filter(route_type='walking').count()
    driving_count = active_routes.filter(route_type='driving').count()
    cycling_count = active_routes.filter(route_type='cycling').count()

    return {
        'total_routes': total_routes,
        'total_users': total_users,
        'total_countries': total_countries,
        'walking_count': walking_count,
        'driving_count': driving_count,
        'cycling_count': cycling_count,
    }


def get_popular_routes(limit: int = 6):

    return Route.objects.filter(is_active=True).order_by('-created_at')[:limit]


def get_user_favorite_ids(user) -> list:

    if user.is_authenticated:
        return list(
            Favorite.objects.filter(user=user).values_list(
                'route_id', flat=True
            )
        )
    return []


def get_filtered_routes(
    route_type: str = '', search_query: str = '', sort_by: str = 'newest'
):

    routes = Route.objects.filter(
        privacy='public', is_active=True
    ).prefetch_related('photos')

    if route_type:
        routes = routes.filter(route_type=route_type)

    if search_query:
        routes = routes.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(short_description__icontains=search_query)
            | Q(points__name__icontains=search_query)
            | Q(points__description__icontains=search_query)
        ).distinct()

    routes = routes.annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings'),
        favorites_count=Count('favorites'),
    )

    if sort_by == 'popular':
        routes = routes.order_by('-favorites_count', '-created_at')
    elif sort_by == 'rating':
        routes = routes.order_by('-avg_rating', '-rating_count', '-created_at')
    else:
        routes = routes.order_by('-created_at')

    return routes


def get_friendship_stats(user) -> dict:

    if not user.is_authenticated:
        return {}

    pending_requests = Friendship.objects.filter(
        to_user=user, status='pending'
    )

    return {
        'pending_friend_requests': pending_requests[:5],
        'pending_requests_count': pending_requests.count(),
    }


def get_author_routes_data(user) -> dict:
    base_qs = Route.objects.filter(author=user).prefetch_related('photos')
    base_qs = base_qs.annotate(
        rating=Avg('ratings__rating'), rating_count=Count('ratings')
    ).order_by('-created_at')

    active_routes = base_qs.filter(is_active=True)
    inactive_routes = base_qs.filter(is_active=False)

    total_count = base_qs.count()

    return {
        'active_routes': active_routes,
        'inactive_routes': inactive_routes,
        'total_count': total_count,
    }


def get_detailed_favorite_routes(user):

    if not user.is_authenticated:
        return Route.objects.none()

    return (
        Route.objects.filter(
            favorites__user=user,
            is_active=True,
        )
        .prefetch_related('photos')
        .annotate(rating=Avg('ratings__rating'), rating_count=Count('ratings'))
        .order_by('-favorites__created_at')
    )


def get_shared_routes_list(user):

    routes = Route.objects.filter(
        Q(shared_with=user) | Q(privacy='link'), is_active=True
    ).exclude(author=user)

    routes = routes.prefetch_related('photos').distinct()

    routes = routes.annotate(
        rating=Avg('ratings__rating'), rating_count=Count('ratings')
    ).order_by('-created_at')

    return routes


def get_shared_routes_counts(user) -> dict:

    base_qs = Route.objects.filter(is_active=True).exclude(author=user)

    shared_count = base_qs.filter(shared_with=user).count()
    link_count = base_qs.filter(privacy='link').count()

    return {
        'shared_count': shared_count,
        'link_count': link_count,
    }
