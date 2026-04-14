from itertools import chain
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.hashers import make_password, check_password
from django.core.cache import cache
from urllib.parse import urlparse
import hashlib
import logging
import time
import requests
import requests.exceptions
import secrets
from django.core.mail import send_mail
from .utils import (
    guess_specification_language_by_extension,
    guess_language_by_extension,
)

logger = logging.getLogger(__name__)


class BaseModel(models.Model):
    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.RESTRICT)

    @classmethod
    def create(cls, created_by):
        return cls(created_by=created_by)

class PermanentURLManager(models.Manager):
    BASE_URL = f'https://{settings.PERMANENT_URL_HOST}/'

    def get_org_url_for_suffix(self, organization, suffix):
        return self.BASE_URL + 'o/' + organization.slug + '/' + suffix

    def create_from_org_suffix(self, created_by, suffix, **kwargs):
        """
        Creates a URL from the user's organization and a suffix.
        """
        url = self.get_org_url_for_suffix(
            organization=created_by.profile.organization,
            suffix=suffix
        )
        kwargs.update(
            created_by=created_by,
            url=url
        )
        return super().create(**kwargs)

    def get_email_url_for_suffix(self, email_address, suffix):
        return self.BASE_URL + 'e/' + email_address + '/' + suffix

    def create_from_email_suffix(self, created_by, suffix, **kwargs):
        """
        Creates a URL from the user's email address and a suffix.
        """
        url = self.get_email_url_for_suffix(
            email_address=created_by.email,
            suffix=suffix
        )
        kwargs.update(
            created_by=created_by,
            url=url
        )
        return super().create(**kwargs)

    def create_from_uuid(self, uuid, **kwargs):
        url = self.BASE_URL + 'u/' + str(uuid)
        kwargs.update(
            url=url
        )
        return super().create(**kwargs)


class PermanentURL(BaseModel):
    objects = PermanentURLManager()
    content_type = models.ForeignKey(ContentType, on_delete=models.RESTRICT)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    url = models.URLField()
    
    class Meta:
        # As of writing, Django does *not* automatically create an index
        # on the GenericForeignKey as it does with ForeignKey.
        indexes = [
            models.Index(fields=["content_type", "object_id"])
        ]


class PublicSchemaManager(models.Manager):
    def get_queryset(self):
        return (
            super().get_queryset().filter(
                published_at__isnull=False,
                published_at__lte=timezone.now()
            )
        )


class Schema(BaseModel):
    objects = models.Manager()
    public_objects = PublicSchemaManager()
    name = models.CharField(max_length=200)
    published_at = models.DateTimeField(blank=True, null=True)
    permanent_urls = GenericRelation(PermanentURL, related_query_name="schema")
    description = models.CharField(blank=True, null=True, max_length=350)

    class Meta:
        indexes = [
            models.Index(fields=['published_at'])
        ]

    def __str__(self):
        return self.name

    @property
    def is_published(self):
        return self.published_at is not None and self.published_at <= timezone.now()

    @property
    def url_providers(self):
        documentation_items =  self.documentationitem_set.all()
        schema_refs = self.schemaref_set.all()
        provider_names = {
            reference_item.url_provider_info.provider_name
            for reference_item in chain(documentation_items, schema_refs)
        }
        return provider_names

    @property
    def organization(self):
        return self.created_by.profile.organization
    
    @property
    def closed_source_implementation_set(self):
        return self.implementation_set.filter(is_open_source=False)

    @property
    def open_source_implementation_set(self):
        return self.implementation_set.filter(is_open_source=True)

    @property
    def has_open_source_implementation(self):
        return self.open_source_implementation_set.exists()

    def _latest_documentation_item_of_type(self, role):
        return self.documentationitem_set.filter(role=role).order_by('-created_at').first()

    def latest_reference(self):
        return self.schemaref_set.order_by('-created_at').first()

    def latest_readme(self):
        return self._latest_documentation_item_of_type(role=DocumentationItem.DocumentationItemRole.README)

    def latest_license(self):
        return self._latest_documentation_item_of_type(role=DocumentationItem.DocumentationItemRole.License)
    
    def latest_rfc(self):
        return self._latest_documentation_item_of_type(role=DocumentationItem.DocumentationItemRole.RFC)

    def latest_w3c(self):
        return self._latest_documentation_item_of_type(role=DocumentationItem.DocumentationItemRole.W3C)

    def additional_documentation_items(self):
        return self.documentationitem_set.exclude(role__in=[
            DocumentationItem.DocumentationItemRole.README,
            DocumentationItem.DocumentationItemRole.License
        ])


