from routes.models import (
    PointComment,
    Route,
    RouteComment,
    RouteFavorite,
    RouteRating,
)


def toggle_route_favorite(user, route):
    favorite, created = RouteFavorite.objects.get_or_create(
        route=route, user=user
    )
    if not created:
        favorite.delete()
        return False
    return True


def set_route_rating(route: Route, user, rating_value) -> float:
    try:
        rating_value = float(rating_value)
    except (TypeError, ValueError):
        raise ValueError('Rating must be a number.') from None

    if not (1 <= rating_value <= 5):
        raise ValueError('Rating must be between 1 and 5.')

    RouteRating.objects.update_or_create(
        route=route, user=user, defaults={'rating': rating_value}
    )

    return route.get_average_rating()


def create_route_comment(user, route, text):
    if text:
        RouteComment.objects.create(route=route, user=user, text=text)
        return True
    return False


def create_point_comment(user, point, text):
    if text:
        PointComment.objects.create(point=point, text=text, user=user)
        return True
    return False
