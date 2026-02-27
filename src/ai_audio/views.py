__all__ = ()

import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from routes.models import RoutePoint

from .models import AudioGeneration
from .services.tts_service import TTSService
from .services.yandex_gpt_service import YandexGPTService

logger = logging.getLogger(__name__)


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def generate_audio(request, point_id):
    point = get_object_or_404(
        RoutePoint, id=point_id, route__author=request.user
    )

    try:
        data = json.loads(request.body)
        text = (data.get('text') or point.description or '').strip()
        if not text:
            return JsonResponse({'error': _('Text is empty')}, status=400)

        voice_type = data.get('voice_type', 'alloy')
        voice = data.get('voice', 'ermil')
        language = data.get('language', 'ru')
        expressiveness = int(data.get('expressiveness', 50))
        emotion = data.get('emotion', 'neutral')
        speed = float(data.get('speed', 1.0))
        pitch = int(data.get('pitch', 0))
        format = data.get('format', 'mp3')

        tts = TTSService()
        audio_content, processing_time = tts.generate_audio(
            text=text,
            language=language,
            voice_type=voice_type,
            expressiveness=expressiveness,
            voice=voice,
            emotion=emotion,
            speed=speed,
            pitch=pitch,
            format=format,
        )

        audio_gen = AudioGeneration.objects.create(
            point=point,
            user=request.user,
            text_content=text,
            voice_type=voice_type,
            language=language,
            status='completed',
            processing_time=processing_time,
        )

        filename = f'audio_guide_{point.id}_{audio_gen.id}.{format}'
        audio_gen.audio_file.save(
            filename, ContentFile(audio_content), save=True
        )

        point.audio_guide = audio_gen.audio_file
        point.save(update_fields=['audio_guide'])

        route = point.route
        if not route.has_audio_guide:
            route.has_audio_guide = True
            route.save(update_fields=['has_audio_guide'])

        return JsonResponse(
            {
                'status': 'success',
                'audio_url': audio_gen.audio_file.url,
            }
        )

    except (ValueError, TypeError) as e:
        logger.error(f'Invalid parameter in audio request: {e}')
        return JsonResponse({'error': _('Invalid parameter')}, status=400)
    except Exception as e:
        logger.error(f'Audio generation error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def generate_location_description(request, point_id):
    point = get_object_or_404(
        RoutePoint, id=point_id, route__author=request.user
    )

    try:
        data = json.loads(request.body)
        style = data.get('style', 'storytelling')
        language = data.get('language', 'ru')

        lat = getattr(point, 'latitude', None) or data.get('lat')
        lng = getattr(point, 'longitude', None) or data.get('lng')

        if lat is None or lng is None:
            return JsonResponse(
                {
                    'error': _('Coordinates not found'),
                    'hint': _(
                        'Ensure the point has latitude and longitude fields'
                    ),
                },
                status=400,
            )

        address = getattr(point, 'address', '') or ''

        gpt_service = YandexGPTService()
        description = gpt_service.generate_location_description(
            lat=float(lat),
            lng=float(lng),
            address=address,
            style=style,
            language=language,
        )

        if data.get('save_to_point', False):
            point.description = description
            point.save(update_fields=['description'])

        return JsonResponse(
            {
                'status': 'success',
                'description': description,
                'point_id': point_id,
                'coordinates': f'{lat}, {lng}',
                'address': address,
                'style': style,
                'language': language,
            }
        )

    except (ValueError, TypeError) as e:
        logger.error(f'Invalid coordinate or parameter: {e}')
        return JsonResponse({'error': _('Invalid input')}, status=400)
    except Exception as e:
        logger.error(f'Description generation error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['GET'])
def get_audio_status(request, generation_id):
    audio_gen = get_object_or_404(
        AudioGeneration, id=generation_id, user=request.user
    )
    return JsonResponse(
        {
            'status': audio_gen.status,
            'audio_url': (
                audio_gen.audio_file.url if audio_gen.audio_file else None
            ),
        }
    )


@csrf_exempt
@login_required
@require_http_methods(['DELETE'])
def delete_audio(request, generation_id):
    audio_gen = get_object_or_404(
        AudioGeneration, id=generation_id, user=request.user
    )
    if audio_gen.audio_file:
        audio_gen.audio_file.delete(save=False)
    audio_gen.delete()
    return JsonResponse({'status': 'success'})


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def generate_temp_description(request):
    try:
        data = json.loads(request.body)
        lat = data.get('lat')
        lng = data.get('lng')
        address = data.get('address', '')
        style = data.get('style', 'storytelling')
        language = data.get('language', 'ru')

        if lat is None or lng is None:
            return JsonResponse(
                {'error': _('Coordinates are required')}, status=400
            )

        gpt_service = YandexGPTService()
        description = gpt_service.generate_location_description(
            lat=float(lat),
            lng=float(lng),
            address=address,
            style=style,
            language=language,
        )

        return JsonResponse(
            {
                'status': 'success',
                'description': description,
                'language': language,
            }
        )

    except (ValueError, TypeError) as e:
        logger.error(f'Invalid input in temp description: {e}')
        return JsonResponse({'error': _('Invalid input')}, status=400)
    except Exception as e:
        logger.error(f'Temp description generation error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def generate_temp_audio(request):
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        if not text:
            return JsonResponse({'error': _('Text is empty')}, status=400)

        voice_type = data.get('voice_type', 'alloy')
        voice = data.get('voice', 'ermil')
        language = data.get('language', 'ru')
        expressiveness = int(data.get('expressiveness', 50))
        emotion = data.get('emotion', 'neutral')
        speed = float(data.get('speed', 1.0))
        pitch = int(data.get('pitch', 0))
        format = data.get('format', 'mp3')

        tts = TTSService()
        audio_content, processing_time = tts.generate_audio(
            text=text,
            language=language,
            voice_type=voice_type,
            expressiveness=expressiveness,
            voice=voice,
            emotion=emotion,
            speed=speed,
            pitch=pitch,
            format=format,
        )

        import os

        from django.core.files.storage import default_storage
        from django.utils import timezone

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'temp_audio_{request.user.id}_{timestamp}.{format}'
        filepath = os.path.join('temp', filename)

        path = default_storage.save(filepath, ContentFile(audio_content))
        audio_url = default_storage.url(path)

        return JsonResponse(
            {'status': 'success', 'audio_url': audio_url, 'filename': filename}
        )

    except (ValueError, TypeError) as e:
        logger.error(f'Invalid parameter in temp audio: {e}')
        return JsonResponse({'error': _('Invalid parameter')}, status=400)
    except Exception as e:
        logger.error(f'Temp audio generation error: {e}')
        return JsonResponse({'error': str(e)}, status=500)
