import json

import gpxpy.gpx as gpx

from routes.services import external_api


def generate_route_gpx(route, absolute_uri: str) -> str:

    points = route.points.all().order_by('order')

    gpx_instance = gpx.GPX()
    gpx_instance.name = route.name
    gpx_instance.description = (
        route.description or route.short_description or ''
    )
    gpx_instance.author_name = (
        str(route.author.username) if route.author else 'Waylines'
    )
    gpx_instance.link = absolute_uri

    gpx_track = gpx.GPXTrack()
    gpx_track.name = route.name
    gpx_segment = gpx.GPXTrackSegment()

    geometry = external_api.fetch_route_geometry_from_api(
        points, route.route_type
    )

    if geometry:
        for coord in geometry:
            if len(coord) >= 3:
                track_point = gpx.GPXTrackPoint(
                    latitude=coord[1], longitude=coord[0], elevation=coord[2]
                )
            else:
                track_point = gpx.GPXTrackPoint(
                    latitude=coord[1], longitude=coord[0]
                )
            gpx_segment.points.append(track_point)
    else:
        for point in points:
            gpx_segment.points.append(
                gpx.GPXTrackPoint(
                    latitude=float(point.latitude),
                    longitude=float(point.longitude),
                )
            )

    gpx_track.segments.append(gpx_segment)
    gpx_instance.tracks.append(gpx_track)

    _add_waypoints_to_gpx(gpx_instance, points)

    return gpx_instance.to_xml()


def _add_waypoints_to_gpx(gpx_instance, points):
    for idx, point in enumerate(points):
        name = f'{idx + 1}. {point.name}' if point.name else f'Point {idx + 1}'
        waypoint = gpx.GPXWaypoint(
            latitude=float(point.latitude),
            longitude=float(point.longitude),
            name=name,
        )

        description_parts = []
        if point.description:
            description_parts.append(point.description)
        if point.address:
            description_parts.append(f'Address: {point.address}')
        if point.category:
            description_parts.append(f'Category: {point.category}')

        if description_parts:
            waypoint.description = '\n'.join(description_parts)[:500]

        gpx_instance.waypoints.append(waypoint)


def generate_route_kml(route) -> str:
    points = route.points.all().order_by('order')

    geometry = external_api.fetch_route_geometry_from_api(
        points, route.route_type, elevation=False
    )

    if geometry:
        route_coordinates = [f'{coord[0]},{coord[1]},0' for coord in geometry]
    else:
        route_coordinates = [
            f'{point.longitude},{point.latitude},0' for point in points
        ]

    coordinates_xml = '\n'.join(
        f'          {coord}' for coord in route_coordinates
    )

    placemarks_xml = _build_kml_placemarks(points)

    route_desc = route.description or route.short_description or ''

    kml_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{route.name}</name>
    <description><![CDATA[{route_desc}]]></description>

    <Style id="routeStyle">
      <LineStyle>
        <color>ff0000ff</color>
        <width>4</width>
      </LineStyle>
    </Style>

    <Placemark>
      <name>Route</name>
      <styleUrl>#routeStyle</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>
{coordinates_xml}
        </coordinates>
      </LineString>
    </Placemark>
{placemarks_xml}
  </Document>
</kml>"""

    return kml_template


def _build_kml_placemarks(points) -> str:
    placemarks = []
    for idx, point in enumerate(points):
        description_parts = []
        if point.description:
            description_parts.append(
                f'<b>Description:</b> {point.description}'
            )
        if point.address:
            description_parts.append(f'<b>Address:</b> {point.address}')
        if point.category:
            description_parts.append(f'<b>Category:</b> {point.category}')

        description = (
            '<br/>'.join(description_parts) if description_parts else ''
        )
        name = point.name if point.name else f'Point {idx + 1}'

        placemark = f"""
    <Placemark>
      <name>{idx + 1}. {name}</name>
      <description><![CDATA[{description}]]></description>
      <Point>
        <coordinates>{point.longitude},{point.latitude},0</coordinates>
      </Point>
    </Placemark>"""
        placemarks.append(placemark)

    return ''.join(placemarks)


def generate_route_geojson(route) -> str:
    points = route.points.all().order_by('order')

    geometry = external_api.fetch_route_geometry_from_api(
        points, route.route_type, elevation=True
    )

    route_coordinates = []
    is_api_used = False

    if geometry:
        is_api_used = True
        for coord in geometry:
            alt = float(coord[2]) if len(coord) > 2 else 0.0
            route_coordinates.append([float(coord[0]), float(coord[1]), alt])
    else:
        route_coordinates = [
            [float(point.longitude), float(point.latitude), 0.0]
            for point in points
        ]

    distance = (
        float(route.total_distance)
        if getattr(route, 'total_distance', None)
        else 0.0
    )
    duration = getattr(route, 'duration_display', None) or getattr(
        route, 'duration_minutes', 0
    )

    geojson_data = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {
                    'name': route.name,
                    'description': route.description
                    or route.short_description
                    or '',
                    'type': 'route',
                    'route_type': route.route_type,
                    'distance': distance,
                    'duration': duration,
                    'source': 'OpenRouteService'
                    if is_api_used
                    else 'Waylines',
                },
                'geometry': {
                    'type': 'LineString',
                    'coordinates': route_coordinates,
                },
            }
        ],
    }

    for idx, point in enumerate(points):
        geojson_data['features'].append(
            {
                'type': 'Feature',
                'properties': {
                    'name': point.name or '',
                    'description': point.description or '',
                    'address': point.address or '',
                    'category': point.category or '',
                    'type': 'waypoint',
                    'order': idx + 1,
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [
                        float(point.longitude),
                        float(point.latitude),
                        0.0,
                    ],
                },
            }
        )

    return json.dumps(geojson_data, ensure_ascii=False, indent=2)
