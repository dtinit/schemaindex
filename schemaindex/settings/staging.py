"""
Staging settings for Schema Index.

This inherits from base settings and adds Cloud Run specific configuration.
"""

import os
import sys
import environ
from .base import *

# Override base settings for staging environment
DEBUG = False

# Update ALLOWED_HOSTS with actual Cloud Run URL
ALLOWED_HOSTS = ['schemaindex-stg-run-799626592344.us-central1.run.app']

# Use PostgreSQL if environment variable exists, otherwise inherit SQLite from base.py
if 'DJ_DATABASE_CONN_STRING' in os.environ:
    env = environ.Env()
    DATABASES = {
        'default': env.db('DJ_DATABASE_CONN_STRING')
    }

# CSRF and CORS configuration for staging
CSRF_TRUSTED_ORIGINS = [
    'https://*.run.app',  # Wildcard for Cloud Run URLs
    'https://staging-schemaindex.dtinit.org'  # Custom domain if planned
]

# Google Cloud Storage configuration
GS_BUCKET_NAME = 'schemaindex-stg-storage'

# Use Cloud Storage for static and media files
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "bucket_name": GS_BUCKET_NAME,
            "location": "logos",
            "querystring_auth": False,
        }
    },
    "staticfiles": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            "bucket_name": GS_BUCKET_NAME,
            "location": "site-assets",
            "querystring_auth": False,
        }
    }
}

# Static files configuration
STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/static/'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'

# Security settings for production-like environment
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY)

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Logging configuration for Cloud Run (matches Trust Registry pattern)
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
