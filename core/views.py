from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.contrib.auth.decorators import login_required
import requests
import cmarkgfm
import bleach
from .models import (Schema,
                     DocumentationItem,
                     SchemaRef,
                     DocumentationItem)
from .forms import SchemaForm, DocumentationItemForm


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

    latest_schema_ref = schema.latest_reference()
    latest_definition = None
    if latest_schema_ref:
        schema_ref_fetch_response = requests.get(latest_schema_ref.url)
        latest_definition = escape(schema_ref_fetch_response.text)
    
    latest_readme = schema.latest_readme()
    latest_readme_content = None
    if latest_readme and latest_readme.format == DocumentationItem.DocumentationItemFormat.Markdown:
        markdown_readme_fetch_response = requests.get(latest_readme.url)
        unsanitized_html_content = cmarkgfm.github_flavored_markdown_to_html(markdown_readme_fetch_response.text)
        sanitized_html_content = bleach.clean(unsanitized_html_content, MARKDOWN_HTML_TAGS, MARKDOWN_HTML_ATTRIBUTES)
        # WARNING: Be careful not to pass any untrusted HTML to mark_safe!
        latest_readme_content = mark_safe(sanitized_html_content)

    return render(request, "core/schemas/detail.html", {
        "schema": schema,
        "latest_definition": latest_definition,
        "latest_definition_url": latest_schema_ref.url if latest_schema_ref else None,
        "latest_readme_content": latest_readme_content,
        "latest_readme_url": latest_readme.url if latest_readme else None,
        "latest_license": schema.latest_license
    })

@login_required
def account_profile(request):
    user_schemas = Schema.objects.filter(created_by=request.user)
    return render(request, "account/profile.html", {
        'user_schemas': user_schemas
    })


@login_required
def manage_schema(request, schema_id=None):
    schema = get_object_or_404(Schema.objects.filter(created_by=request.user), pk=schema_id) if schema_id else None

    if request.method == 'POST':
        form = SchemaForm(request.POST, schema=schema)
        if form.is_valid():
            schema = schema if schema else Schema.objects.create(created_by=request.user)
            schema.name = form.cleaned_data['name']
            schema.save()

            latest_reference = schema.latest_reference()
            if latest_reference == None:
                latest_reference = SchemaRef.objects.create(schema=schema, created_by=request.user)
            latest_reference.url = form.cleaned_data['reference_url']
            latest_reference.save()

            latest_readme = schema.latest_readme()
            if latest_readme == None:
                latest_readme = DocumentationItem.objects.create(
                    schema=schema,
                    created_by=request.user,
                    role=DocumentationItem.DocumentationItemRole.README,
                    name="README"
                )
            latest_readme.url = form.cleaned_data['readme_url']
            latest_readme.format = form.cleaned_data['readme_format']
            latest_readme.save()

            license_url = form.cleaned_data['license_url']
            if license_url:
                latest_license = schema.latest_license()
                if latest_license == None:
                    latest_license = DocumentationItem.objects.create(
                        schema=schema,
                        created_by=request.user,
                        role=DocumentationItem.DocumentationItemRole.License,
                        name="License",
                        format=DocumentationItem.DocumentationItemFormat.PlainText
                    )
                latest_license.url = license_url
                latest_license.save()

            previous_documentation_items = schema.documentationitem_set.exclude(role__in=[
                DocumentationItem.DocumentationItemRole.README,
                DocumentationItem.DocumentationItemRole.License
            ])
            previous_documentation_items_by_id = {
                item.id: item for item in previous_documentation_items
            }
            
            updated_item_ids = set()
            # Create/update documentation items
            for documentation_item_form in form.additional_documentation_items_formset:
                item_id = documentation_item_form.cleaned_data.get('id')
                if item_id:
                    db_item = previous_documentation_items_by_id[item_id]
                    updated_item_ids.add(item_id)
                else:
                    db_item = DocumentationItem.objects.create(schema=schema, created_by=request.user)
                db_item.name = documentation_item_form.cleaned_data.get('name')
                db_item.url = documentation_item_form.cleaned_data.get('url')
                db_item.role = documentation_item_form.cleaned_data.get('role')
                db_item.format = documentation_item_form.cleaned_data.get('format')
                db_item.save()

            # Delete documentation items that were removed
            for previous_item in previous_documentation_items:
                if not previous_item.id in updated_item_ids:
                    previous_item.delete()

            return redirect('account_profile')

    else:
        form = SchemaForm(schema=schema)

    return render(request, "core/manage/schema.html", {
        'schema': schema,
        'is_new': schema == None,
        'form': form
    })


@login_required
def manage_schema_delete(request, schema_id):
    schema = get_object_or_404(Schema.objects.filter(created_by=request.user), pk=schema_id)

    if request.method == 'POST':
        schema.delete()
        return redirect('account_profile')
       
    return render(request, "core/manage/delete_schema.html", {
        'schema': schema
    })

def about(request):
    return render(request, "core/about.html")
