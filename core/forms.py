from django import forms
from django.core.exceptions import ValidationError
import requests
from pygments.lexers import get_lexer_for_filename
from pygments.util import ClassNotFound
from urllib.parse import urlparse
from .models import DocumentationItem, SchemaRef

'''
This is currently just a list of languages supported
by our syntax highlighter, Highlight.js, *without plaintext.*
You can regenerate this list by loading up the site,
opening a JS REPL in the browser's dev tools,
and executing `hljs.listLanguanges()`.

Note that the actual allowlist is an intersection
of this list and the lexers from pygments.
'''
SPECIFICATION_LANGUAGE_ALLOWLIST = [
"bash","c","cpp","csharp","css","diff","go","graphql","ini","java","javascript","json","kotlin","less","lua","makefile","markdown","objectivec","perl","php","php-template","python","python-repl","r","ruby","rust","scss","shell","sql","swift","typescript","vbnet","wasm","xml","yaml"
]

class DocumentationItemForm(forms.Form):
    name = forms.CharField(label="Name", max_length=200, required=False)
    url = forms.URLField(label="URL")
    format = forms.ChoiceField(
        choices=[('', 'Other')] + list(DocumentationItem.DocumentationItemFormat.choices),
        required=False,
        label="Format",
        initial=''
    )

DocumentationItemFormsetFactory = forms.formset_factory(DocumentationItemForm)

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

    def __init__(self, *args, schema = None, **kwargs):
        super().__init__(*args, **kwargs)
        if schema == None:
            self.additional_documentation_items_formset = DocumentationItemFormsetFactory()
            return

        latest_reference = schema.latest_reference()
        latest_readme = schema.latest_readme()
        latest_license = schema.latest_license()
        other_documentation_items = schema.documentationitem_set.exclude(
            id__in=[ref.id for ref in (latest_readme, latest_license) if ref is not None]
        )
        initial_formset_data = [{
            'name': documentation_item.name,
            'url': documentation_item.url,
            'format': documentation_item.format
        } for documentation_item in other_documentation_items]
        self.additional_documentation_items_formset = DocumentationItemFormsetFactory(initial=initial_formset_data, prefix='additional_documentation_items')
        self.initial = {
            'name': schema.name,
            'reference_url': latest_reference.url if latest_reference else None,
            'readme_url': latest_readme.url if latest_readme else None,
            'readme_format': latest_readme.format if latest_readme else None,
            'license_url': latest_license.url if latest_license else None
        }
        self.id = schema.id

    def _clean_url(self, url_field_name, language_allowlist):
        data = self.cleaned_data[url_field_name]
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
            if not "plaintext" in language_allowlist:
                raise ValidationError("The provided URL does not have a supported file extension")
            else:
                # If we don't have a match but plaintext is allowed, we'll just treat it as plaintext
                return [data, "plaintext"]

        matched_language = next(
            (alias for alias in language_allowlist if alias in lexer.aliases),
            "plaintext" if "plaintext" in language_allowlist else None
        )
        if not matched_language:
            raise ValidationError("The text content at the provided URL is not in a supported format")

        return [data, matched_language]

    def clean_reference_url(self):
        [data, matched_language] = self._clean_url('reference_url', language_allowlist=SPECIFICATION_LANGUAGE_ALLOWLIST)
        schema_refs = SchemaRef.objects.exclude(schema__id=self.id)
        parsed_data = urlparse(data)
        for schema_ref in schema_refs:
            parsed_url = urlparse(schema_ref.url)
            if parsed_url.netloc == parsed_data.netloc and parsed_url.path == parsed_data.path:
                raise ValidationError("The provided URL is already in use by another Schema")
        return data

    def clean_readme_url(self):
        [data, matched_language] = self._clean_url('readme_url', language_allowlist=DocumentationItem.DocumentationItemFormat)
        self.readme_format = matched_language
        return data

    def clean_license_url(self):
        if self.cleaned_data['license_url'] == None:
            return None;
        [data, matched_language] = self._clean_url('license_url', language_allowlist=[DocumentationItem.DocumentationItemFormat.PlainText])
        return data

