from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from core.models import SchemaRef, Schema
from core.api_responses import ApiResponse

def find(request):
    id_value = request.GET.get('id')
    published_schema_refs = SchemaRef.objects.filter(schema__in=Schema.public_objects.all()).all()
    schema_ref = get_object_or_404(published_schema_refs, id_value=id_value)
    return ApiResponse({'url': schema_ref.url})
