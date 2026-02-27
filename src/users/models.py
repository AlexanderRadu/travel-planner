from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Friendship(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('accepted', _('Accepted')),
        ('rejected', _('Rejected')),
    ]

    from_user = models.ForeignKey(
        User,
        related_name='friendship_requests_sent',
        on_delete=models.CASCADE,
        verbose_name=_('From user'),
    )
    to_user = models.ForeignKey(
        User,
        related_name='friendship_requests_received',
        on_delete=models.CASCADE,
        verbose_name=_('To user'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Status'),
    )
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)

    class Meta:
        unique_together = ('from_user', 'to_user')
        verbose_name = _('Friendship')
        verbose_name_plural = _('Friendships')

    def __str__(self):
        return f'{self.from_user} → {self.to_user} ({self.status})'


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('User'),
    )
    bio = models.TextField(_('Bio'), blank=True)
    avatar = models.ImageField(_('Avatar'), upload_to='avatars/', blank=True)
    location = models.CharField(_('Location'), max_length=100, blank=True)
    website = models.URLField(_('Website'), blank=True)
    last_username_change = models.DateTimeField(
        _('Last username change'),
        null=True,
        blank=True,
        help_text=_('Date when username was last changed'),
    )
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)

    class Meta:
        verbose_name = _('User profile')
        verbose_name_plural = _('User profiles')

    def __str__(self):
        return _('Profile of %(username)s') % {'username': self.user.username}

    def save(self, *args, **kwargs):
        if not self.pk:
            self.last_username_change = timezone.now()
        super().save(*args, **kwargs)
