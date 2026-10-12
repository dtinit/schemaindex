from django.conf import settings


# Please do not export *sensitive* settings!
def export_settings(request):
    return {
        "settings": {
            "SITE_NAME": settings.SITE_NAME,
            "SITE_URL": settings.SITE_URL,
            "PLAUSIBLE_DOMAIN": settings.PLAUSIBLE_DOMAIN,
            "ENABLE_DTI_PAGES": settings.ENABLE_DTI_PAGES,
            "ENABLE_ACCOUNTS": settings.ENABLE_ACCOUNTS,
        }
    }
