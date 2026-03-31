import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from topic_extraction.models import ArticleTopic, Topic


class ExtractConversationViewTest(TestCase):
    def setUp(self):
        Topic.objects.create(slug='education_policy', label_en='Education Policy', labels={})

    @patch('topic_extraction.views.pipeline')
    def test_post_returns_201_with_topics(self, mock_pipeline):
        mock_record = MagicMock(spec=ArticleTopic)
        mock_record.id = '00000000-0000-0000-0000-000000000001'
        mock_record.language = 'el'
        mock_record.raw_topics = [{'label': 'Εκπαιδευτική Πολιτική', 'score': 0.9}]
        mock_record.normalized = [{'topic_id': 'education_policy', 'score': 0.9}]
        mock_record.backend = 'embedding'
        mock_pipeline.run.return_value = mock_record

        payload = {
            'article_id': 'art-1',
            'platform': 'ypepth',
            'article': 'Article about teacher hiring.',
            'comments': ['comment 1', 'comment 2'],
        }
        response = self.client.post(
            '/api/topics/extract-conversation',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['language'], 'el')
        self.assertEqual(len(data['raw_topics']), 1)

    @patch('topic_extraction.views.pipeline')
    def test_post_missing_required_field_returns_400(self, mock_pipeline):
        response = self.client.post(
            '/api/topics/extract-conversation',
            data=json.dumps({'article_id': 'art-1'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class ArticleTopicViewTest(TestCase):
    def setUp(self):
        ArticleTopic.objects.create(
            article_id='art-42',
            platform='ypepth',
            language='el',
            raw_topics=[{'label': 'test', 'score': 0.8}],
            normalized=[{'topic_id': 'education_policy', 'score': 0.8}],
            backend='embedding',
        )

    def test_get_returns_latest_record(self):
        response = self.client.get('/api/topics/article/art-42')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['article_id'], 'art-42')
        self.assertEqual(data['language'], 'el')

    def test_get_nonexistent_returns_404(self):
        response = self.client.get('/api/topics/article/does-not-exist')
        self.assertEqual(response.status_code, 404)
