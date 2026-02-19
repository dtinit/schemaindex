from .production import *

ALLOWED_HOSTS = ['schemaindex-stg-run-799626592344.us-central1.run.app']
PERMANENT_URL_HOST = ALLOWED_HOSTS[0]
SITE_URL = 'https://schemaindex-stg-run-799626592344.us-central1.run.app'
CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
GS_BUCKET_NAME = 'schemaindex-stg-storage'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Update the STORAGES configuration with the staging bucket
for key in STORAGES:
    STORAGES[key]["OPTIONS"]["bucket_name"] = GS_BUCKET_NAME

# Buckets URLs for static and media files
STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/site-assets/'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/schemas/'
