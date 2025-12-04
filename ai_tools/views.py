from django.conf import settings
from django.shortcuts import render
from rest_framework import views, status
from rest_framework.response import Response

from ai_tools.utils import categorization


class CategorizeTextView(views.APIView):
    def post(self, request, format=None):
        predictions = categorization([request.data['text']])
        return Response({'topics': predictions}, status=status.HTTP_200_OK)
