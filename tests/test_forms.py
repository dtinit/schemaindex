import pytest
import requests_mock
from urllib.parse import urlparse, urlunparse
from core.forms import SchemaForm, SPECIFICATION_LANGUAGE_ALLOWLIST, clean_url
from tests.factories import SchemaFactory, SchemaRefFactory
from core.models import DocumentationItem

@pytest.mark.django_db
def test_schema_management_form_prevents_duplicate_published_urls():
    existing_schema_ref = SchemaRefFactory(url='http://example.com/definition.json')
    https_url = urlunparse(urlparse(existing_schema_ref.url)._replace(scheme='https'))
    edited_schema = SchemaFactory()
    with requests_mock.Mocker() as m:
        m.get(https_url, text='{}')
        m.get('http://example.com', text='{}')
        form = SchemaForm(schema=edited_schema, data={
            'readme_url': 'http://example.com',
            'schema_refs-0-url': https_url,
            'documentation_items-TOTAL_FORMS': 0,
            'documentation_items-INITIAL_FORMS': 0,
            'schema_refs-TOTAL_FORMS': 1,
            'schema_refs-INITIAL_FORMS': 0
        })
        assert not form.is_valid()
        error = form.schema_refs_formset.errors[0]['url'][0] # Form 0, error list for 'url', error 0
        assert error == 'The provided URL is already in use by another Schema'


@pytest.mark.django_db
def test_schema_management_form_allows_duplicate_private_urls():
    existing_schema_ref = SchemaRefFactory(
        url='http://example.com/definition.json',
        schema=SchemaFactory(published_at=None)
    )
    with requests_mock.Mocker() as m:
        m.get(existing_schema_ref.url, text='{}')
        m.get('http://example.com', text='{}')
        form = SchemaForm(data={
            'name': 'New schema',
            'schema_refs-0-url': existing_schema_ref.url,
            'readme_url': 'http://example.com',
            'documentation_items-TOTAL_FORMS': 0,
            'documentation_items-INITIAL_FORMS': 0,
            'schema_refs-TOTAL_FORMS': 1,
            'schema_refs-INITIAL_FORMS': 0
        })
        assert form.is_valid()


@pytest.mark.django_db
@pytest.mark.parametrize("spec_url, expect_success",
                         [['http://example.com/schema.cddl', True],
                           ['', False],
                           ['http://example.com/schema.BOGUS', False],
                            ['http://example.com/schema.cddl?param=hello#anchor', True]])
def test_clean_url(spec_url, expect_success):
    with requests_mock.Mocker() as m:
        m.get(spec_url, text='{}')
        m.get('http://example.com', text='{}')
        form = SchemaForm(data={
            'name': 'New schema',
            'schema_refs-0-url': spec_url,
            'readme_url': 'http://example.com',
            'documentation_items-TOTAL_FORMS': 0,
            'documentation_items-INITIAL_FORMS': 0,
            'schema_refs-TOTAL_FORMS': 1,
            'schema_refs-INITIAL_FORMS': 0
        })
        assert expect_success == form.is_valid()


@pytest.mark.django_db
def test_schema_management_form_requires_one_schema_ref():
    with requests_mock.Mocker() as m:
        m.get('http://example.com', text='{}')
        form = SchemaForm(data={
            'name': 'New schema',
            'readme_url': 'http://example.com',
            'documentation_items-TOTAL_FORMS': 0,
            'documentation_items-INITIAL_FORMS': 0,
            'schema_refs-TOTAL_FORMS': 0,
            'schema_refs-INITIAL_FORMS': 0
        })
        assert not form.is_valid()
        error = form.non_field_errors()[0]
        assert error == 'A schema must have at least one definition'

