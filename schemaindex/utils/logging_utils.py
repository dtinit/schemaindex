import os
import logging


def get_cloud_logging_handler():
    """
    Creates basic Cloud Logging handler.

    Returns:
        logging.Handler: CloudLoggingHandler (if enabled) or NullHandler

    Environment Variables:
        USE_GCLOUD_LOGGING: Set to "1" to enable Cloud Logging (default: "0")

    Notes:
        Import Google Cloud packages only when enabled
    """
    if os.environ.get('USE_GCLOUD_LOGGING', '0') != '1':
        return logging.NullHandler()

    try:
        
        from google.cloud.logging import Client as CloudLoggingClient
        from google.cloud.logging.handlers import CloudLoggingHandler

        client = CloudLoggingClient()

        handler = CloudLoggingHandler(
            client,
            name="schemaindex"
        )

        return handler

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Failed to initialize Cloud Logging: {e}. "
            "Falling back to NullHandler. Logs will not appear in Cloud Logging."
        )
        return logging.NullHandler()
