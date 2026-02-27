from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from routes.models import Route


class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Conversation')
        verbose_name_plural = _('Conversations')
        ordering = ['-updated_at']

    def __str__(self):
        return f'Conversation #{self.id}'

    def get_participants_preview(self, limit=3):
        return list(
            self.participants.values_list('username', flat=True)[:limit]
        )

    def get_other_participant(self, user):
        return (
            self.participants.only('id', 'username')
            .exclude(id=user.id)
            .first()
        )

    def get_unread_count(self, user):
        return self.messages.exclude(sender=user).filter(is_read=False).count()


class PrivateMessage(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('Conversation'),
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name=_('Sender'),
    )
    content = models.TextField(_('Message'), max_length=1000)
    is_read = models.BooleanField(_('Read'), default=False)
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)

    class Meta:
        verbose_name = _('Private message')
        verbose_name_plural = _('Private messages')
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.content[:50]}'


class RouteChat(models.Model):
    route = models.OneToOneField(
        Route,
        on_delete=models.CASCADE,
        related_name='chat',
        verbose_name=_('Route'),
    )
    is_active = models.BooleanField(_('Active'), default=True)
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated'), auto_now=True)

    class Meta:
        verbose_name = _('Route chat')
        verbose_name_plural = _('Route chats')
        ordering = ['-updated_at']

    def __str__(self):
        return f'Chat for route: {self.route.name}'


class RouteChatMessage(models.Model):
    route_chat = models.ForeignKey(
        RouteChat,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('Route chat'),
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_('User')
    )
    message = models.TextField(_('Message'), max_length=1000)
    timestamp = models.DateTimeField(_('Time'), auto_now_add=True)
    is_read = models.BooleanField(_('Read'), default=False)

    class Meta:
        verbose_name = _('Route chat message')
        verbose_name_plural = _('Route chat messages')
        ordering = ['timestamp']

    def __str__(self):
        return (
            f'{self.user.username} in {self.route_chat.route.name}: '
            f'{self.message[:50]}'
        )


@receiver(post_save, sender=Route)
def create_route_chat(sender, instance, created, **kwargs):
    if created:
        RouteChat.objects.get_or_create(route=instance)
