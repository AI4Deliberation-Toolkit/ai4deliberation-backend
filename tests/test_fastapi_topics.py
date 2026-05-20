import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai4deliberation_backend.settings.settings')
import django
django.setup()

from unittest.mock import patch, MagicMock
from django.core.management import call_command
from django.test import TransactionTestCase
from fastapi.testclient import TestClient
from fastapi_app.main import app


class FastAPITopicsParityTest(TransactionTestCase):
    def setUp(self):
        call_command('seed_taxonomy')
        self.client = TestClient(app)

    @patch('fastapi_app.main.topic_pipeline')
    def test_extract_default_excludes_raw_topics(self, mock_pipeline):
        m = MagicMock()
        m.id = 'id'
        m.article_id = 'a1'
        m.platform = 'p'
        m.language = 'el'
        m.language_source = 'explicit'
        m.normalized = [{'topic_id': 'education_policy', 'score': 0.9}]
        m.raw_topics = []
        m.backend = 'embedding'
        m.computed_at = MagicMock(isoformat=lambda: '2026-05-15T10:00:00Z')
        m.taxonomy_version = '2026-05-15-1'
        mock_pipeline.run.return_value = m
        r = self.client.post('/topics/extract-conversation', json={
            'article_id': 'a1', 'platform': 'p', 'article': 'x', 'comments': []
        })
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('raw_topics', r.json())

    def test_topics_listing_endpoint(self):
        r = self.client.get('/topics?language=en')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn('parents', body)
        self.assertIn('leaves', body)
        self.assertIn('hierarchy', body)
        self.assertIn('version', body)
