from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_homepage_redirects_to_the_public_matches_page(self):
        response = self.client.get(reverse("home"))

        self.assertRedirects(response, reverse("matches:list"))
