from django.conf import settings
from django.urls import path
from .views import CategorizeTextView

urlpatterns = []

if getattr(settings, 'ENABLE_LEGACY_CATEGORIZE', True):
    urlpatterns.append(
        path('categorize-text/', CategorizeTextView.as_view(), name='categorize-text'),
    )
