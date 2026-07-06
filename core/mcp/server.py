import json
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from mcp.server.fastmcp import FastMCP
from core.models import Schema
from asgiref.sync import sync_to_async

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
    # TODO: dedupe from api_views.py
    schema_path = settings.BASE_DIR / "core" / "schemas" / "manifest.schema.json"
    with open(schema_path, "r") as f:
        return f.read()


@mcp.resource("schema://{schema_id}")
async def get_schema(schema_id):
    """Get a schema's manifest"""

    @sync_to_async
    def fetch_from_db():
        # TODO: dedupe from core.views:lookup_schema
        schema_filter = Q(published_at__lte=timezone.now())

        # TODO: get the user from the API key
        # if request.user.is_authenticated:
        #    schema_filter |= Q(created_by=request.user)

        schema = (
            Schema.objects
            .prefetch_related("schemaref_set")
            .prefetch_related("documentationitem_set")
            .filter(schema_filter)
            .get(pk=schema_id)
        )
        return schema.to_manifest()

    # Await the sync-to-async execution
    manifest = await fetch_from_db()
    return json.dumps(manifest, indent=2)
