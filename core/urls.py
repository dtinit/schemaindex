from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("about", views.about),
    path("schemas/<int:schema_id>", views.schema_detail, name="schema_detail"),
    path("schemas/<int:schema_id>/definition/<int:schema_ref_id>", views.schema_ref_detail, name="schema_ref_detail"),
    path("account/profile/", views.account_profile, name="account_profile"),
    path("manage/schema/<int:schema_id>", views.manage_schema, name="manage_schema"),
    path("manage/schema/new", views.manage_schema, name="manage_schema_new"),
    path("manage/schema/<int:schema_id>/delete", views.manage_schema_delete, name="manage_schema_delete"),
    path("manage/schema/<int:schema_id>/publish", views.manage_schema_publish, name="manage_schema_publish"),
    path("manage/schema/<int:schema_id>/permanent-urls", views.manage_schema_permanent_urls, name="manage_schema_permanent_urls"),
    path("organization/<int:organization_id>", views.organization_detail, name="organization_detail"),
    path("o/<path:partial_path>", views.permanent_url_redirect, name="permanent_url_redirect")
]

