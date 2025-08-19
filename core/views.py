from django.shortcuts import render
from django.db.models import Count
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
        "schemas": results.order_by("name")[:MAX_SCHEMA_RESULT_COUNT]
    })
