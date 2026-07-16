"""Root URLconf for stapel-tasks — v1 canon mount (api-versioning.md §2, §6).

Canon: ``/<mod>/api/v1/...`` — the version segment sits right after ``api/``.
The host mounts ``include('stapel_tasks.urls')`` under ``tasks/``; this
module contributes the ``api/v1/`` prefix (the ``api/`` segment historically
lives inside this package, not in the host mount). The actual URL set lives
in ``urls_v1.py``.
"""
from django.urls import include, path


urlpatterns = [
    path('api/v1/', include('stapel_tasks.urls_v1')),
]
