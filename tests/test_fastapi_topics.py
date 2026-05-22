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


class FastAPIArticleSimilarityTest(TransactionTestCase):
    def setUp(self):
        call_command('seed_taxonomy')
        from topic_extraction.models import ArticleEmbedding
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='src', language='en',
            vector=[1.0, 0.0], embedding_model_name='mpnet',
        )
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='c1', language='en',
            vector=[0.9, 0.1], embedding_model_name='mpnet',
        )
        self.client = TestClient(app)

    def test_happy_path(self):
        r = self.client.get('/articles/opengov/src/similar?k=10')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['platform'], 'opengov')
        self.assertEqual(body['article_id'], 'src')
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['results'][0]['article_id'], 'c1')

    def test_missing_source_returns_404(self):
        r = self.client.get('/articles/opengov/does-not-exist/similar')
        self.assertEqual(r.status_code, 404)

    def test_k_out_of_range_returns_400(self):
        r = self.client.get('/articles/opengov/src/similar?k=0')
        self.assertEqual(r.status_code, 400)

    def test_unknown_topic_slug_returns_422(self):
        # FastAPI convention: bad slug → 422 (Pydantic validation code).
        r = self.client.get('/articles/opengov/src/similar?topic_slug=not-a-real-slug')
        self.assertEqual(r.status_code, 422)

    def test_recommend_endpoint_is_deprecated(self):
        # The old /recommend endpoint should no longer be active — commented
        # out in this task. Hitting it returns 404 (FastAPI route not found).
        r = self.client.post('/recommend', json={'current_text': 'x', 'all_texts': ['y']})
        self.assertEqual(r.status_code, 404)
