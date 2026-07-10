from django.urls import path
from .detail import lead_detail
from .pipeline import PipelineView
from .views import (
    lead_list,
    lead_create,
    lead_update,
    lead_delete,
    AssignAgentView,
    CategoryListView,
    CategoryDetailView,
    LeadCategoryUpdateView,
)

app_name = "leads"

urlpatterns = [
    path("", lead_list, name="lead_list"),
    path("pipeline/", PipelineView.as_view(), name="pipeline"),
    path("<int:pk>/", lead_detail, name="lead_detail"),
    path("<int:pk>/update", lead_update, name="lead_update"),
    path("<int:pk>/delete", lead_delete, name="lead_delete"),
    path("create/", lead_create, name="lead_create"),
    path("<int:pk>/assign-agent", AssignAgentView.as_view(), name="assign_agent"),
    path("categories/", CategoryListView.as_view(), name="category_list"),
    path("categories/<int:pk>", CategoryDetailView.as_view(), name="category_detail"),
    path("<int:pk>/category", LeadCategoryUpdateView.as_view(), name="category_update"),
]
