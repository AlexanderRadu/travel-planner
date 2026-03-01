import json
import logging
from contextlib import suppress

from django.conf import settings
from django.core import cache
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from routes.models import (
    PointPhoto,
    Route,
    RoutePhoto,
    RoutePoint,
)
from routes.services import media

logger = logging.getLogger(__name__)


def create_route_from_data(user, data: dict):

    name = data.get('name')
    waypoints = data.get('waypoints')

    if not name:
        raise ValueError(_('Route name is required.'))
    if not waypoints:
        raise ValueError(_('Add at least one route point.'))

    with transaction.atomic():
        route = Route.objects.create(
            author=user,
            name=name,
            description=data.get('description', ''),
            short_description=data.get('short_description', ''),
            privacy=data.get('privacy', 'public'),
            route_type=data.get('route_type', 'walking'),
            duration_minutes=data.get('duration_minutes', 0),
            total_distance=data.get('total_distance', 0),
            has_audio_guide=data.get('has_audio_guide', False),
            is_elderly_friendly=data.get('is_elderly_friendly', False),
        )

        _process_photos(
            target_obj=route,
            photo_model=RoutePhoto,
            photos_data=data.get('route_photos', []),
        )

        for i, point_data in enumerate(waypoints):
            point = RoutePoint.objects.create(
                route=route,
                name=point_data.get('name', f'Point {i + 1}'),
                description=point_data.get('description', ''),
                address=point_data.get('address', ''),
                latitude=point_data.get('lat', 0),
                longitude=point_data.get('lng', 0),
                category=point_data.get('category', ''),
                order=i,
            )

            _process_photos(
                target_obj=point,
                photo_model=PointPhoto,
                photos_data=point_data.get('photos', []),
            )

    return route


def _process_photos(target_obj, photo_model, photos_data):
    for i, photo_data in enumerate(photos_data):
        if not photo_data:
            continue

        url = ''
        caption = ''

        if isinstance(photo_data, dict):
            url = photo_data.get('url', '')
            caption = photo_data.get('caption', '')
        elif isinstance(photo_data, str):
            url = photo_data

        if not url:
            continue

        if url.startswith('data:'):
            media.save_base64_photo(
                url, target_obj, photo_model, order=i, caption=caption
            )
        elif url.startswith(('/uploads/', '/media/')):
            media.copy_existing_photo(
                url, target_obj, photo_model, order=i, caption=caption
            )


def delete_route_completely(
    route, delete_all_files: bool = True, clear_cache: bool = True
):

    route_id = route.id
    if delete_all_files:
        for photo in route.photos.all():
            _delete_physical_file(photo.image)

        for point in route.points.all():
            for photo in point.photos.all():
                _delete_physical_file(photo.image)

        if hasattr(route, 'audio_guides'):
            for audio in route.audio_guides.all():
                _delete_physical_file(audio.audio_file)

    if clear_cache:
        _clear_route_cache(route_id)

    route.delete()


def _delete_physical_file(file_field):

    if file_field and file_field.name:
        file_field.storage.delete(file_field.name)


def _clear_route_cache(route_id):

    cache_keys = [
        f'route_{route_id}',
        f'route_{route_id}_points',
        f'route_{route_id}_photos',
        f'route_{route_id}_audio',
    ]
    for key in cache_keys:
        cache.delete(key)

    with suppress(AttributeError):
        cache.delete_pattern(f'*route_{route_id}*')


def save_route_point(
    route_id: int,
    point_id: int,
    data: dict,
    existing_photos_json: str,
    new_files: list,
):
    route = Route.objects.get(id=route_id)

    with transaction.atomic():
        if point_id:
            point = RoutePoint.objects.get(id=point_id, route=route)
        else:
            point = RoutePoint(route=route)

        point.name = data.get('name', '')[:255]
        point.address = data.get('address', '')[:255]
        point.lat = data.get('lat')
        point.lng = data.get('lng')
        point.description = data.get('description', '')
        point.category = data.get('category', '')[:100]
        point.hint_author = data.get('hint_author', '')[:255]

        tags_raw = data.get('tags', '[]')
        try:
            tags = json.loads(tags_raw)
            point.tags = [
                str(tag)[:50] for tag in tags if isinstance(tag, str)
            ]
        except json.JSONDecodeError:
            point.tags = []

        point.save()

        _sync_existing_photos(point, existing_photos_json)

        _save_new_photos(point, new_files)

    return point


