from unittest.mock import patch, MagicMock
from django.test import TestCase
from topic_extraction import pipeline
from topic_extraction.extractors.base import TopicResult
from topic_extraction.normalizer import NormalizedTopic
from topic_extraction.models import ArticleTopic, Topic


class PipelineRunTest(TestCase):
    def setUp(self):
        Topic.objects.create(slug='education_policy', label_en='Education Policy', labels={})

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline._get_extractor')
    @patch('topic_extraction.pipeline.detect_language')
    def test_creates_article_topic_record(self, mock_detect, mock_get_extractor, mock_normalize):
        mock_detect.return_value = 'el'
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = [TopicResult(label='Εκπαιδευτική Πολιτική', score=0.9)]
        mock_get_extractor.return_value = mock_extractor
        mock_normalize.return_value = [NormalizedTopic(topic_id='education_policy', score=0.9)]

        record = pipeline.run('art-1', 'ypepth', 'Article about teachers', ['comment 1'])

        self.assertIsInstance(record, ArticleTopic)
        self.assertEqual(record.article_id, 'art-1')
        self.assertEqual(record.platform, 'ypepth')
        self.assertEqual(record.language, 'el')
        self.assertEqual(record.raw_topics[0]['label'], 'Εκπαιδευτική Πολιτική')
        self.assertEqual(record.normalized[0]['topic_id'], 'education_policy')

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline._get_extractor')
    @patch('topic_extraction.pipeline.detect_language')
    def test_falls_back_to_embedding_extractor_on_llm_failure(
        self, mock_detect, mock_get_extractor, mock_normalize
    ):
        mock_detect.return_value = 'el'
        mock_llm = MagicMock()
        mock_llm.extract.side_effect = ValueError('LLM parse error')
        mock_get_extractor.return_value = mock_llm
        mock_normalize.return_value = []

        with patch('topic_extraction.extractors.embedding.EmbeddingExtractor') as mock_emb_cls:
            mock_emb = MagicMock()
            mock_emb.extract.return_value = [TopicResult(label='Education Policy', score=0.6)]
            mock_emb_cls.return_value = mock_emb

            record = pipeline.run('art-2', 'ypepth', 'Article text', [])

        mock_emb.extract.assert_called_once()
        self.assertIsInstance(record, ArticleTopic)
        self.assertEqual(record.backend, 'embedding')

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline._get_extractor')
    @patch('topic_extraction.pipeline.detect_language')
    def test_stores_backend_used(self, mock_detect, mock_get_extractor, mock_normalize):
        mock_detect.return_value = 'en'
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = []
        mock_get_extractor.return_value = mock_extractor
        mock_normalize.return_value = []

        with self.settings(EXTRACTION_BACKEND='embedding'):
            record = pipeline.run('art-3', 'ypepth', 'text', [])

        self.assertEqual(record.backend, 'embedding')
