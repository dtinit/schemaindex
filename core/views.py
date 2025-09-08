from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.contrib.auth.decorators import login_required
import requests
import cmarkgfm
import bleach
from .models import Schema, DocumentationItem

MAX_SCHEMA_RESULT_COUNT = 30

# Pulled these from https://github.com/yourcelf/bleach-allowlist.
# These are the only tags/attributes we'll allow to be rendered from Markdown sources.
MARKDOWN_HTML_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "b", "i", "strong", "em", "tt",
    "p", "br",
    "span", "div", "blockquote", "code", "pre", "hr",
    "ul", "ol", "li", "dd", "dt",
    "img",
    "a",
    "sub", "sup",
] 
MARKDOWN_HTML_ATTRIBUTES = {
    "*": ["id"],
    "img": ["src", "alt", "title"],
    "a": ["href", "alt", "title"],
}

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
    latest_definition = None
    if latest_schema_ref:
        schema_ref_fetch_response = requests.get(latest_schema_ref.url)
        latest_definition = escape(schema_ref_fetch_response.text)
    
    latest_readme_content = None
    latest_readme = schema.documentationitem_set.filter(
        role=DocumentationItem.DocumentationItemRole.README,
        format=DocumentationItem.DocumentationItemFormat.Markdown
    ).order_by('-created_by').first()
    if latest_readme:
        markdown_readme_fetch_response = requests.get(latest_readme.url)
        unsanitized_html_content = cmarkgfm.github_flavored_markdown_to_html(markdown_readme_fetch_response.text)
        sanitized_html_content = bleach.clean(unsanitized_html_content, MARKDOWN_HTML_TAGS, MARKDOWN_HTML_ATTRIBUTES)
        # WARNING: Be careful not to pass any untrusted HTML to mark_safe!
        latest_readme_content = mark_safe(sanitized_html_content)

    return render(request, "core/schemas/detail.html", {
        "schema": schema,
        "latest_definition": latest_definition,
        "latest_readme_content": latest_readme_content
    })

@login_required
def account_profile(request):
    user_schemas = Schema.objects.filter(created_by=request.user)
    return render(request, "core/account/profile.html", {
        'user_schemas': user_schemas
    })
