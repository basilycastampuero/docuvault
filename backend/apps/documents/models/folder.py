from django.db import models

from apps.core.models import BaseModel


class Folder(BaseModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="folders",
    )
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    owner = models.ForeignKey(
        "authentication.User",
        on_delete=models.PROTECT,
        related_name="owned_folders",
    )

    class Meta:
        db_table = "folders"
        indexes = [
            models.Index(
                fields=["organization", "parent"],
                name="idx_folders_org_parent",
            ),
            models.Index(
                fields=["organization", "owner"],
                name="idx_folders_org_owner",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "parent", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_folders_org_parent_name_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        if (
            self.parent_id is not None
            and self.pk is not None
            and self.parent_id == self.pk
        ):
            raise ValidationError("A folder cannot be its own parent.")
