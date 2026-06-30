import django_filters

from apps.audit.models import AuditAction, AuditLog


class AuditLogFilter(django_filters.FilterSet):
    action = django_filters.ChoiceFilter(choices=AuditAction.choices)
    entity_type = django_filters.CharFilter()
    entity_id = django_filters.CharFilter()
    user = django_filters.UUIDFilter(field_name="user_id")
    user_email = django_filters.CharFilter(
        field_name="user__email", lookup_expr="iexact"
    )
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = AuditLog
        fields = ["action", "entity_type", "entity_id", "user", "user_email"]
