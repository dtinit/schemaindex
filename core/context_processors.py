from django.conf import settings


# Please do not export *sensitive* settings!
def export_settings(request):
    return {
        "settings": {
            "PLAUSIBLE_DOMAIN": settings.PLAUSIBLE_DOMAIN,
            "ENABLE_DTI_PAGES": settings.ENABLE_DTI_PAGES,
        }
    }
