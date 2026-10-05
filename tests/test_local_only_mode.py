import pytest
import requests_mock
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from core.local_user import LOCAL_USERNAME, get_local_user
from core.models import Profile, Schema
from tests.factories import SchemaFactory, SchemaRefFactory, UserFactory


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_get_local_user_returns_the_same_superuser():
    user = get_local_user()
    assert get_local_user().pk == user.pk
    assert get_user_model().objects.filter(username=LOCAL_USERNAME).count() == 1
    assert user.username == LOCAL_USERNAME
    assert user.is_staff
    assert user.is_superuser
    assert not user.has_usable_password()


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_get_local_user_has_a_profile():
    user = get_local_user()
    assert Profile.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_get_local_user_refuses_when_accounts_are_on():
    with pytest.raises(RuntimeError):
        get_local_user()
    assert not get_user_model().objects.filter(username=LOCAL_USERNAME).exists()


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_local_only_mode_requests_run_as_local_user():
    client = Client()
    response = client.get("/account/profile/")
    assert response.status_code == 200
    assert response.wsgi_request.user == get_local_user()


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_local_only_mode_overrides_logged_in_user():
    client = Client()
    client.force_login(UserFactory())
    response = client.get("/account/profile/")
    assert response.wsgi_request.user == get_local_user()


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_local_only_mode_admin_loads_without_login():
    client = Client()
    response = client.get("/admin/")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_local_only_mode_schema_can_be_created_without_login():
    schema_ref_url = "https://example.com/definition.json"
    readme_url = "https://example.com/readme.md"
    client = Client()
    with requests_mock.Mocker() as m:
        m.get(schema_ref_url, text="{}")
        m.get(readme_url, text="# README")
        response = client.post(
            "/manage/schema/new",
            {
                "name": "Local schema",
                "readme_url": readme_url,
                "schema_refs-0-url": schema_ref_url,
                "documentation_items-TOTAL_FORMS": 0,
                "documentation_items-INITIAL_FORMS": 0,
                "schema_refs-TOTAL_FORMS": 1,
                "schema_refs-INITIAL_FORMS": 0,
                "implementations-TOTAL_FORMS": 0,
                "implementations-INITIAL_FORMS": 0,
            },
        )
    schema = Schema.objects.get(name="Local schema")
    assert response.status_code == 302
    assert schema.created_by == get_local_user()
    assert schema.schemaref_set.get().created_by == get_local_user()


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_local_only_mode_schema_can_be_edited_without_login():
    schema = SchemaFactory(created_by=get_local_user(), published_at=None)
    schema_ref = SchemaRefFactory(
        schema=schema,
        created_by=schema.created_by,
        url="https://example.com/definition.json",
    )
    readme_url = "https://example.com/readme.md"
    client = Client()
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, text="{}")
        m.get(readme_url, text="# README")
        response = client.post(
            f"/manage/schema/{schema.id}",
            {
                "name": "Renamed schema",
                "readme_url": readme_url,
                "schema_refs-0-id": schema_ref.id,
                "schema_refs-0-url": schema_ref.url,
                "documentation_items-TOTAL_FORMS": 0,
                "documentation_items-INITIAL_FORMS": 0,
                "schema_refs-TOTAL_FORMS": 1,
                "schema_refs-INITIAL_FORMS": 1,
                "implementations-TOTAL_FORMS": 0,
                "implementations-INITIAL_FORMS": 0,
            },
        )
    assert response.status_code == 302
    schema.refresh_from_db()
    assert schema.name == "Renamed schema"


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_local_only_mode_schema_can_be_published_without_login():
    schema = SchemaFactory(created_by=get_local_user(), published_at=None)
    schema_ref = SchemaRefFactory(schema=schema, created_by=schema.created_by)
    client = Client()
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, text="{}")
        response = client.post(f"/manage/schema/{schema.id}/publish")
    assert response.status_code == 302
    schema.refresh_from_db()
    assert schema.published_at is not None


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_local_only_mode_schema_can_be_deleted_without_login():
    schema = SchemaFactory(created_by=get_local_user(), published_at=None)
    client = Client()
    response = client.post(f"/manage/schema/{schema.id}/delete")
    assert response.status_code == 302
    assert not Schema.objects.filter(id=schema.id).exists()


@pytest.mark.django_db
@override_settings(ENABLE_ACCOUNTS=False)
def test_local_only_mode_cannot_manage_other_users_schemas():
    schema = SchemaFactory(published_at=None)
    client = Client()
    response = client.post(f"/manage/schema/{schema.id}/delete")
    assert response.status_code == 404
    assert Schema.objects.filter(id=schema.id).exists()


@pytest.mark.django_db
def test_accounts_mode_leaves_anonymous_users_logged_out():
    client = Client()
    response = client.get("/account/profile/")
    assert response.status_code == 302
    assert not response.wsgi_request.user.is_authenticated
    assert not get_user_model().objects.filter(username=LOCAL_USERNAME).exists()


@pytest.mark.django_db
def test_accounts_mode_keeps_logged_in_user():
    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get("/account/profile/")
    assert response.status_code == 200
    assert response.wsgi_request.user == user
