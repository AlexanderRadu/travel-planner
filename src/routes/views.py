import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from interactions.models import Comment, Favorite, Rating
from routes.models import (
    Route,
    RoutePoint,
    User,
)
from routes.services import (
    access,
    exports,
    interactions,
    qr_codes,
    route_editor,
    routes_selector,
    routes_stats,
    sharing,
)
from users.models import Friendship

logger = logging.getLogger(__name__)


def home(request):
    stats = routes_stats.get_general_stats()

    popular_routes = routes_stats.get_popular_routes()

    user_favorites_ids = routes_stats.get_user_favorite_ids(request.user)

    context = {
        'popular_routes': popular_routes,
        'user_favorites_ids': user_favorites_ids,
        **stats,
    }

    return render(request, 'home.html', context)


def all_routes(request):
    route_type = request.GET.get('type', '')
    search_query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'newest')
    page_number = request.GET.get('page')

    routes_qs = routes_stats.get_filtered_routes(
        route_type=route_type, search_query=search_query, sort_by=sort_by
    )

    paginator = Paginator(routes_qs, 12)
    page_obj = paginator.get_page(page_number)

    user_favorites_ids = routes_stats.get_user_favorite_ids(request.user)
    friendship_stats = routes_stats.get_friendship_stats(request.user)

    context = {
        'page_obj': page_obj,
        'route_types': Route.ROUTE_TYPE_CHOICES,
        'current_sort': sort_by,
        'search_query': search_query,
        'selected_type': route_type,
        'user_favorites_ids': user_favorites_ids,
        'get_params': {'q': search_query, 'type': route_type, 'sort': sort_by},
        **friendship_stats,
    }

    return render(request, 'routes/all_routes.html', context)


@login_required
def my_routes(request):
    user = request.user

    my_routes_data = routes_stats.get_author_routes_data(user)

    favorite_routes = routes_stats.get_detailed_favorite_routes(user)

    user_favorites_ids = routes_stats.get_user_favorite_ids(user)

    friendship_stats = routes_stats.get_friendship_stats(user)

    context = {
        **my_routes_data,
        'favorite_routes': favorite_routes,
        'favorites_count': favorite_routes.count(),
        'user_favorites_ids': user_favorites_ids,
        **friendship_stats,
    }

    return render(request, 'routes/my_routes.html', context)


@login_required
def shared_routes(request):
    user = request.user

    routes = routes_stats.get_shared_routes_list(user)

    counts_data = routes_stats.get_shared_routes_counts(user)

    user_favorites_ids = routes_stats.get_user_favorite_ids(user)

    friendship_stats = routes_stats.get_friendship_stats(user)

    context = {
        'routes': routes,
        **counts_data,
        'user_favorites_ids': user_favorites_ids,
        **friendship_stats,
    }

    return render(request, 'routes/shared_routes.html', context)


def route_detail(request, route_id):
    route = get_object_or_404(
        Route.objects.select_related('author').prefetch_related(
            'photos', 'shared_with'
        ),
        id=route_id,
    )

    if not access.can_view_route(request.user, route):
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

    try:
        data = json.loads(request.body)
        friend_id = data.get('friend_id')
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': _('Invalid data format.')}
        )

    try:
        friend = sharing.share_route_with_friend(
            route=route, requesting_user=request.user, friend_id=friend_id
        )

        friend_name = friend.first_name or friend.username
        return JsonResponse(
            {
                'success': True,
                'message': _('Route "{}" has been sent to friend {}').format(
                    route.name, friend_name
                ),
            }
        )

    except (PermissionDenied, ValueError) as e:
        return JsonResponse({'success': False, 'error': str(e)})

    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': f'Error sending: {e!s}'}
        )


@login_required
def create_route(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            route = route_editor.create_route_from_data(
                user=request.user, data=data
            )

            return JsonResponse({'success': True, 'route_id': route.id})

        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': _('Invalid JSON format.')}
            )
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'error': f'Server error: {e!s}'}
            )

    pending_friendships = Friendship.objects.filter(
        to_user=request.user, status='pending'
    )

    context = {
        'pending_friend_requests': pending_friendships[:5],
        'pending_requests_count': pending_friendships.count(),
    }
    return render(request, 'routes/route_editor.html', context)


@login_required
@csrf_exempt
def edit_route(request, route_id):
    route = get_object_or_404(Route, id=route_id, author=request.user)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            route_editor.update_route_details(route, data)
            return JsonResponse({'success': True, 'route_id': route.id})
        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': 'Invalid JSON data'}
            )
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    route_data_dict = route_editor.get_serialized_route_data(route)

    context = {
        'route': route,
        'route_data_json': json.dumps(route_data_dict),
        'pending_friend_requests': Friendship.objects.filter(
            to_user=request.user, status='pending'
        )[:5],
        'pending_requests_count': Friendship.objects.filter(
            to_user=request.user, status='pending'
        ).count(),
    }
    return render(request, 'routes/route_editor.html', context)


