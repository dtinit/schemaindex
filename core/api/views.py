import json
from functools import wraps
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from jsonschema import ValidationError as JSONValidationError
from core.models import SchemaRef, Schema
from core.api.responses import ApiResponse, ApiErrorResponse
from core.views import lookup_schema


def require_manifest(function):
    @wraps(function)
    def _wrap_request(request, *args, **kwargs):
        try:
            data = Schema.validate_manifest(request.body)
        except json.JSONDecodeError as e:
            return ApiErrorResponse(
                status_code=400, message="Undecodable JSON payload", details=e.msg
            )
        except JSONValidationError as e:
            return ApiErrorResponse(
                status_code=400,
                message="Incorrect JSON payload format",
                details=e.message,
            )
        return function(request, manifest=data, *args, **kwargs)

    return _wrap_request


@require_GET
def find(request):
    id_value = request.GET.get("id")
    published_schema_refs = SchemaRef.objects.filter(schema__in=Schema.objects.public())
    schema_ref = get_object_or_404(published_schema_refs, id_value__iexact=id_value)
    return ApiResponse({"url": schema_ref.url})


@require_POST
@require_manifest
@transaction.atomic
@csrf_exempt
def schemas_create(request, manifest):
    schema = Schema(created_by=request.user)
    try:
        schema.overwrite_from_manifest(manifest)
    except DjangoValidationError as e:
        return ApiErrorResponse(
            status_code=400, message="Validation Error", details=e.message
        )

    return ApiResponse(
        data={
            "id": schema.id,
            "url": reverse("schema_detail", kwargs={"schema_id": schema.id}),
        }
    )


@require_http_methods(["PUT"])
@require_manifest
@lookup_schema
@transaction.atomic
@csrf_exempt
def schemas_update(request, manifest, schema):
    if schema.created_by != request.user:
        return ApiErrorResponse(
            status_code=403,
            message="Forbbiden",
            details="You are not authorized to make changes to this schema",
        )
    try:
        schema.overwrite_from_manifest(manifest)
    except DjangoValidationError as e:
        return ApiErrorResponse(
            status_code=400, message="Validation Error", details=e.message
        )

    return ApiResponse(
        data={
            "id": schema.id,
            "url": reverse("schema_detail", kwargs={"schema_id": schema.id}),
        }
    )
