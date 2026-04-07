import pytest
import requests_mock
from unittest.mock import patch
from django.utils import timezone
from django.core import mail
from core.models import Schema, SchemaRef, APIKey
from factories import (
    UserFactory,
    SchemaRefFactory,
    ProfileFactory,
    APIKeyFactory
)
import requests.exceptions


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


@pytest.mark.django_db
def test_reference_item_content_is_fetched_from_raw_url_if_available():
    schema_ref = SchemaRefFactory(url="https://github.com/userorg/reponame/blob/branch/path/to/file.json")
    mock_content = '{"MOCK_CONTENT":true}'
    # Make sure the URL we expect to be fetched isn't the one we provided
    assert schema_ref.url != schema_ref.url_provider_info.raw_url
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url_provider_info.raw_url, text=mock_content)
        assert schema_ref.get_content() == mock_content


@pytest.mark.django_db
@patch("core.models.time.sleep", return_value=None)
def test_reference_item_get_content_success(mock_sleep):
    schema_ref = SchemaRefFactory.create()
    mock_content = "some content"
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, text=mock_content)
        content = schema_ref.get_content()
        assert content == mock_content
        schema_ref.refresh_from_db()
        assert schema_ref.content_fetch_failing_since is None


@pytest.mark.django_db
@patch("core.models.time.sleep", return_value=None)
def test_reference_item_get_content_failure_sends_email_and_sets_timestamp(mock_sleep):
    schema_ref = SchemaRefFactory.create()
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, status_code=500)
        with pytest.raises(requests.exceptions.HTTPError):
            schema_ref.get_content()

        schema_ref.refresh_from_db()
        assert schema_ref.content_fetch_failing_since is not None
        assert len(mail.outbox) == 1
        assert "Content Failure" in mail.outbox[0].subject


@pytest.mark.django_db
@patch("core.models.time.sleep", return_value=None)
def test_reference_item_get_content_subsequent_failure_no_email_or_timestamp_change(mock_sleep):
    mock_failure_time = timezone.now() - timezone.timedelta(hours=1)
    schema_ref = SchemaRefFactory.create(
        content_fetch_failing_since=mock_failure_time
    )
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, status_code=500)
        with pytest.raises(requests.exceptions.HTTPError):
            schema_ref.get_content()

        schema_ref.refresh_from_db()
        assert schema_ref.content_fetch_failing_since == mock_failure_time
        assert len(mail.outbox) == 0


@pytest.mark.django_db
@patch("core.models.time.sleep", return_value=None)
def test_reference_item_get_content_success_after_failure_clears_timestamp(mock_sleep):
    schema_ref = SchemaRefFactory.create(
        content_fetch_failing_since=timezone.now() - timezone.timedelta(hours=1)
    )
    mock_content = "some content"
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, text=mock_content)
        content = schema_ref.get_content()
        assert content == mock_content
        schema_ref.refresh_from_db()
        assert schema_ref.content_fetch_failing_since is None


@pytest.mark.django_db
@patch("core.models.time.sleep", return_value=None)
def test_reference_item_get_content_retries_on_unreachable(mock_sleep):
    schema_ref = SchemaRefFactory.create()
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, exc=requests.exceptions.HTTPError)
        with pytest.raises(requests.exceptions.HTTPError):
            schema_ref.get_content()

        # 3 attempts total (initial + 2 retries)
        assert m.call_count == 3
        assert mock_sleep.call_count == 2


@pytest.mark.django_db
def test_reference_item_save_resets_failure_timestamp_on_url_change():
    schema_ref = SchemaRefFactory.create(
        content_fetch_failing_since=timezone.now(),
    )
    schema_ref.url = "https://example.com/new-url"
    schema_ref.save()
    assert schema_ref.content_fetch_failing_since is None


@pytest.mark.django_db
def test_reference_item_save_does_not_reset_failure_timestamp_on_other_change():
    now = timezone.now()
    schema_ref = SchemaRefFactory.create(
        content_fetch_failing_since=now,
        name="Old Name",
    )
    schema_ref.name = "New Name"
    schema_ref.save()
    assert schema_ref.content_fetch_failing_since == now


@pytest.mark.django_db
@patch("core.models.time.sleep", return_value=None)
def test_reference_item_get_content_no_email_on_non_http_error(mock_sleep):
    schema_ref = SchemaRefFactory.create()
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, exc=requests.exceptions.ConnectionError)
        with pytest.raises(requests.exceptions.ConnectionError):
            schema_ref.get_content()

        schema_ref.refresh_from_db()
        assert schema_ref.content_fetch_failing_since is None
        assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_api_key_creation():
    profile = ProfileFactory.create()
    api_key = profile.set_new_api_key()
    prefix = api_key.split('.')[0]
    assert APIKey.objects.filter(profile=profile).count() == 1
    assert profile.api_key.prefix == prefix


@pytest.mark.django_db
def test_api_key_replacement():
    existing_api_key = APIKeyFactory.create();
    profile = existing_api_key.profile
    profile.set_new_api_key()
    assert not APIKey.objects.filter(pk=existing_api_key.pk).exists()
    profile.refresh_from_db()
    assert profile.api_key.pk != existing_api_key.pk

