import logging
import time

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class YandexGPTService:
    def __init__(self):
        self.api_key = settings.YANDEX_API_KEY
        self.folder_id = settings.YANDEX_FOLDER_ID

        if not self.api_key or self.api_key == 'your-yandex-key-here':
            raise ImproperlyConfigured(
                'YANDEX_API_KEY is not configured. '
                'Add to settings.py: YANDEX_API_KEY ='
                " 'your_yandex_cloud_api_key'"
            )

        if not self.folder_id:
            raise ImproperlyConfigured(
                'YANDEX_FOLDER_ID is not configured. '
                'Add to settings.py: YANDEX_FOLDER_ID ='
                " 'your_yandex_folder_id'"
            )

    def generate_location_description(
        self,
        lat: float,
        lng: float,
        address: str = '',
        style: str = 'storytelling',
        language: str = 'ru',
    ) -> str:
        lang_config = {
            'ru': {
                'system_intro': 'Ты профессиональный гид и экскурсовод.',
                'structure': (
                    '2. Основное описание: что это за место, его особенности\n'
                    '3. Интересные факты и история (если известны)\n'
                    '4. Что можно увидеть/сделать на месте\n'
                    '5. Советы посетителям\n'
                    '6. Завершение'
                ),
                'user_intro': 'Создай текст экскурсии о месте по координатам',
                'address_fallback': 'не указан',
                'live_guide': 'Будь естественным, говори от первого лица как'
                ' гид. Используй живую речь.',
                'length': 'Длина: 250–400 слов.',
                'style_prompts': {
                    'storytelling': 'рассказ как от живого гида',
                    'historical': 'историческое повествование с'
                    ' акцентом на историю места',
                    'touristic': 'описание для туристов с'
                    ' практической информацией',
                    'poetic': 'поэтическое и художественное описание места',
                    'scientific': 'научное и фактологическое описание',
                },
            },
            'kk': {
                'system_intro': 'Сіз кәсіби экскурсоводсыз.',
                'structure': (
                    '2. Негізгі сипаттама: бұл қандай орын,'
                    ' оның ерекшеліктері\n'
                    '3. Қызықты деректер мен тарихы (егер белгілі болса)\n'
                    '4. Осында не көруге/не істеуге болады\n'
                    '5. Туристке кеңестер\n'
                    '6. Қорытынды'
                ),
                'user_intro': 'Координаталары бойынша орның экскурсия'
                ' мәтінін жасаңыз',
                'address_fallback': 'көрсетілмеген',
                'live_guide': 'Табиғи болыңыз, гид ретінде бірінші жақтан'
                ' сөйлеңіз. Тартымды тіл қолданыңыз.',
                'length': 'Ұзындығы: 250–400 сөз.',
                'style_prompts': {
                    'storytelling': 'тікелей гидтен айтылған әңгіме',
                    'historical': 'орның тарихына назар аударатын'
                    ' тарихи әңгіме',
                    'touristic': 'тәжірибелік ақпараты бар туристік сипаттама',
                    'poetic': 'поэтикалық және көркем сипаттама',
                    'scientific': 'ғылыми және фактологиялық сипаттама',
                },
            },
            'uz': {
                'system_intro': "Siz professional ekskursiya o'tkazuvchisiz.",
                'structure': (
                    '2. Asosiy tavsif: bu qanday joy, uning xususiyatlari\n'
                    "3. Qiziqarli faktlar va tarixi (agar ma’lum bo'lsa)\n"
                    "4. Bu yerda nima ko'rish/kilish mumkin\n"
                    '5. Tashrif buyuruvchilar uchun maslahatlar\n'
                    '6. Xulosa'
                ),
                'user_intro': "Koordinatalar bo'yicha joy haqida ekskursiya"
                ' matnini yarating',
                'address_fallback': "ko'rsatilmagan",
                'live_guide': "Tabiiy bo'ling, gid sifatida birinchi shaxsda"
                " gapiring. Jo'shqin til ishlating.",
                'length': "Uzunligi: 250–400 so'z.",
                'style_prompts': {
                    'storytelling': 'tirik gid sifatida hikoya qilish',
                    'historical': "joyning tarixiga e'tibor qaratuvchi"
                    ' tarixiy hikoya',
                    'touristic': "amaliy ma'lumotli sayyohlik tavsifi",
                    'poetic': "she'riy va san'atli tavsif",
                    'scientific': 'ilmiy va faktologik tavsif',
                },
            },
            'en': {
                'system_intro': 'You are a professional tour guide.',
                'structure': (
                    '2. Main description: what this place is, its key'
                    ' features\n'
                    '3. Interesting facts and history (if known)\n'
                    '4. What to see or do here\n'
                    '5. Tips for visitors\n'
                    '6. Conclusion'
                ),
                'user_intro': 'Create a tour guide text for the location with'
                ' these coordinates',
                'address_fallback': 'not specified',
                'live_guide': 'Be natural, speak in first person as a guide.'
                ' Use engaging language.',
                'length': 'Length: 250–400 words.',
                'style_prompts': {
                    'storytelling': 'a storytelling narration as if from'
                    ' a live guide',
                    'historical': 'historical narrative focusing on'
                    ' the place’s history',
                    'touristic': 'practical tourist-oriented description',
                    'poetic': 'poetic and artistic description of the'
                    ' location',
                    'scientific': 'scientific and factual description',
                },
            },
            'de': {
                'system_intro': 'Sie sind ein professioneller Reiseführer.',
                'structure': (
                    '2. Hauptbeschreibung: Was ist dieser Ort, seine'
                    ' Merkmale\n'
                    '3. Interessante Fakten und Geschichte (falls bekannt)\n'
                    '4. Was man hier sehen oder unternehmen kann\n'
                    '5. Tipps für Besucher\n'
                    '6. Fazit'
                ),
                'user_intro': 'Erstellen Sie einen Reiseführer-Text für den'
                ' Ort mit diesen Koordinaten',
                'address_fallback': 'nicht angegeben',
                'live_guide': 'Seien Sie natürlich, sprechen Sie in der'
                ' ersten Person als Guide. Verwenden Sie'
                ' ansprechende Sprache.',
                'length': 'Länge: 250–400 Wörter.',
                'style_prompts': {
                    'storytelling': 'erzählender Stil wie von einem'
                    ' Live-Guide',
                    'historical': 'historische Erzählung mit Fokus auf die'
                    ' Geschichte des Ortes',
                    'touristic': 'praktische touristische Beschreibung',
                    'poetic': 'poetische und künstlerische Beschreibung',
                    'scientific': 'wissenschaftliche und faktenbasierte'
                    ' Beschreibung',
                },
            },
            'he': {
                'system_intro': 'אתה מדריך מקצועי.',
                'structure': (
                    '2. תיאור עיקרי: מה המקום הזה, התכונות הבולטות שלו\n'
                    '3. עובדות מעניינות והיסטוריה (אם ידוע)\n'
                    '4. מה ניתן לראות או לעשות במקום\n'
                    '5. טיפים למטיילים\n'
                    '6. סיכום'
                ),
                'user_intro': 'צור טקסט הדרכה למיקום עם הקואורדינטות האלו',
                'address_fallback': 'לא צוין',
                'live_guide': 'דבוק בסגנון טבעי, '
                'דבר בגוף ראשון כמדריך. השתמש בשפה חיה.',
                'length': 'אורך: 250–400 מילים.',
                'style_prompts': {
                    'storytelling': 'סיפור בסגנון מדריך חי',
                    'historical': 'סיפור היסטורי עם דגש על ההיסטוריה של המקום',
                    'touristic': 'תיאור תיירותי עם מידע מעשי',
                    'poetic': 'תיאור שירי ואמנותי',
                    'scientific': 'תיאור מדעי ומבוסס עובדות',
                },
            },
        }

        config = lang_config.get(language, lang_config['ru'])
        style_desc = config['style_prompts'].get(
            style, config['style_prompts']['storytelling']
        )

        system_prompt = (
            f'{config["system_intro"]} Create an engaging tour guide text'
            f' about this location in the style of {style_desc}.\n\n'
            f'{config["structure"]}\n\n'
            f'{config["live_guide"]}\n'
            f'{config["length"]}'
        )

        user_prompt = (
            f'{config["user_intro"]}:\n'
            f'Latitude: {lat}\n'
            f'Longitude: {lng}\n'
            f'Address:'
            f' {address if address else config["address_fallback"]}\n\n'
            'If a specific address is known, use it for a'
            ' more accurate description.\n'
            "If it's a famous landmark, describe its"
            ' history and significance.\n'
            "If it's an ordinary location, describe its"
            ' atmosphere and surroundings.\n\n'
            'Important: Make the text lively and engaging,'
            ' as if a guide is giving a live tour right here!'
        )

        try:
            start_time = time.time()
            response = requests.post(
                'https://llm.api.cloud.yandex.'
                'net/foundationModels/v1/completion',
                headers={
                    'Authorization': f'Api-Key {self.api_key}',
                    'x-folder-id': self.folder_id,
                    'Content-Type': 'application/json',
                },
                json={
                    'modelUri': f'gpt://{self.folder_id}/yandexgpt/latest',
                    'completionOptions': {
                        'stream': False,
                        'temperature': 0.7,
                        'maxTokens': 2000,
                    },
                    'messages': [
                        {'role': 'system', 'text': system_prompt},
                        {'role': 'user', 'text': user_prompt},
                    ],
                },
                timeout=30,
            )

            if response.status_code != 200:
                raise Exception(
                    f'Yandex GPT error'
                    f' ({response.status_code}): {response.text[:200]}'
                )

            result = response.json()
            generated_text = result['result']['alternatives'][0]['message'][
                'text'
            ]
            processing_time = time.time() - start_time
            logger.info(
                f'Yandex GPT: generated in {processing_time:.2f}s,'
                f' {len(generated_text)} chars, lang={language}'
            )
            return generated_text

        except Exception as e:
            logger.error(f'Yandex GPT error: {e}')
            return self._generate_fallback_description(
                lat, lng, address, style, language
            )

    def _generate_fallback_description(
        self,
        lat: float,
        lng: float,
        address: str,
        style: str,
        language: str = 'ru',
    ) -> str:
        coord_text = {
            'ru': f'Координаты: {lat:.6f}, {lng:.6f}',
            'kk': f'Координаталар: {lat:.6f}, {lng:.6f}',
            'uz': f'Koordinatalar: {lat:.6f}, {lng:.6f}',
            'en': f'Coordinates: {lat:.6f}, {lng:.6f}',
            'de': f'Koordinaten: {lat:.6f}, {lng:.6f}',
            'he': f'קואורדינטות: {lat:.6f}, {lng:.6f}',
        }.get(language, f'Coordinates: {lat:.6f}, {lng:.6f}')

        location_text = {
            'ru': (
                f'Это место находится по адресу: {address}'
                if address
                else 'Это интересное место с живописными окрестностями.'
            ),
            'kk': (
                f'Бұл орын: {address}'
                if address
                else 'Бұл қызықты жер, айналасы көркем.'
            ),
            'uz': (
                f'Bu joy manzili: {address}'
                if address
                else "Bu qiziqarli joy, atrofi go'zal."
            ),
            'en': (
                f'This location is at: {address}'
                if address
                else 'This is an interesting location'
                ' with scenic surroundings.'
            ),
            'de': (
                f'Dieser Ort befindet sich unter: {address}'
                if address
                else 'Dies ist ein interessanter Ort mit malerischer Umgebung.'
            ),
            'he': (
                f'המיקום הזה הוא ב: {address}'
                if address
                else 'זהו מקום מעניין עם סביבה ציורית.'
            ),
        }.get(
            language,
            (
                f'This location is at: {address}'
                if address
                else 'Interesting scenic location.'
            ),
        )

        descriptions = {
            'ru': {
                'storytelling': f"""Приветствую вас на этой уникальной
                 локации! Меня зовут Матвей, и я буду вашим гидом сегодня.

{location_text} {coord_text}

Представьте, что мы стоим прямо здесь...""",
                'historical': f"""Место с координатами {coord_text}
                 имеет свою историю и значение.

{location_text}

Исторический контекст этой локации уходит корнями в прошлое...""",
                'touristic': f"""Туристическая точка: {coord_text}

{location_text}

Для путешественников это место предлагает...""",
                'poetic': f"""Здесь, на {coord_text},
                 время замедляет свой бег...

{location_text}

Каждый камень, каждый изгиб ландшафта хранит свою историю...""",
            },
            'en': {
                'storytelling': f"""Welcome to this unique location! My
                 name is Matvey, and I’ll be your guide today.

{location_text} {coord_text}

Imagine we’re standing right here...""",
                'historical': f"""The location at {coord_text}
                 has its own history and significance.

{location_text}

Its historical context dates back centuries...""",
                'touristic': f"""Tourist point: {coord_text}

{location_text}

This spot offers travelers...""",
                'poetic': f"""Here, at {coord_text}, time slows down...

{location_text}

Every stone, every curve of the landscape holds a story...""",
            },
        }

        lang_desc = descriptions.get(language, descriptions['ru'])
        return lang_desc.get(style, lang_desc['storytelling'])
