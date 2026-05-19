import logging
import os
import sys
import environ

from django.core.exceptions import ImproperlyConfigured
from google.oauth2 import service_account
from .base import *

logger = logging.getLogger("schemaindex")

DEBUG = False
PERMANENT_URL_HOST = 'id.schemas.pub'
ALLOWED_HOSTS = [ 
    'schemas.pub',
    'www.schemas.pub',
    'schemaindex-prod-run-768243509223.us-central1.run.app',
    PERMANENT_URL_HOST
]
SITE_URL = 'https://schemas.pub'
CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
    'service-account-credentials.json'
)
GS_BUCKET_NAME = 'schemaindex-prod-storage'

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY)

# Shared Valkey cache (Memorystore for Valkey in GCP)
VALKEY_URL = env.str('VALKEY_URL', default='')
if not VALKEY_URL:
    raise ImproperlyConfigured(
        "VALKEY_URL is required in staging/production."
    )

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": VALKEY_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Fail open on runtime Valkey errors: callers see a cache miss,
            # not a 500. get_content() then fetches the remote URL directly.
            "IGNORE_EXCEPTIONS": True,
            "SOCKET_CONNECT_TIMEOUT": 1,
            "SOCKET_TIMEOUT": 1,
            "CONNECTION_POOL_KWARGS": {"max_connections": 32},
        },
    }
}

DJANGO_REDIS_IGNORE_EXCEPTIONS = True

logger.info(
    "Valkey cache configured (tls=%s, auth=none)",
    VALKEY_URL.startswith("rediss://"),
)

# Shared Valkey TLS CA trust.
# The deploy workflow writes the PEM to disk and points us at it via VALKEY_SERVER_CA
VALKEY_SERVER_CA = env.str("VALKEY_SERVER_CA", default="")
if VALKEY_URL.startswith("rediss://") and VALKEY_SERVER_CA:
    _ca_path = VALKEY_SERVER_CA
    if not os.path.isabs(_ca_path):
        _ca_path = str(BASE_DIR / _ca_path)
    _pool_kwargs = CACHES["default"]["OPTIONS"].setdefault("CONNECTION_POOL_KWARGS", {})
    _pool_kwargs["ssl_ca_certs"] = _ca_path
    _pool_kwargs["ssl_cert_reqs"] = "required"
    logger.info(
        "Valkey TLS CA configured (path=%s, exists=%s)",
        _ca_path, os.path.exists(_ca_path),
    )
else:
    logger.info(
        "Valkey TLS CA not configured (tls=%s, ca_env_set=%s)",
        VALKEY_URL.startswith("rediss://"), bool(VALKEY_SERVER_CA),
    )

# Observability on so we can verify Valkey behavior end-to-end.
# TODO: Cleanup these flags and associated logging after we've verified Valkey is working well in staging/production. Upcoming PR!
CONTENT_CACHE_OBSERVABILITY = True
RATE_LIMIT_OBSERVABILITY = True

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "bucket_name": GS_BUCKET_NAME,
            "location": "logos",
        }
    },
    "staticfiles": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "bucket_name": GS_BUCKET_NAME,
            "location": "site-assets",
        }
    }
}

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

if os.environ.get('USE_GCLOUD_LOGGING', '0') == '1':
    LOGGING["handlers"]["cloud_logging"] = {
        "()": "schemaindex.utils.logging_utils.get_cloud_logging_handler",
    }
    
    LOGGING["root"] = {
        "handlers": ["cloud_logging"],
        "level": "INFO",
    }
    
    LOGGING["loggers"]["django"]["handlers"] = ["cloud_logging"]
    LOGGING["loggers"]["django"]["propagate"] = False

    LOGGING["loggers"]["schemaindex"] = {
        "handlers": ["cloud_logging"],
        "level": "INFO",
        "propagate": False,
    }
    
    LOGGING["loggers"]["django.request"] = {
        "handlers": ["cloud_logging"],
        "level": "INFO",
        "propagate": False,
    }

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = "noreply@dtinit.org"
EMAIL_HOST_PASSWORD = env.str('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = "noreply@dtinit.org"
SERVER_EMAIL = "noreply@dtinit.org"
