import pytest
import json
from mcp.shared.memory import create_connected_server_and_client_session
from asgiref.sync import sync_to_async
from unittest.mock import patch, MagicMock
from starlette.responses import JSONResponse
from django.test import override_settings
from core.mcp.server import mcp
from core.mcp.api_key_authentication import MCPAPIKeyAuthenticationMiddleware
from factories import SchemaFactory, ProfileFactory, UserFactory


# Force all database tests in this file to flush tables instead of rolling back,
# preventing background threads (sync_to_async) from leaking state.
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def anyio_backend():
    # Required by pytest-anyio to specify the async backend.
    return "asyncio"


@pytest.fixture
async def client_session():
    # Creates an isolated in-memory client session connected to your FastMCP server.
    # raise_exceptions=True ensures that internal server errors fail the test immediately.
    async with create_connected_server_and_client_session(
        mcp, raise_exceptions=True
    ) as session:
        yield session


@pytest.fixture
async def error_client_session():
    # Creates a client session where the server catches unhandled exceptions
    # and serializes them into MCP error payloads over the wire. Use this
    # specifically for testing expected error states.
    async with create_connected_server_and_client_session(
        mcp, raise_exceptions=False
    ) as session:
        yield session


def create_mock_request(headers=None, path="/mcp/sse"):
    # Helper to mock a Starlette Request object
    request = MagicMock()
    request.headers = headers or {}
    request.url.path = path
    return request


# A dummy call_next function that pretends the inner application processed the request successfully
async def dummy_call_next(request):
    return JSONResponse({"status": "success"}, status_code=200)


@pytest.mark.anyio
async def test_middleware_requires_api_key_header():
    middleware = MCPAPIKeyAuthenticationMiddleware(app=None)
    request = create_mock_request(headers={})
    response = await middleware.dispatch(request, dummy_call_next)
    assert response.status_code == 401
    body = json.loads(response.body)
    assert body["message"] == "Missing API Key"


@pytest.mark.anyio
async def test_middleware_requires_valid_api_key():
    middleware = MCPAPIKeyAuthenticationMiddleware(app=None)
    request = create_mock_request(headers={"x-api-key": "invalid_key_value"})
    response = await middleware.dispatch(request, dummy_call_next)
    assert response.status_code == 401
    body = json.loads(response.body)
    assert body["message"] == "Invalid API key"


@pytest.mark.anyio
async def test_middleware_allows_valid_api_key():
    profile = await sync_to_async(ProfileFactory.create)()
    raw_api_key = await sync_to_async(profile.set_new_api_key)()
    middleware = MCPAPIKeyAuthenticationMiddleware(app=None)
    request = create_mock_request(headers={"x-api-key": raw_api_key})
    response = await middleware.dispatch(request, dummy_call_next)
    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["status"] == "success"


@pytest.mark.anyio
@override_settings(HOURLY_API_REQUEST_LIMIT=2)
async def test_middleware_enforces_rate_limit():
    profile = await sync_to_async(ProfileFactory.create)()
    raw_api_key = await sync_to_async(profile.set_new_api_key)()
    middleware = MCPAPIKeyAuthenticationMiddleware(app=None)
    request = create_mock_request(headers={"x-api-key": raw_api_key})

    # Burn through the allowed limit
    for _ in range(2):
        response = await middleware.dispatch(request, dummy_call_next)
        assert response.status_code == 200

    # The third request should be intercepted by the middleware and return 429
    blocked_response = await middleware.dispatch(request, dummy_call_next)
    assert blocked_response.status_code == 429
    body = json.loads(blocked_response.body)
    assert body["message"] == "Too many requests"


@pytest.mark.anyio
async def test_manifest_resource(client_session):
    result = await client_session.read_resource("schema://manifest.json")
    parsed_contents = json.loads(result.contents[0].text)
    assert parsed_contents["$id"] == "https://id.schemas.pub/o/dti/manifest.schema.json"


@pytest.mark.anyio
async def test_schema_by_id_resource(client_session):
    schema = await sync_to_async(SchemaFactory.create)()
    manifest = await sync_to_async(schema.to_manifest)()
    result = await client_session.read_resource(f"schema://{schema.id}")
    # We parse the string result as JSON so we can stringify it with sorted keys
    parsed_contents = json.loads(result.contents[0].text)
    sorted_contents_str = json.dumps(parsed_contents, sort_keys=True)
    expected_manifest_str = json.dumps(manifest, sort_keys=True)
    # Now we have two JSON strings with sorted keys we can just compare directly
    assert sorted_contents_str == expected_manifest_str


@pytest.mark.anyio
async def test_schema_by_id_resource_supports_own_private_schemas(client_session):
    schema = await sync_to_async(SchemaFactory.create)(published_at=None)
    manifest = await sync_to_async(schema.to_manifest)()
    # Mock the current_user (normally provided by middleware)
    mock_current_user = MagicMock()
    mock_current_user.get.return_value = schema.created_by
    with patch("core.mcp.server.current_user", mock_current_user):
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
):
    # Create a private schema
    schema = await sync_to_async(SchemaFactory.create)(published_at=None)

    # Mock the current_user to be a completely different user from the creator
    mock_current_user = MagicMock()
    mock_current_user.get.return_value = await sync_to_async(UserFactory.create)()

    with patch("core.mcp.server.current_user", mock_current_user):
        expected_error_message = f"Resource not found: Schema with ID '{schema.id}' does not exist or you lack permission to view it."

        with pytest.raises(Exception, match=expected_error_message):
            await error_client_session.read_resource(f"schema://{schema.id}")
