from django.urls import path

from . import views

app_name = "army"

urlpatterns = [
    path("", views.people_list, name="people_list"),
    path("people/<int:pk>/", views.person_detail, name="person_detail"),
    path("people/register/", views.register_view, name="register"),
    path("draft/", views.draft_view, name="draft"),
    path("draft/status/", views.draft_status, name="draft_status"),
]
