import json
import pytest
import requests_mock
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, override_settings
from mcp.client import Client as MCPClient
from core.checks import check_local_only_hosts
from core.local_user import LOCAL_USERNAME, get_local_user
from core.mcp.server import build_mcp_server, mcp
from core.mcp.sync_to_async_with_db_cleanup import (
    sync_to_async_with_db_cleanup as sync_to_async,
)
from core.models import Profile, Schema
from tests.factories import SchemaFactory, SchemaRefFactory, UserFactory


@pytest.mark.django_db
def test_get_local_user_returns_the_same_superuser(local_only_mode):
    user = get_local_user()
    assert get_local_user().pk == user.pk
    assert get_user_model().objects.filter(username=LOCAL_USERNAME).count() == 1
    assert user.username == LOCAL_USERNAME
    assert user.is_staff
    assert user.is_superuser
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_get_local_user_has_a_profile(local_only_mode):
    user = get_local_user()
    assert Profile.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_get_local_user_refuses_when_accounts_are_on():
    with pytest.raises(RuntimeError):
        get_local_user()
    assert not get_user_model().objects.filter(username=LOCAL_USERNAME).exists()


def test_check_local_only_hosts_refuses_nonlocal_hosts(settings):
    settings.ENABLE_ACCOUNTS = False
    settings.ALLOW_NONLOCAL_HOSTS_WITHOUT_ACCOUNTS = False
    settings.ALLOWED_HOSTS = ["localhost", "schemas.example.com"]
    with pytest.raises(ImproperlyConfigured, match=r"\(schemas\.example\.com\)"):
        check_local_only_hosts()


@pytest.mark.django_db
def test_local_only_mode_requests_run_as_local_user(local_only_mode):
    client = Client()
    response = client.get("/manage/schema/new")
    assert response.status_code == 200
    assert response.wsgi_request.user == get_local_user()


@pytest.mark.django_db
def test_local_only_mode_overrides_logged_in_user(local_only_mode):
    client = Client()
    client.force_login(UserFactory())
    response = client.get("/manage/schema/new")
    assert response.wsgi_request.user == get_local_user()


@pytest.mark.django_db
def test_local_only_mode_admin_loads_without_login(local_only_mode):
    client = Client()
    response = client.get("/admin/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_local_only_mode_profile_renders_and_has_no_account_links(local_only_mode):
    response = Client().get("/account/profile/")
    assert response.status_code == 200
    assert b"Change password" not in response.content
    assert b"Sign out" not in response.content
    assert b"API Key" not in response.content


@pytest.mark.django_db
def test_local_only_mode_schema_can_be_created_without_login(local_only_mode):
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
def test_local_only_mode_schema_can_be_edited_without_login(local_only_mode):
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
def test_local_only_mode_schema_can_be_published_without_login(local_only_mode):
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
def test_local_only_mode_schema_can_be_deleted_without_login(local_only_mode):
    schema = SchemaFactory(created_by=get_local_user(), published_at=None)
    client = Client()
    response = client.post(f"/manage/schema/{schema.id}/delete")
    assert response.status_code == 302
    assert not Schema.objects.filter(id=schema.id).exists()


@pytest.mark.django_db
def test_local_only_mode_cannot_manage_other_users_schemas(local_only_mode):
    schema = SchemaFactory(published_at=None)
    client = Client()
    response = client.post(f"/manage/schema/{schema.id}/delete")
    assert response.status_code == 404
    assert Schema.objects.filter(id=schema.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/account/login/",
        "/account/signup/",
        "/account/api-key/",
        "/oauth/authorize/",
        "/oauth/token/",
        "/oauth/register/",
        "/.well-known/oauth-authorization-server",
    ],
)
def test_local_only_mode_account_and_oauth_urls_are_removed(local_only_mode, path):
    response = Client().get(path)
    assert response.status_code == 404


API_MANIFEST = {
    "name": "Local API schema",
    "documents": {
        "https://example.com/definition.json": {"type": "definition"},
    },
}


@pytest.mark.django_db
def test_local_only_mode_api_create_works_without_api_key(local_only_mode):
    # Enforce CSRF checks, like the api_client fixture, to make sure the
    # request isn't relying on the test client's default CSRF exemption.
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        "/api/schemas", data=json.dumps(API_MANIFEST), content_type="application/json"
    )
    assert response.status_code == 200
    schema = Schema.objects.get(id=response.json()["data"]["id"])
    assert schema.created_by == get_local_user()


@pytest.mark.django_db
def test_local_only_mode_api_update_works_without_api_key(local_only_mode):
    schema = SchemaFactory(created_by=get_local_user(), published_at=None)
    client = Client(enforce_csrf_checks=True)
    response = client.put(
        f"/api/schemas/{schema.id}",
        data=json.dumps(API_MANIFEST),
        content_type="application/json",
    )
    assert response.status_code == 200
    schema.refresh_from_db()
    assert schema.name == API_MANIFEST["name"]


@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=1)
def test_local_only_mode_api_has_no_rate_limit(local_only_mode):
    client = Client()
    for _ in range(3):
        response = client.get("/api/find?id=https://example.com/missing")
        assert response.status_code == 404


# Use transaction=True as in tests/test_mcp.py
@pytest.mark.anyio
@pytest.mark.django_db(transaction=True)
async def test_local_only_mode_mcp_create_schema_works_without_auth(local_only_mode):
    async with MCPClient(mcp) as client:
        result = await client.call_tool(
            "create_schema", arguments={"manifest": json.dumps(API_MANIFEST)}
        )
    assert not result.is_error
    schema = await sync_to_async(Schema.objects.select_related("created_by").get)(
        name=API_MANIFEST["name"]
    )
    assert schema.created_by == await sync_to_async(get_local_user)()


@pytest.mark.anyio
@pytest.mark.django_db(transaction=True)
async def test_local_only_mode_mcp_update_schema_works_without_auth(local_only_mode):
    local_user = await sync_to_async(get_local_user)()
    schema = await sync_to_async(SchemaFactory.create)(
        created_by=local_user, published_at=None
    )
    async with MCPClient(mcp) as client:
        result = await client.call_tool(
            "update_schema",
            arguments={"schema_id": schema.id, "manifest": json.dumps(API_MANIFEST)},
        )
    assert not result.is_error
    await sync_to_async(schema.refresh_from_db)()
    assert schema.name == API_MANIFEST["name"]


@pytest.mark.anyio
@pytest.mark.django_db(transaction=True)
async def test_local_only_mode_mcp_search_schemas_works_without_auth(
    local_only_mode,
):
    local_user = await sync_to_async(get_local_user)()
    await sync_to_async(SchemaFactory.create)(
        name="Local private schema", created_by=local_user, published_at=None
    )
    async with MCPClient(mcp) as client:
        result = await client.call_tool("search_schemas", arguments={"scope": "user"})
    assert not result.is_error
    assert "Local private schema" in result.content[0].text


def test_local_only_mode_mcp_server_requires_no_token(local_only_mode):
    mcp_server = build_mcp_server()
    assert mcp_server.settings.auth is None
