"""Canonical-prefix URLconf for contract emission (contract-pipeline.md §2).

The host mounts tasks at ``path("tasks/", include("stapel_tasks.urls"))``,
which yields the canonical versioned surface ``/tasks/api/v1/...``
(api-versioning.md §2 — the version segment is part of the contract).
This URLconf reproduces that mount exactly, so drf-spectacular emits
``/tasks/api/v1/...`` paths (and matching ``tasks_api_v1_*`` operationIds)
and ``generate_flow_docs`` resolves flow endpoints to the same.
"""
from django.urls import include, path

urlpatterns = [
    path("tasks/", include("stapel_tasks.urls")),
]
