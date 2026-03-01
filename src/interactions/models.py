from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from routes.models import Route


class Favorite(models.Model):
    user = models.ForeignKey(
        User,
        related_name='favorite_routes',
        verbose_name=_('User'),
        on_delete=models.CASCADE,
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='favorites_by',
        verbose_name=_('Route'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_('Date added')
    )

    class Meta:
        unique_together = ('user', 'route')
        verbose_name = _('Favorite')
        verbose_name_plural = _('Favorites')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} → {self.route.name}'


class Rating(models.Model):
    user = models.ForeignKey(
        User,
        related_name='interaction_ratings',
        verbose_name=_('User'),
        on_delete=models.CASCADE,
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='interaction_ratings',
        verbose_name=_('Route'),
    )
    score = models.PositiveIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)], verbose_name=_('Score')
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_('Created at')
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name=_('Updated at')
    )

    class Meta:
        unique_together = ('user', 'route')
        verbose_name = _('Rating')
        verbose_name_plural = _('Ratings')

    def __str__(self):
        return f'{self.user.username} rated {self.route.name} as {self.score}'


class Comment(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interaction_comments',
        verbose_name=_('User'),
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='interaction_comments',
        verbose_name=_('Route'),
    )
    text = models.TextField(verbose_name=_('Comment text'))
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_('Created at')
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name=_('Updated at')
    )

    class Meta:
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.text[:50]}'


class RouteShare(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_route_shares',
        verbose_name=_('Sender'),
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_route_shares',
        verbose_name=_('Recipient'),
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='shares',
        verbose_name=_('Route'),
    )
    message = models.TextField(
        _('Message'),
        blank=True,
        help_text=_('Optional message for recipient'),
    )
    sent_at = models.DateTimeField(_('Sent at'), auto_now_add=True)
    is_read = models.BooleanField(_('Is read'), default=False)
    read_at = models.DateTimeField(_('Read at'), null=True, blank=True)

    class Meta:
        verbose_name = _('Route share')
        verbose_name_plural = _('Route shares')
        ordering = ['-sent_at']
        unique_together = ['sender', 'recipient', 'route']

    def __str__(self):
        return (
            f'{self.sender.username} →'
            f' {self.recipient.username}: {self.route.name}'
        )

    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
