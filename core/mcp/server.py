import json
import logging
from typing import Literal
from jsonschema import ValidationError as JSONValidationError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from django.utils import timezone
from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from core.models import Schema
from core.utils import is_url
from core.mcp.sync_to_async_with_db_cleanup import sync_to_async_with_db_cleanup
from core.mcp.token_verifier import DjangoOAuthToolkitTokenVerifier
from core.mcp.rate_limit import enforce_rate_limit

MAX_PAGE_SIZE = 10

logger = logging.getLogger("schemaindex")
User = get_user_model()

mcp = MCPServer(
    "Schemas.Pub",
    token_verifier=DjangoOAuthToolkitTokenVerifier(),
    auth=AuthSettings(
        issuer_url=settings.SITE_URL,
        resource_server_url=settings.SITE_URL + "/mcp",
        required_scopes=["mcp"],
    ),
)

mcp.middleware.append(enforce_rate_limit)


def format_schema(schema):
    formatted_schema = f"""
Name: {schema.name}
Schemas.Pub ID: {schema.id}
MCP Resource URI: schema://{schema.id}
Schemas.Pub URL: https://schemas.pub{reverse("schema_detail", kwargs={"schema_id": schema.id})}
"""

    if schema.published_at is None or schema.published_at > timezone.now():
        formatted_schema += "Visibility: Private\n"

    if schema.description:
        formatted_schema += f"Description: {schema.description}\n"

    return formatted_schema


def get_authenticated_user():
    access_token = get_access_token()
    # subject is the Django user id, stamped by DjangoOAuthToolkitTokenVerifier
    return User.objects.get(pk=int(access_token.subject))


# We don't use type hints elsewhere in the codebase,
# but they can influence MCPServer's behavior for tools and resources.
# Function descriptions are the actual descriptions surfaced to models.
# Since MCP runs on JSON-RPC, types should be referenced in JSON terms
# instead of Python. For example, null instead of None,
# true/false instead of True/False, etc.


@mcp.tool()
@sync_to_async_with_db_cleanup
def search_schemas(
    query: str | None = None, scope: Literal["all", "user"] = "all", page: int = 1
):
    """
    Browse and search for schemas.

    Args:
      query: A search query. Can be a list of keywords or a JSON Schema $id. Pass null to list all schemas in scope. Optional; defaults to null.
      scope: 'user' to search only the user's own schemas (including private), or 'all' to search the entire registry. Optional; defaults to 'all'.
      page: Which page of search results to return. Optional; defaults to 1.
    """
    logger.info(
        "[MCP] search_schemas call: query=%s, scope=%s, page=%s", query, scope, page
    )

    user = get_authenticated_user()

    scoped_results = (
        Schema.objects.accessible_to(user)
        if scope == "all"
        else Schema.objects.filter(created_by=user)
    )

    # If query looks like a URL, assume it's an $id
    is_id_value_query = is_url(query)
    id_value_results = (
        scoped_results.filter(schemaref__id_value__iexact=query.strip()).distinct()
        if is_id_value_query
        else scoped_results.none()
    )

    has_exact_id_value_match = is_id_value_query and id_value_results.exists()

    # Log when someone searched for a specific schema by $id and we didn't have it
    if is_id_value_query and not has_exact_id_value_match and scope == "all":
        logger.info('[MCP] search_schemas $id miss: no schema found for "%s".', query)

    results = (
        id_value_results if has_exact_id_value_match else scoped_results.search(query)
    )

    total_count = results.count()
    if total_count == 0:
        logger.info("[MCP] search_schemas query returned no results")
        return "No results matched your query."

    total_pages = (total_count + MAX_PAGE_SIZE - 1) // MAX_PAGE_SIZE
    if page < 1 or page > total_pages:
        raise ValueError(
            f"Invalid page number for query. Please request a page between 1 and {total_pages}."
        )

    start = (page - 1) * MAX_PAGE_SIZE
    end = start + MAX_PAGE_SIZE
    paginated_results = results[start:end]

    formatted_results = [format_schema(schema) for schema in paginated_results]
    formatted_page = "\n---\n".join(formatted_results)

    match_description = (
        "with an $id exactly matching your query"
        if has_exact_id_value_match
        else "matching your query"
    )
    response = f"Found {total_count} schema{'s' if total_count > 1 else ''} {match_description}{':' if total_pages == 1 else '.'}"

    if total_pages == 1:
        response += f"\n\n{formatted_page}"
        return response

    response += f"\n\nThe results are truncated. Showing page {page} of {total_pages}:"
    response += f"\n\n{formatted_page}"

    if page < total_pages:
        formatted_query = f"{query!r}" if query else "null"
        response += f'\n\nTo get the next page, use `search_schemas(query: {formatted_query}, scope: "{scope}", page: {page + 1})`'

    return response


