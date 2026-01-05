import pytest
import requests_mock
from core.models import Schema, SchemaRef
from factories import UserFactory

@pytest.mark.django_db
def test_multiple_schemarefs():
    # A simple test but leaving it in as I used it to debug a simple thing
    user = UserFactory.create()
    my_schema = Schema.objects.create(name="Star Trek", created_by=user)
    ship_schema = SchemaRef.objects.create(schema=my_schema, url="https://example.com/ships", created_by=user)
    station_schema = SchemaRef.objects.create(schema=my_schema, url="https://example.com/stns", created_by=user)
    assert Schema.objects.all().count() == 1
    assert my_schema.schemaref_set.count() == 2

@pytest.mark.parametrize("repo_url, raw_url", [
    [
        "https://github.com/userorg/reponame/blob/branch/path/to/file.json",
        "https://raw.githubusercontent.com/userorg/reponame/branch/path/to/file.json"
    ],
    [
        "https://github.com/userorg/reponame/blob/2a7ec7e5f3006aadaadb9535b452d0d0352c7a39/path/to/file.json",
        "https://raw.githubusercontent.com/userorg/reponame/2a7ec7e5f3006aadaadb9535b452d0d0352c7a39/path/to/file.json"
    ],

])
def test_reference_item_github_url_info_converts_repo_url_to_raw(repo_url, raw_url):
    schema_ref = SchemaRef(url=repo_url)
    assert schema_ref.url_provider_info.raw_url == raw_url
     

@pytest.mark.parametrize("repo_url, raw_url", [
    [
        "https://github.com/userorg/reponame/blob/branch/path/to/file.json",
        "https://raw.githubusercontent.com/userorg/reponame/refs/heads/branch/path/to/file.json"
    ],
    [
        "https://github.com/userorg/reponame/blob/2a7ec7e5f3006aadaadb9535b452d0d0352c7a39/path/to/file.json",
        "https://raw.githubusercontent.com/userorg/reponame/2a7ec7e5f3006aadaadb9535b452d0d0352c7a39/path/to/file.json"
    ],
    [
        "https://github.com/userorg/reponame/blob/branch/path/to/file.json",
        # GitHub provides this style of link in the web UI
        # but redirects them to raw.githubusercontent.com
        "https://github.com/userorg/reponame/raw/refs/heads/branch/path/to/file.json"
    ],
    [
        "https://github.com/userorg/reponame/blob/2a7ec7e5f3006aadaadb9535b452d0d0352c7a39/path/to/file.json",
        "https://github.com/userorg/reponame/raw/2a7ec7e5f3006aadaadb9535b452d0d0352c7a39/path/to/file.json"
    ]
])
def test_reference_item_github_url_info_converts_raw_url_to_repo(repo_url, raw_url):
    schema_ref = SchemaRef(url=raw_url)
    assert schema_ref.url_provider_info.repo_url == repo_url


def test_reference_item_content_is_fetched_from_raw_url_if_available():
    schema_ref = SchemaRef(url="https://github.com/userorg/reponame/blob/branch/path/to/file.json")
    mock_content = '{"MOCK_CONTENT":true}'
    # Make sure the URL we expect to be fetched isn't the one we provided
    assert schema_ref.url != schema_ref.url_provider_info.raw_url
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url_provider_info.raw_url, text=mock_content)
        assert schema_ref.get_content() == mock_content