def _sync_existing_photos(point, existing_photos_json: str):
    try:
        existing_data = json.loads(existing_photos_json)
        current_photos = {
            p.image.url: p for p in point.photos.all() if p.image
        }
        incoming_urls = set()

        media_url = getattr(settings, 'MEDIA_URL', '/media/')

        for idx, photo_data in enumerate(existing_data):
            if isinstance(photo_data, dict) and 'url' in photo_data:
                url = photo_data['url']

                if isinstance(url, str) and url.startswith(media_url):
                    incoming_urls.add(url)

                    if url not in current_photos:
                        new_photo = PointPhoto(point=point, order=idx)
                        new_photo.image.name = url.replace(media_url, '', 1)
                        new_photo.save()
                    else:
                        photo = current_photos[url]
                        if photo.order != idx:
                            photo.order = idx
                            photo.save()

        for url, photo in current_photos.items():
            if url not in incoming_urls:
                photo.delete()

    except json.JSONDecodeError as e:
        logger.error(f'Error syncing existing photos (JSON decode): {e}')
    except Exception as e:
        logger.error(f'Error syncing existing photos: {e}', exc_info=True)


def _save_new_photos(point, new_files: list):
    if not new_files:
        return

    aggr = point.photos.aggregate(max_order=models.Max('order'))
    last_order = aggr['max_order'] if aggr['max_order'] is not None else -1

    for file in new_files:
        last_order += 1
        photo = PointPhoto(point=point, order=last_order)
        photo.image.save(file.name, file, save=True)


def toggle_route_status(route) -> bool:
    route.is_active = not route.is_active
    route.last_status_update = timezone.now()
    route.save(update_fields=['is_active', 'last_status_update'])
    return route.is_active


def get_serialized_route_data(route: Route) -> dict:
    route_data = {
        'id': route.id,
        'name': route.name,
        'description': route.description,
        'short_description': route.short_description,
        'privacy': route.privacy,
        'route_type': route.route_type,
        'duration_minutes': route.duration_minutes,
        'total_distance': route.total_distance,
        'has_audio_guide': route.has_audio_guide,
        'is_elderly_friendly': route.is_elderly_friendly,
        'is_active': route.is_active,
        'duration_display': route.duration_display,
        'route_photos': [],
        'points': [],
    }

    for photo in route.photos.all().order_by('order'):
        route_data['route_photos'].append(
            {
                'id': photo.id,
                'url': photo.image.url if photo.image else '',
                'caption': photo.caption or '',
                'order': photo.order,
            }
        )

    points = route.points.prefetch_related('photos').all().order_by('order')
    for point in points:
        point_data = {
            'id': point.id,
            'name': point.name,
            'description': point.description or '',
            'address': point.address or '',
            'lat': float(point.latitude) if point.latitude else 0,
            'lng': float(point.longitude) if point.longitude else 0,
            'category': point.category or '',
            'photos': [],
        }
        for photo in point.photos.all().order_by('order'):
            point_data['photos'].append(
                {
                    'id': photo.id,
                    'url': photo.image.url if photo.image else '',
                    'caption': photo.caption or '',
                    'order': photo.order,
                }
            )
        route_data['points'].append(point_data)

    return route_data


@transaction.atomic
def update_route_details(route: Route, data: dict):
    fields_to_update = [
        'name',
        'description',
        'short_description',
        'privacy',
        'route_type',
        'duration_minutes',
        'total_distance',
        'has_audio_guide',
        'is_elderly_friendly',
        'is_active',
        'duration_display',
    ]
    for field in fields_to_update:
        if field in data:
            setattr(route, field, data[field])
    route.save()

    removed_photo_ids = data.get('removed_photo_ids', [])
    if removed_photo_ids:
        RoutePhoto.objects.filter(
            route=route, id__in=removed_photo_ids
        ).delete()

    points_data = data.get('points', [])
    incoming_point_ids = []

    for i, point_data in enumerate(points_data):
        point_id = point_data.get('id')

        defaults = {
            'name': point_data.get('name', f'Point {i + 1}'),
            'description': point_data.get('description', ''),
            'address': point_data.get('address', ''),
            'latitude': point_data.get('lat', 0),
            'longitude': point_data.get('lng', 0),
            'category': point_data.get('category', ''),
            'order': i,
        }

        if point_id:
            RoutePoint.objects.filter(id=point_id, route=route).update(
                **defaults
            )
            point = RoutePoint.objects.get(id=point_id, route=route)
            incoming_point_ids.append(point.id)
        else:
            point = RoutePoint.objects.create(route=route, **defaults)
            incoming_point_ids.append(point.id)

        _sync_point_photos(point, point_data.get('photos'))

    RoutePoint.objects.filter(route=route).exclude(
        id__in=incoming_point_ids
    ).delete()


