__all__ = ()
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files import File
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class Route(models.Model):
    PRIVACY_CHOICES = [
        ('public', _('Public')),
        ('private', _('Private')),
        ('link', _('Link-only')),
        ('personal', _('Personal')),
    ]

    ROUTE_TYPE_CHOICES = [
        ('driving', _('Driving')),
        ('walking', _('Walking')),
        ('cycling', _('Cycling')),
        ('mixed', _('Mixed')),
    ]

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='routes',
        verbose_name=_('Author'),
    )
    name = models.CharField(_('Name'), max_length=200)
    description = models.TextField(_('Description'), blank=True)
    short_description = models.TextField(
        _('Short description'), max_length=300, blank=True
    )
    privacy = models.CharField(
        _('Privacy'), max_length=20, choices=PRIVACY_CHOICES, default='public'
    )
    route_type = models.CharField(
        _('Route type'),
        max_length=20,
        choices=ROUTE_TYPE_CHOICES,
        default='walking',
    )
    duration_minutes = models.IntegerField(_('Duration (minutes)'), default=0)
    duration_display = models.CharField(
        _('Display duration'),
        max_length=100,
        blank=True,
        help_text=_('e.g. 2-3 hours, 1 day, 30 minutes'),
    )
    country = models.CharField(
        _('Country'),
        max_length=100,
        blank=True,
    )
    total_distance = models.FloatField(_('Total distance (km)'), default=0)
    is_active = models.BooleanField(_('Active'), default=True)
    has_audio_guide = models.BooleanField(_('Has audio guide'), default=False)
    is_elderly_friendly = models.BooleanField(
        _('Elderly-friendly'), default=False
    )
    shared_with = models.ManyToManyField(
        User,
        related_name='shared_routes',
        blank=True,
        verbose_name=_('Shared with'),
    )
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated'), auto_now=True)
    last_status_update = models.DateTimeField(
        _('Last status update'), auto_now=True
    )
    qr_code = models.ImageField(
        _('QR code'), upload_to='qr_codes/', blank=True, null=True
    )

    class Meta:
        verbose_name = _('Route')
        verbose_name_plural = _('Routes')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} (ID: {self.id})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('route_detail', kwargs={'route_id': self.id})

    def generate_qr_code(self, request=None):
        if self.qr_code:
            return self.qr_code.url

        if request:
            full_url = request.build_absolute_uri(self.get_absolute_url())
        else:
            domain = getattr(settings, 'DOMAIN', 'http://localhost:8000')
            full_url = f'{domain}{self.get_absolute_url()}'

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(full_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        filename = f'qr_code_route_{self.id}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        self.save(update_fields=['qr_code'])
        return self.qr_code.url

    def get_average_rating(self):
        from django.db.models import Avg

        from interactions.models import Rating

        result = Rating.objects.filter(route=self).aggregate(
            average=Avg('score')
        )
        return result['average'] or 0

    def get_ratings_count(self):
        from interactions.models import Rating

        return Rating.objects.filter(route=self).count()

    @property
    def interaction_comments(self):
        from interactions.models import Comment

        return Comment.objects.filter(route=self)

    @property
    def interaction_ratings(self):
        from interactions.models import Rating

        return Rating.objects.filter(route=self)

    @property
    def favorites_by(self):
        from interactions.models import Favorite

        return Favorite.objects.filter(route=self)


class RoutePhoto(models.Model):
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name=_('Route'),
    )
    image = models.ImageField(_('Photo'), upload_to='route_photos/')
    caption = models.CharField(_('Caption'), max_length=255, blank=True)
    is_main = models.BooleanField(_('Main photo'), default=False)
    order = models.PositiveIntegerField(_('Order'), default=0)
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)

    class Meta:
        verbose_name = _('Route photo')
        verbose_name_plural = _('Route photos')
        ordering = ['order']

    def __str__(self):
        return f'Photo for {self.route.name}'


