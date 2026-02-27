import base64
import json
import os
from pathlib import Path

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from gpxpy import gpx

from interactions.models import Comment, Favorite, Rating
from routes.models import (
    PointComment,
    PointPhoto,
    Route,
    RouteComment,
    RouteFavorite,
    RoutePhoto,
    RoutePoint,
    RouteRating,
    User,
)
from users.models import Friendship


def home(request):
    total_routes = Route.objects.filter(is_active=True).count()
    total_users = User.objects.count()
    total_countries = (
        Route.objects.filter(is_active=True)
        .values('country')
        .distinct()
        .count()
    )
    walking_count = Route.objects.filter(
        route_type='walking', is_active=True
    ).count()
    driving_count = Route.objects.filter(
        route_type='driving', is_active=True
    ).count()
    cycling_count = Route.objects.filter(
        route_type='cycling', is_active=True
    ).count()
    popular_routes = Route.objects.filter(is_active=True).order_by(
        '-created_at'
    )[:6]

    user_favorites_ids = []
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)

    context = {
        'popular_routes': popular_routes,
        'walking_count': walking_count,
        'driving_count': driving_count,
        'cycling_count': cycling_count,
        'total_routes': total_routes,
        'total_users': total_users,
        'total_countries': total_countries,
        'user_favorites_ids': list(user_favorites_ids),
    }
    return render(request, 'home.html', context)


def all_routes(request):
    route_type = request.GET.get('type', '')
    search_query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'newest')

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

    paginator = Paginator(routes, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    user_favorites_ids = []
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)

    context = {
        'page_obj': page_obj,
        'route_types': Route.ROUTE_TYPE_CHOICES,
        'current_sort': sort_by,
        'search_query': search_query,
        'selected_type': route_type,
        'user_favorites_ids': list(user_favorites_ids),
        'get_params': {'q': search_query, 'type': route_type, 'sort': sort_by},
    }

    if request.user.is_authenticated:
        context['pending_friend_requests'] = Friendship.objects.filter(
            to_user=request.user, status='pending'
        )[:5]
        context['pending_requests_count'] = Friendship.objects.filter(
            to_user=request.user, status='pending'
        ).count()

    return render(request, 'routes/all_routes.html', context)


@login_required
def my_routes(request):
    user_routes = Route.objects.filter(author=request.user).prefetch_related(
        'photos'
    )
    user_routes = user_routes.annotate(
        rating=Avg('ratings__rating'), rating_count=Count('ratings')
    ).order_by('-created_at')

    active_routes = user_routes.filter(is_active=True)
    inactive_routes = user_routes.filter(is_active=False)

    user_favorites_ids = []
    favorite_routes_list = []
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)
        favorites = (
            Favorite.objects.filter(user=request.user)
            .select_related('route')
            .order_by('-created_at')
        )
        for fav in favorites:
            if fav.route.is_active:
                favorite_routes_list.append(fav.route)

        favorite_routes = (
            Route.objects.filter(id__in=[r.id for r in favorite_routes_list])
            .prefetch_related('photos')
            .annotate(
                rating=Avg('ratings__rating'), rating_count=Count('ratings')
            )
        )
    else:
        favorite_routes = []

    total_count = active_routes.count() + inactive_routes.count()
    favorites_count = len(favorite_routes_list)

    context = {
        'active_routes': active_routes,
        'inactive_routes': inactive_routes,
        'favorite_routes': favorite_routes,
        'favorites_count': favorites_count,
        'total_count': total_count,
        'user_favorites_ids': list(user_favorites_ids),
    }

    if request.user.is_authenticated:
        context['pending_friend_requests'] = Friendship.objects.filter(
            to_user=request.user, status='pending'
        )[:5]
        context['pending_requests_count'] = Friendship.objects.filter(
            to_user=request.user, status='pending'
        ).count()

    return render(request, 'routes/my_routes.html', context)


@login_required
def shared_routes(request):
    routes = (
        Route.objects.filter(
            Q(shared_with=request.user) | Q(privacy='link'), is_active=True
        )
        .exclude(author=request.user)
        .prefetch_related('photos')
        .distinct()
    )

    user_favorites_ids = []
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)

    routes = routes.annotate(
        rating=Avg('ratings__rating'), rating_count=Count('ratings')
    ).order_by('-created_at')

    shared_count = (
        Route.objects.filter(shared_with=request.user, is_active=True)
        .exclude(author=request.user)
        .count()
    )
    link_count = (
        Route.objects.filter(privacy='link', is_active=True)
        .exclude(author=request.user)
        .count()
    )

    context = {
        'routes': routes,
        'shared_count': shared_count,
        'link_count': link_count,
        'user_favorites_ids': list(user_favorites_ids),
    }

    if request.user.is_authenticated:
        context['pending_friend_requests'] = Friendship.objects.filter(
            to_user=request.user, status='pending'
        )[:5]
        context['pending_requests_count'] = Friendship.objects.filter(
            to_user=request.user, status='pending'
        ).count()

    return render(request, 'routes/shared_routes.html', context)