@require_POST
def delete_route(request, route_id):
    try:
        route = get_object_or_404(Route, id=route_id, author=request.user)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

        delete_all_data = data.get('delete_all_data', True)
        clear_cache = data.get('clear_cache', True)

        route_editor.delete_route_completely(
            route=route,
            delete_all_files=delete_all_data,
            clear_cache=clear_cache,
        )

        return JsonResponse(
            {'success': True, 'message': _('Route deleted successfully.')}
        )

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def toggle_route_active(request, route_id):
    route = get_object_or_404(Route, id=route_id, author=request.user)

    is_active_now = route_editor.toggle_route_status(route)

    status_text = _('activated') if is_active_now else _('deactivated')
    messages.success(request, _('Route has been {}.').format(status_text))

    return redirect('route_detail', route_id=route_id)


@login_required
@csrf_exempt
def rate_route(request, route_id):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'error': _('Only POST allowed.')}
        )

    route = get_object_or_404(Route, id=route_id)

    try:
        data = json.loads(request.body)
        rating_value = data.get('rating')

        average_rating = interactions.set_route_rating(
            route, request.user, rating_value
        )

        return JsonResponse(
            {'success': True, 'average_rating': average_rating}
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': _('Invalid JSON format.')}
        )

    except ValueError as e:
        return JsonResponse({'success': False, 'error': _(str(e))})


@login_required
@csrf_exempt
def toggle_favorite(request, route_id):
    if request.method == 'POST':
        route = get_object_or_404(Route, id=route_id)
        ok = interactions.toggle_route_favorite(
            user=request.user,
            route=route,
        )
        if not ok:
            return JsonResponse({'success': True, 'is_favorite': False})
        return JsonResponse({'success': True, 'is_favorite': True})
    return JsonResponse({'success': False, 'error': _('Only POST allowed.')})


@login_required
def add_route_comment(request, route_id):
    if request.method == 'POST':
        route = get_object_or_404(Route, id=route_id)
        text = request.POST.get('text')
        success = interactions.create_route_comment(
            user=request.user,
            route=route,
            text=text,
        )
        if success:
            messages.success(request, _('Comment added.'))
    return redirect('route_detail', route_id=route_id)


@login_required
def add_point_comment(request, point_id):
    point = get_object_or_404(RoutePoint, id=point_id)
    if request.method == 'POST':
        text = request.POST.get('text')
        success = interactions.create_point_comment(
            user=request.user,
            point=point,
            text=text,
        )
        if success:
            messages.success(request, _('Comment added.'))
    return redirect('route_detail', route_id=point.route_id)


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
        email = data.get('email', '')
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': _('Invalid data format.')}, status=400
        )

    try:
        target_user = sharing.share_route_with_user(route, request.user, email)

        return JsonResponse(
            {
                'success': True,
                'message': _(
                    'Access to route “{}” has been granted to user {}'
                ).format(route.name, target_user.email),
            }
        )

    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

    except User.DoesNotExist:
        return JsonResponse(
            {
                'success': False,
                'error': _('No user registered with this email.'),
            },
            status=404,
        )


def walking_routes(request):
    routes = routes_selector.get_active_routes(route_type='walking')
    user_favorites_ids = routes_selector.get_user_favorite_route_ids(
        request.user
    )

    context = {
        'routes': routes,
        'page_title': _('Walking Routes'),
        'route_type': 'walking',
        'total_count': routes.count(),
        'user_favorites_ids': user_favorites_ids,
    }
    return render(request, 'routes/filtered_routes.html', context)


def driving_routes(request):
    routes = routes_selector.get_active_routes(route_type='driving')
    user_favorites_ids = routes_selector.get_user_favorite_route_ids(
        request.user
    )

    context = {
        'routes': routes,
        'page_title': _('Driving Routes'),
        'route_type': 'driving',
        'total_count': routes.count(),
        'user_favorites_ids': user_favorites_ids,
    }
    return render(request, 'routes/filtered_routes.html', context)


def cycling_routes(request):
    routes = routes_selector.get_active_routes(route_type='cycling')
    user_favorites_ids = routes_selector.get_user_favorite_route_ids(
        request.user
    )

    context = {
        'routes': routes,
        'page_title': _('Cycling Routes'),
        'route_type': 'cycling',
        'total_count': routes.count(),
        'user_favorites_ids': user_favorites_ids,
    }
    return render(request, 'routes/filtered_routes.html', context)


def adventure_routes(request):
    routes = routes_selector.get_active_routes(route_type=None)
    user_favorites_ids = routes_selector.get_user_favorite_route_ids(
        request.user
    )

    context = {
        'routes': routes,
        'page_title': _('Adventure Routes'),
        'total_count': routes.count(),
        'user_favorites_ids': user_favorites_ids,
    }
    return render(request, 'routes/filtered_routes.html', context)


