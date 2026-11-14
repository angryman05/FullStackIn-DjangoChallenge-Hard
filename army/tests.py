from unittest import mock

import requests
from django.test import TestCase, override_settings
from django.urls import reverse

from . import tasks
from .models import DraftBatch, Person

PEOPLE = [{"id": i, "name": f"Person {i}", "age": 20 + i} for i in range(4)]
PEOPLE[-1]["key"] = "draft-info"
RANKS = ["Private", "Sergeant", "Lieutenant", "General"]


def fake_api(timeouts=None):
    """Fake /people and /draft/<n> (2 batches of 2). ``timeouts`` maps path -> failures."""
    timeouts = dict(timeouts or {})

    def fetch(path):
        if timeouts.get(path, 0) > 0:
            timeouts[path] -= 1
            raise requests.Timeout("simulated timeout")
        if path == "people":
            return {"data": PEOPLE, "status": 200}
        n = int(path.split("/")[1])
        if n > 1:
            raise tasks.ChallengeAPIError("Invalid batch id")
        batch = [dict(p, rank=RANKS[p["id"]], health=100) for p in PEOPLE[n * 2 : n * 2 + 2]]
        return {"data": batch, "next_batch": n + 1 if n < 1 else None, "status": 200}

    return fetch


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class DraftingTests(TestCase):
    def setUp(self):
        tasks.register_people.app.conf.task_always_eager = True
        no_sleep = mock.patch.object(tasks, "backoff", return_value=0)
        no_sleep.start()
        self.addCleanup(no_sleep.stop)

    def test_full_drafting_flow(self):
        with mock.patch.object(tasks, "fetch", fake_api()):
            tasks.start_drafting.delay()

        self.assertEqual(Person.objects.count(), 4)
        self.assertFalse(Person.objects.filter(drafted_at__isnull=True).exists())
        self.assertEqual(Person.objects.get(external_id=3).rank, "General")
        self.assertEqual(Person.objects.get(external_id=3).key, "draft-info")
        self.assertEqual(
            list(DraftBatch.objects.values_list("number", "status")),
            [(0, "drafted"), (1, "drafted")],
        )

    def test_batch_timeout_is_retried(self):
        with mock.patch.object(tasks, "fetch", fake_api({"draft/1": 2})):
            tasks.start_drafting.delay()

        batch = DraftBatch.objects.get(number=1)
        self.assertEqual(batch.status, "drafted")
        self.assertEqual(batch.attempts, 3)
        self.assertEqual(Person.objects.filter(rank="").count(), 0)

    def test_batch_marked_failed_after_max_retries(self):
        with mock.patch.object(tasks, "fetch", fake_api({"draft/0": 99})):
            tasks.start_drafting.delay()  # eager chains swallow the final exception

        batch = DraftBatch.objects.get(number=0)
        self.assertEqual(batch.status, "failed")
        self.assertEqual(batch.attempts, tasks.MAX_RETRIES + 1)
        self.assertEqual(Person.objects.count(), 4)  # registration still happened

    def test_status_endpoint_and_pages(self):
        with mock.patch.object(tasks, "fetch", fake_api()):
            tasks.start_drafting.delay()

        status = self.client.get(reverse("army:draft_status")).json()
        self.assertEqual((status["registered"], status["drafted"]), (4, 4))
        self.assertEqual(self.client.get(reverse("army:people_list")).status_code, 200)
        self.assertContains(self.client.get(reverse("army:people_list") + "?rank=General"), "Person 3")
        person = Person.objects.get(external_id=3)
        self.assertContains(self.client.get(reverse("army:person_detail", args=[person.pk])), "General")
