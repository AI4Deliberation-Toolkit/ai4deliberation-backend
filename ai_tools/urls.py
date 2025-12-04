from django.urls import path
from .views import CategorizeTextView

urlpatterns = [
    path('categorize-text/', CategorizeTextView.as_view(), name='categorize-text'),
]