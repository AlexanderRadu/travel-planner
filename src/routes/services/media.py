import base64
from contextlib import suppress
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.timezone import timezone

from routes.models import (
    PointPhoto,
    RoutePhoto,
)


def save_base64_photo(
    photo_data, parent_obj, photo_model, order=0, caption=''
):
    with suppress(Exception):
        if (
            not isinstance(photo_data, str)
            or not photo_data.startswith('data:')
            or ';base64,' not in photo_data
        ):
            return None

        header, data = photo_data.split(';base64,', 1)
        mime_type = header.replace('data:', '')
        extensions = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/bmp': '.bmp',
        }
        ext = extensions.get(mime_type, '.jpg')
        image_data = base64.b64decode(data)

        timestamp = int(timezone.now().timestamp())
        parent_type = parent_obj.__class__.__name__.lower()
        prefix = 'route' if photo_model == RoutePhoto else 'point'
        filename = (
            f'{prefix}_{parent_type}_{parent_obj.id}_{timestamp}_{order}{ext}'
        )

        if photo_model == RoutePhoto:
            photo = RoutePhoto.objects.create(
                route=parent_obj, order=order, caption=caption, is_main=False
            )
        elif photo_model == PointPhoto:
            photo = PointPhoto.objects.create(
                point=parent_obj, order=order, caption=caption
            )
        else:
            return None

        photo.image.save(filename, ContentFile(image_data), save=True)
        return photo
    return None


def copy_existing_photo(
    photo_url, parent_obj, photo_model, order=0, caption=''
):
    with suppress(Exception):
        media_path = (
            photo_url.replace('/media/', '', 1)
            if photo_url.startswith('/media/')
            else (
                photo_url.replace('/uploads/', '', 1)
                if photo_url.startswith('/uploads/')
                else None
            )
        )
        if not media_path:
            return None

        full_path = Path(settings.MEDIA_ROOT) / media_path
        if not full_path.exists():
            return None

        with open(full_path, 'rb') as f:
            file_data = f.read()

        import uuid

        timestamp = int(timezone.now().timestamp())
        random_str = str(uuid.uuid4())[:8]
        ext = full_path.suffix or '.jpg'
        parent_type = parent_obj.__class__.__name__.lower()
        prefix = 'point' if photo_model == PointPhoto else 'route'
        filename = (
            f'{prefix}_{parent_type}_{parent_obj.id}'
            f'_{timestamp}_{random_str}{ext}'
        )

        if photo_model == RoutePhoto:
            photo = RoutePhoto.objects.create(
                route=parent_obj, order=order, caption=caption, is_main=False
            )
        elif photo_model == PointPhoto:
            photo = PointPhoto.objects.create(
                point=parent_obj, order=order, caption=caption
            )
        else:
            return None

        photo.image.save(filename, ContentFile(file_data), save=True)
        return photo
    return None
