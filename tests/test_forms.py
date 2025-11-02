import pytest
import requests_mock
from urllib.parse import urlparse, urlunparse
from core.forms import SchemaForm
from tests.factories import SchemaFactory, SchemaRefFactory
from core.models import DocumentationItem

@pytest.mark.django_db
def test_schema_management_form_prevents_duplicate_urls():
    existing_schema_ref = SchemaRefFactory(url='http://example.com/definiton.json')
    https_url = urlunparse(urlparse(existing_schema_ref.url)._replace(scheme='https'))
    with requests_mock.Mocker() as m:
        m.get(existing_schema_ref.url, text='{}')
        m.get('http://example.com', text='{}')
        form = SchemaForm(data={
            'name': 'New schema',
            'reference_url': existing_schema_ref.url,
            'readme_url': 'http://example.com'
        })
        assert not form.is_valid()
        error = form.errors['reference_url'][0]
        assert error == 'The provided URL is already in use by another Schema'

@pytest.mark.django_db
def test_clean_url():
    with requests_mock.Mocker() as m:
        m.get("http://example.com/schema.cddl", text='{}')
        m.get('http://example.com', text='{}')
        form = SchemaForm(data={
            'name': 'New schema',
            'reference_url': "http://example.com/schema.cddl",
            'readme_url': 'http://example.com',
        })
        form.is_valid()
        assert form.errors == {}
        # TECHNICALLY this works.  The form is NOT valid because the formset does not validate correctly.
        # But this does test whether the CDDL extension adds an error or not.
        # TODO: Sort out how to write tests for forms that have formsets? Or move _clean_url to a
        # location where we can test it directly? because I wanted a test to make sure I understood _clean_url