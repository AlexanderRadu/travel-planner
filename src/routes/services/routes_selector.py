from django.db.models import Q

from interactions.models import Favorite
from routes.models import Route


def get_active_routes(route_type):

    queryset = Route.objects.filter(is_active=True).prefetch_related('photos')

    if route_type:
        queryset = queryset.filter(route_type=route_type)

    return queryset


def get_user_favorite_route_ids(user):

    if user.is_authenticated:
        return list(
            Favorite.objects.filter(user=user).values_list(
                'route_id', flat=True
            )
        )

    return []


def search_active_routes(text_query, route_type):

    queryset = Route.objects.filter(is_active=True)

    if text_query:
        queryset = queryset.filter(
            Q(name__icontains=text_query)
            | Q(description__icontains=text_query)
            | Q(country__icontains=text_query)
        )

    if route_type:
        queryset = queryset.filter(route_type=route_type)

    return queryset