@mcp.resource("schema://manifest.json")
async def get_manifest_schema():
    """Get the Schemas.Pub manifest schema"""
    logger.info("[MCP] Fetching manifest definition")
    return json.dumps(Schema.get_manifest_schema(), indent=2)


@mcp.resource("schema://{schema_id}")
async def get_schema(schema_id: int):
    """Get a schema's manifest"""

    logger.info("[MCP] Fetching schema manifest: schema_id=%s", schema_id)

    @sync_to_async_with_db_cleanup
    def fetch_from_db():
        user = get_authenticated_user()

        try:
            schema = (
                Schema.objects
                .accessible_to(user)
                .prefetch_related("schemaref_set")
                .prefetch_related("documentationitem_set")
                .get(pk=schema_id)
            )

            return schema.to_manifest()
        except Schema.DoesNotExist:
            return None

    manifest = await fetch_from_db()

    if manifest is None:
        raise ResourceNotFoundError(
            f"Resource not found: Schema with ID '{schema_id}' does not exist or you lack permission to view it."
        )

    return json.dumps(manifest, indent=2)


def _validate_manifest_and_update_schema(manifest, schema):
    """
    Shared synchronous helper to validate a manifest, apply it to a Schema instance,
    and handle common validation exceptions.
    """
    try:
        manifest_data = Schema.validate_manifest(manifest)
        schema.overwrite_from_manifest(manifest_data)
    except json.JSONDecodeError as e:
        logger.warning("[MCP] Manifest JSON decode error: %s", e.msg)
        raise ValueError(f"Undecodable JSON payload: {e.msg}")
    except JSONValidationError as e:
        logger.warning("[MCP] Manifest JSON validation error: %s", e.message)
        raise ValueError(f"Incorrect JSON payload format: {e.message}")
    except DjangoValidationError as e:
        logger.warning("[MCP] Manifest Django validation error: %s", e.message)
        raise ValueError(f"Validation Error: {e.message}")


@mcp.tool()
async def create_schema(manifest: str):
    """
    Create a new schema from a manifest.
    The manifest should be a JSON string following the Schemas.Pub manifest schema available at schema://manifest.json
    """
    logger.info("[MCP] create_schema called")

    @sync_to_async_with_db_cleanup
    def do_create():
        user = get_authenticated_user()
        schema = Schema(created_by=user)
        _validate_manifest_and_update_schema(manifest, schema)
        response = "Schema created successfully:\n\n"
        response += format_schema(schema)
        return response

    return await do_create()


@mcp.tool()
async def update_schema(schema_id: int, manifest: str):
    """
    Update an existing schema from a manifest.
    The manifest should be a JSON string following the Schemas.Pub manifest schema available at schema://manifest.json
    """
    logger.info("[MCP] update_schema called: schema_id=%s", schema_id)

    @sync_to_async_with_db_cleanup
    def do_update():
        user = get_authenticated_user()

        try:
            schema = Schema.objects.get(pk=schema_id)
            if schema.created_by != user:
                raise Schema.DoesNotExist
        except Schema.DoesNotExist:
            logger.warning(
                "[MCP] update_schema called with unrecognized schema id %s", schema_id
            )
            raise ValueError(f"Schema with ID '{schema_id}' not found.")

        _validate_manifest_and_update_schema(manifest, schema)
        response = "Schema updated successfully:\n\n"
        response += format_schema(schema)
        return response

    return await do_update()
