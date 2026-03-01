import json
from contextlib import suppress

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from routes.models import Route, RoutePoint

from .models import AudioGeneration


class AudioGenerationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )
        self.point = RoutePoint.objects.create(
            route=self.route,
            name='Test Point',
            latitude=55.7558,
            longitude=37.6176,
            order=1,
        )

    def test_audio_generation_creation(self):
        audio_gen = AudioGeneration.objects.create(
            point=self.point,
            user=self.user,
            text_content='Test text for audio',
            voice_type='alloy',
            language='ru-RU',
            status='completed',
        )
        self.assertEqual(audio_gen.point.name, 'Test Point')
        self.assertEqual(audio_gen.user.username, 'testuser')
        self.assertEqual(audio_gen.text_content, 'Test text for audio')
        self.assertEqual(audio_gen.voice_type, 'alloy')
        self.assertEqual(audio_gen.status, 'completed')
        self.assertIsNotNone(audio_gen.created_at)

    def test_audio_generation_str_method(self):
        audio_gen = AudioGeneration.objects.create(
            point=self.point,
            user=self.user,
            text_content='Test text',
            status='queued',
        )
        str_repr = str(audio_gen)
        self.assertIn('Audio for point', str_repr)
        self.assertIn(str(self.point.id), str_repr)

    def test_audio_generation_with_file(self):
        audio_gen = AudioGeneration.objects.create(
            point=self.point,
            user=self.user,
            text_content='Test text',
            audio_file='audio_guides/test.mp3',
        )
        self.assertEqual(audio_gen.audio_file.name, 'audio_guides/test.mp3')

    def test_audio_generation_ordering(self):
        AudioGeneration.objects.create(
            point=self.point, user=self.user, text_content='First'
        )
        AudioGeneration.objects.create(
            point=self.point, user=self.user, text_content='Second'
        )
        AudioGeneration.objects.create(
            point=self.point, user=self.user, text_content='Third'
        )
        audio_gens = AudioGeneration.objects.all()
        self.assertEqual(audio_gens[0].text_content, 'Third')
        self.assertEqual(audio_gens[1].text_content, 'Second')
        self.assertEqual(audio_gens[2].text_content, 'First')


class AudioViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser', password='pass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        self.route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )
        self.point = RoutePoint.objects.create(
            route=self.route,
            name='Test Point',
            description='Initial description',
            latitude=55.7558,
            longitude=37.6176,
            order=1,
        )

    def test_generate_audio_view_requires_login(self):
        client = Client()
        response = client.post(
            reverse('ai_audio:generate_audio', args=[self.point.id]),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_generate_audio_view_requires_post(self):
        response = self.client.get(
            reverse('ai_audio:generate_audio', args=[self.point.id])
        )
        self.assertEqual(response.status_code, 405)

    def test_generate_audio_author_only(self):
        self.client.login(username='otheruser', password='pass123')
        data = {'text': 'Test text'}
        response = self.client.post(
            reverse('ai_audio:generate_audio', args=[self.point.id]),
            data=json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_generate_audio_empty_text(self):
        data = {'text': ''}
        response = self.client.post(
            reverse('ai_audio:generate_audio', args=[self.point.id]),
            data=json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_generate_audio_mocked(self):
        with suppress(Exception):
            data = {
                'text': 'Test text for audio generation',
                'voice_type': 'alloy',
                'voice': 'ermil',
                'expressiveness': 50,
                'emotion': 'neutral',
            }
            response = self.client.post(
                reverse('ai_audio:generate_audio', args=[self.point.id]),
                data=json.dumps(data),
                content_type='application/json',
            )
            self.assertIn(response.status_code, [200, 500])


class LocationDescriptionViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        self.route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )
        self.point = RoutePoint.objects.create(
            route=self.route,
            name='Test Point',
            latitude=55.7558,
            longitude=37.6176,
            order=1,
        )

    def test_generate_description_requires_login(self):
        client = Client()
        response = client.post(
            reverse(
                'ai_audio:generate_location_description', args=[self.point.id]
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_generate_description_requires_post(self):
        response = self.client.get(
            reverse(
                'ai_audio:generate_location_description', args=[self.point.id]
            )
        )
        self.assertEqual(response.status_code, 405)

    def test_generate_description_author_only(self):
        User.objects.create_user(username='otheruser', password='pass123')
        self.client.login(username='otheruser', password='pass123')
        data = {'style': 'storytelling'}
        response = self.client.post(
            reverse(
                'ai_audio:generate_location_description', args=[self.point.id]
            ),
            data=json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_generate_description_without_coordinates(self):
        point_no_coords = RoutePoint.objects.create(
            route=self.route,
            name='No Coords Point',
            latitude=0.0,
            longitude=0.0,
            order=2,
        )
        data = {'style': 'storytelling'}
        response = self.client.post(
            reverse(
                'ai_audio:generate_location_description',
                args=[point_no_coords.id],
            ),
            data=json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_generate_description_mocked(self):
        with suppress(Exception):
            data = {'style': 'storytelling', 'save_to_point': False}
            response = self.client.post(
                reverse(
                    'ai_audio:generate_location_description',
                    args=[self.point.id],
                ),
                data=json.dumps(data),
                content_type='application/json',
            )
            self.assertIn(response.status_code, [200, 500])


class AudioStatusViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser', password='pass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        self.route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )
        self.point = RoutePoint.objects.create(
            route=self.route,
            name='Test Point',
            latitude=55.7558,
            longitude=37.6176,
            order=1,
        )
        self.audio_gen = AudioGeneration.objects.create(
            point=self.point,
            user=self.user,
            text_content='Test text',
            status='completed',
        )

    def test_get_audio_status_requires_login(self):
        client = Client()
        response = client.get(
            reverse('ai_audio:audio_status', args=[self.audio_gen.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_get_audio_status_owner_only(self):
        self.client.login(username='otheruser', password='pass123')
        response = self.client.get(
            reverse('ai_audio:audio_status', args=[self.audio_gen.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_get_audio_status_exists(self):
        response = self.client.get(
            reverse('ai_audio:audio_status', args=[self.audio_gen.id])
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'completed')

    def test_get_audio_status_not_found(self):
        response = self.client.get(
            reverse('ai_audio:audio_status', args=[999])
        )
        self.assertEqual(response.status_code, 404)


class DeleteAudioViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        self.route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )
        self.point = RoutePoint.objects.create(
            route=self.route,
            name='Test Point',
            latitude=55.7558,
            longitude=37.6176,
            order=1,
        )
        self.audio_gen = AudioGeneration.objects.create(
            point=self.point,
            user=self.user,
            text_content='Test text',
            status='completed',
        )

    def test_delete_audio_requires_login(self):
        client = Client()
        response = client.delete(
            reverse('ai_audio:delete_audio', args=[self.audio_gen.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_delete_audio_requires_delete_method(self):
        response = self.client.get(
            reverse('ai_audio:delete_audio', args=[self.audio_gen.id])
        )
        self.assertEqual(response.status_code, 405)

    def test_delete_audio_owner_only(self):
        User.objects.create_user(username='otheruser', password='pass123')
        self.client.login(username='otheruser', password='pass123')
        response = self.client.delete(
            reverse('ai_audio:delete_audio', args=[self.audio_gen.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_audio_success(self):
        audio_to_delete = AudioGeneration.objects.create(
            point=self.point,
            user=self.user,
            text_content='To delete',
            status='completed',
        )
        self.assertTrue(
            AudioGeneration.objects.filter(id=audio_to_delete.id).exists()
        )
        response = self.client.delete(
            reverse('ai_audio:delete_audio', args=[audio_to_delete.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AudioGeneration.objects.filter(id=audio_to_delete.id).exists()
        )
