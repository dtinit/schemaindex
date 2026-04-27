from urllib.parse import urlparse
import json
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.core.validators import RegexValidator
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

MAX_PERMANENT_URL_COUNT_PER_USER = 100

class ReferenceItemForm(forms.Form):
    id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    url = forms.URLField(label="URL")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # By default, Django just ignores totally empty formset entries,
        # even if it has required fields!
        # This undoes that
        self.empty_permitted = False


def clean_url_and_get_body(url):
    try:
        response = requests.get(url)
    except requests.exceptions.RequestException:
        raise ValidationError("The provided URL could not be reached")

    if response.status_code != requests.codes.ok:
        raise ValidationError("The provided URL returned an invalid status code")

    if not response.text:
        raise ValidationError("The provided URL has no text content")

    return response.text


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
        url = self.cleaned_data['url'] 
        content = clean_url_and_get_body(url)
        matched_language = guess_specification_language_by_extension(url)

        if not matched_language:
            raise ValidationError("The provided URL does not have a supported file extension")
        
        # If the schema is unpublished, we don't care if the URL or $id are already in use
        if self.schema_id is None or not Schema.public_objects.filter(id=self.schema_id).exists():
            return url
    
        # But if it's a published schema, we need to make sure the URL and $id aren't already in use
        schema_refs = SchemaRef.objects.select_related('schema').filter(
            schema__in=Schema.public_objects.exclude(id=self.schema_id)
        )
        # First check the URL
        for schema_ref in schema_refs:
            if schema_ref.url_provider_info.is_same_resource(url):
                raise ValidationError("The provided URL is already in use by another Schema")

        if matched_language != 'json':
            return url

        # Then check the $id
        try:
            parsed_data = json.loads(content)
            if isinstance(parsed_data, dict):
                id_value = parsed_data.get('$id')
        except (json.JSONDecodeError, TypeError):
            id_value = None
      
        if id_value == None:
            return url

        for schema_ref in schema_refs:
            if schema_ref.id_value == id_value:
                raise ValidationError("A JSON schema with this resource's $id is already in use by another Schema")

        return url


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


class ImplementationForm(ReferenceItemForm):
    is_open_source = forms.BooleanField(label="This implementation is open source", required=False)


ImplementationFormsetFactory = forms.formset_factory(ImplementationForm, extra=0)


class SchemaForm(forms.Form):
    id = None

    name = forms.CharField(
        label="Name",
        max_length=200,
        help_text="A descriptive name for your schema"
    )
    description = forms.CharField(
        label="Description",
        widget=forms.Textarea(attrs={'rows': 3, 'maxlength': 350}),
        required=False,
        max_length=350
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
            self.additional_documentation_items_formset = DocumentationItemFormsetFactory(
                prefix="documentation_items",
                *args,
                **kwargs
            )
            SchemaRefFormsetFactory = forms.formset_factory(SchemaRefForm, extra=1)
            self.schema_refs_formset = SchemaRefFormsetFactory(prefix="schema_refs", *args, **kwargs)
            self.implementation_formset = ImplementationFormsetFactory(prefix="implementations", *args, **kwargs)
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
            *args,
            **kwargs
        )

        initial_schema_refs_formset_data = [{
            'schema_id': schema.id,
            'id': schema_ref.id,
            'name': schema_ref.name,
            'url': schema_ref.url,
        } for schema_ref in schema.schemaref_set.all()]
        # If there aren't any schema_refs, render the formset with an extra empty formset item
        extra_formset_item_count = max(1 - len(initial_schema_refs_formset_data), 0)
        SchemaRefFormsetFactory = forms.formset_factory(
            SchemaRefForm,
            extra=extra_formset_item_count
        )
        self.schema_refs_formset = SchemaRefFormsetFactory(
            prefix="schema_refs",
            initial=initial_schema_refs_formset_data,
            *args,
            **kwargs
        )
        for schema_ref_form in self.schema_refs_formset:
            schema_ref_form.schema_id = schema.id

        
        initial_implementation_formset_data = [{
            'id': implementation.id,
            'url': implementation.url,
            'is_open_source': implementation.is_open_source,
        } for implementation in schema.implementation_set.all()]
        self.implementation_formset = ImplementationFormsetFactory(
            prefix="implementations",
            initial=initial_implementation_formset_data,
            *args,
            **kwargs
        )

        self.initial = {
            'name': schema.name,
            'description': schema.description,
            'readme_url': latest_readme.url if latest_readme else None,
            'readme_format': latest_readme.format if latest_readme else None,
            'license_url': latest_license.url if latest_license else None
        }
        self.id = schema.id

    def clean_readme_url(self):
        if not self.cleaned_data['readme_url']:
            return None
        url = self.cleaned_data['readme_url']
        clean_url_and_get_body(url)
        return url

    def clean_license_url(self):
        if not self.cleaned_data['license_url']:
            return None
        url = self.cleaned_data['license_url']
        clean_url_and_get_body(url)
        return url

    def clean(self):
        if self.schema_refs_formset.total_form_count() == 0:
            raise ValidationError('A schema must have at least one definition')

        self.additional_documentation_items_formset.clean()
        self.schema_refs_formset.clean()
        self.implementation_formset.clean()
        cleaned_data = super().clean()
        # Make sure none of the schema refs have the same URL
        schema_ref_urls = set()
        for schema_ref_form in self.schema_refs_formset:
            schema_ref_urls.add(schema_ref_form.cleaned_data.get('url'))
        if len(schema_ref_urls) < len(self.schema_refs_formset):
            raise ValidationError('Each schema definition URL must be unique')
        return cleaned_data

    def is_valid(self):
        is_documentation_items_formset_valid = self.additional_documentation_items_formset.is_valid()
        is_schema_refs_formset_valid = self.schema_refs_formset.is_valid()
        is_implementation_formset_valid = self.implementation_formset.is_valid()
        # This must be called *after* the formsets,
        # as the clean method requires access
        # to formset cleaned_data
        is_form_valid = super().is_valid()
        return (
            is_form_valid and
            is_documentation_items_formset_valid and
            is_schema_refs_formset_valid and
            is_implementation_formset_valid
        )


