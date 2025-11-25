from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
import requests
from pygments.lexers import get_lexer_for_filename
from pygments.util import ClassNotFound
from .models import DocumentationItem, SchemaRef, Schema

'''
This is currently just a list of languages supported
by our syntax highlighter, Highlight.js, *without plaintext.*
You can regenerate this list by loading up the site,
opening a JS REPL in the browser's dev tools,
and executing `hljs.listLanguanges()`.

CDDL is an IETF schema language so it is added.  We may eventually need some logic so that we
can less tightly connect what file extension something is to what we tell the highlighter what to use.

Note that the actual allowlist is an intersection
of this list and the lexers from pygments.
'''
SPECIFICATION_LANGUAGE_ALLOWLIST = [
"bash","c","cpp","csharp","css","diff","go","graphql","ini","java","javascript","json","kotlin","less","lua","makefile","markdown","objectivec","perl","php","php-template","python","python-repl","r","ruby","rust","scss","shell","sql","swift","typescript","vbnet","wasm","xml","yaml","cddl"
]

class ReferenceItemForm(forms.Form):
    id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    url = forms.URLField(label="URL")


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # By default, Django just ignores totally empty formset entries,
        # even if it has required fields!
        # This undoes that
        self.empty_permitted = False

def clean_url(url):
    try:
        response = requests.get(url)
    except requests.exceptions.RequestException:
        raise ValidationError("The provided URL could not be reached")

    if response.status_code != requests.codes.ok:
        raise ValidationError("The provided URL returned an invalid status code")

    if not response.text:
        raise ValidationError("The provided URL has no text content")

    return url


class SchemaRefForm(ReferenceItemForm):
    schema_id = None

    name = forms.CharField(label="Name", max_length=200, required=False)

    def clean_url(self):
        if not self.cleaned_data['url']:
            return None

        data = clean_url(self.cleaned_data['url'])

        # Use pygments to verify the language from the filename
        try:
            lexer = get_lexer_for_filename(data)
        except ClassNotFound:
            raise ValidationError("The provided URL does not have a supported file extension")

        matched_language = next(
            (alias for alias in SPECIFICATION_LANGUAGE_ALLOWLIST if alias in lexer.aliases),
            None
        )
        if not matched_language:
            raise ValidationError("The text content at the provided URL is not in a supported format")
        
        # If the schema is unpublished, we don't care if the URL is already in use
        if self.schema_id is None or not Schema.public_objects.filter(id=self.schema_id).exists():
            return data

        # But if it's a published schema, we need to make sure the URL isn't already in use
        schema_refs = SchemaRef.objects.select_related('schema').filter(
            schema__in=Schema.public_objects.exclude(id=self.schema_id)
        )
        for schema_ref in schema_refs:
            if schema_ref.has_same_domain_and_path(data):
                raise ValidationError("The provided URL is already in use by another Schema")
        return data


class DocumentationItemForm(ReferenceItemForm):
    name = forms.CharField(label="Name", max_length=200, required=True)
    role = forms.ChoiceField(
        choices=[('', 'Other')] +
        [role for role in DocumentationItem.DocumentationItemRole.choices
         if role[0] not in (DocumentationItem.DocumentationItemRole.License, DocumentationItem.DocumentationItemRole.README)],
        required=False,
        label="Role",
        initial=''
    )
    format = forms.ChoiceField(
        choices=[('', 'Other')] + list(DocumentationItem.DocumentationItemFormat.choices),
        required=False,
        label="Format",
        initial=''
    )


SchemaRefFormsetFactory = forms.formset_factory(SchemaRefForm, extra=0)
DocumentationItemFormsetFactory = forms.formset_factory(DocumentationItemForm, extra=0)

class SchemaForm(forms.Form):
    id = None

    name = forms.CharField(label="Name", max_length=200)
    readme_url = forms.URLField(label="README URL")
    readme_format = forms.ChoiceField(
        choices=DocumentationItem.DocumentationItemFormat.choices,
        required=False,
        label="README format",
    )
    license_url = forms.URLField(label="License URL", required=False)

    def __init__(self, *args, schema = None, **kwargs):
        super().__init__(*args, **kwargs)
        if schema == None:
            self.additional_documentation_items_formset = DocumentationItemFormsetFactory(prefix="documentation_items", *args, **kwargs)
            self.schema_refs_formset = SchemaRefFormsetFactory(prefix="schema_refs", *args, **kwargs)
            return

        latest_readme = schema.latest_readme()
        latest_license = schema.latest_license()

        other_documentation_items = schema.documentationitem_set.exclude(
            id__in=[ref.id for ref in (latest_readme, latest_license) if ref is not None]
        )
        initial_documentation_items_formset_data = [{
            'id': documentation_item.id,
            'name': documentation_item.name,
            'url': documentation_item.url,
            'format': documentation_item.format
        } for documentation_item in other_documentation_items]
        self.additional_documentation_items_formset = DocumentationItemFormsetFactory(
            prefix="documentation_items",
            initial=initial_documentation_items_formset_data,
            *args, **kwargs
        )

        initial_schema_refs_formset_data = [{
            'schema_id': schema.id,
            'id': schema_ref.id,
            'name': schema_ref.name,
            'url': schema_ref.url,
        } for schema_ref in schema.schemaref_set.all()]
        self.schema_refs_formset = SchemaRefFormsetFactory(prefix="schema_refs", initial=initial_schema_refs_formset_data, *args, **kwargs)
        for schema_ref_form in self.schema_refs_formset:
            schema_ref_form.schema_id = schema.id

        self.initial = {
            'name': schema.name,
            'readme_url': latest_readme.url if latest_readme else None,
            'readme_format': latest_readme.format if latest_readme else None,
            'license_url': latest_license.url if latest_license else None
        }
        self.id = schema.id

    def clean_readme_url(self):
        if not self.cleaned_data['readme_url']:
            return None
        data = clean_url(self.cleaned_data['readme_url'])
        return data

    def clean_license_url(self):
        if not self.cleaned_data['license_url']:
            return None
        data = clean_url(self.cleaned_data['license_url'])
        return data

    def clean(self):
        if self.schema_refs_formset.total_form_count() == 0:
            raise ValidationError('A schema must have at least one definition')

        self.additional_documentation_items_formset.clean()
        self.schema_refs_formset.clean()
        cleaned_data = super().clean()

        return cleaned_data

    def is_valid(self):
        is_form_valid = super().is_valid()
        is_documentation_items_formset_valid = self.additional_documentation_items_formset.is_valid()
        is_schema_refs_formset_valid = self.schema_refs_formset.is_valid()
        return is_form_valid and is_documentation_items_formset_valid and is_schema_refs_formset_valid


