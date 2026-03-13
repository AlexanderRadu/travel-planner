import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import gettext as _

from interactions.models import Comment, Favorite, Rating

logger = logging.getLogger(__name__)


def render_comments_html(route, user):
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


def toggle_route_favorite(user, route):

    favorite, created = Favorite.objects.get_or_create(user=user, route=route)

    if created:
        message = _('Added to favorites')
        is_favorite = True
        logger.info(
            f'User {user.username} added route {route.id} to favorites'
        )
    else:
        favorite.delete()
        message = _('Removed from favorites')
        is_favorite = False
        logger.info(
            f'User {user.username} removed route {route.id} from favorites'
        )
    favorites_count = Favorite.objects.filter(user=user).count()

    return {
        'success': True,
        'message': message,
        'is_favorite': is_favorite,
        'favorites_count': favorites_count,
    }


def rate_route(user, route, score_raw):
    if route.author == user:
        raise ValidationError(_('You cannot rate your own route'))

    try:
        score = int(score_raw)
    except (ValueError, TypeError):
        raise ValidationError(_('Invalid rating'))

    if not (1 <= score <= 5):
        raise ValidationError(_('Rating must be between 1 and 5'))

    Rating.objects.update_or_create(
        user=user,
        route=route,
        defaults={'score': score, 'updated_at': timezone.now()},
    )


def create_comment(user, route, text):

    text = text.strip() if text else ''

    if not text:
        raise ValidationError(_('Comment cannot be empty'))

    comment = Comment.objects.create(route=route, user=user, text=text)
    return comment


def remove_comment(user, comment) -> None:

    if comment.user != user:
        raise PermissionDenied(_('You do not have permission to delete this comment'))

    comment.delete()