def route_detail(request, route_id):
    route = get_object_or_404(
        Route.objects.select_related('author').prefetch_related(
            'photos', 'shared_with'
        ),
        id=route_id,
    )

    if not can_view_route(request.user, route):
        messages.error(request, _('You do not have access to this route.'))
        return redirect('home')

    points = (
        RoutePoint.objects.filter(route=route)
        .prefetch_related('photos')
        .order_by('order')
    )
    route_photos = route.photos.all().order_by('order')
    comments = (
        Comment.objects.filter(route=route)
        .select_related('user')
        .order_by('-created_at')[:10]
    )
    ratings = Rating.objects.filter(route=route)

    full_audio_guide = None
    points_with_audio = []
    try:
        from ai_audio.models import RouteAudioGuide

        full_audio_guide = RouteAudioGuide.objects.filter(route=route).first()
        for point in points:
            if point.audio_guide:
                points_with_audio.append(point.id)
    except ImportError:
        pass

    route_chat_messages = []
    if hasattr(route, 'chat'):
        route_chat_messages = (
            route.chat.messages.all()
            .select_related('user')
            .order_by('-timestamp')[:20]
        )

    user_favorites_ids = []
    is_favorite = False
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)
        is_favorite = route.id in user_favorites_ids

    user_rating = None
    if request.user.is_authenticated:
        try:
            user_rating = Rating.objects.get(
                user=request.user, route=route
            ).score
        except Rating.DoesNotExist:
            pass

    similar_routes = Route.objects.filter(
        route_type=route.route_type, privacy='public', is_active=True
    ).exclude(id=route.id)[:5]

    context = {
        'route': route,
        'points': points,
        'route_photos': route_photos,
        'comments': comments,
        'ratings': ratings,
        'route_chat_messages': route_chat_messages,
        'user_favorites_ids': list(user_favorites_ids),
        'is_favorite': is_favorite,
        'user_rating': user_rating,
        'similar_routes': similar_routes,
        'full_audio_guide': full_audio_guide,
        'points_with_audio': points_with_audio,
    }

    if request.user.is_authenticated:
        pending_friend_requests = Friendship.objects.filter(
            to_user=request.user, status='pending'
        )
        context['pending_friend_requests'] = pending_friend_requests[:5]
        context['pending_requests_count'] = pending_friend_requests.count()

    return render(request, 'routes/route_detail.html', context)


@login_required
@csrf_exempt
def send_to_friend(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    if route.author != request.user and not request.user.is_staff:
        return JsonResponse(
            {
                'success': False,
                'error': _('You do not have permission to send this route.'),
            }
        )

    try:
        data = json.loads(request.body)
        friend_id = data.get('friend_id')
        if not friend_id:
            return JsonResponse(
                {'success': False, 'error': _('Friend not selected.')}
            )

        try:
            friend = User.objects.get(id=friend_id)
            friendship = Friendship.objects.filter(
                (
                    Q(from_user=request.user, to_user=friend)
                    | Q(from_user=friend, to_user=request.user)
                ),
                status='accepted',
            ).first()
            if not friendship:
                return JsonResponse(
                    {
                        'success': False,
                        'error': _('The user is not your friend.'),
                    }
                )

            route.shared_with.add(friend)
            route.save()

            try:
                from notifications.models import Notification

                Notification.objects.create(
                    user=friend,
                    title=_('A route has been shared with you'),
                    message=_('{} has shared the route "{}" with you.').format(
                        request.user.username, route.name
                    ),
                    notification_type='route_shared',
                    related_object_id=route.id,
                    related_object_type='route',
                )
            except ImportError:
                pass

            friend_name = friend.first_name or friend.username
            return JsonResponse(
                {
                    'success': True,
                    'message': _(
                        'Route "{}" has been sent to friend {}'
                    ).format(route.name, friend_name),
                }
            )
        except User.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': _('Friend not found.')}
            )
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': _('Invalid data format.')}
        )
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': f'Error sending: {e!s}'}
        )


@login_required
def create_route(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if not data.get('name'):
                return JsonResponse(
                    {'success': False, 'error': _('Route name is required.')}
                )
            if not data.get('waypoints'):
                return JsonResponse(
                    {
                        'success': False,
                        'error': _('Add at least one route point.'),
                    }
                )

            route = Route.objects.create(
                author=request.user,
                name=data.get('name'),
                description=data.get('description', ''),
                short_description=data.get('short_description', ''),
                privacy=data.get('privacy', 'public'),
                route_type=data.get('route_type', 'walking'),
                duration_minutes=data.get('duration_minutes', 0),
                total_distance=data.get('total_distance', 0),
                has_audio_guide=data.get('has_audio_guide', False),
                is_elderly_friendly=data.get('is_elderly_friendly', False),
            )

            route_photos = data.get('route_photos', [])
            for i, photo_data in enumerate(route_photos):
                if not photo_data:
                    continue
                if isinstance(photo_data, dict):
                    url = photo_data.get('url', '')
                    caption = photo_data.get('caption', '')
                    if url.startswith('data:'):
                        save_base64_photo(
                            url, route, RoutePhoto, order=i, caption=caption
                        )
                    elif url.startswith(('/uploads/', '/media/')):
                        copy_existing_photo(
                            url, route, RoutePhoto, order=i, caption=caption
                        )
                elif isinstance(photo_data, str):
                    if photo_data.startswith('data:'):
                        save_base64_photo(
                            photo_data, route, RoutePhoto, order=i
                        )
                    elif photo_data.startswith(('/uploads/', '/media/')):
                        copy_existing_photo(
                            photo_data, route, RoutePhoto, order=i
                        )

            points_data = data.get('waypoints', [])
            for i, point_data in enumerate(points_data):
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

                point_photos = point_data.get('photos', [])
                for j, photo_data in enumerate(point_photos):
                    if not photo_data:
                        continue
                    if isinstance(photo_data, dict):
                        url = photo_data.get('url', '')
                        caption = photo_data.get('caption', '')
                        if url.startswith('data:'):
                            save_base64_photo(
                                url,
                                point,
                                PointPhoto,
                                order=j,
                                caption=caption,
                            )
                        elif url.startswith(('/uploads/', '/media/')):
                            copy_existing_photo(
                                url,
                                point,
                                PointPhoto,
                                order=j,
                                caption=caption,
                            )
                    elif isinstance(photo_data, str):
                        if photo_data.startswith('data:'):
                            save_base64_photo(
                                photo_data, point, PointPhoto, order=j
                            )
                        elif photo_data.startswith(('/uploads/', '/media/')):
                            copy_existing_photo(
                                photo_data, point, PointPhoto, order=j
                            )

            return JsonResponse({'success': True, 'route_id': route.id})
        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': _('Invalid JSON format.')}
            )
        except Exception as e:
            return JsonResponse(
                {'success': False, 'error': f'Server error: {e!s}'}
            )

    context = {
        'pending_friend_requests': Friendship.objects.filter(
            to_user=request.user, status='pending'
        )[:5],
        'pending_requests_count': Friendship.objects.filter(
            to_user=request.user, status='pending'
        ).count(),
    }
    return render(request, 'routes/route_editor.html', context)


