from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from routes.models import Route


def generate_route_qr(user, route_id, request):
    route = get_object_or_404(Route, id=route_id)

    if route.author != user and not user.is_staff:
        raise PermissionDenied(
            'You do not have permission to generate a QR code for this route.'
        )

    qr_url = route.generate_qr_code(request)

    route_absolute_url = request.build_absolute_uri(route.get_absolute_url())

    return qr_url, route_absolute_url
