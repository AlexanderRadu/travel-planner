import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Route, RouteFavorite, RoutePhoto, RoutePoint, RouteRating


class RouteModelsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

    def test_route_creation(self):
        route = Route.objects.create(
            author=self.user,
            name='Test Route',
            description='Test description',
            privacy='public',
            route_type='walking',
            total_distance=10.5,
            is_active=True,
        )

        self.assertEqual(route.name, 'Test Route')
        self.assertEqual(route.author.username, 'testuser')
        self.assertEqual(route.privacy, 'public')
        self.assertTrue(route.is_active)
        self.assertIsNotNone(route.created_at)

    def test_route_str_method(self):
        route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )

        str_repr = str(route)
        self.assertIn('Test Route', str_repr)
        self.assertIn('ID:', str_repr)

    def test_route_point_creation(self):
        route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )

        point = RoutePoint.objects.create(
            route=route,
            name='Test Point',
            latitude=55.7558,
            longitude=37.6176,
            order=1,
        )

        self.assertEqual(point.name, 'Test Point')
        self.assertEqual(point.route.name, 'Test Route')
        self.assertEqual(point.latitude, 55.7558)
        self.assertEqual(point.order, 1)

    def test_route_photo_creation(self):
        route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )

        photo = RoutePhoto.objects.create(
            route=route, caption='Test photo', order=1
        )

        self.assertEqual(photo.caption, 'Test photo')
        self.assertEqual(photo.route, route)
        self.assertEqual(photo.order, 1)

    def test_route_rating_creation(self):
        route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )

        rating = RouteRating.objects.create(
            route=route, user=self.user, rating=5
        )

        self.assertEqual(rating.rating, 5)
        self.assertEqual(rating.user.username, 'testuser')
        self.assertEqual(rating.route.name, 'Test Route')

    def test_route_favorite_creation(self):
        route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )

        favorite = RouteFavorite.objects.create(route=route, user=self.user)

        self.assertEqual(favorite.user.username, 'testuser')
        self.assertEqual(favorite.route.name, 'Test Route')
        self.assertIsNotNone(favorite.created_at)


class RouteViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.route = Route.objects.create(
            author=self.user,
            name='Test Route',
            description='Test description',
            privacy='public',
            route_type='walking',
            total_distance=10.5,
            is_active=True,
        )

    def test_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Route')

    def test_all_routes_page(self):
        response = self.client.get(reverse('all_routes'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'routes/all_routes.html')

    def test_my_routes_page_authenticated(self):
        response = self.client.get(reverse('my_routes'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'routes/my_routes.html')

    def test_route_detail_page(self):
        response = self.client.get(
            reverse('route_detail', args=[self.route.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Route')
        self.assertTemplateUsed(response, 'routes/route_detail.html')

    def test_create_route_page(self):
        response = self.client.get(reverse('create_route'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'routes/route_editor.html')

    def test_edit_route_page(self):
        response = self.client.get(reverse('edit_route', args=[self.route.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'routes/route_editor.html')

    def test_shared_routes_page(self):
        response = self.client.get(reverse('shared_routes'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'routes/shared_routes.html')


class RouteAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )

    def test_toggle_route_active(self):
        self.assertTrue(self.route.is_active)

        response = self.client.post(
            reverse('toggle_route_active', args=[self.route.id])
        )

        self.assertEqual(response.status_code, 302)
        self.route.refresh_from_db()
        self.assertFalse(self.route.is_active)

    def test_toggle_favorite_api(self):
        response = self.client.post(
            reverse('toggle_favorite', args=[self.route.id]),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        self.assertTrue(
            RouteFavorite.objects.filter(
                user=self.user, route=self.route
            ).exists()
        )

        response = self.client.post(
            reverse('toggle_favorite', args=[self.route.id]),
            content_type='application/json',
        )

        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['is_favorite'])

    def test_rate_route_api(self):
        data = {'rating': 4}
        response = self.client.post(
            reverse('rate_route', args=[self.route.id]),
            data=json.dumps(data),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

        self.assertTrue(
            RouteRating.objects.filter(
                user=self.user, route=self.route, rating=4
            ).exists()
        )


class RouteSearchTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client = Client()

        self.route1 = Route.objects.create(
            author=self.user,
            name='Пеший маршрут по лесу',
            description='Красивый лесной маршрут',
            privacy='public',
            route_type='walking',
            is_active=True,
        )

        self.route2 = Route.objects.create(
            author=self.user,
            name='Автомобильная поездка',
            description='Длинная автомобильная дорога',
            privacy='public',
            route_type='driving',
            is_active=True,
        )

    def test_search_by_type(self):
        response = self.client.get(reverse('all_routes'), {'type': 'walking'})
        self.assertEqual(response.status_code, 200)

        routes = response.context['page_obj'].object_list
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].route_type, 'walking')

    def test_search_combined(self):
        response = self.client.get(
            reverse('search'), {'q': 'маршрут', 'type': 'walking'}
        )
        self.assertEqual(response.status_code, 200)


class RoutePrivacyTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1', password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2', password='pass123'
        )

        self.public_route = Route.objects.create(
            author=self.user1,
            name='Public Route',
            privacy='public',
            is_active=True,
        )

        self.private_route = Route.objects.create(
            author=self.user1,
            name='Private Route',
            privacy='private',
            is_active=True,
        )

        self.link_route = Route.objects.create(
            author=self.user1,
            name='Link Route',
            privacy='link',
            is_active=True,
        )

    def test_public_route_access(self):
        client = Client()

        response = client.get(
            reverse('route_detail', args=[self.public_route.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_private_route_access_owner(self):
        client = Client()
        client.login(username='user1', password='pass123')

        response = client.get(
            reverse('route_detail', args=[self.private_route.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_private_route_access_non_owner(self):
        client = Client()
        client.login(username='user2', password='pass123')

        response = client.get(
            reverse('route_detail', args=[self.private_route.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_link_route_access(self):
        client = Client()

        response = client.get(
            reverse('route_detail', args=[self.link_route.id])
        )
        self.assertEqual(response.status_code, 302)


class RouteFilterTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

        Route.objects.create(
            author=self.user,
            name='Walking Route 1',
            route_type='walking',
            privacy='public',
            is_active=True,
        )

        Route.objects.create(
            author=self.user,
            name='Driving Route 1',
            route_type='driving',
            privacy='public',
            is_active=True,
        )

        Route.objects.create(
            author=self.user,
            name='Cycling Route 1',
            route_type='cycling',
            privacy='public',
            is_active=True,
        )

    def test_walking_routes_view(self):
        client = Client()
        response = client.get(reverse('walking_routes'))

        self.assertEqual(response.status_code, 200)
        routes = response.context['routes']
        self.assertEqual(routes.count(), 1)
        self.assertEqual(routes.first().route_type, 'walking')

    def test_driving_routes_view(self):
        client = Client()
        response = client.get(reverse('driving_routes'))

        self.assertEqual(response.status_code, 200)
        routes = response.context['routes']
        self.assertEqual(routes.count(), 1)
        self.assertEqual(routes.first().route_type, 'driving')

    def test_cycling_routes_view(self):
        client = Client()
        response = client.get(reverse('cycling_routes'))

        self.assertEqual(response.status_code, 200)
        routes = response.context['routes']
        self.assertEqual(routes.count(), 1)
        self.assertEqual(routes.first().route_type, 'cycling')


class RouteCommentsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.route = Route.objects.create(
            author=self.user,
            name='Test Route',
            privacy='public',
            is_active=True,
        )

    def test_add_route_comment(self):
        response = self.client.post(
            reverse('add_route_comment', args=[self.route.id]),
            {'text': 'Great route!'},
        )

        self.assertEqual(response.status_code, 302)

        from routes.models import RouteComment

        self.assertTrue(
            RouteComment.objects.filter(
                route=self.route, user=self.user, text='Great route!'
            ).exists()
        )


class RoutePointsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

        self.route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )

    def test_create_route_with_points(self):
        point1 = RoutePoint.objects.create(
            route=self.route,
            name='Point 1',
            latitude=55.7558,
            longitude=37.6176,
            order=1,
        )

        point2 = RoutePoint.objects.create(
            route=self.route,
            name='Point 2',
            latitude=55.7600,
            longitude=37.6200,
            order=2,
        )

        self.assertEqual(self.route.points.count(), 2)
        self.assertEqual(point1.route, self.route)
        self.assertEqual(point2.route, self.route)

        points = list(self.route.points.order_by('order'))
        self.assertEqual(points[0].name, 'Point 1')
        self.assertEqual(points[1].name, 'Point 2')


class TestBasicFunctionality(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
        )
        self.client = Client()

    def test_login_required_pages(self):
        pages = [
            ('my_routes', []),
            ('create_route', []),
            ('shared_routes', []),
        ]

        for view_name, args in pages:
            response = self.client.get(reverse(view_name, args=args))
            self.assertEqual(response.status_code, 302)


class TestRouteMethods(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

        self.route = Route.objects.create(
            author=self.user,
            name='Test Route',
            privacy='public',
            is_active=True,
        )

    def test_get_absolute_url(self):
        url = self.route.get_absolute_url()
        self.assertIn(str(self.route.id), url)


class TestRoutePointCategories(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )

        self.route = Route.objects.create(
            author=self.user, name='Test Route', privacy='public'
        )

    def test_point_categories(self):
        categories = ['attraction', 'nature', 'restaurant', 'museum']

        for i, category in enumerate(categories):
            RoutePoint.objects.create(
                route=self.route,
                name=f'Point {category}',
                latitude=55.7558 + i * 0.01,
                longitude=37.6176 + i * 0.01,
                category=category,
                order=i,
            )

        self.assertEqual(self.route.points.count(), 4)

        point = self.route.points.first()
        self.assertIn(point.category, categories)
