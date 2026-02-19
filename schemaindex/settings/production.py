import os
import sys
import environ

from google.oauth2 import service_account
from .base import *

DEBUG = False
PERMANENT_URL_HOST = 'id.schemas.pub'
ALLOWED_HOSTS = [ 
    'schemas.pub',
    'www.schemas.pub',
    'id.schemas.pub',
    'schemaindex-prod-run-768243509223.us-central1.run.app'
]
SITE_URL = 'https://schemas.pub'
CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
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
