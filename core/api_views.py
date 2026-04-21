from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from core.models import SchemaRef
from core.api_responses import ApiResponse

def find(request):
    id_value = request.GET.get('id')
    schema_ref = get_object_or_404(SchemaRef, id_value=id_value)
    return ApiResponse({'url': schema_ref.url})
