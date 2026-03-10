import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from interactions.models import Comment, Rating
from routes.models import Route
from interactions import services

logger = logging.getLogger(__name__)


@login_required
def toggle_favorite(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # Вся логика теперь здесь:
    result_data = services.toggle_route_favorite(request.user, route)

    if is_ajax:
        return JsonResponse(result_data)

    # Логика редиректа - это часть представления (HTTP), а не бизнес-логики
    messages.success(request, result_data['message'])
    referer = request.META.get('HTTP_REFERER', '')
    if 'my_routes' in referer and '#favorites' in referer:
        return redirect(referer + '#favorites')
    return redirect(referer or reverse('route_detail', args=[route_id]))


@login_required
def add_rating(request, route_id):
    if request.method != 'POST':
        messages.error(request, _('Invalid request method'))
        return redirect('route_detail', id=route_id)

    route = get_object_or_404(Route, id=route_id)
    score_str = request.POST.get('score', '').strip()

    try:
        services.rate_route(request.user, route, score_str)
        messages.success(request, _('Thank you for your rating!'))
    except ValidationError as e:
        messages.error(request, e.message)

    return redirect(
        request.META.get(
            'HTTP_REFERER', reverse('route_detail', args=[route_id])
        )
    )


@login_required
def add_comment(request, route_id):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        if is_ajax:
            return JsonResponse(
                {'success': False, 'error': _('Invalid method')}, status=405
            )
        return redirect('route_detail', id=route_id)

    route = get_object_or_404(Route, id=route_id)
    text = request.POST.get('text', '')

    try:
        services.create_comment(request.user, route, text)

        if is_ajax:
            html = services.render_comments_html(route, request.user)
            return JsonResponse(
                {
                    'success': True,
                    'html': html,
                    'comments_count': route.interaction_comments.count(),
                    'message': _('Comment added successfully'),
                }
            )

        messages.success(request, _('Comment added'))

    except ValidationError as e:
        if is_ajax:
            return JsonResponse(
                {'success': False, 'error': e.message}, status=400
            )
        messages.error(request, e.message)

    return redirect('route_detail', id=route_id)


@login_required
def delete_comment(request, comment_id):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        if is_ajax:
            return JsonResponse(
                {'success': False, 'error': _('Invalid method')}, status=405
            )
        return redirect('home')

    comment = get_object_or_404(Comment, id=comment_id)
    route = comment.route

    try:
        services.remove_comment(request.user, comment)

        if is_ajax:
            html = services.render_comments_html(route, request.user)
            return JsonResponse(
                {
                    'success': True,
                    'html': html,
                    'comments_count': route.interaction_comments.count(),
                    'message': _('Comment deleted successfully'),
                }
            )

        messages.success(request, _('Comment deleted'))

    except PermissionDenied as e:
        if is_ajax:
            return JsonResponse(
                {'success': False, 'error': str(e)}, status=403
            )
        messages.error(request, str(e))
        return redirect('route_detail', id=route.id)

    return redirect('route_detail', id=route.id)
