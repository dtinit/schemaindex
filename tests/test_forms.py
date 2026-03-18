import pytest
import requests_mock
from urllib.parse import urlparse, urlunparse
from django.contrib.contenttypes.models import ContentType
from core.forms import SchemaForm, clean_url, PermanentURLForm
from core.models import Schema
from tests.factories import (
    SchemaFactory,
    SchemaRefFactory,
    OrganizationSchemaRefFactory,
    OrganizationSchemaFactory,
    PermanentURLFactory,
    DocumentationItemFactory
)
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
            'schema_refs-INITIAL_FORMS': 0,
            'implementations-TOTAL_FORMS': 0,
            'implementations-INITIAL_FORMS': 0
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
            'schema_refs-INITIAL_FORMS': 0,
            'implementations-TOTAL_FORMS': 0,
            'implementations-INITIAL_FORMS': 0
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
            'schema_refs-INITIAL_FORMS': 0,
            'implementations-TOTAL_FORMS': 0,
            'implementations-INITIAL_FORMS': 0
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
            'schema_refs-INITIAL_FORMS': 0,
            'implementations-TOTAL_FORMS': 0,
            'implementations-INITIAL_FORMS': 0
        })
        assert not form.is_valid()
        error = form.non_field_errors()[0]
        assert error == 'A schema must have at least one definition'


@pytest.mark.django_db
def test_schema_management_form_prevents_duplicate_schema_ref_urls():
    spec_url = 'http://example.com/schema.json'
    with requests_mock.Mocker() as m:
        m.get('http://example.com', text='{}')
        m.get(spec_url, text='{}')
        form = SchemaForm(data={
            'name': 'New schema',
            'readme_url': 'http://example.com',
            'name': 'New schema',
            'schema_refs-0-url': spec_url,
            'schema_refs-1-url': spec_url,
            'readme_url': 'http://example.com',
            'documentation_items-TOTAL_FORMS': 0,
            'documentation_items-INITIAL_FORMS': 0,
            'schema_refs-TOTAL_FORMS': 2,
            'schema_refs-INITIAL_FORMS': 0,
            'implementations-TOTAL_FORMS': 0,
            'implementations-INITIAL_FORMS': 0
        })
        assert not form.is_valid()
        error = form.non_field_errors()[0]
        assert error == 'Each schema definition URL must be unique'


@pytest.mark.django_db
@pytest.mark.parametrize(
    "link_type",
    [PermanentURLForm.LinkType.ORGANIZATION, PermanentURLForm.LinkType.EMAIL]
)
def test_permanent_url_form_prevents_duplicate_urls(link_type):
    managed_schema = OrganizationSchemaFactory()
    other_schema = SchemaFactory(created_by=managed_schema.created_by)
    duplicate_suffix_value = 'duplicate_suffix'
    other_schema_permanent_url = PermanentURLFactory(
        content_object=other_schema,
        link_type=link_type,
        suffix=duplicate_suffix_value
    )
    form_data = {
        'target': f'schema:{managed_schema.id}',
        'link_type': link_type,
        'suffix': duplicate_suffix_value
    }
    form = PermanentURLForm(schema=managed_schema, data=form_data)
    assert not form.is_valid()
    error = form.non_field_errors()[0]
    assert error == 'This URL is already in use.'


@pytest.mark.django_db
def test_permanent_url_form_hides_org_url_option_for_non_org_users():
    managed_schema = SchemaFactory()
    form = PermanentURLForm(schema=managed_schema)
    choice_ids = {value for value, label in form.fields['link_type'].choices}
    assert PermanentURLForm.LinkType.ORGANIZATION not in choice_ids


@pytest.mark.django_db
def test_user_max_permanent_url_limit():
    managed_schema = SchemaFactory()
    for i in range(100):
        PermanentURLFactory(
            content_object=managed_schema,
            link_type=PermanentURLForm.LinkType.UUID,
        )
    form = PermanentURLForm(schema=managed_schema, data={
        'target': f'schema:{managed_schema.id}',
        'link_type': PermanentURLForm.LinkType.UUID
    })
    assert not form.is_valid()
    error = form.non_field_errors()[0]
    assert error == "You have reached the limit of 100 permanent URLs for your account."

