from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.utils.html import escape
import requests
from .models import Schema

MAX_SCHEMA_RESULT_COUNT = 30

def index(request):
    defined_schemas = (
        Schema.objects
        .prefetch_related("schemaref_set")
        .filter(schemaref__isnull=False)
    )

    search_query = request.GET.get('search_query', None)
    results = defined_schemas.filter(name__icontains=search_query) if search_query else defined_schemas

    return render(request, "core/index.html", {
        "total_schema_count": defined_schemas.count(),
        "schemas": results.order_by("name")[:MAX_SCHEMA_RESULT_COUNT],
    })


def schema_detail(request, schema_id):
    schema = get_object_or_404(
        Schema.objects.prefetch_related("schemaref_set").prefetch_related("documentationitem_set"),
        pk=schema_id
    )

    latest_schema_ref = schema.schemaref_set.order_by('-created_by').first()

    if latest_schema_ref:
        schema_ref_fetch_response = requests.get(latest_schema_ref.url)
       
    return render(request, "core/schemas/detail.html", {
        "schema": schema,
        "latest_definition": escape(schema_ref_fetch_response.text)
    })
   