def edit_route(request, route_id):
    route = get_object_or_404(Route, id=route_id, author=request.user)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
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
            route.total_distance = data.get(
                'total_distance', route.total_distance
            )
            route.has_audio_guide = data.get(
                'has_audio_guide', route.has_audio_guide
            )
            route.is_elderly_friendly = data.get(
                'is_elderly_friendly', route.is_elderly_friendly
            )
            route.is_active = data.get('is_active', route.is_active)
            route.duration_display = data.get(
                'duration_display', route.duration_display
            )
            route.save()

            removed_photo_ids = data.get('removed_photo_ids', [])
            for photo_id in removed_photo_ids:
                try:
                    photo = RoutePhoto.objects.get(id=photo_id, route=route)
                    photo.delete()
                except RoutePhoto.DoesNotExist:
                    pass

            points_data = data.get('points', [])
            incoming_point_ids = []
            for i, point_data in enumerate(points_data):
                point_id = point_data.get('id')
                if point_id:
                    try:
                        point = RoutePoint.objects.get(
                            id=point_id, route=route
                        )
                        point.name = point_data.get('name', f'Point {i + 1}')
                        point.description = point_data.get('description', '')
                        point.address = point_data.get('address', '')
                        point.latitude = point_data.get('lat', point.latitude)
                        point.longitude = point_data.get(
                            'lng', point.longitude
                        )
                        point.category = point_data.get('category', '')
                        point.order = i
                        point.save()
                        incoming_point_ids.append(point_id)
                    except RoutePoint.DoesNotExist:
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
                        incoming_point_ids.append(point.id)
                else:
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
                    incoming_point_ids.append(point.id)

            RoutePoint.objects.filter(route=route).exclude(
                id__in=incoming_point_ids
            ).delete()

            for point_data in points_data:
                point_id = point_data.get('id')
                if not point_id:
                    continue
                try:
                    point = RoutePoint.objects.get(id=point_id, route=route)
                except RoutePoint.DoesNotExist:
                    continue

                point_photos_data = point_data.get('photos')
                if point_photos_data is not None and isinstance(
                    point_photos_data, list
                ):
                    existing_photos = {
                        p.image.url: p for p in point.photos.all() if p.image
                    }
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
                        PointPhoto.objects.filter(
                            id__in=photos_to_delete
                        ).delete()

                    for j, photo_data in enumerate(point_photos_data):
                        if not photo_data:
                            continue
                        if isinstance(photo_data, dict):
                            photo_url = photo_data.get('url', '')
                            caption = photo_data.get('caption', '')
                        else:
                            photo_url = photo_data
                            caption = ''

                        if photo_url.startswith('data:'):
                            save_base64_photo(
                                photo_url,
                                point,
                                PointPhoto,
                                order=j,
                                caption=caption,
                            )
                        elif photo_url.startswith(('/media/', '/uploads/')):
                            existing = point.photos.filter(
                                image__url=photo_url
                            ).first()
                            if not existing:
                                copy_existing_photo(
                                    photo_url,
                                    point,
                                    PointPhoto,
                                    order=j,
                                    caption=caption,
                                )
                            else:
                                existing.order = j
                                if caption:
                                    existing.caption = caption
                                existing.save()
                else:
                    pass

            return JsonResponse({'success': True, 'route_id': route.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

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

    for point in (
        route.points.prefetch_related('photos').all().order_by('order')
    ):
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

    context = {
        'route': route,
        'route_data_json': json.dumps(route_data),
        'pending_friend_requests': Friendship.objects.filter(
            to_user=request.user, status='pending'
        )[:5],
        'pending_requests_count': Friendship.objects.filter(
            to_user=request.user, status='pending'
        ).count(),
    }
    return render(request, 'routes/route_editor.html', context)


def save_base64_photo(
    photo_data, parent_obj, photo_model, order=0, caption=''
):
    try:
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
    except Exception:
        return None


def copy_existing_photo(
    photo_url, parent_obj, photo_model, order=0, caption=''
):
    try:
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
    except Exception:
        return None


@require_POST
def delete_route(request, route_id):
    try:
        route = get_object_or_404(Route, id=route_id, author=request.user)
        data = json.loads(request.body)
        delete_all_data = data.get('delete_all_data', True)
        clear_cache = data.get('clear_cache', True)

        if delete_all_data:
            for photo in route.photos.all():
                if photo.image and photo.image.name:
                    photo_path = os.path.join(
                        settings.MEDIA_ROOT, photo.image.name
                    )
                    if os.path.exists(photo_path):
                        os.remove(photo_path)

            for point in route.points.all():
                for photo in point.photos.all():
                    if photo.image and photo.image.name:
                        photo_path = os.path.join(
                            settings.MEDIA_ROOT, photo.image.name
                        )
                        if os.path.exists(photo_path):
                            os.remove(photo_path)

            if hasattr(route, 'audio_guides'):
                for audio in route.audio_guides.all():
                    if (
                        delete_all_data
                        and audio.audio_file
                        and audio.audio_file.name
                    ):
                        audio_path = os.path.join(
                            settings.MEDIA_ROOT, audio.audio_file.name
                        )
                        if os.path.exists(audio_path):
                            os.remove(audio_path)

        if clear_cache:
            from django.core.cache import cache

            cache_keys = [
                f'route_{route_id}',
                f'route_{route_id}_points',
                f'route_{route_id}_photos',
                f'route_{route_id}_audio',
            ]
            for key in cache_keys:
                cache.delete(key)
            try:
                cache.delete_pattern(f'*route_{route_id}*')
            except AttributeError:
                pass

        route.delete()
        return JsonResponse(
            {'success': True, 'message': _('Route deleted successfully.')}
        )
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def toggle_route_active(request, route_id):
    route = get_object_or_404(Route, id=route_id, author=request.user)
    route.is_active = not route.is_active
    route.last_status_update = timezone.now()
    route.save()
    messages.success(
        request,
        _('Route has been {}.').format(
            _('activated') if route.is_active else _('deactivated')
        ),
    )
    return redirect('route_detail', route_id=route_id)


@login_required
@csrf_exempt
def rate_route(request, route_id):
    if request.method == 'POST':
        route = get_object_or_404(Route, id=route_id)
        data = json.loads(request.body)
        rating_value = data.get('rating')
        if not (1 <= rating_value <= 5):
            return JsonResponse(
                {
                    'success': False,
                    'error': _('Rating must be between 1 and 5.'),
                }
            )

        rating, created = RouteRating.objects.get_or_create(
            route=route, user=request.user, defaults={'rating': rating_value}
        )
        if not created:
            rating.rating = rating_value
            rating.save()

        return JsonResponse(
            {'success': True, 'average_rating': route.get_average_rating()}
        )
    return JsonResponse({'success': False, 'error': _('Only POST allowed.')})


@login_required
@csrf_exempt
def toggle_favorite(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    if request.method == 'POST':
        favorite, created = RouteFavorite.objects.get_or_create(
            route=route, user=request.user
        )
        if not created:
            favorite.delete()
            return JsonResponse({'success': True, 'is_favorite': False})
        return JsonResponse({'success': True, 'is_favorite': True})
    return JsonResponse({'success': False, 'error': _('Only POST allowed.')})


@login_required
def add_route_comment(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    if request.method == 'POST':
        text = request.POST.get('text')
        if text:
            RouteComment.objects.create(
                route=route, user=request.user, text=text
            )
            messages.success(request, _('Comment added.'))
    return redirect('route_detail', route_id=route_id)


@login_required
def add_point_comment(request, point_id):
    point = get_object_or_404(RoutePoint, id=point_id)
    if request.method == 'POST':
        text = request.POST.get('text')
        if text:
            PointComment.objects.create(
                point=point, user=request.user, text=text
            )
            messages.success(request, _('Comment added.'))
    return redirect('route_detail', route_id=point.route.id)


def map_view(request):
    routes = (
        Route.objects.filter(privacy='public', is_active=True)
        .prefetch_related('points', 'photos')
        .annotate(avg_rating=Avg('ratings__rating'))
    )
    routes_data = []
    for route in routes:
        route_data = {
            'id': route.id,
            'title': route.name,
            'short_description': route.short_description,
            'description': route.description,
            'distance': route.total_distance,
            'rating': route.avg_rating or 0,
            'has_audio': route.has_audio_guide,
            'difficulty': route.route_type,
            'photos': [
                {'url': photo.image.url, 'caption': photo.caption}
                for photo in route.photos.all()[:3]
            ],
            'points': [
                {
                    'lat': p.latitude,
                    'lng': p.longitude,
                    'name': p.name,
                    'address': p.address,
                    'description': p.description,
                    'order': p.order,
                }
                for p in route.points.all()
            ],
        }
        routes_data.append(route_data)

    routes_json = json.dumps(routes_data, ensure_ascii=False)
    return render(
        request,
        'map/map_view.html',
        {'routes_json': routes_json, 'routes': routes},
    )


def can_view_route(user, route):
    if route.privacy == 'public':
        return True
    if not user.is_authenticated:
        return False
    if route.privacy == 'private' and route.author == user:
        return True
    if route.privacy == 'personal' and (
        route.author == user or user in route.shared_with.all()
    ):
        return True
    if route.privacy == 'link':
        return True
    return False


@login_required
@require_http_methods(['POST'])
def share_route(request, route_id):
    try:
        route = Route.objects.get(id=route_id, author=request.user)
    except Route.DoesNotExist:
        return JsonResponse(
            {
                'success': False,
                'error': _('Route not found or you are not the author.'),
            },
            status=403,
        )

    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {'success': False, 'error': _('Invalid data format.')}, status=400
        )

    if not email:
        return JsonResponse(
            {'success': False, 'error': _('Email not provided.')}, status=400
        )

    try:
        target_user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse(
            {
                'success': False,
                'error': _('No user registered with this email.'),
            },
            status=404,
        )

    if target_user == request.user:
        return JsonResponse(
            {
                'success': False,
                'error': _('You cannot share access with yourself.'),
            },
            status=400,
        )

    route.privacy = 'personal'
    route.shared_with.add(target_user)
    route.save()
    return JsonResponse(
        {
            'success': True,
            'message': _(
                'Access to route “{}” has been granted to user {}'
            ).format(route.name, email),
        }
    )


def get_user_rating(user, route):
    if not user.is_authenticated:
        return None
    try:
        rating = RouteRating.objects.get(user=user, route=route)
        return rating.rating
    except RouteRating.DoesNotExist:
        return None


def walking_routes(request):
    routes = Route.objects.filter(
        route_type='walking', is_active=True
    ).prefetch_related('photos')
    context = {
        'routes': routes,
        'page_title': _('Walking Routes'),
        'route_type': 'walking',
        'total_count': routes.count(),
    }
    return render(request, 'routes/filtered_routes.html', context)


def driving_routes(request):
    routes = Route.objects.filter(
        route_type='driving', is_active=True
    ).prefetch_related('photos')
    user_favorites_ids = []
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)
    context = {
        'routes': routes,
        'page_title': _('Driving Routes'),
        'route_type': 'driving',
        'total_count': routes.count(),
        'user_favorites_ids': list(user_favorites_ids),
    }
    return render(request, 'routes/filtered_routes.html', context)


def cycling_routes(request):
    routes = Route.objects.filter(
        route_type='cycling', is_active=True
    ).prefetch_related('photos')
    user_favorites_ids = []
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)
    context = {
        'routes': routes,
        'page_title': _('Cycling Routes'),
        'route_type': 'cycling',
        'total_count': routes.count(),
        'user_favorites_ids': list(user_favorites_ids),
    }
    return render(request, 'routes/filtered_routes.html', context)


def adventure_routes(request):
    routes = Route.objects.filter(is_active=True).prefetch_related('photos')
    user_favorites_ids = []
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)
    context = {
        'routes': routes,
        'page_title': _('Adventure Routes'),
        'total_count': routes.count(),
        'user_favorites_ids': list(user_favorites_ids),
    }
    return render(request, 'routes/filtered_routes.html', context)