class ReferenceItemManager(models.Manager):
    def get_published_by_domain_and_path(self, url):
        published_schema_refs = super().get_queryset().select_related('schema').exclude(
            schema__published_at__isnull=True
        )
        matching_published_schema_ref_ids = [
            schema_ref.id for schema_ref in published_schema_refs
            if schema_ref.url_provider_info.is_same_resource(url)
        ]
        # Custom manager methods like this typically return a QuerySet.
        # In this case, we already retrieved these items from the db,
        # so we *could* break convention and just return the actual objects.
        # Instead, we're making an extra db request just to return a QuerySet
        # of the matching objects, prefering developer ergonomics
        # over max performance. For now, the performance hit should be negligible.
        return super().get_queryset().filter(id__in=matching_published_schema_ref_ids)


class URLProviderInfo:
    """
    Encapsulates provider-specific (e.g. GitHub) URL info and helpers.
    """
    provider_name = None


    def __init__(self, url):
        self.url = url

    @classmethod
    def from_url(cls, url):
        if GitHubURLInfo.matches(url):
            return GitHubURLInfo(url)

        return cls(url)

    def is_same_resource(self, url):
        parsed_url_1 = urlparse(self.url)
        parsed_url_2 = urlparse(url)
        return parsed_url_1.netloc == parsed_url_2.netloc and parsed_url_1.path == parsed_url_2.path


class GitHubURLInfo(URLProviderInfo):
    """
    GitHub URL helpers for converting "repo URLs"
    (github.com/user/repo/branch/blob/path/file.json)
    to "raw URLs"
    (raw.githubusercontent.com/user/repo/path/file.json)
    and vice versa.

    Repo URLs host a file within GitHub's web UI and are meant to be
    accessed by a browser, whereas raw URLs resolve to the actual file.

    We don't currently support every possible format of these two URLs,
    but we've tried to cover the most common ones for now.

    The raw URLs constructed by this class may differ slightly from what
    you'd get when clicking the actual "Raw" link for a file in GitHub's web UI,
    but they should both resolve to the same file.
    """

    REPO_NETLOC = "github.com"
    RAW_NETLOC = "raw.githubusercontent.com"

    provider_name = 'GitHub'

    @classmethod
    def matches(cls, url):
        parsed = urlparse(url)
        return parsed.netloc in (cls.REPO_NETLOC, cls.RAW_NETLOC)

    @property
    def _is_raw_url(self):
        parsed = urlparse(self.url)
        if parsed.netloc == self.RAW_NETLOC:
            return True
        # {{REPO_NETLOC}}/{userorg}/{reponame}/raw/... 
        # is a special case for raw URLs even though it's
        # hosted at the netloc for repo URLs
        if parsed.netloc != self.REPO_NETLOC:
            return False
        path_parts = parsed.path.strip("/").split("/")
        return len(path_parts) >= 3 and path_parts[2] == "raw"

    @property
    def _is_repo_url(self):
        parsed = urlparse(self.url)
        return parsed.netloc == self.REPO_NETLOC and not self._is_raw_url
    
    @property
    def raw_url(self):
        """
        Returns a "raw.githubusercontent.com/..." URL if possible.
        """
        if self._is_raw_url:
            return self.url
        parsed = urlparse(self.url)
        # github.com/{user}/{repo}/blob/{branch}/{path} -> raw.githubuser.content.com/{user}/{repo}/{branch}/{path}
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 5:
            return None
        user, repo, blob, branch, *filepath = path_parts
        raw_path = "/".join([user, repo, branch] + filepath)
        return f"https://{self.RAW_NETLOC}/{raw_path}"

    @property
    def repo_url(self):
        """
        Returns a "github.com/..." URL if possible.
        """
        if self._is_repo_url:
            return self.url
        parsed = urlparse(self.url)
        # raw.githubusercontent.com/{user}/{repo}/(refs/heads/){branch}/{path}
        # or
        # github.com/{user}/{repo}/raw/(refs/heads/){branch}/{path}
        # -> github.com/{user}/{repo}/blob/{branch}/{path}
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 4:
            return None
        # Handle special case for raw URLs hosted at REPO_NETLOC
        if path_parts[2] == 'raw':
            del path_parts[2]
        # Permalinks don't have "/refs/heads"
        if path_parts[2] == 'refs' and path_parts[3] == 'heads':
            del path_parts[2:4]
        user, repo, branch, *filepath = path_parts
        normal_path = "/".join([user, repo, "blob", branch] + filepath)
        return f"https://{self.REPO_NETLOC}/{normal_path}"

    def is_same_resource(self, url):
        # If the url isn't even known to be hosted by GitHub,
        # there's no point trying to compare it with more complicated logic.
        if not self.matches(url):
            return False

        url_provider_info = GitHubURLInfo(url) 
        # If either raw_url or repo_url has a value, compare 'url' to them.
        if self.raw_url is not None or self.repo_url is not None:
            return (
                self.raw_url == url_provider_info.raw_url or
                self.repo_url == url_provider_info.repo_url
            )

        # Otherwise, fallback to the parent implementation.
        # If this happens, it probably means our repo_url or raw_url
        # logic needs to be updated to handle this self.url better.
        return super().is_same_resource(url)


