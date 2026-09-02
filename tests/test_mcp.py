import base64
import hashlib
import json
import re
import secrets
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
import httpx2
import pytest
import requests_mock
from django.conf import settings
from django.test import Client as DjangoTestClient, override_settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from mcp.client import Client
from mcp.server.auth.provider import AccessToken as VerifiedAccessToken
from oauth2_provider.models import get_access_token_model, get_application_model
from core.mcp.rate_limit import RATE_LIMITED
from core.mcp.server import mcp, MAX_PAGE_SIZE
from core.mcp.sync_to_async_with_db_cleanup import (
    sync_to_async_with_db_cleanup as sync_to_async,
)
from core.models import Schema
from factories import SchemaFactory, UserFactory, SchemaRefFactory
from schemaindex.asgi import create_application as create_asgi_application
from utils import assert_schema_matches_manifest

AccessToken = get_access_token_model()
Application = get_application_model()

REDIRECT_URI = "http://localhost:6274/oauth/callback"

RESOURCE_METADATA_URL = f"{settings.SITE_URL}/.well-known/oauth-protected-resource/mcp"

# Force all database tests in this file to flush tables instead of rolling back,
# preventing background threads (sync_to_async) from leaking state.
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def anyio_backend():
    # Required by pytest-anyio to specify the async backend.
    return "asyncio"


@pytest.fixture
async def client_session():
    async with Client(mcp, raise_exceptions=True) as client:
        yield client


@pytest.fixture
def authenticate_as():
    with patch("core.mcp.server.get_access_token") as get_token:
        get_token.return_value = None

        def _authenticate_as(user):
            get_token.return_value = VerifiedAccessToken(
                token="in-memory-test-token",
                client_id="in-memory-test-client",
                scopes=["mcp"],
                subject=str(user.id),
            )

        yield _authenticate_as


@pytest.fixture
async def error_client_session():
    # Creates a client where the server catches unhandled exceptions
    # and serializes them into MCP error payloads over the wire. Use this
    # specifically for testing expected error states.
    async with Client(mcp, raise_exceptions=False) as client:
        yield client


@pytest.fixture
async def mcp_http_client():
    with override_settings(ENABLE_MCP_SERVER=True):
        application = create_asgi_application()

    async with mcp.session_manager.run():
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=application),
            base_url=settings.SITE_URL,
        ) as http:
            yield http


def issue_access_token(user, *, scope="mcp", expires_in=3600):
    application = Application.objects.create(
        name="Test MCP client",
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=REDIRECT_URI,
        registration_source=Application.RegistrationSource.DCR,
    )
    raw_token = secrets.token_urlsafe(32)
    AccessToken.objects.create(
        user=user,
        application=application,
        token=raw_token,
        scope=scope,
        expires=timezone.now() + timedelta(seconds=expires_in),
    )
    return raw_token


