import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Q
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.exceptions import PermissionDenied
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
        Schema.public_objects
        .prefetch_related("schemaref_set")
        .exclude(schemaref__isnull=True)
    )

    search_query = request.GET.get('search_query', None)
    results = defined_schemas.filter(name__icontains=search_query) if search_query else defined_schemas

    return render(request, "core/index.html", {
        "total_schema_count": defined_schemas.count(),
        "schemas": results.order_by("name")[:MAX_SCHEMA_RESULT_COUNT],
    })


# Unpublished schemas can be viewed by their creators
def _get_public_or_owned_schema_or_404(request, schema_id):
    schema_filter = Q(published_at__lte=timezone.now())

    if request.user.is_authenticated:
        schema_filter |= Q(created_by=request.user)

    return get_object_or_404(
        Schema.objects
            .prefetch_related("schemaref_set")
            .prefetch_related("documentationitem_set")
            .filter(schema_filter),
        pk=schema_id,
    )


def schema_detail(request, schema_id):
    schema = _get_public_or_owned_schema_or_404(request, schema_id)

    latest_readme = schema.latest_readme()
    latest_readme_content = None
    if latest_readme:
        fetch_response = requests.get(latest_readme.url).text
        if latest_readme.format == DocumentationItem.DocumentationItemFormat.Markdown:
            html_content = cmarkgfm.github_flavored_markdown_to_html(fetch_response)
            sanitized_html_content = bleach.clean(html_content, MARKDOWN_HTML_TAGS,
                                                  MARKDOWN_HTML_ATTRIBUTES)
            # WARNING: Be careful not to pass any untrusted HTML to mark_safe!
            latest_readme_content = mark_safe(sanitized_html_content)
        elif latest_readme.format == DocumentationItem.DocumentationItemFormat.PlainText:
            latest_readme_content = fetch_response 
        else:
            logging.error(f"Unhandled README content format: {latest_readme.format}")
            # Any other format is returned as None
            latest_readme_content = None

    return render(request, "core/schemas/detail.html", {
        "schema": schema,
        "latest_readme_format": latest_readme.format if latest_readme else None,
        "latest_readme_content": latest_readme_content,
        "latest_readme_url": latest_readme.url if latest_readme else None,
        "latest_license": schema.latest_license()
    })


def schema_ref_detail(request, schema_id, schema_ref_id):
    schema = _get_public_or_owned_schema_or_404(request, schema_id)
    schema_ref = get_object_or_404(schema.schemaref_set.filter(id=schema_ref_id))
    # I feel like we can do better here- e.g. put the get request in the model and
    # pull from cache
    schema_ref.content = escape(requests.get(schema_ref.url).text)

    return render(request, "core/schemas/detail_schema_ref.html", {
        "schema": schema,
        "schema_ref": schema_ref,
        "latest_license": schema.latest_license()
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
            
            previous_schema_refs = schema.schemaref_set.all()
            previous_schema_refs_by_id = {
                schema_ref.id: schema_ref for schema_ref in previous_schema_refs
            }
            updated_schema_ref_ids = set()
            # Create/update schema_refs
            for schema_ref_form in form.schema_refs_formset:
                schema_ref_id = schema_ref_form.cleaned_data.get('id')
                if schema_ref_id:
                    db_item = previous_schema_refs_by_id[schema_ref_id]
                    updated_schema_ref_ids.add(schema_ref_id)
                else:
                    db_item = SchemaRef.objects.create(schema=schema, created_by=request.user)
                db_item.name = schema_ref_form.cleaned_data.get('name')
                db_item.url = schema_ref_form.cleaned_data.get('url')
                db_item.save()

            # Delete schema refs that were removed
            for schema_ref in previous_schema_refs:
                if not schema_ref.id in updated_schema_ref_ids:
                    schema_ref.delete()

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

            return redirect('schema_detail', schema_id=schema.id)

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

    if schema.published_at:
        raise PermissionDenied('Public schemas cannot be deleted except by an admin')

    if request.method == 'POST':
        schema.delete()
        return redirect('account_profile')
       
    return render(request, "core/manage/delete_schema.html", {
        'schema': schema
    })


@login_required
def manage_schema_publish(request, schema_id):
    schema = get_object_or_404(Schema.objects.filter(created_by=request.user).prefetch_related('schemaref_set'), id=schema_id)
    published_schema_refs = SchemaRef.objects.filter(schema__in=Schema.public_objects.all()).all()
    conflicting_published_schema_ref = None
    for schema_ref in schema.schemaref_set.all():
        for published_schema_ref in published_schema_refs:
            if published_schema_ref.has_same_domain_and_path(schema_ref.url):
                conflicting_published_schema_ref = published_schema_ref
                break;
        if conflicting_published_schema_ref:
            break;

    if request.method == 'POST':
        if conflicting_published_schema_ref:
            raise PermissionDenied('Another public schema has claimed this definition URL')

        if schema.schemaref_set.count() == 0:
            raise PermissionDenied('Schemas without a definition cannot be published')

        schema.published_at = timezone.now() 
        schema.save()
        return redirect('schema_detail', schema_id=schema.id)
   
    return render(request, "core/manage/publish_schema.html", {
        'schema': schema,
        'conflicting_schema': conflicting_published_schema_ref.schema if conflicting_published_schema_ref else None
    })


def about(request):
    return render(request, "core/about.html")
