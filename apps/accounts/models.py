from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Back-office user. Fans consume the public API anonymously, so every
    account belongs to either the organising staff or a table official.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", _("Administrator")
        TABLE_OFFICIAL = "TABLE_OFFICIAL", _("Table official")

    role = models.CharField(
        _("role"),
        max_length=20,
        choices=Role.choices,
        default=Role.TABLE_OFFICIAL,
        db_index=True,
    )
    phone = models.CharField(_("phone"), max_length=20, blank=True)

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ("first_name", "last_name", "username")

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_table_official(self):
        return self.role == self.Role.TABLE_OFFICIAL

    def save(self, *args, **kwargs):
        # Admins manage the tournament through the Django admin as well.
        if self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)
