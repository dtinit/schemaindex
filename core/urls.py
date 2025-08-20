from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("schemas/<int:schema_id>", views.schema_detail, name="schema_detail")
]

