from django.urls import path

from . import views

app_name = "army"

urlpatterns = [
    # Dashboard / People list
    path("", views.people_list, name="people_list"),
    path("people/", views.people_list, name="people_list_alt"),
    
    # Page 1: /people/import/
    path("people/import/", views.people_import, name="people_import"),
    path("people/import/start/", views.register_view, name="import_start"),
    path("people/import/status/", views.import_status, name="import_status"),
    path("people/register/", views.register_view, name="register"),
    
    # Page 2 & 3: Detail
    path("people/<int:pk>/", views.person_detail, name="person_detail"),
    
    # Page 4: /draft/ (Phase 2 UI)
    path("draft/", views.draft_view, name="draft"),
    path("draft/start/", views.draft_view, name="draft_start"),
    path("draft/status/", views.draft_status, name="draft_status"),
]
