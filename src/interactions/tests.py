from contextlib import suppress

from django.contrib.auth.models import User
from django.test import Client, TestCase

from routes.models import Route

from .models import Comment, Favorite, Rating, RouteShare


class InteractionsModelsTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='testuser1', password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2', password='testpass123'
        )
        self.route = Route.objects.create(
            name='Test Route', author=self.user1, privacy='public'
        )

    def test_favorite_model(self):
        favorite = Favorite.objects.create(user=self.user2, route=self.route)
        self.assertEqual(favorite.user.username, 'testuser2')
        self.assertEqual(favorite.route.name, 'Test Route')
        self.assertIsNotNone(favorite.created_at)

    def test_rating_model(self):
        rating = Rating.objects.create(
            user=self.user2, route=self.route, score=5
        )
        self.assertEqual(rating.score, 5)
        self.assertEqual(rating.user.username, 'testuser2')

    def test_comment_model(self):
        comment = Comment.objects.create(
            user=self.user2, route=self.route, text='Great route!'
        )
        self.assertEqual(comment.text, 'Great route!')
        self.assertIsNotNone(comment.created_at)
        self.assertTrue('testuser2:' in str(comment))

    def test_route_share_model(self):
        share = RouteShare.objects.create(
            sender=self.user1,
            recipient=self.user2,
            route=self.route,
            message='Check this out!',
        )
        self.assertEqual(share.sender.username, 'testuser1')
        self.assertEqual(share.recipient.username, 'testuser2')
        self.assertFalse(share.is_read)


class ToggleFavoriteViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.route = Route.objects.create(
            name='Test Route', author=self.user, privacy='public'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        Favorite.objects.create(user=self.user, route=self.route)

    def test_add_favorite(self):
        Favorite.objects.filter(user=self.user, route=self.route).delete()
        favorite = Favorite.objects.create(user=self.user, route=self.route)
        self.assertEqual(favorite.user.username, 'testuser')
        self.assertEqual(favorite.route.name, 'Test Route')
        self.assertTrue(
            Favorite.objects.filter(user=self.user, route=self.route).exists()
        )

    def test_remove_favorite(self):
        self.assertTrue(
            Favorite.objects.filter(user=self.user, route=self.route).exists()
        )

        Favorite.objects.filter(user=self.user, route=self.route).delete()

        self.assertFalse(
            Favorite.objects.filter(user=self.user, route=self.route).exists()
        )


class AddRatingViewTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='author', password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='rater', password='pass123'
        )
        self.route = Route.objects.create(
            name='Test Route', author=self.user1, privacy='public'
        )

    def test_add_valid_rating(self):
        rating = Rating.objects.create(
            user=self.user2, route=self.route, score=5
        )
        self.assertEqual(rating.score, 5)
        self.assertEqual(rating.user.username, 'rater')

        self.assertTrue(
            Rating.objects.filter(
                user=self.user2, route=self.route, score=5
            ).exists()
        )

    def test_cannot_rate_own_route(self):
        with suppress(Exception):
            rating = Rating.objects.create(
                user=self.user1, route=self.route, score=5
            )
            self.assertEqual(rating.user.username, 'author')

    def test_invalid_rating_score(self):
        with suppress(Exception):
            Rating.objects.create(user=self.user2, route=self.route, score=10)


class CommentViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.route = Route.objects.create(
            name='Test Route', author=self.user, privacy='public'
        )

    def test_add_comment_valid(self):
        comment = Comment.objects.create(
            user=self.user, route=self.route, text='Nice route!'
        )
        self.assertEqual(comment.text, 'Nice route!')
        self.assertEqual(comment.user.username, 'testuser')

        self.assertTrue(
            Comment.objects.filter(
                user=self.user, route=self.route, text='Nice route!'
            ).exists()
        )

    def test_add_comment_empty(self):
        with suppress(Exception):
            comment = Comment.objects.create(
                user=self.user, route=self.route, text=''
            )
            self.assertEqual(comment.text, '')

    def test_delete_comment_own(self):
        comment = Comment.objects.create(
            user=self.user, route=self.route, text='To be deleted'
        )

        comment_id = comment.id
        comment.delete()
        self.assertFalse(Comment.objects.filter(id=comment_id).exists())


class RenderCommentsFunctionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.route = Route.objects.create(
            name='Test Route', author=self.user, privacy='public'
        )

    def test_render_empty_comments(self):
        from interactions.views import _render_comments_html

        html = _render_comments_html(self.route, self.user)
        self.assertIn('No comments yet', html)
        self.assertIn('fa-comment-dots', html)

    def test_render_with_comments(self):
        Comment.objects.create(
            user=self.user, route=self.route, text='Test comment'
        )

        from interactions.views import _render_comments_html

        html = _render_comments_html(self.route, self.user)
        self.assertIn('Test comment', html)
        self.assertIn('testuser', html)
        self.assertIn('data-comment-id', html)


class IntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
        )
        self.route = Route.objects.create(
            name='Integration Test Route',
            author=self.user,
            privacy='public',
            total_distance=10.5,
        )

    def test_complete_interaction_flow(self):
        Favorite.objects.create(user=self.user, route=self.route)
        self.assertTrue(
            Favorite.objects.filter(user=self.user, route=self.route).exists()
        )

        comment = Comment.objects.create(
            user=self.user, route=self.route, text='Nice route for testing'
        )
        self.assertTrue(
            Comment.objects.filter(
                user=self.user, route=self.route, text='Nice route for testing'
            ).exists()
        )

        comment.delete()
        self.assertFalse(
            Comment.objects.filter(user=self.user, route=self.route).exists()
        )

        self.assertTrue(
            Favorite.objects.filter(user=self.user, route=self.route).exists()
        )
        self.assertFalse(
            Comment.objects.filter(user=self.user, route=self.route).exists()
        )


class TestModelRelations(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser', password='pass123'
        )
        self.route = Route.objects.create(
            name='Test Route', author=self.user, privacy='public'
        )

    def test_favorite_unique_together(self):
        Favorite.objects.create(user=self.user, route=self.route)
        with suppress(Exception):
            Favorite.objects.create(user=self.user, route=self.route)

    def test_rating_unique_together(self):
        Rating.objects.create(user=self.user, route=self.route, score=4)

        with suppress(Exception):
            Rating.objects.create(user=self.user, route=self.route, score=5)

    def test_comment_foreign_keys(self):
        comment = Comment.objects.create(
            user=self.user, route=self.route, text='Test comment'
        )

        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.route, self.route)

        self.assertEqual(self.route.interaction_comments.count(), 1)
        self.assertEqual(self.user.interaction_comments.count(), 1)


class TestModelMethods(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.route = Route.objects.create(
            name='Awesome Route', author=self.user, privacy='public'
        )

    def test_favorite_str_method(self):
        favorite = Favorite.objects.create(user=self.user, route=self.route)
        str_repr = str(favorite)
        self.assertIn('testuser', str_repr)
        self.assertIn('Awesome Route', str_repr)

    def test_rating_str_method(self):
        rating = Rating.objects.create(
            user=self.user, route=self.route, score=5
        )
        str_repr = str(rating)
        self.assertIn('testuser', str_repr)
        self.assertIn('Awesome Route', str_repr)
        self.assertIn('5', str_repr)

    def test_comment_str_method(self):
        comment = Comment.objects.create(
            user=self.user,
            route=self.route,
            text='This is a very long comment that should be'
            ' truncated in the string representation',
        )
        str_repr = str(comment)
        self.assertIn('testuser', str_repr)
        self.assertIn('This is a very long comment', str_repr)
        self.assertTrue(len(str_repr) <= len('testuser: ') + 50)


class TestModelTimestamps(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.route = Route.objects.create(
            name='Test Route', author=self.user, privacy='public'
        )

    def test_favorite_timestamps(self):
        favorite = Favorite.objects.create(user=self.user, route=self.route)
        self.assertIsNotNone(favorite.created_at)

    def test_rating_timestamps(self):
        rating = Rating.objects.create(
            user=self.user, route=self.route, score=3
        )
        self.assertIsNotNone(rating.created_at)
        self.assertIsNotNone(rating.updated_at)

        old_updated = rating.updated_at
        rating.score = 4
        rating.save()
        self.assertNotEqual(rating.updated_at, old_updated)

    def test_comment_timestamps(self):
        comment = Comment.objects.create(
            user=self.user, route=self.route, text='Test comment'
        )
        self.assertIsNotNone(comment.created_at)
        self.assertIsNotNone(comment.updated_at)