class ReferenceItem(BaseModel):
    class Meta:
        abstract = True

    objects = ReferenceItemManager()
    url = models.URLField()
    name = models.CharField(max_length=300, blank=True, null=True)
    content_fetch_failing_since = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.url

    def save(self, *args, **kwargs):
        # If the URL changed, set content_fetch_failing_since to None
        if self.id:
            original = self.__class__.objects.get(id=self.id)
            if original.url != self.url:
                self.content_fetch_failing_since = None
        super().save(*args, **kwargs)

    def _get_content_url(self):
        # Resolve the URL to fetch content from 
        if (
            self.url_provider_info.provider_name == GitHubURLInfo.provider_name
            and self.url_provider_info.raw_url
        ):
            return self.url_provider_info.raw_url
        return self.url

    def _content_cache_key(self):
        # Build a cache key from the resolved content URL
        content_url = self._get_content_url()
        url_hash = hashlib.sha256(content_url.encode()).hexdigest()[:16]
        return f"content:{url_hash}"

    def get_content(self, force_refresh=False):
        cache_key = self._content_cache_key()

        # Return cached content unless a refresh is forced
        if not force_refresh:
            cached_content = cache.get(cache_key)
            if cached_content is not None:
                logger.info("Cache hit for %s", cache_key)
                return cached_content

        content_url = self._get_content_url()
        logger.info("Cache miss for %s, fetching from %s", cache_key, content_url)

        # Retry logic with exponential backoff
        retries = 2
        # Initial backoff of 0.5s, then 1s, then 2s, etc (though currently limited to 2 retries)
        backoff_factor = 0.5
        last_exception = None

        for i in range(retries + 1):  # +1 for the initial attempt
            try:
                response = requests.get(content_url)
                response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

                if self.content_fetch_failing_since != None:
                    self.content_fetch_failing_since = None
                    self.save()

                # Cache the successfully fetched content
                cache.set(cache_key, response.text, timeout=settings.CONTENT_CACHE_TTL)
                logger.info("Cached content for %s (TTL: %ds)", cache_key, settings.CONTENT_CACHE_TTL)
                return response.text
            except requests.exceptions.RequestException as e:
                last_exception = e
                if i < retries:
                    time.sleep(backoff_factor * (2**i))  # Exponential backoff
                else:
                    # All retries exhausted, handle as a failure.

                    # Only notify the user if it's an HTTPError
                    # and hasn't already been failing
                    is_http_error = isinstance(e, requests.exceptions.HTTPError)
                    if is_http_error and self.content_fetch_failing_since == None:
                        self.content_fetch_failing_since = timezone.now()
                        self._send_failure_notification_email()
                        self.save()

                    raise last_exception  # Re-raise the last exception after all retries and email logic

    def _send_failure_notification_email(self):
        recipient_email = self.created_by.email
        subject = "Schemas.Pub Content Failure"
        message = (
            f"Hello,\n\n"
            f'One of the URLs associated with "{self.schema.name}" could not be reached:\n'
            f"{self.name}: {self.url}\n"
            if self.name
            else f"{self.url}\n"
            f"Please check the URL is correct or replace it if necessary.\n\n"
            f"Thank you!\n\n"
            f"The Schemas.Pub Admin Team"
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=True,
        )

    @property
    def url_provider_info(self):
        return URLProviderInfo.from_url(self.url)