def search_routes(request):
    query = request.GET.get('q', '')
    route_type = request.GET.get('type', '')
    routes = Route.objects.filter(is_active=True)
    if query:
        routes = routes.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(country__icontains=query)
        )
    if route_type:
        routes = routes.filter(route_type=route_type)

    user_favorites_ids = []
    if request.user.is_authenticated:
        user_favorites_ids = Favorite.objects.filter(
            user=request.user
        ).values_list('route_id', flat=True)

    context = {
        'routes': routes,
        'query': query,
        'route_type': route_type,
        'total_count': routes.count(),
        'user_favorites_ids': list(user_favorites_ids),
    }
    return render(request, 'routes/search_results.html', context)


class RouteCreateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            content_type = request.META.get('CONTENT_TYPE', '')
            if 'application/json' in content_type:
                data = json.loads(request.body)
                point_photo_files = {}
            else:
                route_data_str = request.POST.get('route_data', '{}')
                data = json.loads(route_data_str)
                point_photo_files = {k: v for k, v in request.FILES.items()}

            if not data.get('name'):
                return JsonResponse(
                    {'success': False, 'error': _('Route name is required.')}
                )
            if not data.get('waypoints') or len(data.get('waypoints', [])) < 2:
                return JsonResponse(
                    {
                        'success': False,
                        'error': _('Add at least two route points.'),
                    }
                )

            route = Route.objects.create(
                author=request.user,
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

            route_photos = data.get('route_photos', [])
            for i, photo_data in enumerate(route_photos):
                if not photo_data:
                    continue
                if photo_data.startswith('data:'):
                    save_base64_photo(photo_data, route, RoutePhoto, order=i)
                elif photo_data.startswith(('/uploads/', '/media/')):
                    copy_existing_photo(photo_data, route, RoutePhoto, order=i)

            waypoints_data = data.get('waypoints', [])
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

                main_photo_key = f'point_{i}_main_photo'
                if main_photo_key in point_photo_files:
                    save_base64_photo(
                        point_photo_files[main_photo_key],
                        point,
                        PointPhoto,
                        order=0,
                    )

                additional_counter = 0
                while True:
                    additional_key = (
                        f'point_{i}_additional_{additional_counter}'
                    )
                    if additional_key not in point_photo_files:
                        break
                    save_base64_photo(
                        point_photo_files[additional_key],
                        point,
                        PointPhoto,
                        order=additional_counter + 1,
                    )
                    additional_counter += 1

                point_photos = point_data.get('photos', [])
                for j, photo_data in enumerate(point_photos):
                    if not photo_data:
                        continue
                    if isinstance(photo_data, str) and photo_data.startswith(
                        'data:'
                    ):
                        save_base64_photo(
                            photo_data,
                            point,
                            PointPhoto,
                            order=j + additional_counter,
                        )
                    elif isinstance(photo_data, str) and photo_data.startswith(
                        ('/uploads/', '/media/')
                    ):
                        copy_existing_photo(
                            photo_data,
                            point,
                            PointPhoto,
                            order=j + additional_counter,
                        )

            return JsonResponse(
                {'success': True, 'route_id': route.id, 'id': route.id}
            )
        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': _('Invalid JSON format.')}
            )
        except Exception as e:
            return JsonResponse(
                {'success': False, 'error': f'Server error: {e!s}'}
            )


