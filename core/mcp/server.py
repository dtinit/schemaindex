import json
from typing import Literal
from jsonschema import ValidationError as JSONValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from django.utils import timezone
from mcp.server.fastmcp import FastMCP
from core.models import Schema
from core.mcp.sync_to_async_with_db_cleanup import sync_to_async_with_db_cleanup
from core.mcp.context import current_user

mcp = FastMCP(
    "Schemas.Pub", stateless_http=True, json_response=True, streamable_http_path="/"
)


def format_schema(schema):
    formatted_schema = f"""
ID: {schema.id}
Name: {schema.name}
"""
    if schema.description:
        formatted_schema += f"Description: {schema.description}\n"

    if schema.published_at is None or schema.published_at > timezone.now():
        formatted_schema += "Visibility: Private\n"

    return formatted_schema


# This is just a fallback since our middleware
# rejects any request without an API key tied to a user.
def ensure_current_user():
    user = current_user.get()
    if not user:
        raise ValueError("Not authenticated.")
    return user


# Note: We don't use type hints elsewhere in the codebase,
# but they can influence FastMCP's behavior for tools and resources.
# Function descriptions are the actual descriptions surfaced to models.

MAX_PAGE_SIZE = 10


@mcp.tool()
@sync_to_async_with_db_cleanup
def search_schemas(
    query: str | None = None, scope: Literal["all", "user"] = "all", page: int = 1
):
    """
    Search for schemas.

    Args:
      query: A search query. Can be a list of keywords or an $id. Pass None or an empty string to list all schemas in scope.
      scope: 'user' to search only the user's own schemas (including private), or 'all' to search the entire registry. Defaults to 'all.'
      page: Which page of search results to return. Defaults to 1.
    """

    user = ensure_current_user()

    scope_results = (
        Schema.objects.accessible_to(user)
        if scope == "all"
        else Schema.objects.filter(created_by=user)
    )

    matched_by_id_value = scope_results.filter(schemaref__id_value__iexact=query)

    # If there is a query and it matches an exact ID, skip the full-text search.
    if query and matched_by_id_value.exists():
        results = matched_by_id_value
    else:
        results = scope_results.search(query)

    total_count = results.count()
    if total_count == 0:
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

    response = f"Found {total_count} schema{'s' if total_count > 1 else ''} matching your query{':' if total_pages == 1 else '.'}"

    if total_pages == 1:
        response += f"\n\n{formatted_page}"
        return response

    response += f"\n\nThe results are truncated. Showing page {page} of {total_pages}:"
    response += f"\n\n{formatted_page}"

    if page < total_pages:
        response += f'\n\nTo get the next page, use `search_schemas(query: {query!r}, scope: "{scope}", page: {page + 1})`'

    return response


@mcp.resource("schema://manifest.json")
async def get_manifest_schema():
    """Get the Schemas.Pub manifest schema"""
    return json.dumps(Schema.get_manifest_schema(), indent=2)


@mcp.resource("schema://{schema_id}")
async def get_schema(schema_id: int):
    """Get a schema's manifest"""

    user = current_user.get()

    @sync_to_async_with_db_cleanup
    def fetch_from_db():
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
        # The MCP SDK will wrap this nicely for the MCP client
        raise ValueError(
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
        return {
            "id": schema.id,
            "url": reverse("schema_detail", kwargs={"schema_id": schema.id}),
        }
    except json.JSONDecodeError as e:
        raise ValueError(f"Undecodable JSON payload: {e.msg}")
    except JSONValidationError as e:
        raise ValueError(f"Incorrect JSON payload format: {e.message}")
    except DjangoValidationError as e:
        raise ValueError(f"Validation Error: {e.message}")


@mcp.tool()
async def create_schema(manifest: str):
    """
    Create a new schema from a manifest.
    The manifest should be a JSON string following the Schemas.Pub manifest schema available at schema://manifest.json
    """
    user = ensure_current_user()

    @sync_to_async_with_db_cleanup
    def do_create():
        schema = Schema(created_by=user)
        return _validate_manifest_and_update_schema(manifest, schema)

    return await do_create()


@mcp.tool()
async def update_schema(schema_id: int, manifest: str):
    """
    Update an existing schema from a manifest.
    The manifest should be a JSON string following the Schemas.Pub manifest schema available at schema://manifest.json
    """
    user = ensure_current_user()

    @sync_to_async_with_db_cleanup
    def do_update():
        try:
            schema = Schema.objects.get(pk=schema_id)
            if schema.created_by != user:
                raise Schema.DoesNotExist
        except Schema.DoesNotExist:
            raise ValueError(f"Schema with ID '{schema_id}' not found.")

        return _validate_manifest_and_update_schema(manifest, schema)

    return await do_update()
