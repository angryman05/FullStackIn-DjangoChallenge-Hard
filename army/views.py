from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import DraftBatch, Person
from .tasks import register_people, start_drafting


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
    people = Person.objects.all()
    rank = request.GET.get("rank")
    if rank:
        people = people.filter(rank=rank)
    return render(
        request,
        "army/people_list.html",
        {"people": people, "selected_rank": rank, **draft_summary()},
    )


def person_detail(request, pk):
    person = get_object_or_404(Person, pk=pk)
    return render(request, "army/person_detail.html", {"person": person})


@require_POST
def register_view(request):
    register_people.delay()
    messages.info(request, "Registration started in the background.")
    return redirect("army:people_list")


@require_POST
def draft_view(request):
    start_drafting.delay()
    messages.info(request, "Drafting started in the background.")
    return redirect("army:people_list")


def draft_status(request):
    """JSON for live progress polling from the frontend."""
    return JsonResponse(draft_summary())