class RouteUpdateView(LoginRequiredMixin, View):
    def put(self, request, pk):
        try:
            route = get_object_or_404(Route, id=pk, author=request.user)
            content_type = request.content_type or ''
            if 'application/json' in content_type:
                data = json.loads(request.body)
            else:
                data = request.POST.dict()
                for key in request.FILES:
                    data[key] = request.FILES[key]
                if 'photos_data' in data:
                    try:
                        data['photos_data'] = json.loads(data['photos_data'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                if 'removed_photo_ids' in data:
                    try:
                        data['removed_photo_ids'] = json.loads(
                            data['removed_photo_ids']
                        )
                    except (json.JSONDecodeError, TypeError):
                        pass
                if 'route_data' in data:
                    try:
                        data['route_data'] = json.loads(data['route_data'])
                    except (json.JSONDecodeError, TypeError):
                        pass

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
            route.total_distance = data.get(
                'total_distance', route.total_distance
            )
            route.has_audio_guide = data.get(
                'has_audio_guide', route.has_audio_guide
            )
            route.is_elderly_friendly = data.get(
                'is_elderly_friendly', route.is_elderly_friendly
            )
            route.is_active = data.get('is_active', route.is_active)
            route.duration_display = data.get(
                'duration_display', route.duration_display
            )
            route.save()

            removed_photo_ids = data.get('removed_photo_ids', [])
            for photo_id in removed_photo_ids:
                try:
                    photo = RoutePhoto.objects.get(id=photo_id, route=route)
                    photo.delete()
                except RoutePhoto.DoesNotExist:
                    pass

            main_photo_id = data.get('main_photo_id')
            if 'photos_data' in data and isinstance(data['photos_data'], dict):
                main_photo_id = data['photos_data'].get(
                    'main_photo_id', main_photo_id
                )

            if main_photo_id:
                try:
                    main_photo_id = int(main_photo_id)
                    main_photo = RoutePhoto.objects.filter(
                        id=main_photo_id, route=route
                    ).first()
                    if main_photo:
                        RoutePhoto.objects.filter(route=route).update(
                            is_main=False
                        )
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
            for i, photo_data in enumerate(route_photos):
                if not photo_data:
                    continue
                if photo_data.startswith('data:'):
                    save_base64_photo(photo_data, route, RoutePhoto, order=i)
                elif photo_data.startswith(('/uploads/', '/media/')):
                    copy_existing_photo(photo_data, route, RoutePhoto, order=i)

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

            old_points = {p.id: p for p in route.points.all()}
            for i, point_data in enumerate(waypoints_data):
                point_name = point_data.get('name', f'Point {i + 1}')
                incoming_id = point_data.get('id')
                incoming_id_key = None
                if incoming_id is not None:
                    try:
                        incoming_id_key = int(incoming_id)
                    except Exception:
                        incoming_id_key = incoming_id

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
                        latitude=point_data.get(
                            'lat', point_data.get('latitude', 0)
                        ),
                        longitude=point_data.get(
                            'lng', point_data.get('longitude', 0)
                        ),
                        category=point_data.get('category', ''),
                        order=i,
                    )

                removed_point_photo_ids = data.get(
                    'removed_point_photo_ids', []
                )
                if isinstance(removed_point_photo_ids, list):
                    for photo_id in removed_point_photo_ids:
                        try:
                            photo = PointPhoto.objects.get(
                                id=photo_id, point=point
                            )
                            photo.delete()
                        except PointPhoto.DoesNotExist:
                            pass

                point_photos = point_data.get('photos', None)
                if isinstance(point_photos, list):
                    for j, photo_data in enumerate(point_photos):
                        if not photo_data:
                            continue
                        if isinstance(
                            photo_data, str
                        ) and photo_data.startswith('data:'):
                            save_base64_photo(
                                photo_data, point, PointPhoto, order=j
                            )
                        elif isinstance(
                            photo_data, str
                        ) and photo_data.startswith(('/uploads/', '/media/')):
                            copy_existing_photo(
                                photo_data, point, PointPhoto, order=j
                            )
                        elif isinstance(photo_data, dict):
                            photo_url = photo_data.get('url', '')
                            caption = photo_data.get('caption', '')
                            if photo_url.startswith('data:'):
                                save_base64_photo(
                                    photo_url,
                                    point,
                                    PointPhoto,
                                    order=j,
                                    caption=caption,
                                )
                            elif photo_url.startswith(
                                '/uploads/'
                            ) or photo_url.startswith('/media/'):
                                copy_existing_photo(
                                    photo_url,
                                    point,
                                    PointPhoto,
                                    order=j,
                                    caption=caption,
                                )

            return JsonResponse(
                {'success': True, 'route_id': route.id, 'id': route.id}
            )
        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': _('Invalid JSON format.')}
            )
        except Exception as e:
            return JsonResponse(
                {'success': False, 'error': f'Server error: {e!s}'}
            )

    def post(self, request, pk):
        return self.put(request, pk)