def complete_oauth_flow(user):
    client = DjangoTestClient()

    registration = client.post(
        "/oauth/register/",
        data=json.dumps({
            "client_name": "MCP Inspector",
            "redirect_uris": [REDIRECT_URI],
            "grant_types": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_method": "none",
        }),
        content_type="application/json",
    )
    assert registration.status_code == 201, registration.content
    client_id = registration.json()["client_id"]

    code_verifier = get_random_string(64)
    verifier_digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(verifier_digest).decode().rstrip("=")

    client.force_login(user)
    consent = client.post(
        "/oauth/authorize/",
        data={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "mcp",
            "state": "test-state",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "allow": True,
        },
    )
    assert consent.status_code == 302, consent.content
    redirect_query = parse_qs(urlparse(consent["Location"]).query)
    assert redirect_query["state"] == ["test-state"], redirect_query

    token_response = client.post(
        "/oauth/token/",
        data={
            "grant_type": "authorization_code",
            "code": redirect_query["code"][0],
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
    )
    assert token_response.status_code == 200, token_response.content
    return token_response.json()


async def post_mcp(http, method, params=None, *, token=None):
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    message = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        message["params"] = params

    return await http.post("/mcp", json=message, headers=headers)


async def call_tool(http, name, arguments=None, *, token=None):
    return await post_mcp(
        http, "tools/call", {"name": name, "arguments": arguments or {}}, token=token
    )


@pytest.mark.anyio
async def test_manifest_resource(client_session):
    result = await client_session.read_resource("schema://manifest.json")
    parsed_contents = json.loads(result.contents[0].text)
    assert parsed_contents["$id"] == "https://id.schemas.pub/o/dti/manifest.schema.json"


@pytest.mark.anyio
async def test_schema_by_id_resource(client_session, authenticate_as):
    schema = await sync_to_async(SchemaFactory.create)()
    manifest = await sync_to_async(schema.to_manifest)()
    # A published schema is readable by any authenticated caller, creator or not.
    authenticate_as(await sync_to_async(UserFactory.create)())
    result = await client_session.read_resource(f"schema://{schema.id}")
    # We parse the string result as JSON so we can stringify it with sorted keys
    parsed_contents = json.loads(result.contents[0].text)
    sorted_contents_str = json.dumps(parsed_contents, sort_keys=True)
    expected_manifest_str = json.dumps(manifest, sort_keys=True)
    # Now we have two JSON strings with sorted keys we can just compare directly
    assert sorted_contents_str == expected_manifest_str


@pytest.mark.anyio
async def test_schema_by_id_resource_supports_own_private_schemas(
    client_session, authenticate_as
):
    schema = await sync_to_async(SchemaFactory.create)(published_at=None)
    manifest = await sync_to_async(schema.to_manifest)()
    authenticate_as(schema.created_by)
    result = await client_session.read_resource(f"schema://{schema.id}")
    # We parse the string result as JSON so we can stringify it with sorted keys
    parsed_contents = json.loads(result.contents[0].text)
    sorted_contents_str = json.dumps(parsed_contents, sort_keys=True)
    expected_manifest_str = json.dumps(manifest, sort_keys=True)
    # Now we have two JSON strings with sorted keys we can just compare directly
    assert sorted_contents_str == expected_manifest_str


@pytest.mark.anyio
async def test_schema_by_id_resource_errors_for_inaccessible_schemas(
    error_client_session,
    authenticate_as,
):
    # Create a private schema
    schema = await sync_to_async(SchemaFactory.create)(published_at=None)

    # Authenticate as a completely different user from the creator
    authenticate_as(await sync_to_async(UserFactory.create)())

    expected_error_message = f"Resource not found: Schema with ID '{schema.id}' does not exist or you lack permission to view it."

    with pytest.raises(Exception, match=expected_error_message):
        await error_client_session.read_resource(f"schema://{schema.id}")


@pytest.mark.anyio
async def test_create_schema_success(client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    manifest = {
        "name": "Test Schema",
        "description": "A schema created via MCP tool",
        "documents": {
            "https://example.com/mcp-definition.json": {
                "type": "definition",
                "name": "Test Definition",
            },
        },
    }
    manifest_str = json.dumps(manifest)

    result = await client_session.call_tool(
        "create_schema", arguments={"manifest": manifest_str}
    )
    match = re.search(r"ID:\s*(\d+)", result.content[0].text)
    assert match
    schema_id = int(match.group(1))
    schema = await sync_to_async(Schema.objects.get)(id=schema_id)
    await sync_to_async(assert_schema_matches_manifest)(schema, manifest)


@pytest.mark.anyio
async def test_create_schema_invalid_json(error_client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    # Intentionally invalid JSON
    manifest_str = '{"name": "Invalid JSON", '
    expected_error_message = "Undecodable JSON payload"
    result = await error_client_session.call_tool(
        "create_schema", arguments={"manifest": manifest_str}
    )
    assert result.is_error
    assert expected_error_message in result.content[0].text


@pytest.mark.anyio
async def test_create_schema_invalid_manifest_format(
    error_client_session, authenticate_as
):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    # Valid JSON, but not a valid manifest
    manifest_str = json.dumps({"wrong_key": "wrong_value"})
    expected_error_message = "Incorrect JSON payload format"
    result = await error_client_session.call_tool(
        "create_schema", arguments={"manifest": manifest_str}
    )
    assert result.is_error
    assert expected_error_message in result.content[0].text


@pytest.mark.anyio
async def test_create_schema_validation_error(error_client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)
    other_user = await sync_to_async(UserFactory.create)()
    published_schema = await sync_to_async(SchemaFactory.create)(created_by=other_user)
    url = "https://example.com/conflict.json"
    await sync_to_async(SchemaRefFactory.create)(schema=published_schema, url=url)

    manifest = {
        "name": "Conflict Schema",
        "public": True,
        "documents": {url: {"type": "definition"}},
    }
    manifest_str = json.dumps(manifest)

    expected_error_message = "Validation Error"
    result = await error_client_session.call_tool(
        "create_schema", arguments={"manifest": manifest_str}
    )
    assert result.is_error
    assert expected_error_message in result.content[0].text


@pytest.mark.anyio
async def test_update_schema_success(client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)
    schema = await sync_to_async(SchemaFactory.create)(created_by=user)

    manifest = {
        "name": "Test Schema",
        "description": "A schema updated via MCP tool",
        "documents": {
            "https://example.com/mcp-definition.json": {
                "type": "definition",
                "name": "Test Definition",
            },
        },
        "public": True,
    }
    manifest_str = json.dumps(manifest)

    result = await client_session.call_tool(
        "update_schema", arguments={"schema_id": schema.id, "manifest": manifest_str}
    )
    match = re.search(r"ID:\s*(\d+)", result.content[0].text)
    assert match
    schema_id = int(match.group(1))
    assert schema_id == schema.id
    await sync_to_async(schema.refresh_from_db)()
    await sync_to_async(assert_schema_matches_manifest)(schema, manifest)


@pytest.mark.anyio
async def test_update_schema_forbidden(error_client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)
    # Schema created by another user
    other_user = await sync_to_async(UserFactory.create)()
    schema = await sync_to_async(SchemaFactory.create)(created_by=other_user)

    expected_error_message = f"Schema with ID '{schema.id}' not found."
    result = await error_client_session.call_tool(
        "update_schema", arguments={"schema_id": schema.id, "manifest": "{}"}
    )
    assert result.is_error
    assert expected_error_message in result.content[0].text


@pytest.mark.anyio
async def test_update_schema_not_found(error_client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)
    # Schema does not exist
    non_existent_id = 99999
    expected_error_message = f"Schema with ID '{non_existent_id}' not found."
    result = await error_client_session.call_tool(
        "update_schema", arguments={"schema_id": non_existent_id, "manifest": "{}"}
    )
    assert result.is_error
    assert expected_error_message in result.content[0].text


@pytest.mark.anyio
async def test_update_schema_invalid_json(error_client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)
    schema = await sync_to_async(SchemaFactory.create)(created_by=user)
    # Intentionally invalid JSON
    manifest_str = '{"name": "Invalid JSON", '
    expected_error_message = "Undecodable JSON payload"
    result = await error_client_session.call_tool(
        "update_schema", arguments={"schema_id": schema.id, "manifest": manifest_str}
    )
    assert result.is_error
    assert expected_error_message in result.content[0].text


@pytest.mark.anyio
async def test_update_schema_invalid_manifest_format(
    error_client_session, authenticate_as
):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)
    schema = await sync_to_async(SchemaFactory.create)(created_by=user)
    # Valid JSON, but not a valid manifest
    manifest_str = json.dumps({"wrong_key": "wrong_value"})
    expected_error_message = "Incorrect JSON payload format"
    result = await error_client_session.call_tool(
        "update_schema", arguments={"schema_id": schema.id, "manifest": manifest_str}
    )
    assert result.is_error
    assert expected_error_message in result.content[0].text


@pytest.mark.anyio
async def test_update_schema_validation_error(error_client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)
    schema = await sync_to_async(SchemaFactory.create)(created_by=user)

    other_user = await sync_to_async(UserFactory.create)()
    published_schema = await sync_to_async(SchemaFactory.create)(created_by=other_user)
    url = "https://example.com/conflict.json"
    await sync_to_async(SchemaRefFactory.create)(schema=published_schema, url=url)

    manifest = {
        "name": "Conflict Schema",
        "public": True,
        "documents": {url: {"type": "definition"}},
    }
    manifest_str = json.dumps(manifest)

    expected_error_message = "Validation Error"
    result = await error_client_session.call_tool(
        "update_schema", arguments={"schema_id": schema.id, "manifest": manifest_str}
    )
    assert result.is_error
    assert expected_error_message in result.content[0].text


@pytest.mark.anyio
async def test_search_schemas_no_results(client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    result = await client_session.call_tool(
        "search_schemas", arguments={"query": "nonexistent"}
    )

    assert result.content[0].text == "No results matched your query."


@pytest.mark.anyio
async def test_search_schemas_scope(client_session, authenticate_as):
    user1 = await sync_to_async(UserFactory.create)()
    user2 = await sync_to_async(UserFactory.create)()
    authenticate_as(user1)

    # Create a schema for user1
    await sync_to_async(SchemaFactory.create)(created_by=user1, name="User One Schema")

    # Create an accessible (published) schema for user2
    await sync_to_async(SchemaFactory.create)(
        created_by=user2, name="User Two Public Schema", published_at=timezone.now()
    )

    # Search with 'user' scope - should only return user1's schema
    user_scope_result = await client_session.call_tool(
        "search_schemas", arguments={"scope": "user"}
    )
    assert "User One Schema" in user_scope_result.content[0].text
    assert "User Two Public Schema" not in user_scope_result.content[0].text

    # Search with 'all' scope - should return both
    all_scope_result = await client_session.call_tool(
        "search_schemas", arguments={"scope": "all"}
    )
    assert "User One Schema" in all_scope_result.content[0].text
    assert "User Two Public Schema" in all_scope_result.content[0].text


@pytest.mark.anyio
async def test_search_schemas_description_query_filtering(
    client_session, authenticate_as
):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    await sync_to_async(SchemaFactory.create)(
        created_by=user, name="Alpha", description="A special testing schema"
    )
    await sync_to_async(SchemaFactory.create)(
        created_by=user, name="Beta", description="Another item entirely"
    )

    result = await client_session.call_tool(
        "search_schemas", arguments={"query": "SPECIAL"}
    )
    text = result.content[0].text

    assert "Alpha" in text
    assert "Beta" not in text


@pytest.mark.anyio
async def test_search_schemas_name_query_filtering(client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    await sync_to_async(SchemaFactory.create)(
        created_by=user, name="Alpha", description="A special testing schema"
    )
    await sync_to_async(SchemaFactory.create)(
        created_by=user, name="Beta", description="Another item entirely"
    )

    result = await client_session.call_tool(
        "search_schemas", arguments={"query": "alpha"}
    )
    text = result.content[0].text

    assert "Alpha" in text
    assert "Beta" not in text


@pytest.mark.anyio
async def test_search_schemas_id_value_query_filtering(client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    schema = await sync_to_async(SchemaFactory.create)(
        created_by=user, name="Alpha", description="A special testing schema"
    )
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(mock_url, text=mock_content)
        await sync_to_async(SchemaRefFactory.create)(url=mock_url, schema=schema)

    await sync_to_async(SchemaFactory.create)(
        created_by=user, name="Beta", description="Another item entirely"
    )

    result = await client_session.call_tool(
        "search_schemas", arguments={"query": mock_id_value.upper()}
    )
    text = result.content[0].text

    assert "Alpha" in text
    assert "Beta" not in text


@pytest.mark.anyio
async def test_search_schemas_pagination(client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    # Trigger pagination
    for i in range(MAX_PAGE_SIZE + 1):
        await sync_to_async(SchemaFactory.create)(
            created_by=user, name=f"Pagination Schema {i}"
        )

    # Fetch page 1
    result_page_1 = await client_session.call_tool(
        "search_schemas", arguments={"page": 1}
    )
    text_1 = result_page_1.content[0].text

    assert f"Found {MAX_PAGE_SIZE + 1} schemas matching your query." in text_1
    assert "The results are truncated. Showing page 1 of 2:" in text_1
    assert (
        'To get the next page, use `search_schemas(query: None, scope: "all", page: 2)`'
        in text_1
    )

    # Fetch page 2
    result_page_2 = await client_session.call_tool(
        "search_schemas", arguments={"page": 2}
    )
    text_2 = result_page_2.content[0].text

    assert "Showing page 2 of 2:" in text_2


@pytest.mark.anyio
async def test_search_schemas_pagination_with_query(client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    # Trigger pagination with a specific query
    for i in range(MAX_PAGE_SIZE + 1):
        await sync_to_async(SchemaFactory.create)(
            created_by=user, name=f"Alpha Schema {i}"
        )

    # Fetch page 1
    result_page_1 = await client_session.call_tool(
        "search_schemas", arguments={"query": "alpha", "page": 1}
    )
    text_1 = result_page_1.content[0].text

    assert f"Found {MAX_PAGE_SIZE + 1} schemas matching your query." in text_1
    assert "The results are truncated. Showing page 1 of 2:" in text_1
    assert (
        "To get the next page, use `search_schemas(query: 'alpha', scope: \"all\", page: 2)`"
        in text_1
    )

    # Fetch page 2
    result_page_2 = await client_session.call_tool(
        "search_schemas", arguments={"query": "alpha", "page": 2}
    )
    text_2 = result_page_2.content[0].text

    assert "Showing page 2 of 2:" in text_2


@pytest.mark.anyio
async def test_search_schemas_invalid_page(error_client_session, authenticate_as):
    user = await sync_to_async(UserFactory.create)()
    authenticate_as(user)

    # Create 1 schema so there is only 1 page
    await sync_to_async(SchemaFactory.create)(created_by=user)

    result = await error_client_session.call_tool(
        "search_schemas", arguments={"page": 5}
    )

    assert result.is_error
    assert (
        "Invalid page number for query. Please request a page between 1 and 1."
        in result.content[0].text
    )


# These tests use the mcp_http_client which actually go over HTTP
# so we can test authentication.


@pytest.mark.anyio
async def test_associated_user_for_bearer_token_provided_to_tools(mcp_http_client):
    user = await sync_to_async(UserFactory.create)()
    # A private schema is visible only to its creator, so finding it is proof that
    # the token's user reached the tool.
    await sync_to_async(SchemaFactory.create)(
        created_by=user, name="Token Bearer Schema", published_at=None
    )
    token = await sync_to_async(issue_access_token)(user)
    response = await call_tool(
        mcp_http_client, "search_schemas", {"scope": "user"}, token=token
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert not result.get("isError")
    assert "Token Bearer Schema" in result["content"][0]["text"]


@pytest.mark.anyio
async def test_request_without_a_bearer_token_is_challenged(mcp_http_client):
    response = await post_mcp(mcp_http_client, "tools/list")
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer ")
    assert 'error="invalid_token"' in challenge
    # The challenge points clients at the RFC 9728 document django-oauth-toolkit serves.
    assert f'resource_metadata="{RESOURCE_METADATA_URL}"' in challenge


@pytest.mark.anyio
async def test_unknown_bearer_token_is_rejected(mcp_http_client):
    response = await post_mcp(mcp_http_client, "tools/list", token="not-a-real-token")
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.anyio
async def test_expired_bearer_token_is_rejected(mcp_http_client):
    user = await sync_to_async(UserFactory.create)()
    token = await sync_to_async(issue_access_token)(user, expires_in=-60)
    response = await post_mcp(mcp_http_client, "tools/list", token=token)
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.anyio
async def test_token_without_the_mcp_scope_is_forbidden(mcp_http_client):
    user = await sync_to_async(UserFactory.create)()
    token = await sync_to_async(issue_access_token)(user, scope="profile")
    response = await post_mcp(mcp_http_client, "tools/list", token=token)
    # 403, not 401: the token is valid, it just isn't authorized for this resource.
    assert response.status_code == 403
    assert 'error="insufficient_scope"' in response.headers["www-authenticate"]


@pytest.mark.anyio
async def test_token_of_an_unusable_application_is_rejected(mcp_http_client):
    user = await sync_to_async(UserFactory.create)()
    token = await sync_to_async(issue_access_token)(user)

    # The default is_usable() always returns True; a deployment that disables an
    # application should see its live tokens stop working.
    with patch.object(Application, "is_usable", return_value=False):
        response = await post_mcp(mcp_http_client, "tools/list", token=token)

    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.anyio
async def test_work_methods_are_refused_over_the_hourly_limit(mcp_http_client):
    user = await sync_to_async(UserFactory.create)()
    token = await sync_to_async(issue_access_token)(user)

    with override_settings(HOURLY_API_REQUEST_LIMIT=1):
        allowed = await call_tool(mcp_http_client, "search_schemas", token=token)
        blocked = await call_tool(mcp_http_client, "search_schemas", token=token)

    assert "error" not in allowed.json()
    assert blocked.status_code == 200
    error = blocked.json()["error"]
    assert error["code"] == RATE_LIMITED
    assert "Hourly request limit exceeded" in error["message"]


@pytest.mark.anyio
async def test_the_hourly_limit_is_per_user(mcp_http_client):
    exhausted_user = await sync_to_async(UserFactory.create)()
    other_user = await sync_to_async(UserFactory.create)()
    exhausted_token = await sync_to_async(issue_access_token)(exhausted_user)
    other_token = await sync_to_async(issue_access_token)(other_user)

    with override_settings(HOURLY_API_REQUEST_LIMIT=1):
        await call_tool(mcp_http_client, "search_schemas", token=exhausted_token)
        blocked = await call_tool(
            mcp_http_client, "search_schemas", token=exhausted_token
        )
        unaffected = await call_tool(
            mcp_http_client, "search_schemas", token=other_token
        )

    assert blocked.json()["error"]["code"] == RATE_LIMITED
    assert "error" not in unaffected.json()


@pytest.mark.anyio
async def test_a_dcr_client_reaches_the_tools_after_the_full_oauth_flow(
    mcp_http_client,
):
    user = await sync_to_async(UserFactory.create)()
    await sync_to_async(SchemaFactory.create)(
        created_by=user, name="End To End Schema", published_at=None
    )
    tokens = await sync_to_async(complete_oauth_flow)(user)
    assert tokens["token_type"] == "Bearer"
    assert tokens["scope"] == "mcp"

    response = await call_tool(
        mcp_http_client,
        "search_schemas",
        {"scope": "user"},
        token=tokens["access_token"],
    )
    assert response.status_code == 200
    assert "End To End Schema" in response.json()["result"]["content"][0]["text"]
