"""
Abstract building blocks shared by the bounded contexts.

This package is intentionally *not* a Django app (it is not listed in
INSTALLED_APPS and owns no tables). It only holds abstract models, so no
domain logic can accumulate here.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True
