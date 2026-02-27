import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import gettext as _

from interactions.models import Comment, Favorite, Rating
from routes.models import Route

logger = logging.getLogger(__name__)


def _render_comments_html(route, user):
    comments = route.interaction_comments.select_related('user').order_by(
        'created_at'
    )
    comments_count = len(comments)
    html_parts = []

    for i, cmt in enumerate(comments):
        can_delete = cmt.user == user
        is_author = cmt.user == route.author

        delete_button = ''
        if can_delete:
            delete_button = f"""
            <button type="button" class="btn btn-link text-danger p-0 btn-sm
             opacity-75 hover-opacity-100 delete-comment-btn"
                    data-comment-id="{cmt.id}" title="{_('Delete')}">
                <i class="far fa-trash-alt"></i>
            </button>
            """

        author_badge = ''
        if is_author:
            author_badge = f"""
            <span class="badge bg-light text-muted border px-2 py-1 ms-2"
             style="font-size: 0.65rem; font-weight: 500;">
                <i class="fas fa-feather-alt me-1"></i>{_('Author')}
            </span>
            """

        border_class = 'border-bottom' if i < comments_count - 1 else ''
        iso_time = cmt.created_at.isoformat()
        server_time = cmt.created_at.strftime('%d.%m.%Y %H:%M')

        html_parts.append(
            f"""
        <div class="comment-item d-flex mb-3 pb-3 {border_class}"
             data-comment-id="{cmt.id}"
             data-user-id="{cmt.user.id}"
             data-timestamp="{iso_time}">
            <div class="flex-shrink-0">
                <div class="avatar-placeholder rounded-circle bg-light d-flex
                 align-items-center justify-content-center border"
                  style="width: 40px; height: 40px;">
                    <i class="fas fa-user text-secondary"></i>
                </div>
            </div>
            <div class="flex-grow-1 ms-3">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <div class="d-flex align-items-center gap-2 mb-1">
                            <h6 class="mb-0 text-dark
                             fw-bold">{cmt.user.username}</h6>
                            {author_badge}
                        </div>
                        <small class="text-muted comment-time"
                         data-timestamp="{iso_time}">{server_time}</small>
                    </div>
                    {delete_button}
                </div>
                <p class="comment-text text-secondary mt-2 mb-0"
                 style="white-space: pre-line;">{escape(cmt.text)}</p>
            </div>
        </div>
        """
        )

    if not html_parts:
        return f"""
        <div class="text-center py-4 text-muted">
            <i class="far fa-comment-dots fa-3x mb-3 opacity-25"></i>
            <p class="mb-0">{_('No comments yet. Be the first!')}</p>
        </div>
        """
    return ''.join(html_parts)


@login_required
def toggle_favorite(request, route_id):
    route = get_object_or_404(Route, id=route_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    favorite, created = Favorite.objects.get_or_create(
        user=request.user, route=route
    )

    if created:
        message = _('Added to favorites')
        is_favorite = True
        logger.info(
            f'User {request.user.username} added route {route_id} to favorites'
        )
    else:
        favorite.delete()
        message = _('Removed from favorites')
        is_favorite = False
        logger.info(
            f'User {request.user.username} removed route {route_id}'
            f' from favorites'
        )

    if is_ajax:
        favorites_count = Favorite.objects.filter(user=request.user).count()
        return JsonResponse(
            {
                'success': True,
                'message': message,
                'is_favorite': is_favorite,
                'favorites_count': favorites_count,
            }
        )

    messages.success(request, message)
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

    if route.author == request.user:
        messages.error(request, _('You cannot rate your own route'))
        return redirect('route_detail', id=route_id)

    score_str = request.POST.get('score', '').strip()
    if not score_str.isdigit():
        messages.error(request, _('Invalid rating'))
        return redirect('route_detail', id=route_id)

    score = int(score_str)
    if not (1 <= score <= 5):
        messages.error(request, _('Rating must be between 1 and 5'))
        return redirect('route_detail', id=route_id)

    Rating.objects.update_or_create(
        user=request.user,
        route=route,
        defaults={'score': score, 'updated_at': timezone.now()},
    )

    messages.success(request, _('Thank you for your rating!'))
    return redirect(
        request.META.get(
            'HTTP_REFERER', reverse('route_detail', args=[route_id])
        )
    )


@login_required
def add_comment(request, route_id):
    if request.method != 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'error': _('Invalid request method')},
                status=405,
            )
        return redirect('route_detail', id=route_id)

    route = get_object_or_404(Route, id=route_id)
    text = request.POST.get('text', '').strip()

    if not text:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'error': _('Comment cannot be empty')},
                status=400,
            )
        messages.error(request, _('Comment cannot be empty'))
        return redirect('route_detail', id=route_id)

    Comment.objects.create(route=route, user=request.user, text=text)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = _render_comments_html(route, request.user)
        comments_count = route.interaction_comments.count()
        return JsonResponse(
            {
                'success': True,
                'html': html,
                'comments_count': comments_count,
                'message': _('Comment added successfully'),
            }
        )

    messages.success(request, _('Comment added'))
    return redirect('route_detail', id=route_id)


@login_required
def delete_comment(request, comment_id):
    if request.method != 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'error': _('Invalid request method')},
                status=405,
            )
        return redirect('home')

    comment = get_object_or_404(Comment, id=comment_id)

    if comment.user != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {
                    'success': False,
                    'error': _(
                        'You do not have permission to delete this comment'
                    ),
                },
                status=403,
            )
        messages.error(
            request, _('You do not have permission to delete this comment')
        )
        return redirect('route_detail', id=comment.route_id)

    route = comment.route
    comment.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = _render_comments_html(route, request.user)
        comments_count = route.interaction_comments.count()
        return JsonResponse(
            {
                'success': True,
                'html': html,
                'comments_count': comments_count,
                'message': _('Comment deleted successfully'),
            }
        )

    messages.success(request, _('Comment deleted'))
    return redirect('route_detail', id=route.id)