@login_required
@csrf_exempt
def generate_qr_code(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    if route.author != request.user and not request.user.is_staff:
        return JsonResponse(
            {
                'success': False,
                'error': _(
                    'You do not have permission to'
                    ' generate a QR code for this route.'
                ),
            }
        )

    try:
        qr_url = route.generate_qr_code(request)
        return JsonResponse(
            {
                'success': True,
                'qr_url': qr_url,
                'route_url': request.build_absolute_uri(
                    route.get_absolute_url()
                ),
            }
        )
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': f'QR code generation error: {e!s}'}
        )


def route_qr_code(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    if not can_view_route(request.user, route):
        messages.error(request, _('You do not have access to this route.'))
        return redirect('home')

    qr_url = route.qr_code.url if route.qr_code else None
    if not qr_url:
        qr_url = route.generate_qr_code(request)

    route_url = request.build_absolute_uri(route.get_absolute_url())
    context = {
        'route': route,
        'qr_url': qr_url,
        'route_url': route_url,
    }

    if request.user.is_authenticated:
        context['pending_friend_requests'] = Friendship.objects.filter(
            to_user=request.user, status='pending'
        )[:5]
        context['pending_requests_count'] = Friendship.objects.filter(
            to_user=request.user, status='pending'
        ).count()

    return render(request, 'routes/route_qr_code.html', context)


@login_required
@csrf_exempt
def share_route_access(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    if route.author != request.user and not request.user.is_staff:
        return JsonResponse(
            {
                'success': False,
                'error': _(
                    'You do not have permission to share access to this route.'
                ),
            }
        )

    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        if not email:
            return JsonResponse(
                {'success': False, 'error': _('Email not provided.')}
            )

        try:
            target_user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse(
                {
                    'success': False,
                    'error': _('No user registered with this email.'),
                }
            )

        if target_user == request.user:
            return JsonResponse(
                {
                    'success': False,
                    'error': _('You cannot share access with yourself.'),
                }
            )

        route.privacy = 'personal'
        route.shared_with.add(target_user)
        route.save()
        return JsonResponse(
            {
                'success': True,
                'message': _(
                    'Access to route “{}” has been granted to user {}'
                ).format(route.name, email),
            }
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': _('Invalid data format.')}
        )
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error: {e!s}'})


@login_required
@csrf_exempt
def get_friends_list(request):
    try:
        friends = Friendship.objects.filter(
            Q(from_user=request.user, status='accepted')
            | Q(to_user=request.user, status='accepted')
        ).select_related('from_user', 'to_user')

        friends_list = []
        for friendship in friends:
            friend = (
                friendship.to_user
                if friendship.from_user == request.user
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
        return JsonResponse({'success': True, 'friends': friends_list})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def export_gpx(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    points = route.points.all().order_by('order')

    gpx_instance = gpx.GPX()
    gpx_instance.name = route.name
    if route.description:
        gpx_instance.description = route.description
    elif route.short_description:
        gpx_instance.description = route.short_description

    gpx_instance.author_name = (
        str(route.author.username) if route.author else 'Waylines'
    )
    gpx_instance.link = request.build_absolute_uri(f'/routes/{route_id}/')

    gpx_track = gpx.GPXTrack()
    gpx_track.name = route.name
    gpx_segment = gpx.GPXTrackSegment()

    try:
        from django.conf import settings

        api_key = settings.OPENROUTESERVICE_API_KEY

        if api_key and len(points) >= 2:
            coordinates = [
                [float(p.longitude), float(p.latitude)] for p in points
            ]
            profile_map = {
                'walking': 'foot-walking',
                'cycling': 'cycling-regular',
                'driving': 'driving-car',
            }
            profile = profile_map.get(route.route_type, 'foot-walking')

            headers = {
                'Authorization': api_key,
                'Content-Type': 'application/json',
            }
            body = {
                'coordinates': coordinates,
                'elevation': True,
                'instructions': False,
                'format': 'geojson',
            }

            response = requests.post(
                'https://api.openrouteservice.org'
                f'/v2/directions/{profile}/geojson',
                headers=headers,
                data=json.dumps(body),
                timeout=30,
            )

            if response.status_code == 200:
                route_data = response.json()
                if route_data.get('features'):
                    geometry = route_data['features'][0]['geometry'][
                        'coordinates'
                    ]
                    for coord in geometry:
                        if len(coord) >= 3:
                            track_point = gpx.GPXTrackPoint(
                                latitude=coord[1],
                                longitude=coord[0],
                                elevation=coord[2],
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
        else:
            for point in points:
                gpx_segment.points.append(
                    gpx.GPXTrackPoint(
                        latitude=float(point.latitude),
                        longitude=float(point.longitude),
                    )
                )
    except Exception:
        for point in points:
            gpx_segment.points.append(
                gpx.GPXTrackPoint(
                    latitude=float(point.latitude),
                    longitude=float(point.longitude),
                )
            )

    gpx_track.segments.append(gpx_segment)
    gpx_instance.tracks.append(gpx_track)

    for idx, point in enumerate(points):
        waypoint = gpx.GPXWaypoint(
            latitude=float(point.latitude),
            longitude=float(point.longitude),
            name=(
                f'{idx + 1}. {point.name}'
                if point.name
                else f'Point {idx + 1}'
            ),
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

    response = HttpResponse(
        gpx_instance.to_xml(), content_type='application/gpx+xml'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="route_{route_id}.gpx"'
    )
    return response


def export_kml(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    points = route.points.all().order_by('order')

    route_coordinates = []
    try:
        from django.conf import settings

        api_key = getattr(settings, 'OPENROUTESERVICE_API_KEY', None)

        if api_key and len(points) >= 2:
            coordinates = [
                [float(p.longitude), float(p.latitude)] for p in points
            ]
            profile_map = {
                'walking': 'foot-walking',
                'cycling': 'cycling-regular',
                'driving': 'driving-car',
            }
            profile = profile_map.get(route.route_type, 'foot-walking')

            headers = {
                'Authorization': api_key,
                'Content-Type': 'application/json',
            }
            body = {
                'coordinates': coordinates,
                'elevation': False,
                'instructions': False,
                'format': 'geojson',
            }

            response = requests.post(
                'https://api.openrouteservice.org'
                f'/v2/directions/{profile}/geojson',
                headers=headers,
                data=json.dumps(body),
                timeout=30,
            )

            if response.status_code == 200:
                route_data = response.json()
                if route_data.get('features'):
                    geometry = route_data['features'][0]['geometry'][
                        'coordinates'
                    ]
                    route_coordinates = [
                        f'{coord[0]},{coord[1]},0' for coord in geometry
                    ]
    except Exception:
        pass

    if not route_coordinates:
        route_coordinates = [
            f'{point.longitude},{point.latitude},0' for point in points
        ]

    coordinates_xml = '\n'.join(
        f'          {coord}' for coord in route_coordinates
    )

    placemarks_xml = ''
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
        placemarks_xml += f"""
    <Placemark>
      <name>{idx + 1}. {point.name}</name>
      <description><![CDATA[{description}]]></description>
      <Point>
        <coordinates>{point.longitude},{point.latitude},0</coordinates>
      </Point>
    </Placemark>"""

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
{coordinates_xml}        </coordinates>
      </LineString>
    </Placemark>

    {placemarks_xml}

  </Document>
</kml>"""

    response = HttpResponse(
        kml_template, content_type='application/vnd.google-earth.kml+xml'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="route_{route_id}.kml"'
    )
    return response


def export_geojson(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    points = route.points.all().order_by('order')

    route_coordinates = []
    try:
        from django.conf import settings

        api_key = getattr(settings, 'OPENROUTESERVICE_API_KEY', None)

        if api_key and len(points) >= 2:
            coordinates = [
                [float(p.longitude), float(p.latitude)] for p in points
            ]
            profile_map = {
                'walking': 'foot-walking',
                'cycling': 'cycling-regular',
                'driving': 'driving-car',
            }
            profile = profile_map.get(route.route_type, 'foot-walking')

            headers = {
                'Authorization': api_key,
                'Content-Type': 'application/json',
            }
            body = {
                'coordinates': coordinates,
                'elevation': True,
                'instructions': False,
                'format': 'geojson',
            }

            response = requests.post(
                'https://api.openrouteservice.org'
                f'/v2/directions/{profile}/geojson',
                headers=headers,
                data=json.dumps(body),
                timeout=30,
            )

            if response.status_code == 200:
                route_data = response.json()
                if route_data.get('features'):
                    geometry = route_data['features'][0]['geometry'][
                        'coordinates'
                    ]
                    route_coordinates = [
                        [
                            float(coord[0]),
                            float(coord[1]),
                            float(coord[2]) if len(coord) > 2 else 0,
                        ]
                        for coord in geometry
                    ]
    except Exception:
        pass

    if not route_coordinates:
        route_coordinates = [
            [float(point.longitude), float(point.latitude), 0]
            for point in points
        ]

    geojson_data = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {
                    'name': route.name,
                    'description': route.description
                    or route.short_description,
                    'type': 'route',
                    'route_type': route.route_type,
                    'distance': (
                        float(route.total_distance)
                        if route.total_distance
                        else 0
                    ),
                    'duration': route.duration_display
                    or route.duration_minutes,
                    'source': (
                        'OpenRouteService' if route_coordinates else 'Waylines'
                    ),
                },
                'geometry': {
                    'type': 'LineString',
                    'coordinates': route_coordinates,
                },
            }
        ],
    }

    for idx, point in enumerate(points):
        point_properties = {
            'name': point.name,
            'description': point.description or '',
            'address': point.address or '',
            'category': point.category or '',
            'type': 'waypoint',
            'order': idx + 1,
        }
        geojson_data['features'].append(
            {
                'type': 'Feature',
                'properties': point_properties,
                'geometry': {
                    'type': 'Point',
                    'coordinates': [
                        float(point.longitude),
                        float(point.latitude),
                        0,
                    ],
                },
            }
        )

    response = HttpResponse(
        json.dumps(geojson_data, ensure_ascii=False, indent=2),
        content_type='application/json',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="route_{route_id}.geojson"'
    )
    return response


@require_http_methods(['POST', 'PUT'])
def save_point(request, point_id=None):
    try:
        route_id = request.POST.get('route_id')
        if not route_id:
            return JsonResponse({'error': 'Route ID is required'}, status=400)
        route = Route.objects.get(id=route_id)

        if point_id:
            point = RoutePoint.objects.get(id=point_id, route=route)
        else:
            point = RoutePoint(route=route)

        point.name = request.POST.get('name', '')[:255]
        point.address = request.POST.get('address', '')[:255]
        point.lat = request.POST.get('lat')
        point.lng = request.POST.get('lng')
        point.description = request.POST.get('description', '')
        point.category = request.POST.get('category', '')[:100]
        point.hint_author = request.POST.get('hint_author', '')[:255]

        tags_raw = request.POST.get('tags', '[]')
        try:
            tags = json.loads(tags_raw)
            point.tags = [tag[:50] for tag in tags if isinstance(tag, str)]
        except Exception:
            point.tags = []

        point.save()

        existing_photos_json = request.POST.get('existing_photos_json', '[]')
        try:
            existing_data = json.loads(existing_photos_json)
            current_photos = {
                p.image.url: p for p in point.photos.all() if p.image
            }
            incoming_urls = set()

            for idx, photo_data in enumerate(existing_data):
                if isinstance(photo_data, dict) and 'url' in photo_data:
                    url = photo_data['url']
                    if isinstance(url, str) and url.startswith('/media/'):
                        incoming_urls.add(url)
                        if url not in current_photos:
                            new_photo = PointPhoto(point=point, order=idx)
                            new_photo.image.name = url.replace(
                                '/media/', '', 1
                            )
                            new_photo.save()

            for url, photo in current_photos.items():
                if url not in incoming_urls:
                    photo.delete()

        except Exception as e:
            print('Error syncing existing photos:', e)

        new_photos = request.FILES.getlist('photos')
        last_order = (
            point.photos.aggregate(max_order=models.Max('order'))['max_order']
            or -1
        )
        for file in new_photos:
            if isinstance(file, InMemoryUploadedFile):
                last_order += 1
                photo = PointPhoto(point=point, order=last_order)
                photo.image.save(
                    file.name, ContentFile(file.read()), save=True
                )

        return JsonResponse({'success': True, 'point_id': point.id})

    except Route.DoesNotExist:
        return JsonResponse({'error': 'Route not found'}, status=404)
    except RoutePoint.DoesNotExist:
        return JsonResponse({'error': 'Point not found'}, status=404)
    except Exception as e:
        print('Save point error:', e)
        import traceback

        traceback.print_exc()
        return JsonResponse({'error': 'Internal error'}, status=500)
