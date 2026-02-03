from urllib.parse import urlparse
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
import requests
from .models import DocumentationItem, SchemaRef, Schema, PermanentURL
from .utils import guess_specification_language_by_extension


# These are just alphabetized and shown as help text
EXPLICITLY_SUPPORTED_FILE_EXTENSIONS = [
    '.json',
    '.markdown',
    '.md',
    '.xml',
    '.yaml',
    '.yml',
    '.cddl'
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

    name = forms.CharField(
        label="Name",
        max_length=200,
        required=False,
        help_text="Optional: Descriptive name for this schema file"
    )
    url = forms.URLField(
        label="URL",
        help_text=f"Accepted formats: {', '.join(sorted(EXPLICITLY_SUPPORTED_FILE_EXTENSIONS))}"
    )

    def clean_url(self):
        if not self.cleaned_data['url']:
            return None
        data = self.cleaned_data['url']; 
        matched_language = guess_specification_language_by_extension(data)

        if not matched_language:
            raise ValidationError("The provided URL does not have a supported file extension")
        
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['format'].widget.attrs['data-url-format-selector-for'] = self['url'].id_for_label


DocumentationItemFormsetFactory = forms.formset_factory(DocumentationItemForm, extra=0)

class SchemaForm(forms.Form):
    id = None

    name = forms.CharField(
        label="Name",
        max_length=200,
        help_text="A descriptive name for your schema"
    )
    readme_url = forms.URLField(
        label="README URL",
        widget=forms.TextInput(attrs={'placeholder': 'https://example.com/README.md'})
    )
    readme_format = forms.ChoiceField(
        choices=[('', 'Other')] + list(DocumentationItem.DocumentationItemFormat.choices),
        required=False,
        label="README format",
        help_text="Markdown and Plaintext READMEs are displayed on Schemas.Pub",
        widget=forms.Select(attrs={'data-url-format-selector-for': 'id_readme_url'})
    )
    license_url = forms.URLField(
        label="License URL",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'https://example.com/LICENSE'})
    )

    def __init__(self, *args, schema = None, **kwargs):
        super().__init__(*args, **kwargs)

        if schema == None:
            self.additional_documentation_items_formset = DocumentationItemFormsetFactory(prefix="documentation_items", *args, **kwargs)
            SchemaRefFormsetFactory = forms.formset_factory(SchemaRefForm, extra=1)
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
        # If there aren't any schema_refs, render the formset with an extra empty formset item
        extra_formset_item_count = max(1 - len(initial_schema_refs_formset_data), 0)
        SchemaRefFormsetFactory = forms.formset_factory(SchemaRefForm, extra=extra_formset_item_count)
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


def clean_permanent_url_slug(organization, slug):
    proposed_url = PermanentURL.objects.get_url_for_slug(
        organization=organization,
        slug=slug
    )
    if PermanentURL.objects.filter(url=proposed_url).exists():
        raise ValidationError('This URL is already in use.')
    return slug


class SchemaRefPermanentURLForm(forms.Form):
    slug = forms.SlugField(
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'my-schema.json'})
    )

    def set_schema_ref(self, schema_ref, fallback_name):
        self.schema_ref = schema_ref
        self.name = schema_ref.name or fallback_name
        self.fields['slug'].help_text = "This URL will route to the Schemas.Pub listing for " + schema_ref.url
        self.fields['slug'].label = "New unique URL for " + self.name

    def clean_slug(self):
        return clean_permanent_url_slug(
            organization=self.schema_ref.created_by.profile.organization,
            slug=self.cleaned_data['slug']
        )


class PermanentURLsForm(forms.Form):
    schema_slug = forms.SlugField(
        label="New unique URL for schema",
        max_length=300,
        help_text="This URL will route to the Schemas.Pub listing for your schema.",
        widget=forms.TextInput(attrs={'placeholder': 'my-schema.json'}),
        required=False
    )

    def __init__(self, *args, schema, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema = schema
        schema_refs = self.schema.schemaref_set.all()
        # Create a formset with one form per SchemaRef
        SchemaRefPermanentURLFormsetFactory = forms.formset_factory(
            SchemaRefPermanentURLForm,
            extra=len(schema_refs),
            max_num=len(schema_refs),
        )
        self.schema_ref_permanent_url_formset = SchemaRefPermanentURLFormsetFactory(
            *args,
            **kwargs
        )
        for index, schema_ref_form in enumerate(self.schema_ref_permanent_url_formset):
            schema_ref_form.set_schema_ref(schema_refs[index], f"Definition {index + 1}")

    def clean_slug(self):
        return clean_permanent_url_slug(
            organization=self.schema.created_by.profile.organization,
            slug=self.cleaned_data['schema_slug']
        )

    def clean(self):
        self.schema_ref_permanent_url_formset.clean()
        cleaned_data = super().clean()
        # Make sure none of the slugs are the same
        schema_slug = cleaned_data.get('schema_slug')
        slugs = {schema_slug} if schema_slug else set()
        for schema_ref_form in self.schema_ref_permanent_url_formset:
            schema_ref_slug = schema_ref_form.cleaned_data.get('slug')
            if schema_ref_slug in slugs:
                raise ValidationError('Each URL must be unique')
            
        return cleaned_data

    def is_valid(self):
        return self.schema_ref_permanent_url_formset.is_valid() and super().is_valid()
