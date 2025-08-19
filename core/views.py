from django.shortcuts import render
from .models import Schema

def index(request):
    schemas = (Schema.objects
               .prefetch_related("schemaref_set")
               .filter(schemaref__isnull=False)
               .order_by("name").all())
    return render(request, "core/index.html", {
        "schemas": schemas
    })
