import json
from jsonschema import ValidationError as JSONValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from django.db.models import Q
from django.utils import timezone
from mcp.server.fastmcp import FastMCP
from core.models import Schema
from asgiref.sync import sync_to_async
from core.mcp.context import current_user

mcp = FastMCP(
    "Schemas.Pub", stateless_http=True, json_response=True, streamable_http_path="/"
)


def format_schema(schema):
    formatted_schema = f"""
Name: {schema.name}
ID: {schema.id}
"""
    if schema.description:
        formatted_schema += f"""Description: {schema.description}
"""
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


# TODO: This will need to be paginated
@mcp.tool()
@sync_to_async
def list_schemas():
    """List all available schemas."""
    public_schemas = [format_schema(schema) for schema in Schema.public_objects.all()]
    return "\n---\n".join(public_schemas)


@mcp.resource("schema://manifest.json")
async def get_manifest_schema():
    """Get the Schemas.Pub manifest schema"""
    return json.dumps(Schema.get_manifest_schema())


@mcp.resource("schema://{schema_id}")
async def get_schema(schema_id: int):
    """Get a schema's manifest"""

    user = current_user.get()

    @sync_to_async
    def fetch_from_db():
        # TODO: dedupe from core.views:lookup_schema
        schema_filter = Q(published_at__lte=timezone.now())

        if user and user.is_authenticated:
            schema_filter |= Q(created_by=user)

        try:
            schema = (
                Schema.objects
                .prefetch_related("schemaref_set")
                .prefetch_related("documentationitem_set")
                .filter(schema_filter)
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

    @sync_to_async
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

    @sync_to_async
    def do_update():
        try:
            schema = Schema.objects.get(pk=schema_id)
            if schema.created_by != user:
                raise Schema.DoesNotExist
        except Schema.DoesNotExist:
            raise ValueError(f"Schema with ID '{schema_id}' not found.")

        return _validate_manifest_and_update_schema(manifest, schema)

    return await do_update()
