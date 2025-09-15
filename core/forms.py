from django import forms
from .models import DocumentationItem

class SchemaForm(forms.Form):
    name = forms.CharField(label="Schema name", max_length=200)
    reference_url = forms.URLField(label="Schema definition URL")
    readme_url = forms.URLField(label="Schema README URL")
    readme_format = forms.ChoiceField(
        choices=list(DocumentationItem.DocumentationItemFormat.choices) + [('', 'Other')],
        required=False,
        label="README format"
    )
