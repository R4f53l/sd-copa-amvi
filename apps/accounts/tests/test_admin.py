from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            "root", "root@example.com", "pass"
        )
        cls.official = User.objects.create_user(
            "mesario", password="pass", first_name="Marcos"
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_user_is_registered(self):
        self.assertIn(User, site._registry)

    def test_changelist_filters_by_role(self):
        url = reverse("admin:accounts_user_changelist")
        response = self.client.get(url, {"role__exact": "TABLE_OFFICIAL"})
        self.assertEqual(response.status_code, 200)
        users = list(response.context["cl"].result_list)
        self.assertEqual(users, [self.official])

    def test_change_form_shows_role_fieldset(self):
        url = reverse("admin:accounts_user_change", args=[self.official.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="role"')
        self.assertContains(response, 'name="phone"')

    def test_create_user_with_role(self):
        url = reverse("admin:accounts_user_add")
        response = self.client.post(
            url,
            {
                "username": "novo_admin",
                "role": User.Role.ADMIN,
                "password1": "Senha-Forte-123",
                "password2": "Senha-Forte-123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="novo_admin")
        self.assertEqual(user.role, User.Role.ADMIN)
        # Administrators get access to the Django admin automatically.
        self.assertTrue(user.is_staff)
