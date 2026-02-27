import logging
import time
from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class TTSConfig:
    def __init__(
        self,
        text: str,
        language: str = 'ru',
        voice_type: str = 'alloy',
        expressiveness: int = 50,
        voice: str | None = None,
        emotion: str = 'neutral',
        speed: float = 1.0,
        pitch: int = 0,
        audio_format: str = 'mp3',
        sample_rate: int = 48000,
    ):
        self.text = text
        self.language = language
        self.voice_type = voice_type
        self.expressiveness = expressiveness
        self.voice = voice
        self.emotion = emotion
        self.speed = speed
        self.pitch = pitch
        self.format = audio_format
        self.sample_rate = sample_rate


class TTSService:
    def __init__(self):
        self.api_key = settings.YANDEX_API_KEY
        self.folder_id = settings.YANDEX_FOLDER_ID

        if not self.api_key or self.api_key == 'your-yandex-key-here':
            raise ImproperlyConfigured(
                'YANDEX_API_KEY is not configured. '
                'Add to settings.py: '
                "YANDEX_API_KEY = 'your_yandex_cloud_api_key'"
            )

        self.lang_voice_map = {
            'ru': {'lang': 'ru-RU', 'voice': 'filipp'},
            'kk': {'lang': 'kk-KZ', 'voice': 'madim'},
            'uz': {'lang': 'uz-UZ', 'voice': 'yulduz'},
            'en': {'lang': 'en-US', 'voice': 'john'},
            'de': {'lang': 'de-DE', 'voice': 'lea'},
            'he': {'lang': 'he-IL', 'voice': 'naomi'},
        }

        self.voice_mapping = {
            'Filipp': 'filipp',
            'Ermil': 'ermil',
            'Zahar': 'zahar',
            'Dasha': 'dasha',
            'Julia': 'yuliya',
            'Lera': 'lera',
            'Marina': 'marina',
            'Alexander': 'alexander',
            'Kirill': 'kirill',
            'Anton': 'anton',
            'Masha': 'mary',
            'Zhanar': 'zhanar',
            'Saule': 'saule',
            'Madi': 'madim',
            'Amira': 'amira',
            'Yuldus': 'yulduz',
            'Nigora': 'nigora',
            'Zamira': 'zamira',
            'John': 'john',
            'Lea': 'lea',
            'Naomi': 'naomi',
            'Jane': 'jane',
            'Omazh': 'omazh',
            'Madis': 'madis',
            'Alyss': 'alyss',
            'Lena': 'lena',
            'Maor': 'maor',
        }

        self.voice_type_map = {
            'male_guide_ru': 'filipp',
            'female_guide_ru': 'jane',
            'storyteller_ru': 'filipp',
            'expert_ru': 'zahar',
            'alloy': 'ermil',
            'echo': 'filipp',
            'nova': 'jane',
        }

    def generate_audio_with_config(
        self, config: TTSConfig
    ) -> tuple[bytes, float]:
        lang_info = self.lang_voice_map.get(
            config.language, self.lang_voice_map['ru']
        )

        voice = config.voice or self.voice_type_map.get(config.voice_type)

        if voice and voice in self.voice_mapping:
            final_voice = self.voice_mapping[voice]
        else:
            final_voice = lang_info['voice']

        data = {
            'text': config.text,
            'lang': lang_info['lang'],
            'voice': final_voice,
            'format': config.format,
            'sampleRateHertz': config.sample_rate,
            'emotion': config.emotion,
            'speed': str(config.speed),
        }

        if config.pitch != 0:
            data['pitch'] = str(config.pitch)

        return self._make_tts_request(data, lang_info['lang'], final_voice)

    def generate_audio(
        self,
        text: str,
        language: str = 'ru',
        voice_type: str = 'alloy',
        expressiveness: int = 50,
        **kwargs,
    ) -> tuple[bytes, float]:
        voice = kwargs.get('voice')
        emotion = kwargs.get('emotion', 'neutral')
        speed = float(kwargs.get('speed', 1.0))
        pitch = int(kwargs.get('pitch', 0))
        audio_format = kwargs.get('format', 'mp3')
        sample_rate = int(kwargs.get('sample_rate', 48000))

        config = TTSConfig(
            text=text,
            language=language,
            voice_type=voice_type,
            expressiveness=expressiveness,
            voice=voice,
            emotion=emotion,
            speed=speed,
            pitch=pitch,
            audio_format=audio_format,
            sample_rate=sample_rate,
        )

        return self.generate_audio_with_config(config)

    def _make_tts_request(
        self, data: dict[str, Any], lang: str, voice: str
    ) -> tuple[bytes, float]:
        try:
            start_time = time.time()
            response = requests.post(
                'https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize',
                headers={'Authorization': f'Api-Key {self.api_key}'},
                data=data,
                timeout=30,
            )

            if response.status_code != 200:
                raise Exception(
                    f'Yandex TTS error ({response.status_code}): '
                    f'{response.text[:500]}'
                )

            audio_content = response.content
            processing_time = time.time() - start_time
            logger.info(
                f'Yandex TTS: generated in {processing_time:.2f}s, '
                f'lang={lang}, voice={voice}'
            )
            return audio_content, processing_time

        except Exception as e:
            logger.error(f'Yandex TTS error: {e}')
            raise
