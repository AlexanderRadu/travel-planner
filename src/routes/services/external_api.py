from contextlib import suppress

import requests
from django.conf import settings

API_URL = 'https://api.openrouteservice.org/v2/directions/{profile}/geojson'


def fetch_route_geometry_from_api(points, route_type, elevation=True):
    api_key = getattr(settings, 'OPENROUTESERVICE_API_KEY', None)

    if not api_key or len(points) < 2:
        return None

    coordinates = [[float(p.longitude), float(p.latitude)] for p in points]
    profile_map = {
        'walking': 'foot-walking',
        'cycling': 'cycling-regular',
        'driving': 'driving-car',
    }
    profile = profile_map.get(route_type, 'foot-walking')

    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json',
    }
    body = {
        'coordinates': coordinates,
        'elevation': elevation,
        'instructions': False,
        'format': 'geojson',
    }

    with suppress(Exception):
        response = requests.post(
            API_URL.format(profile=profile),
            headers=headers,
            json=body,
            timeout=30,
        )

        if response.status_code == 200:
            route_data = response.json()
            features = route_data.get('features')
            if features:
                return features[0]['geometry']['coordinates']

    return None