class SchemaRef(ReferenceItem):
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)
    permanent_urls = GenericRelation(PermanentURL, related_query_name="schemaref")

    @property
    def language(self):
        return guess_specification_language_by_extension(self.url)


class DocumentationItem(ReferenceItem):
    class DocumentationItemRole(models.TextChoices):
        README = 'readme', 'README'
        License = 'license'
        RFC = 'rfc', 'RFC'
        W3C = 'w3c', 'W3C'

    class DocumentationItemFormat(models.TextChoices):
        Markdown = 'markdown'
        PlainText = 'plaintext', 'Plain text'

    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)
    role = models.CharField(max_length=100, choices=DocumentationItemRole, blank=True, null=True)
    format = models.CharField(max_length=100, choices=DocumentationItemFormat, blank=True, null=True)

    def __str__(self):
        return self.name

    @property
    def language(self):
        return guess_language_by_extension(self.url, ['markdown'])


class Implementation(ReferenceItem):
    is_open_source = models.BooleanField(default=False)
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)


class Organization(BaseModel):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    logo = models.ImageField(blank=True, null=True, upload_to="images/logos")

    def __str__(self):
        return self.name

    @property
    def public_schemas(self):
        return Schema.public_objects.filter(
            created_by_id__in=self.profile_set.values_list("user_id", flat=True)
        )


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, blank=True, null=True, on_delete=models.SET_NULL)

    def set_new_api_key(self):
        """
        Deletes any existing key and issues a brand new one.
        Returns the raw string '<prefix>.<secret>' to be shown to the user once.
        """
        # We use a transaction to ensure we don't delete the old key 
        # and then fail to create the new one.
        with transaction.atomic():
            if hasattr(self, 'api_key'):
                self.api_key.delete()

            new_prefix = secrets.token_urlsafe(6)[:8]
            new_secret = secrets.token_urlsafe(32)

            APIKey.objects.create(
                profile=self,
                prefix=new_prefix,
                hashed_secret=make_password(new_secret)
            )

        return f"{new_prefix}.{new_secret}"


class APIKeyManager(models.Manager):
    def get_from_key(self, raw_api_key):
        prefix, secret = raw_api_key.split('.', 1)
        try:
           api_key = self.select_related('profile').get(prefix=prefix)
        except self.model.DoesNotExist:
            return None

        if check_password(secret, api_key.hashed_secret):
            return api_key
        
        return None

# An API key consists of a plaintext prefix for querying,
# and a hashed secret for actual authentication.
class APIKey(models.Model):
    objects = APIKeyManager()
    # If we need to allow multiple APIKeys per profile someday,
    # this can be changed to a ForeignKey.
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="api_key")
    prefix = models.CharField(max_length=8, unique=True, editable=False)
    hashed_secret = models.CharField(max_length=128, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Key {self.prefix} for {self.profile}"

