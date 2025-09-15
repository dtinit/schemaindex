from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("schemas/<int:schema_id>/", views.schema_detail, name="schema_detail"),
    path("account/profile/", views.account_profile, name="account_profile"),
    path("manage/schema/<int:schema_id>", views.manage_schema, name="manage_schema"),
    path("manage/schema/new", views.manage_schema, name="manage_schema_new")
]

