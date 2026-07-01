from django.db import models

from apps.core.models import BaseModel


class Organization(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "organizations"
        indexes = [
            models.Index(fields=["slug"], name="idx_organizations_slug"),
            models.Index(fields=["is_active"], name="idx_organizations_is_active"),
        ]

    def __str__(self) -> str:
        return self.name
