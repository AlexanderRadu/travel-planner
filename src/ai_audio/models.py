from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from routes.models import RoutePoint


class AudioGeneration(models.Model):
    VOICE_CHOICES = [
        ('alloy', _('Alloy (neutral)')),
        ('echo', _('Echo (male)')),
        ('nova', _('Nova (female)')),
        ('onyx', _('Onyx (deep)')),
        ('fable', _('Fable (storyteller)')),
        ('shimmer', _('Shimmer (soft)')),
    ]

    LANGUAGE_CHOICES = [
        ('auto', _('Auto-detect')),
        ('ru-RU', _('Russian')),
        ('en-US', _('English')),
        ('es-ES', _('Spanish')),
        ('fr-FR', _('French')),
    ]

    point = models.ForeignKey(
        RoutePoint,
        on_delete=models.CASCADE,
        related_name='audio_generations',
        verbose_name=_('Point'),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_('User'),
    )
    text_content = models.TextField(_('Text content'))
    voice_type = models.CharField(
        _('Voice type'), max_length=20, choices=VOICE_CHOICES, default='alloy'
    )
    language = models.CharField(
        _('Language'), max_length=10, choices=LANGUAGE_CHOICES, default='ru-RU'
    )
    audio_file = models.FileField(
        _('Audio file'), upload_to='audio_guides/', null=True, blank=True
    )
    status = models.CharField(_('Status'), max_length=20, default='queued')
    error_message = models.TextField(_('Error message'), blank=True, null=True)
    processing_time = models.FloatField(
        _('Processing time (sec)'), null=True, blank=True
    )
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)
    completed_at = models.DateTimeField(_('Completed'), null=True, blank=True)
    is_route_audio = models.BooleanField(_('Route-level audio'), default=False)

    class Meta:
        verbose_name = _('Audio generation')
        verbose_name_plural = _('Audio generations')
        ordering = ['-created_at']

    def __str__(self):
        return f'Audio for point {self.point.id} ({self.status})'
