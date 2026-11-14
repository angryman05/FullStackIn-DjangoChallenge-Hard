from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import DraftBatch, Person
from .tasks import launch_drafting, register_people


def draft_summary():
    """Numbers shared by the HTML page and the JSON status endpoint."""
    people = Person.objects.all()
    return {
        "registered": people.count(),
        "drafted": people.filter(drafted_at__isnull=False).count(),
        "ranks": list(
            people.exclude(rank="").values("rank").annotate(count=Count("id")).order_by("rank")
        ),
        "batches": list(
            DraftBatch.objects.values("number", "status", "attempts", "people_count", "error")
        ),
    }


def people_list(request):
    """Registered people list with server-side pagination, search, and rank filter."""
    people = Person.objects.all()
    rank = request.GET.get("rank")
    if rank:
        people = people.filter(rank=rank)

    key_person = (
        Person.objects.filter(name__icontains="Hellstorm").first()
        or Person.objects.exclude(key="").first()
    )

    paginator = Paginator(people, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    summary = draft_summary()
    context = {
        "people": page_obj,
        "page_obj": page_obj,
        "all_people_count": people.count(),
        "selected_rank": rank,
        "key_person": key_person,
        **summary,
    }
    return render(request, "army/people_list.html", context)


def person_detail(request, pk):
    """Generic detail page for a person inspecting all database fields."""
    person = get_object_or_404(Person, pk=pk)
    
    # Generic inspection of all model fields dynamically
    fields = []
    for f in person._meta.fields:
        val = getattr(person, f.name)
        fields.append({
            "name": f.name,
            "verbose_name": f.verbose_name.title(),
            "value": val,
            "is_key": f.name == "key",
        })

    return render(request, "army/person_detail.html", {
        "person": person,
        "fields": fields,
    })


def people_import(request):
    """Control panel view for starting peacetime registration and live progress."""
    key_person = (
        Person.objects.filter(name__icontains="Hellstorm").first()
        or Person.objects.exclude(key="").first()
    )
    return render(request, "army/import.html", {
        "key_person": key_person,
        **draft_summary(),
    })


def register_view(request):
    """Trigger background peacetime registration from /people endpoint."""
    if request.method == "POST":
        register_people.delay()
        messages.info(request, "Peacetime citizen registration initiated.")
        if request.headers.get("accept") == "application/json" or request.content_type == "application/json":
            return JsonResponse({"job_id": "people-register", "status": "running"}, status=202)
        return redirect("army:people_import")
    return redirect("army:people_import")


def import_status(request):
    """Live status endpoint for peacetime registration progress."""
    count = Person.objects.count()
    key_person = (
        Person.objects.filter(name__icontains="Hellstorm").first()
        or Person.objects.exclude(key="").first()
    )
    status_str = "done" if count > 0 else "idle"
    return JsonResponse({
        "status": status_str,
        "total": count if count > 0 else None,
        "processed": count,
        "failed": 0,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "key_found": bool(key_person and key_person.key),
        "key_value": key_person.key if key_person else "",
    })


def draft_view(request):
    """Phase 2 drafting: GET renders war room UI, POST starts drafting tasks."""
    if request.method == "POST":
        launch_drafting()
        messages.info(request, "Soldier drafting started in the background.")
        if request.headers.get("accept") == "application/json" or request.content_type == "application/json":
            return JsonResponse({"status": "running", "message": "Drafting started"}, status=202)
        return redirect("army:draft")

    key_person = (
        Person.objects.filter(name__icontains="Hellstorm").first()
        or Person.objects.exclude(key="").first()
    )
    return render(request, "army/draft.html", {
        "key_person": key_person,
        **draft_summary(),
    })


def draft_status(request):
    """JSON for live progress polling from the frontend."""
    return JsonResponse(draft_summary())


def custom_404(request, exception=None):
    """Custom command center 404 page."""
    return render(request, "404.html", status=404)
