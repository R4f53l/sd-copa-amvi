from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_homepage_is_available(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome to Copa AMVI")
        self.assertContains(response, 'href="/matches/"')
