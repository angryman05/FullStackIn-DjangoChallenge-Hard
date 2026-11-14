from django.contrib import admin

from .models import DraftBatch, Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("external_id", "name", "age", "rank", "health", "drafted_at")
    list_filter = ("rank",)
    search_fields = ("name",)


@admin.register(DraftBatch)
class DraftBatchAdmin(admin.ModelAdmin):
    list_display = ("number", "status", "attempts", "people_count", "updated_at")
