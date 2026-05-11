import json
from functools import wraps
from django.utils import timezone
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views.decorators.http import (
    require_GET,
    require_POST,
    require_http_methods
)
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from jsonschema import validate, ValidationError as JSONValidationError
from core.models import SchemaRef, Schema, Implementation, DocumentationItem
from core.api_responses import ApiResponse, ApiErrorResponse
from core.views import lookup_schema


def _load_manifest_schema():
    schema_path = settings.BASE_DIR / 'core' / 'schemas' / 'manifest.schema.json'
    with open(schema_path, 'r') as f:
        return json.load(f)


MANIFEST_SCHEMA = _load_manifest_schema()


def require_manifest(function):
    @wraps(function)
    def _wrap_request(request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            validate(instance=data, schema=MANIFEST_SCHEMA)
        except json.JSONDecodeError as e:
            return ApiErrorResponse(
                status_code=400,
                message="Undecodable JSON payload",
                details=e.msg
            )
        except JSONValidationError as e:
            return ApiErrorResponse(
                status_code=400,
                message="Incorrect JSON payload format",
                details=e.message
            )
        return function(request, manifest=data, *args, **kwargs)
    return _wrap_request


@transaction.atomic
def _save_manifest(manifest, schema, created_by):
    schema.name = manifest['name']
    schema.description = manifest.get('description')
    public = manifest.get('public') or False

    # Prevent users from making public schemas private
    if not public and schema.published_at:
        raise DjangoValidationError('Public schemas cannot be made private except by an admin. Please set `public: true` in your manifest.')

    schema.save()
    urls = manifest['documents'].keys()

    # Delete any ReferenceItems with URLs
    # that aren't in the manifest
    schema.schemaref_set.exclude(url__in=urls).delete()
    schema.documentationitem_set.exclude(url__in=urls).delete()
    schema.implementation_set.exclude(url__in=urls).delete()

    # Create or update reference items
    for url, metadata in manifest['documents'].items():
        item_type = metadata['type']
        if item_type == 'definition':
            schema.schemaref_set.update_or_create(
                url=url,
                defaults={
                    'name': metadata.get('name'),
                    'created_by': created_by
                }
            )
        elif item_type == 'documentation':
            schema.documentationitem_set.update_or_create(
                url=url,
                defaults={
                    'name': metadata['name'],
                    'description': metadata.get('description'),
                    'role': metadata.get('role'),
                    'format': metadata.get('format'),
                    'created_by': created_by
                }
            )
        elif item_type == 'implementation':
            schema.implementation_set.update_or_create(
                url=url,
                defaults={
                    'is_open_source': metadata.get('isOpenSource') or False,
                    'created_by': created_by
                }
            )
    
    if public:
        if schema.pk is None:
            # Django requires a pk before we can use
            # schema.check_for_published_conflicts()
            schema.save()
        else:
            # Existing schemas were using stale schemaref_set
            # data without this
            schema.refresh_from_db()

        conflicting_published_schema_ref, conflict_reason = schema.check_for_published_conflicts()
        if conflicting_published_schema_ref:

            conflict_url = reverse(
                'schema_ref_detail', 
                    kwargs={
                        'schema_id': conflicting_published_schema_ref.schema.id, 
                        'schema_ref_id': conflicting_published_schema_ref.id
                    }
            )
            raise DjangoValidationError(
                f'`public: true` was set, but a public schema ({conflict_url})' +
                f'is already using one of the {conflict_reason} values ' + 
                'used in this schema. Please contact a Schemas.Pub administrator.'
            )

    # We only update published_at when we initially publish
    if public and not schema.published_at:
        schema.published_at = timezone.now()

    schema.save()


@require_GET
def find(request):
    id_value = request.GET.get('id')
    published_schema_refs = SchemaRef.objects.filter(schema__in=Schema.public_objects.all())
    schema_ref = get_object_or_404(published_schema_refs, id_value=id_value)
    return ApiResponse({'url': schema_ref.url})


@require_POST
@require_manifest
@transaction.atomic
def schemas_create(request, manifest): 
    schema = Schema(created_by=request.user)
    try:
        _save_manifest(manifest, schema, created_by=request.user)
    except DjangoValidationError as e:
        return ApiErrorResponse(
            status_code=400,
            message="Validation Error",
            details=e.message
        )

    return ApiResponse(data={
        'id': schema.id,
        'url': reverse('schema_detail', kwargs={'schema_id': schema.id}) 
    })


@require_http_methods(['PUT'])
@require_manifest
@lookup_schema
@transaction.atomic
def schemas_update(request, manifest, schema):
    if schema.created_by != request.user:
        return ApiErrorResponse(
            status_code=403,
            message="Forbbiden",
            details="You are not authorized to make changes to this schema"
        )
    try:
        _save_manifest(manifest, schema, created_by=request.user)
    except DjangoValidationError as e:
        return ApiErrorResponse(
            status_code=400,
            message="Validation Error",
            details=e.message
        )

    return ApiResponse(data={
        'id': schema.id,
        'url': reverse('schema_detail', kwargs={'schema_id': schema.id})
    })