def _sync_point_photos(point, point_photos_data):
    if not point_photos_data or not isinstance(point_photos_data, list):
        return

    existing_photos = {p.image.url: p for p in point.photos.all() if p.image}

    incoming_photo_urls = set()
    for photo_data in point_photos_data:
        url = (
            photo_data.get('url', '')
            if isinstance(photo_data, dict)
            else str(photo_data)
        )
        if url.startswith(('/media/', '/uploads/')):
            incoming_photo_urls.add(url)

    photos_to_delete = [
        p.id
        for url, p in existing_photos.items()
        if url not in incoming_photo_urls
    ]
    if photos_to_delete:
        PointPhoto.objects.filter(id__in=photos_to_delete).delete()

    for j, photo_data in enumerate(point_photos_data):
        if not photo_data:
            continue

        if isinstance(photo_data, dict):
            photo_url = photo_data.get('url', '')
            caption = photo_data.get('caption', '')
        else:
            photo_url = str(photo_data)
            caption = ''

        if photo_url.startswith('data:'):
            media.save_base64_photo(
                photo_url, point, PointPhoto, order=j, caption=caption
            )

        elif photo_url.startswith(('/media/', '/uploads/')):
            existing = point.photos.filter(image__url=photo_url).first()
            if not existing:
                media.copy_existing_photo(
                    photo_url, point, PointPhoto, order=j, caption=caption
                )
            else:
                existing.order = j
                if caption:
                    existing.caption = caption
                existing.save()


@transaction.atomic
def create_new_route(user, data: dict, files: dict) -> Route:
    if not data.get('name'):
        raise ValueError(_('Route name is required.'))

    waypoints_data = data.get('waypoints', [])
    if not waypoints_data or len(waypoints_data) < 2:
        raise ValueError(_('Add at least two route points.'))

    route = Route.objects.create(
        author=user,
        name=data.get('name'),
        description=data.get('description', ''),
        short_description=data.get('short_description', ''),
        privacy=data.get('privacy', 'public'),
        route_type=data.get('route_type', 'walking'),
        duration_minutes=data.get('duration_minutes', 0),
        total_distance=data.get('total_distance', 0),
        has_audio_guide=data.get('has_audio_guide', False),
        is_elderly_friendly=data.get('is_elderly_friendly', False),
        duration_display=data.get('duration_display', ''),
    )

    _process_route_photos(route, data.get('route_photos', []))

    for i, point_data in enumerate(waypoints_data):
        point = RoutePoint.objects.create(
            route=route,
            name=point_data.get('name', f'Point {i + 1}'),
            description=point_data.get('description', ''),
            address=point_data.get('address', ''),
            latitude=point_data.get('lat', 0),
            longitude=point_data.get('lng', 0),
            category=point_data.get('category', ''),
            order=i,
        )

        _process_waypoint_photos(
            point, point_data.get('photos', []), files, waypoint_index=i
        )

    return route


def _process_route_photos(route, route_photos: list):
    for i, photo_data in enumerate(route_photos):
        if not photo_data:
            continue
        if photo_data.startswith('data:'):
            media.save_base64_photo(photo_data, route, RoutePhoto, order=i)
        elif photo_data.startswith(('/uploads/', '/media/')):
            media.copy_existing_photo(photo_data, route, RoutePhoto, order=i)


def _process_waypoint_photos(
    point, point_photos: list, files: dict, waypoint_index: int
):
    main_photo_key = f'point_{waypoint_index}_main_photo'
    if main_photo_key in files:
        media.save_base64_photo(
            files[main_photo_key], point, PointPhoto, order=0
        )

    additional_counter = 0
    while True:
        additional_key = (
            f'point_{waypoint_index}_additional_{additional_counter}'
        )
        if additional_key not in files:
            break
        media.save_base64_photo(
            files[additional_key],
            point,
            PointPhoto,
            order=additional_counter + 1,
        )
        additional_counter += 1

    for j, photo_data in enumerate(point_photos):
        if not photo_data or not isinstance(photo_data, str):
            continue

        final_order = j + additional_counter

        if photo_data.startswith('data:'):
            media.save_base64_photo(
                photo_data, point, PointPhoto, order=final_order
            )
        elif photo_data.startswith(('/uploads/', '/media/')):
            media.copy_existing_photo(
                photo_data, point, PointPhoto, order=final_order
            )


