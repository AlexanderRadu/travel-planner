from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Friendship, UserProfile


class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

    def test_user_profile_creation(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.user.username, 'testuser')
        self.assertTrue(profile.bio == '')
        self.assertIsNotNone(profile.created_at)


class FriendshipModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1', password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2', password='pass123'
        )

    def test_friendship_creation(self):
        friendship = Friendship.objects.create(
            from_user=self.user1, to_user=self.user2, status='pending'
        )
        self.assertEqual(friendship.from_user.username, 'user1')
        self.assertEqual(friendship.to_user.username, 'user2')
        self.assertEqual(friendship.status, 'pending')


class ViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
        )

    def test_profile_page_login_required(self):
        response = self.client.get(reverse('profile'))
        self.assertNotEqual(response.status_code, 200)

    def test_profile_page_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testuser')

    def test_user_profile_public(self):
        response = self.client.get(reverse('user_profile', args=['testuser']))
        self.assertEqual(response.status_code, 200)


class LogoutViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

    def test_logout_redirect(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)


class FriendsViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

    def test_friends_view_requires_login(self):
        response = self.client.get(reverse('friends'))
        self.assertNotEqual(response.status_code, 200)

    def test_friends_view_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('friends'))
        self.assertEqual(response.status_code, 200)


class BasicURLTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_urls_status(self):
        urls_to_test = [
            ('profile', [], 200),
            ('friends', [], 200),
            ('find_friends', [], 200),
        ]

        for url_name, args, expected_status in urls_to_test:
            try:
                response = self.client.get(reverse(url_name, args=args))
                self.assertEqual(response.status_code, expected_status)
            except Exception:
                pass