dot_slash_slug_character_validator = RegexValidator(
    regex=r"^[a-zA-Z0-9_./-]+$",
    message='Enter a valid "slug" consisting of letters, numbers, underscores, hyphens, slashes, or periods.',
    code="invalid_dot_slug",
)


no_double_slash_validator = RegexValidator(
    regex=r'^(?!.*//).*$',
    message="Double slashes ('//') are not allowed.",
    code="double_slash_not_allowed"
)


no_edge_slash_validator = RegexValidator(
    regex=r'^(?!/)(?!.*?/$).+$',
    message="Cannot start or end with a slash ('/').",
    code="edge_slash_not_allowed",
)


class DotSlashSlugField(forms.SlugField):
    default_validators = [
        dot_slash_slug_character_validator,
        no_double_slash_validator,
        no_edge_slash_validator
    ]


class PermanentURLForm(forms.Form):
    class LinkType:
        UUID = 'uuid'
        EMAIL = 'email'
        ORGANIZATION = 'organization'

    target = forms.ChoiceField(
        label="Link to",
        widget=forms.Select(attrs={'class': 'js-autorefresh-with-value'})
    )
    link_type = forms.ChoiceField(
        label="URL",
        widget=forms.Select(attrs={'class': 'js-autorefresh-with-value input-group__prefix'})
    )
    suffix = DotSlashSlugField(
        max_length=300,
        widget=forms.TextInput(attrs={'placeholder': 'my/schema.json'}),
        help_text="Your URL can include letters, numbers, spaces, underscores (_), hyphens (-), and slashes (/)."
    )

    def __init__(self, *args, schema, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema = schema

        # Add the schema and all schemaRefs as target options.
        # We use "[modelType]:[id]" as the select values.
        target_choices = [(f"schema:{schema.id}", f"{schema.name} (Schema)")]
        for schema_ref in schema.schemaref_set.all():
            target_choices.append((f"schemaref:{schema_ref.id}", f"{schema_ref.name or schema_ref.url} (Definition)"))
        self.fields['target'].choices = target_choices
        
        link_type_choices = [
            (self.LinkType.UUID, 'schemas.pub/u/'),
            (self.LinkType.EMAIL, f"schemas.pub/e/{schema.created_by.email}/")
        ]
        # Only users in an org can create org URLs
        if schema.created_by.profile.organization:
            link_type_choices.append(
                (self.LinkType.ORGANIZATION, f'schemas.pub/o/{schema.created_by.profile.organization.slug}/')
            )
        self.fields['link_type'].choices = link_type_choices

        link_type = self.data.get('link_type') or self.initial.get('link_type')
        if link_type not in (choice[0] for choice in link_type_choices):
            link_type = self.LinkType.UUID
        # When creating a UUID, change the suffix field to an uneditable placeholder.
        # We'll generate a UUID on submission.
        if link_type == self.LinkType.UUID:
            self.fields['suffix'] = forms.CharField(
                initial='<Generated ID>',
                required=False,
                help_text='A unique URL with a random ID will be generated for you.',
                widget=forms.TextInput(
                    attrs={
                        'readonly': True,
                        'disabled': True,
                        'style': 'font-style: italic'
                    }
                )
            )

    def clean_target(self):
        data = self.cleaned_data['target']
        target_type, target_id = data.split(':', 1)
        
        if (target_type != 'schema' and target_type != 'schemaref') or \
           (target_type == 'schema' and not Schema.objects.filter(id=target_id).exists()) or \
           (target_type == 'schemaref' and not SchemaRef.objects.filter(id=target_id).exists()):
            # This can only happen if the target value isn't one we provided (user shennanigans),
            # or if the target was deleted sometime between loading and submitting the form (unlikely).
            raise forms.ValidationError('Invalid target.')

        return data

    def clean(self):
        cleaned_data = super().clean()
        
        if PermanentURL.objects.filter(created_by=self.schema.created_by).count() >= MAX_PERMANENT_URL_COUNT_PER_USER:
            raise ValidationError(f"You have reached the limit of {MAX_PERMANENT_URL_COUNT_PER_USER} permanent URLs for your account.")

        link_type = cleaned_data.get('link_type')
        if link_type == self.LinkType.UUID:
            return
        if link_type == self.LinkType.EMAIL:
            proposed_url = PermanentURL.objects.get_email_url_for_suffix(
                email_address=self.schema.created_by.email,
                suffix=cleaned_data.get('suffix')
            )
        elif self.schema.created_by.profile.organization: # link_type == self.LinkType.ORGANIZATION
            proposed_url = PermanentURL.objects.get_org_url_for_suffix(
                organization=self.schema.created_by.profile.organization,
                suffix=cleaned_data.get('suffix')
            )
        if PermanentURL.objects.filter(url=proposed_url).exists():
            raise ValidationError('This URL is already in use.')

