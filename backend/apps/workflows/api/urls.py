from django.urls import path

from .views import (
    WorkflowExecutionAdvanceView,
    WorkflowExecutionDetailView,
    WorkflowExecutionListCreateView,
    WorkflowExecutionLogsView,
    WorkflowTemplateDetailView,
    WorkflowTemplateListCreateView,
)

urlpatterns = [
    path(
        "templates/",
        WorkflowTemplateListCreateView.as_view(),
        name="workflow-template-list-create",
    ),
    path(
        "templates/<uuid:template_id>/",
        WorkflowTemplateDetailView.as_view(),
        name="workflow-template-detail",
    ),
    path(
        "executions/",
        WorkflowExecutionListCreateView.as_view(),
        name="workflow-execution-list-create",
    ),
    path(
        "executions/<uuid:execution_id>/",
        WorkflowExecutionDetailView.as_view(),
        name="workflow-execution-detail",
    ),
    path(
        "executions/<uuid:execution_id>/advance/",
        WorkflowExecutionAdvanceView.as_view(),
        name="workflow-execution-advance",
    ),
    path(
        "executions/<uuid:execution_id>/logs/",
        WorkflowExecutionLogsView.as_view(),
        name="workflow-execution-logs",
    ),
]
