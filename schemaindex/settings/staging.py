from .production import *

ALLOWED_HOSTS = ['schemaindex-stg-run-799626592344.us-central1.run.app']
SITE_URL = 'https://schemaindex-stg-run-799626592344.us-central1.run.app'
CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
GS_BUCKET_NAME = 'schemaindex-stg-storage'

# Update the STORAGES configuration with the staging bucket
for key in STORAGES:
    STORAGES[key]["OPTIONS"]["bucket_name"] = GS_BUCKET_NAME

# Buckets URLs for static and media files
STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/site-assets/'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/schemas/'