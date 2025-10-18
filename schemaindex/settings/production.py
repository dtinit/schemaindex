import os
import sys
import environ

from google.oauth2 import service_account
from .base import *

DEBUG = False
ALLOWED_HOSTS = [
    '.run.app', 
    'schemaindex.dtinit.org',
    'www.schemaindex.dtinit.org',
]
SITE_URL = 'https://schemaindex.dtinit.org'
# CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
CSRF_TRUSTED_ORIGINS = [
    'https://*.run.app',
    'https://schemaindex.dtinit.org',
    'https://www.schemaindex.dtinit.org',
]
GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
    'service-account-credentials.json'
)
GS_BUCKET_NAME = 'schemaindex-prod-storage'

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY)

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

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'django_google_structured_logger.formatter.GoogleFormatter',
        },
    },
    'handlers': {
        'google_cloud': {
            'class': 'google.cloud.logging_v2.handlers.StructuredLogHandler',
            'stream': sys.stdout,
            'formatter': 'json',
        },
        # If we need a fallback or for debugging if necessary
        'console': {
            'class': 'logging.StreamHandler',
            'stream': sys.stderr,
        },
    },
    'root': {
        'handlers': ['google_cloud'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['google_cloud'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['google_cloud'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = "noreply@dtinit.org"
EMAIL_HOST_PASSWORD = env.str('EMAIL_HOST_PASSWORD')
