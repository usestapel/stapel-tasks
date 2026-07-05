from django.urls import include, path

urlpatterns = [
    path("tasks/", include("stapel_tasks.urls")),
]
