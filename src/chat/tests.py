import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from chat.models import Conversation, PrivateMessage, RouteChat
from routes.models import Route


class ChatModelsTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='alice', password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='bob', password='pass123'
        )
        self.route = Route.objects.create(
            name='Test Route',
            author=self.user1,
            privacy='public',
            is_active=True,
        )

    def test_private_message_str(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.user1, self.user2)
        msg = PrivateMessage.objects.create(
            conversation=conv, sender=self.user1, content='Hello world!' * 20
        )
        self.assertTrue(len(str(msg)) > 0)
        self.assertIn('Hello world!', str(msg))

    def test_route_chat_created_on_route_save(self):
        self.assertTrue(RouteChat.objects.filter(route=self.route).exists())

    def test_route_chat_str(self):
        chat = self.route.chat
        self.assertIn(self.route.name, str(chat))

    def test_get_other_participant(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.user1, self.user2)
        self.assertEqual(conv.get_other_participant(self.user1), self.user2)
        self.assertEqual(conv.get_other_participant(self.user2), self.user1)

    def test_get_unread_count(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.user1, self.user2)
        PrivateMessage.objects.create(
            conversation=conv, sender=self.user1, content='Hi'
        )
        self.assertEqual(conv.get_unread_count(self.user2), 1)
        self.assertEqual(conv.get_unread_count(self.user1), 0)


class ChatViewsTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='alice', password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='bob', password='pass123'
        )
        self.user3 = User.objects.create_user(
            username='charlie', password='pass123'
        )

        self.route_public = Route.objects.create(
            name='Public Route',
            author=self.user1,
            privacy='public',
            is_active=True,
        )
        self.route_private = Route.objects.create(
            name='Private Route',
            author=self.user1,
            privacy='private',
            is_active=True,
        )
        self.route_private.shared_with.add(self.user2)

        self.client = Client()

    def login(self, user):
        self.client.login(username=user.username, password='pass123')

    def test_chat_dashboard_requires_login(self):
        response = self.client.get(reverse('chat:chat_dashboard'))
        self.assertNotEqual(response.status_code, 200)

    def test_send_private_message_to_self_fails(self):
        self.login(self.user1)
        response = self.client.post(
            reverse('chat:send_private_message'),
            json.dumps({'user_id': self.user1.id, 'message': 'Hi'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('yourself', data['error'])

    def test_send_private_message_success(self):
        self.login(self.user1)
        response = self.client.post(
            reverse('chat:send_private_message'),
            json.dumps({'user_id': self.user2.id, 'message': 'Hello Bob!'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(PrivateMessage.objects.count(), 1)

    def test_delete_conversation_removes_user_and_deletes_if_empty(self):
        conv = Conversation.objects.create()
        conv.participants.add(self.user1, self.user2)

        self.login(self.user1)
        self.client.post(reverse('chat:delete_conversation', args=[conv.id]))
        conv.refresh_from_db()
        self.assertEqual(conv.participants.count(), 1)
        self.assertIn(self.user2, conv.participants.all())

        self.login(self.user2)
        self.client.post(reverse('chat:delete_conversation', args=[conv.id]))
        self.assertFalse(Conversation.objects.filter(id=conv.id).exists())

    def test_cache_cleared_on_message_send(self):
        cache_key = f'chat_dashboard_{self.user1.id}'
        cache.set(cache_key, {'cached': True}, 60)
        self.assertTrue(cache.get(cache_key))

        self.login(self.user1)
        self.client.post(
            reverse('chat:send_private_message'),
            json.dumps({'user_id': self.user2.id, 'message': 'Test'}),
            content_type='application/json',
        )
        self.assertIsNone(cache.get(cache_key))
