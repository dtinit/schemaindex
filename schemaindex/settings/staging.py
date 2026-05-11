import logging
import os

from .production import *

logger = logging.getLogger("schemaindex")

ALLOWED_HOSTS = ['schemaindex-stg-run-799626592344.us-central1.run.app']
PERMANENT_URL_HOST = ALLOWED_HOSTS[0]
SITE_URL = 'https://schemaindex-stg-run-799626592344.us-central1.run.app'
CSRF_TRUSTED_ORIGINS = ['https://' + url for url in ALLOWED_HOSTS]
GS_BUCKET_NAME = 'schemaindex-stg-storage'

# Turn observability on in staging so we can verify Valkey behavior end-to-end
CONTENT_CACHE_OBSERVABILITY = True
RATE_LIMIT_OBSERVABILITY = True

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# The deploy workflow writes the PEM (from a stg env secret) to disk and points us at it via VALKEY_SERVER_CA
VALKEY_SERVER_CA = env.str("VALKEY_SERVER_CA", default="")
if VALKEY_URL.startswith("rediss://") and VALKEY_SERVER_CA:
    _ca_path = VALKEY_SERVER_CA
    if not os.path.isabs(_ca_path):
        _ca_path = str(BASE_DIR / _ca_path)
    _pool_kwargs = CACHES["default"]["OPTIONS"].setdefault("CONNECTION_POOL_KWARGS", {})
    _pool_kwargs["ssl_ca_certs"] = _ca_path
    _pool_kwargs["ssl_cert_reqs"] = "required"
    logger.info(
        "Valkey TLS CA configured for staging (path=%s, exists=%s)",
        _ca_path, os.path.exists(_ca_path),
    )
else:
    logger.info(
        "Valkey TLS CA not configured (tls=%s, ca_env_set=%s)",
        VALKEY_URL.startswith("rediss://"), bool(VALKEY_SERVER_CA),
    )

# Update the STORAGES configuration with the staging bucket
for key in STORAGES:
    STORAGES[key]["OPTIONS"]["bucket_name"] = GS_BUCKET_NAME

# Buckets URLs for static and media files
STATIC_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/site-assets/'
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/schemas/'
