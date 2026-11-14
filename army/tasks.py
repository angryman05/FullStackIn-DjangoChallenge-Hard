"""Background tasks for registering and drafting people.

Flow (started by ``launch_drafting``):

    [register_people]  ->  download_batch(0) | download_batch(1) | ... | download_batch(N-1)
                           (all launched at the same time, run in parallel by a threaded worker)
                               each one, as soon as its batch is downloaded:
                               '-- draft_batch(n, people)   (separate task)

N = CHALLENGE_BATCH_COUNT (default 10). If the API reports a ``next_batch`` that was
not launched yet, it is downloaded too, so more batches than expected still work.
One slow/failed batch doesn't block the others. Downloads retry with exponential
backoff when the remote API times out or errors.
"""

import logging

import requests
from celery import chain, shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import DraftBatch, Person

logger = logging.getLogger(__name__)

MAX_RETRIES = 10  # ~7 min of backoff in total
RETRYABLE = (requests.Timeout, requests.ConnectionError, requests.HTTPError)


class ChallengeAPIError(Exception):
    """The API answered, but with an error payload (not worth retrying)."""


def fetch(path):
    """GET <host>/<path> and return the ``data`` field of the JSON envelope."""
    url = f"{settings.CHALLENGE_API_URL}/{path.lstrip('/')}"
    response = requests.get(url, timeout=settings.CHALLENGE_API_TIMEOUT)
    response.raise_for_status()  # 5xx -> HTTPError -> retried
    payload = response.json()
    # The API sends HTTP 200 with {"status": 400, ...} for logical errors.
    if payload.get("status") != 200:
        raise ChallengeAPIError(f"{url}: {payload.get('data')}")
    return payload


def backoff(retries):
    return min(2 ** retries, 60)  # 1, 2, 4, ... capped at 60 s


@shared_task(bind=True, max_retries=MAX_RETRIES)
def register_people(self):
    """Peacetime: download every person from /people and store them."""
    try:
        people = fetch("people")["data"]
    except RETRYABLE as exc:
        logger.warning("register_people failed (%s), retrying", exc)
        raise self.retry(exc=exc, countdown=backoff(self.request.retries))

    with transaction.atomic():
        for p in people:
            Person.objects.update_or_create(
                external_id=p["id"],
                defaults={"name": p["name"], "age": p["age"], "key": p.get("key", "")},
            )
    logger.info("Registered %d people", len(people))
    return len(people)


@shared_task(bind=True, max_retries=MAX_RETRIES)
def download_batch(self, number):
    """Download one /draft/<number> batch, then hand it to its own drafting task."""
    batch, _ = DraftBatch.objects.get_or_create(number=number)
    batch.attempts = self.request.retries + 1
    batch.status = DraftBatch.Status.DOWNLOADING
    batch.save(update_fields=["attempts", "status", "updated_at"])

    try:
        payload = fetch(f"draft/{number}")
    except RETRYABLE as exc:
        batch.error = str(exc)
        if self.request.retries >= self.max_retries:
            batch.status = DraftBatch.Status.FAILED
            batch.save(update_fields=["status", "error", "updated_at"])
            logger.error("Batch %s failed after %s attempts", number, batch.attempts)
            raise
        batch.status = DraftBatch.Status.RETRYING
        batch.save(update_fields=["status", "error", "updated_at"])
        logger.warning("Batch %s failed (%s), retrying", number, exc)
        raise self.retry(exc=exc, countdown=backoff(self.request.retries))
    except ChallengeAPIError as exc:
        if "Invalid batch id" in str(exc):
            # Launched past the last batch - it simply doesn't exist.
            batch.delete()
            logger.info("Batch %s does not exist, skipped", number)
            return 0
        batch.status = DraftBatch.Status.FAILED
        batch.error = str(exc)
        batch.save(update_fields=["status", "error", "updated_at"])
        raise

    people = payload["data"]
    batch.status = DraftBatch.Status.DOWNLOADED
    batch.error = ""  # keep the last error visible until a download succeeds
    batch.people_count = len(people)
    batch.save(update_fields=["status", "error", "people_count", "updated_at"])

    # Drafting this batch starts right away, in its own task.
    draft_batch.delay(number, people)

    # Safety net: if the API has more batches than we launched, fetch those too.
    next_batch = payload.get("next_batch")
    if next_batch is not None:
        _, created = DraftBatch.objects.get_or_create(number=next_batch)
        if created:
            download_batch.delay(next_batch)
    return len(people)


@shared_task
def draft_batch(number, people):
    """Assign rank and health to the people of one downloaded batch."""
    now = timezone.now()
    with transaction.atomic():
        for p in people:
            Person.objects.update_or_create(
                external_id=p["id"],
                defaults={
                    "name": p["name"],
                    "age": p["age"],
                    "key": p.get("key", ""),
                    "rank": p.get("rank", ""),
                    "health": p.get("health"),
                    "drafted_at": now,
                },
            )
        DraftBatch.objects.filter(number=number).update(
            status=DraftBatch.Status.DRAFTED, updated_at=now
        )
    logger.info("Drafted batch %s (%d people)", number, len(people))
    return len(people)


def download_all_batches():
    """Launch every batch download at once (they run in parallel)."""
    numbers = range(settings.CHALLENGE_BATCH_COUNT)
    DraftBatch.objects.bulk_create(
        [DraftBatch(number=n, status=DraftBatch.Status.DOWNLOADING) for n in numbers],
        ignore_conflicts=True,
    )
    for n in numbers:
        download_batch.delay(n)


@shared_task
def download_all_batches_task(_previous_result=None):
    download_all_batches()


def launch_drafting():
    """Called synchronously from the view, so the UI sees every batch immediately.

    If people are already registered, all batch downloads start right away;
    otherwise registration runs first.
    """
    DraftBatch.objects.all().delete()
    if Person.objects.exists():
        download_all_batches()
    else:
        DraftBatch.objects.create(number=0, status=DraftBatch.Status.DOWNLOADING)
        chain(register_people.si(), download_all_batches_task.si()).delay()


@shared_task
def start_drafting():
    """Task wrapper around launch_drafting (kept for compatibility)."""
    launch_drafting()
