import json
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from django.test import TestCase
from topic_extraction.models import ArticleTopic, Topic


class ExtractConversationViewTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def _mock_record(self, **overrides):
        defaults = {
            'id': '00000000-0000-0000-0000-000000000001',
            'article_id': 'art-1',
            'platform': 'ypepth',
            'language': 'el',
            'language_source': 'explicit',
            'raw_topics': [{'label': 'Εκπαιδευτική Πολιτική', 'score': 0.9}],
            'normalized': [{'topic_id': 'education_policy', 'score': 0.9}],
            'backend': 'embedding',
            'taxonomy_version': '2026-05-15-1',
            'computed_at': MagicMock(isoformat=lambda: '2026-05-15T10:00:00Z'),
        }
        defaults.update(overrides)
        m = MagicMock(spec=ArticleTopic)
        for k, v in defaults.items():
            setattr(m, k, v)
        return m

    @patch('topic_extraction.views.pipeline')
    def test_default_response_excludes_raw_topics(self, mock_pipeline):
        mock_pipeline.run.return_value = self._mock_record()
        payload = {'article_id': 'art-1', 'platform': 'ypepth', 'article': 'Some article text long enough.'}
        response = self.client.post(
            '/api/topics/extract-conversation',
            data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertNotIn('raw_topics', data)
        self.assertIn('taxonomy_version', data)
        self.assertIn('language_source', data)

    @patch('topic_extraction.views.pipeline')
    def test_include_raw_flag_returns_raw_topics(self, mock_pipeline):
        mock_pipeline.run.return_value = self._mock_record()
        payload = {'article_id': 'art-1', 'platform': 'ypepth', 'article': 'text'}
        response = self.client.post(
            '/api/topics/extract-conversation?include_raw=true',
            data=json.dumps(payload), content_type='application/json',
        )
        self.assertIn('raw_topics', response.json())

    @patch('topic_extraction.views.pipeline')
    def test_include_labels_flag_adds_labels(self, mock_pipeline):
        mock_pipeline.run.return_value = self._mock_record()
        payload = {'article_id': 'art-1', 'platform': 'ypepth', 'article': 'text'}
        response = self.client.post(
            '/api/topics/extract-conversation?include_labels=true',
            data=json.dumps(payload), content_type='application/json',
        )
        data = response.json()
        # education_policy must exist; ensure label and parent fields are present
        first = data['normalized'][0]
        self.assertIn('label', first)
        self.assertIn('parent', first)

    @patch('topic_extraction.views.pipeline')
    def test_explicit_language_passed_through(self, mock_pipeline):
        mock_pipeline.run.return_value = self._mock_record()
        payload = {'article_id': 'art-1', 'platform': 'ypepth', 'article': 'text', 'language': 'el'}
        self.client.post(
            '/api/topics/extract-conversation',
            data=json.dumps(payload), content_type='application/json',
        )
        kwargs = mock_pipeline.run.call_args.kwargs
        self.assertEqual(kwargs.get('explicit_language'), 'el')

    @patch('topic_extraction.views.pipeline')
    def test_unsupported_explicit_language_returns_400(self, mock_pipeline):
        # Make pipeline.run raise ValueError as language.py would
        mock_pipeline.run.side_effect = ValueError('Unsupported language: fr')
        payload = {'article_id': 'art-1', 'platform': 'ypepth', 'article': 'text', 'language': 'fr'}
        response = self.client.post(
            '/api/topics/extract-conversation',
            data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    @patch('topic_extraction.views.pipeline')
    def test_missing_required_field_returns_400(self, mock_pipeline):
        response = self.client.post(
            '/api/topics/extract-conversation',
            data=json.dumps({'article_id': 'a'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class ArticleTopicViewTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')
        # Older row
        ArticleTopic.objects.create(
            article_id='art-42', platform='ypepth', language='el',
            language_source='detected',
            raw_topics=[{'label': 'old', 'score': 0.5}],
            normalized=[{'topic_id': 'education_policy', 'score': 0.5}],
            backend='embedding', taxonomy_version='2026-05-14-1',
        )
        # Newer row
        ArticleTopic.objects.create(
            article_id='art-42', platform='ypepth', language='el',
            language_source='detected',
            raw_topics=[{'label': 'new', 'score': 0.9}],
            normalized=[{'topic_id': 'education_policy', 'score': 0.9}],
            backend='embedding', taxonomy_version='2026-05-15-1',
        )

    def test_get_returns_latest_record(self):
        response = self.client.get('/api/topics/article/art-42')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Latest row should have score 0.9 in normalized
        self.assertEqual(data['normalized'][0]['score'], 0.9)
        self.assertEqual(data['taxonomy_version'], '2026-05-15-1')

    def test_default_response_omits_raw_topics(self):
        response = self.client.get('/api/topics/article/art-42')
        self.assertNotIn('raw_topics', response.json())

    def test_include_raw_returns_raw_topics(self):
        response = self.client.get('/api/topics/article/art-42?include_raw=true')
        self.assertIn('raw_topics', response.json())

    def test_include_labels_adds_label_and_parent(self):
        response = self.client.get('/api/topics/article/art-42?include_labels=true')
        first = response.json()['normalized'][0]
        self.assertIn('label', first)
        self.assertIn('parent', first)

    def test_deactivated_slug_gets_null_label(self):
        # Deactivate the leaf and re-query with labels
        leaf = Topic.objects.get(slug='education_policy')
        leaf.is_active = False
        leaf.save()
        response = self.client.get('/api/topics/article/art-42?include_labels=true')
        first = response.json()['normalized'][0]
        self.assertIsNone(first['label'])
        self.assertIsNone(first['parent'])

    def test_response_includes_id(self):
        response = self.client.get('/api/topics/article/art-42')
        self.assertIn('id', response.json())

    def test_nonexistent_returns_404(self):
        response = self.client.get('/api/topics/article/does-not-exist')
        self.assertEqual(response.status_code, 404)


class TopicsListingViewTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_get_topics_returns_parents_leaves_hierarchy(self):
        response = self.client.get('/api/topics?language=en')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('parents', data)
        self.assertIn('leaves', data)
        self.assertIn('hierarchy', data)
        self.assertIn('version', data)
        self.assertIn('language', data)

    def test_get_topics_returns_etag(self):
        response = self.client.get('/api/topics?language=en')
        self.assertIn('ETag', response.headers)

    def test_if_none_match_returns_304(self):
        first = self.client.get('/api/topics?language=en')
        etag = first.headers['ETag']
        second = self.client.get('/api/topics?language=en', HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(second.status_code, 304)

    def test_unsupported_language_returns_400(self):
        response = self.client.get('/api/topics?language=fr')
        self.assertEqual(response.status_code, 400)

    def test_omitted_language_uses_default(self):
        response = self.client.get('/api/topics')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['language'], 'en')


class ArticleSimilarityViewTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')
        # Source + 2 candidates in opengov/en bucket.
        from topic_extraction.models import ArticleEmbedding
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='src', language='en',
            vector=[1.0, 0.0], embedding_model_name='mpnet',
        )
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='c1', language='en',
            vector=[0.9, 0.1], embedding_model_name='mpnet',
        )
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='c2', language='en',
            vector=[0.5, 0.5], embedding_model_name='mpnet',
        )

    def test_happy_path_returns_ranked_results(self):
        response = self.client.get('/api/articles/opengov/src/similar?k=10')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['platform'], 'opengov')
        self.assertEqual(data['article_id'], 'src')
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['results']), 2)
        # Closer match first.
        self.assertEqual(data['results'][0]['article_id'], 'c1')
        # Required fields per result.
        first = data['results'][0]
        self.assertIn('platform', first)
        self.assertIn('article_id', first)
        self.assertIn('language', first)
        self.assertIn('raw_score', first)
        self.assertIn('z_score', first)

    def test_missing_source_returns_404(self):
        response = self.client.get('/api/articles/opengov/does-not-exist/similar')
        self.assertEqual(response.status_code, 404)

    def test_k_zero_returns_400(self):
        response = self.client.get('/api/articles/opengov/src/similar?k=0')
        self.assertEqual(response.status_code, 400)

    def test_k_negative_returns_400(self):
        response = self.client.get('/api/articles/opengov/src/similar?k=-1')
        self.assertEqual(response.status_code, 400)

    def test_k_too_large_returns_400(self):
        response = self.client.get('/api/articles/opengov/src/similar?k=101')
        self.assertEqual(response.status_code, 400)

    def test_k_non_integer_returns_400(self):
        response = self.client.get('/api/articles/opengov/src/similar?k=abc')
        self.assertEqual(response.status_code, 400)

    def test_unknown_topic_slug_returns_400(self):
        response = self.client.get('/api/articles/opengov/src/similar?topic_slug=not-a-real-slug')
        self.assertEqual(response.status_code, 400)

    def test_default_k_is_10(self):
        # No k param — should still return what's available (only 2 candidates here).
        response = self.client.get('/api/articles/opengov/src/similar')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 2)

    def test_url_does_not_shadow_topics_article(self):
        # Sanity: /api/topics/article/<id> still works (Phase 1 endpoint).
        # This test catches any URL pattern collision.
        from topic_extraction.models import ArticleTopic
        ArticleTopic.objects.create(
            article_id='top-1', platform='opengov', language='el',
            language_source='detected',
            raw_topics=[{'label': 'x', 'score': 0.5}],
            normalized=[{'topic_id': 'education_policy', 'score': 0.5}],
            backend='embedding', taxonomy_version='test',
        )
        response = self.client.get('/api/topics/article/top-1')
        self.assertEqual(response.status_code, 200)
