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
