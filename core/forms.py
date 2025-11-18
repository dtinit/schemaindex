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

class DocumentationItemForm(forms.Form):
    id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    url = forms.URLField(label="URL")
    name = forms.CharField(label="Name", max_length=200)
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

DocumentationItemFormsetFactory = forms.formset_factory(DocumentationItemForm, extra=0)

class SchemaForm(forms.Form):
    id = None

    name = forms.CharField(label="Name", max_length=200)
    reference_url = forms.URLField(label="Definition URL")
    readme_url = forms.URLField(label="README URL")
    readme_format = forms.ChoiceField(
        choices=DocumentationItem.DocumentationItemFormat.choices,
        required=False,
        label="README format",
    )
    license_url = forms.URLField(label="License URL", required=False)

    matched_language_cache = {}

    def __init__(self, *args, schema = None, **kwargs):
        super().__init__(*args, **kwargs)
        if schema == None:
            self.additional_documentation_items_formset = DocumentationItemFormsetFactory(*args, **kwargs)
            return

        latest_reference = schema.latest_reference()
        latest_readme = schema.latest_readme()
        latest_license = schema.latest_license()
        other_documentation_items = schema.documentationitem_set.exclude(
            id__in=[ref.id for ref in (latest_readme, latest_license) if ref is not None]
        )
        initial_formset_data = [{
            'id': documentation_item.id,
            'name': documentation_item.name,
            'url': documentation_item.url,
            'format': documentation_item.format
        } for documentation_item in other_documentation_items]
        self.additional_documentation_items_formset = DocumentationItemFormsetFactory(initial=initial_formset_data, *args, **kwargs)
        self.initial = {
            'name': schema.name,
            'reference_url': latest_reference.url if latest_reference else None,
            'readme_url': latest_readme.url if latest_readme else None,
            'readme_format': latest_readme.format if latest_readme else None,
            'license_url': latest_license.url if latest_license else None
        }
        self.id = schema.id

    def _clean_url_field(self, url_field_name, language_allowlist):
        return self._clean_url(url_field_name,
                               self.cleaned_data[url_field_name],
                               language_allowlist)

    def _clean_url(self, field_name, data, language_allowlist):
        try:
            response = requests.get(data)
        except requests.exceptions.RequestException:
            raise ValidationError("The provided URL could not be reached")
            
        if response.status_code != requests.codes.ok:
            raise ValidationError("The provided URL returned an invalid status code")

        if not response.text:
            raise ValidationError("The provided URL has no text content")

        # Use pygments to verify the language from the filename
        try:
            lexer = get_lexer_for_filename(data)
        except ClassNotFound:
            # If we don't have a match we'll just treat it as None
            self.matched_language_cache[data] = None
            return data

        matched_language = next(
            (alias for alias in language_allowlist if alias in lexer.aliases),
            "plaintext" if "plaintext" in language_allowlist else None
        )
        if not matched_language:
            raise ValidationError("The text content at the provided URL is not in a supported format")
        
        self.matched_language_cache[data] = matched_language
        return data

    def clean_reference_url(self):
        data = self._clean_url_field('reference_url', language_allowlist=SPECIFICATION_LANGUAGE_ALLOWLIST)
        # If this schema is unpublished, we don't care if the URL is already in use
        if self.id is None or not Schema.public_objects.filter(id=self.id).exists():
            return data

        # But if it's a published schema, we need to make sure the URL isn't already in use
        schema_refs = SchemaRef.objects.select_related('schema').filter(
            schema__in=Schema.public_objects.exclude(id=self.id)
        )
        for schema_ref in schema_refs:
            if schema_ref.has_same_domain_and_path(data):
                raise ValidationError("The provided URL is already in use by another Schema")
        return data

    def clean_readme_url(self):
        data = self._clean_url_field('readme_url', language_allowlist=DocumentationItem.DocumentationItemFormat)
        return data

    def clean_license_url(self):
        if not self.cleaned_data['license_url']:
            return None;
        data = self._clean_url_field('license_url', language_allowlist=[DocumentationItem.DocumentationItemFormat.PlainText])
        return data

    def clean(self):
        self.additional_documentation_items_formset.clean()
        cleaned_data = super().clean()
        cleaned_data['readme_format'] = self.matched_language_cache.get(cleaned_data['readme_url'])
        return cleaned_data

    def is_valid(self):
        return self.additional_documentation_items_formset.is_valid() and super().is_valid()


