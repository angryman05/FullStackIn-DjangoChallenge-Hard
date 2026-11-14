from django.db import models


class Person(models.Model):
    """A civilian registered from the /people endpoint (peacetime).

    Drafting (background Celery tasks) later fills in rank and health.
    """

    class Rank(models.TextChoices):
        PRIVATE = "Private"
        SERGEANT = "Sergeant"
        LIEUTENANT = "Lieutenant"
        GENERAL = "General"

    external_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=200)
    age = models.PositiveIntegerField()
    # Only Hellstorm Fireburn has it; it points to the next instructions.
    key = models.CharField(max_length=100, blank=True, default="")
    registered_at = models.DateTimeField(auto_now_add=True)

    # --- added by drafting (migration 0002) ---
    # Not limited to Rank.choices on purpose: the remote API may send new ranks.
    rank = models.CharField(max_length=50, blank=True, default="")
    health = models.PositiveIntegerField(null=True, blank=True)
    drafted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["external_id"]

    def __str__(self):
        return self.name

    @property
    def is_drafted(self):
        return self.drafted_at is not None


class DraftBatch(models.Model):
    """Progress of one /draft/<number> batch, so the UI can show what's going on."""

    class Status(models.TextChoices):
        DOWNLOADING = "downloading"
        RETRYING = "retrying"
        DOWNLOADED = "downloaded"
        DRAFTED = "drafted"
        FAILED = "failed"

    number = models.PositiveIntegerField(unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DOWNLOADING)
    attempts = models.PositiveIntegerField(default=0)
    people_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Batch {self.number} ({self.status})"
