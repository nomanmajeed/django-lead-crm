from django.urls import path

from .detail import lead_detail
from .views import LeadCategoryUpdateView, lead_list

app_name = "agent_leads"

urlpatterns = [
    path("", lead_list, name="lead_list"),
    path("<int:pk>/", lead_detail, name="lead_detail"),
    path(
        "<int:pk>/category",
        LeadCategoryUpdateView.as_view(),
        name="category_update",
    ),
]
