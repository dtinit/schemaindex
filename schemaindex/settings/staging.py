"""
Staging settings for Schema Index.

This inherits from base settings and adds Cloud Run specific configuration.
"""

import os
from .base import *

# Override base settings for staging environment
DEBUG = False

# Temporary - will update with real Cloud Run URL after first deployment
ALLOWED_HOSTS = ['*']

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

# Static files configuration
STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/static/'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/media/'

# Security settings for production-like environment
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY)

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Trust the Cloud Run proxy
USE_TZ = True

# Logging configuration for Cloud Run
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
