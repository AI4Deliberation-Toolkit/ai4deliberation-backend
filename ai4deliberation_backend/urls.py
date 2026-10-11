"""
URL configuration for ai4deliberation_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path

from gateway.api import api


def build_urlpatterns():
    """Built by a function so tests can rebuild the URLconf after changing settings."""
    patterns = [
        path('admin/', admin.site.urls),
        path('api/v1/', api.urls),
    ]
    # Admin static files under uvicorn in local dev; empty unless DEBUG.
    patterns += staticfiles_urlpatterns()
    return patterns


urlpatterns = build_urlpatterns()