def search_routes(request):
    query = request.GET.get('q', '')
    route_type = request.GET.get('type', '')

    routes = routes_selector.search_active_routes(
        text_query=query, route_type=route_type
    )

    user_favorites_ids = routes_selector.get_user_favorite_route_ids(
        request.user
    )

    context = {
        'routes': routes,
        'query': query,
        'route_type': route_type,
        'total_count': routes.count(),
        'user_favorites_ids': user_favorites_ids,
    }
    return render(request, 'routes/search_results.html', context)


class RouteCreateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            content_type = request.META.get('CONTENT_TYPE', '')

            if 'application/json' in content_type:
                data = json.loads(request.body)
                files = {}
            else:
                route_data_str = request.POST.get('route_data', '{}')
                data = json.loads(route_data_str)
                files = request.FILES

        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': _('Invalid JSON format.')}
            )

        try:
            route = route_editor.create_new_route(
                user=request.user, data=data, files=files
            )

            return JsonResponse(
                {'success': True, 'route_id': route.id, 'id': route.id}
            )

        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)})

        except Exception as e:
            return JsonResponse(
                {'success': False, 'error': f'Server error: {e!s}'}
            )


class RouteUpdateView(LoginRequiredMixin, View):
    def _parse_request_data(self, request) -> dict:
        content_type = request.content_type or ''

        if 'application/json' in content_type:
            return json.loads(request.body)

        data = request.POST.dict()
        data.update(request.FILES.dict())

        json_fields = ['photos_data', 'removed_photo_ids', 'route_data']
        for field in json_fields:
            if field in data:
                try:
                    data[field] = json.loads(data[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        return data

    def put(self, request, pk):
        try:
            route = get_object_or_404(Route, id=pk, author=request.user)

            data = self._parse_request_data(request)

            updated_route = route_editor.update_route(route, data)

            return JsonResponse(
                {
                    'success': True,
                    'route_id': updated_route.id,
                    'id': updated_route.id,
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': str(_('Invalid JSON format.'))}
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
    try:
        qr_url, route_url = qr_codes.generate_route_qr(
            request.user, route_id, request
        )

        return JsonResponse(
            {
                'success': True,
                'qr_url': qr_url,
                'route_url': route_url,
            }
        )

    except PermissionDenied as e:
        return JsonResponse(
            {
                'success': False,
                'error': str(e),
            }
        )

    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': f'QR code generation error: {e!s}'}
        )


def route_qr_code(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    if not access.can_view_route(request.user, route):
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

    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': _('Invalid data format.')}
        )

    try:
        sharing.grant_route_access(
            route=route, requesting_user=request.user, email=email
        )

        return JsonResponse(
            {
                'success': True,
                'message': _(
                    'Access to route “{}” has been granted to user {}'
                ).format(route.name, email),
            }
        )

    except (PermissionDenied, ValueError) as e:
        return JsonResponse({'success': False, 'error': str(e)})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error: {e!s}'})


@login_required
@csrf_exempt
def get_friends_list(request):
    try:
        friends_list = sharing.get_accepted_friends_for_user(request.user)
        return JsonResponse({'success': True, 'friends': friends_list})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def export_gpx(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    absolute_uri = request.build_absolute_uri(f'/routes/{route_id}/')

    gpx_xml_string = exports.generate_route_gpx(route, absolute_uri)

    response = HttpResponse(gpx_xml_string, content_type='application/gpx+xml')
    response['Content-Disposition'] = (
        f'attachment; filename="route_{route_id}.gpx"'
    )

    return response


def export_kml(request, route_id):
    route = get_object_or_404(Route, id=route_id)

    kml_xml_string = exports.generate_route_kml(route)

    response = HttpResponse(
        kml_xml_string, content_type='application/vnd.google-earth.kml+xml'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="route_{route_id}.kml"'
    )

    return response


def export_geojson(request, route_id):
    route = get_object_or_404(Route, id=route_id)

    geojson_string = exports.generate_route_geojson(route)

    response = HttpResponse(geojson_string, content_type='application/json')
    response['Content-Disposition'] = (
        f'attachment; filename="route_{route_id}.geojson"'
    )

    return response


@require_http_methods(['POST', 'PUT'])
def save_point(request, point_id=None):
    route_id = request.POST.get('route_id')
    if not route_id:
        return JsonResponse({'error': 'Route ID is required'}, status=400)

    try:
        point = route_editor.save_route_point(
            route_id=route_id,
            point_id=point_id,
            data=request.POST.dict(),
            existing_photos_json=request.POST.get(
                'existing_photos_json', '[]'
            ),
            new_files=request.FILES.getlist('photos'),
        )

        return JsonResponse({'success': True, 'point_id': point.id})

    except Route.DoesNotExist:
        return JsonResponse({'error': 'Route not found'}, status=404)
    except RoutePoint.DoesNotExist:
        return JsonResponse({'error': 'Point not found'}, status=404)

    except Exception as e:
        logger.error(f'Save point error: {e}', exc_info=True)
        return JsonResponse({'error': 'Internal error'}, status=500)
