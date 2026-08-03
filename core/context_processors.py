from django.conf import settings


def export_feature_flags(request):
    return {
        "feature_flags": {
            "mcp_server": settings.ENABLE_MCP_SERVER,
        }
    }
