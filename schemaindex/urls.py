"""
URL configuration for schemaindex project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from oauth2_provider import views as oauth2_views
from oauth2_provider.urls import metadata_urlpatterns

# Rather than mounting all of oauth2_provider.urls,
# here we extract the subset we actually use.
oauth2_mcp_urlpatterns = [
    path("authorize/", oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path("token/", oauth2_views.TokenView.as_view(), name="token"),
    path("revoke_token/", oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
    path(
        "register/",
        oauth2_views.DynamicClientRegistrationView.as_view(),
        name="dcr-register",
    ),
    path(
        "register/<str:client_id>/",
        oauth2_views.DynamicClientRegistrationManagementView.as_view(),
        name="dcr-register-management",
    ),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("account/", include("allauth.urls")),
    path(
        "",
        include((metadata_urlpatterns, "oauth2_provider"), namespace="oauth2_metadata"),
    ),
    # Note: django-oauth-toolkit uses the prefix "o/" in their examples,
    # but we already use that for permanent org URLs.
    path("oauth/", include((oauth2_mcp_urlpatterns, "oauth2_provider"))),
    path("", include("core.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