@transaction.atomic
def update_route(route: Route, data: dict) -> Route:
    _update_basic_fields(route, data)
    _manage_route_media(route, data)
    _sync_waypoints(route, data)

    return route


def _update_basic_fields(route: Route, data: dict):
    route.name = data.get('name', route.name)
    route.description = data.get('description', route.description)
    route.short_description = data.get(
        'short_description', route.short_description
    )
    route.privacy = data.get('privacy', route.privacy)
    route.route_type = data.get('route_type', route.route_type)
    route.duration_minutes = data.get(
        'duration_minutes', route.duration_minutes
    )
    route.total_distance = data.get('total_distance', route.total_distance)
    route.has_audio_guide = data.get('has_audio_guide', route.has_audio_guide)
    route.is_elderly_friendly = data.get(
        'is_elderly_friendly', route.is_elderly_friendly
    )
    route.is_active = data.get('is_active', route.is_active)
    route.duration_display = data.get(
        'duration_display', route.duration_display
    )
    route.save()


def _manage_route_media(route: Route, data: dict):
    removed_photo_ids = data.get('removed_photo_ids', [])
    if removed_photo_ids:
        RoutePhoto.objects.filter(
            id__in=removed_photo_ids, route=route
        ).delete()

    main_photo_id = data.get('main_photo_id')
    photos_data = data.get('photos_data')
    if isinstance(photos_data, dict):
        main_photo_id = photos_data.get('main_photo_id', main_photo_id)

    if main_photo_id:
        try:
            main_photo_id = int(main_photo_id)
            main_photo = RoutePhoto.objects.filter(
                id=main_photo_id, route=route
            ).first()
            if main_photo:
                RoutePhoto.objects.filter(route=route).update(is_main=False)
                main_photo.is_main = True
                main_photo.order = 0
                main_photo.save()

                other_photos = (
                    RoutePhoto.objects.filter(route=route)
                    .exclude(id=main_photo_id)
                    .order_by('id')
                )
                for idx, photo in enumerate(other_photos, start=1):
                    photo.order = idx
                    photo.save()
        except (ValueError, TypeError):
            pass

    route_photos = data.get('route_photos', [])
    _process_route_photos(route, route_photos)


def _sync_waypoints(route: Route, data: dict):
    waypoints_data = data.get('waypoints', [])

    incoming_ids = []
    for pd in waypoints_data:
        pid = pd.get('id')
        if pid:
            try:
                incoming_ids.append(int(pid))
            except Exception:
                incoming_ids.append(pid)

    if incoming_ids:
        route.points.exclude(id__in=incoming_ids).delete()
    elif waypoints_data:
        route.points.all().delete()

    old_points = {p.id: p for p in route.points.all()}

    for i, point_data in enumerate(waypoints_data):
        point_name = point_data.get('name', f'Point {i + 1}')
        incoming_id = point_data.get('id')
        incoming_id_key = (
            int(incoming_id)
            if incoming_id and str(incoming_id).isdigit()
            else incoming_id
        )

        if incoming_id_key and incoming_id_key in old_points:
            point = old_points[incoming_id_key]
            point.name = point_name
            point.description = point_data.get('description', '')
            point.address = point_data.get('address', '')
            point.latitude = point_data.get('lat', point.latitude)
            point.longitude = point_data.get('lng', point.longitude)
            point.category = point_data.get('category', point.category)
            point.order = i
            point.save()
        else:
            point = RoutePoint.objects.create(
                route=route,
                name=point_name,
                description=point_data.get('description', ''),
                address=point_data.get('address', ''),
                latitude=point_data.get('lat', point_data.get('latitude', 0)),
                longitude=point_data.get(
                    'lng', point_data.get('longitude', 0)
                ),
                category=point_data.get('category', ''),
                order=i,
            )

        removed_point_photo_ids = data.get('removed_point_photo_ids', [])
        if (
            isinstance(removed_point_photo_ids, list)
            and removed_point_photo_ids
        ):
            PointPhoto.objects.filter(
                id__in=removed_point_photo_ids, point=point
            ).delete()

        point_photos = point_data.get('photos', [])
        if isinstance(point_photos, list):
            _process_waypoint_photos(point, point_photos, data, i)
