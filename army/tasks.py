"""Background tasks for registering and drafting people.

Flow (started by ``start_drafting``):

    register_people  ->  download_batch(0)
                             |-- draft_batch(0, people)   (separate task)
                             '-- download_batch(1)
                                     |-- draft_batch(1, people)
                                     '-- download_batch(2) ... until next_batch is null

Every batch is downloaded and drafted by its own task call, and drafting of a
batch starts as soon as that batch is downloaded. Downloads retry with
exponential backoff when the remote API times out or errors.
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
    batch.error = ""
    batch.save()

    try:
        payload = fetch(f"draft/{number}")
    except RETRYABLE as exc:
        batch.error = str(exc)
        if self.request.retries >= self.max_retries:
            batch.status = DraftBatch.Status.FAILED
            batch.save()
            logger.error("Batch %s failed after %s attempts", number, batch.attempts)
            raise
        batch.status = DraftBatch.Status.RETRYING
        batch.save()
        logger.warning("Batch %s failed (%s), retrying", number, exc)
        raise self.retry(exc=exc, countdown=backoff(self.request.retries))
    except ChallengeAPIError as exc:
        batch.status = DraftBatch.Status.FAILED
        batch.error = str(exc)
        batch.save()
        raise

    people = payload["data"]
    batch.status = DraftBatch.Status.DOWNLOADED
    batch.people_count = len(people)
    batch.save()

    # Drafting this batch starts right away, in its own task...
    draft_batch.delay(number, people)
    # ...while the next batch is downloaded in parallel.
    if payload.get("next_batch") is not None:
        download_batch.delay(payload["next_batch"])
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


@shared_task
def start_drafting():
    """Entry point: register everyone, then start the batch download chain."""
    DraftBatch.objects.all().delete()
    chain(register_people.si(), download_batch.si(0)).delay()