class RouteRating(models.Model):
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name=_('Route'),
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_('User')
    )
    rating = models.IntegerField(
        _('Rating'), validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(_('Comment'), blank=True)
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)

    class Meta:
        verbose_name = _('Route rating')
        verbose_name_plural = _('Route ratings')
        unique_together = ['route', 'user']

    def __str__(self):
        return f'{self.rating}★ for {self.route.name}'


class RouteFavorite(models.Model):
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name=_('Route'),
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_('User')
    )
    created_at = models.DateTimeField(_('Added'), auto_now_add=True)

    class Meta:
        verbose_name = _('Favorite route')
        verbose_name_plural = _('Favorite routes')
        unique_together = ['route', 'user']

    def __str__(self):
        return f'{self.user.username} → {self.route.name}'


class RoutePoint(models.Model):
    CATEGORY_CHOICES = [
        ('attraction', _('Attraction')),
        ('nature', _('Natural')),
        ('forest', _('Forest')),
        ('bus_stop', _('Bus stop')),
        ('viewpoint', _('Viewpoint')),
        ('restaurant', _('Restaurant')),
        ('hotel', _('Hotel')),
        ('museum', _('Museum')),
        ('park', _('Park')),
        ('monument', _('Monument')),
        ('church', _('Church')),
        ('beach', _('Beach')),
    ]

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='points',
        verbose_name=_('Route'),
    )
    name = models.CharField(_('Name'), max_length=200)
    description = models.TextField(_('Description'), blank=True)
    address = models.TextField(_('Address'), blank=True)
    latitude = models.FloatField(
        _('Latitude'),
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
    )
    longitude = models.FloatField(
        _('Longitude'),
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
    )
    elevation = models.FloatField(_('Elevation'), null=True, blank=True)
    category = models.CharField(
        _('Category'), max_length=20, choices=CATEGORY_CHOICES, blank=True
    )
    hint_author = models.CharField(
        _('Hint author'), max_length=100, blank=True
    )
    tags = models.JSONField(_('Tags'), default=list, blank=True)
    order = models.PositiveIntegerField(_('Order'), default=0)
    has_panorama = models.BooleanField(_('Has panorama'), default=False)
    audio_guide = models.FileField(
        _('Audio guide'), upload_to='point_audio/', blank=True, null=True
    )
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)

    class Meta:
        verbose_name = _('Route point')
        verbose_name_plural = _('Route points')
        ordering = ['order']

    def __str__(self):
        return f'{self.name} (lat: {self.latitude}, lng: {self.longitude})'


class PointPhoto(models.Model):
    point = models.ForeignKey(
        RoutePoint,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name=_('Route point'),
    )
    image = models.ImageField(_('Photo'), upload_to='point_photos/')
    caption = models.CharField(_('Caption'), max_length=255, blank=True)
    order = models.PositiveIntegerField(_('Order'), default=0)
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)

    class Meta:
        verbose_name = _('Point photo')
        verbose_name_plural = _('Point photos')
        ordering = ['order']

    def __str__(self):
        return f'Photo for {self.point.name}'


class PointComment(models.Model):
    point = models.ForeignKey(
        RoutePoint,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Point'),
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_('User')
    )
    text = models.TextField(_('Comment text'))
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated'), auto_now=True)

    class Meta:
        verbose_name = _('Point comment')
        verbose_name_plural = _('Point comments')
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.user.username} for {self.point.name}'


class RouteComment(models.Model):
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Route'),
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_('User')
    )
    text = models.TextField(_('Comment text'))
    created_at = models.DateTimeField(_('Created'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated'), auto_now=True)

    class Meta:
        verbose_name = _('Route comment')
        verbose_name_plural = _('Route comments')
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.user.username} for {self.route.name}'


class UserVisitedPoint(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='visited_points',
        verbose_name=_('User'),
    )
    point = models.ForeignKey(
        RoutePoint, on_delete=models.CASCADE, verbose_name=_('Point')
    )
    visited_at = models.DateTimeField(_('Visited at'), auto_now_add=True)

    class Meta:
        verbose_name = _('Visited point')
        verbose_name_plural = _('Visited points')
        unique_together = ['user', 'point']

    def __str__(self):
        return f'{self.user.username} visited {self.point.name}'
