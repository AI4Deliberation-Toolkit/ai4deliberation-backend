from unittest.mock import patch, MagicMock
from django.core.management import call_command
from django.test import TestCase
from topic_extraction import pipeline, taxonomy_data
from topic_extraction.extractors.base import TopicResult
from topic_extraction.normalizer import NormalizedTopic
from topic_extraction.models import ArticleTopic, Topic
from topic_extraction.taxonomy_data import TAXONOMY_VERSION


class PipelineExtractTest(TestCase):
    def setUp(self):
        Topic.objects.create(slug='education_policy', label_en='Education Policy', labels={})

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline._get_extractor')
    @patch('topic_extraction.pipeline.detect_language')
    def test_returns_payload_without_persisting(
        self, mock_detect, mock_get_extractor, mock_normalize
    ):
        mock_detect.return_value = ('el', 'detected')
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = [TopicResult(label='Foo', score=0.9)]
        mock_get_extractor.return_value = mock_extractor
        mock_normalize.return_value = [NormalizedTopic(topic_id='education_policy', score=0.9)]

        before_count = ArticleTopic.objects.count()
        payload = pipeline.extract('art-x', 'opengov', 'text', [])
        after_count = ArticleTopic.objects.count()

        self.assertEqual(before_count, after_count)
        self.assertEqual(payload['article_id'], 'art-x')
        self.assertEqual(payload['platform'], 'opengov')
        self.assertEqual(payload['language'], 'el')
        self.assertEqual(payload['raw_topics'][0]['label'], 'Foo')
        self.assertEqual(payload['normalized'][0]['topic_id'], 'education_policy')
        self.assertEqual(payload['taxonomy_version'], TAXONOMY_VERSION)

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline.detect_language')
    def test_backend_override_selects_similarity_extractor(self, mock_detect, mock_normalize):
        # Verifies pipeline.extract(backend='embedding_similarity') routes to
        # EmbeddingSimilarityExtractor and records the backend in the payload.
        mock_detect.return_value = ('el', 'detected')
        mock_normalize.return_value = []
        with patch('topic_extraction.extractors.embedding.EmbeddingSimilarityExtractor') as mock_cls:
            mock_instance = MagicMock()
            mock_instance.extract.return_value = []
            mock_cls.return_value = mock_instance

            payload = pipeline.extract(
                'art-z', 'opengov', 'text', [],
                backend='embedding_similarity',
            )

        mock_cls.assert_called_once()
        mock_instance.extract.assert_called_once()
        self.assertEqual(payload['backend'], 'embedding_similarity')

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline._get_extractor')
    @patch('topic_extraction.pipeline.detect_language')
    def test_extract_fallback_to_embedding_on_failure(
        self, mock_detect, mock_get_extractor, mock_normalize
    ):
        mock_detect.return_value = ('el', 'detected')
        mock_llm = MagicMock()
        mock_llm.extract.side_effect = ValueError('LLM parse error')
        mock_get_extractor.return_value = mock_llm
        mock_normalize.return_value = []

        with patch('topic_extraction.extractors.embedding.EmbeddingExtractor') as mock_emb_cls:
            mock_emb = MagicMock()
            mock_emb.extract.return_value = []
            mock_emb_cls.return_value = mock_emb
            payload = pipeline.extract('art-y', 'opengov', 'text', [])

        self.assertEqual(payload['backend'], 'embedding')





class PipelineRunTest(TestCase):
    def setUp(self):
        Topic.objects.create(slug='education_policy', label_en='Education Policy', labels={})

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline._get_extractor')
    @patch('topic_extraction.pipeline.detect_language')
    def test_creates_article_topic_record(self, mock_detect, mock_get_extractor, mock_normalize):
        mock_detect.return_value = ('el', 'detected')
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
        mock_detect.return_value = ('el', 'detected')
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
        mock_detect.return_value = ('en', 'default')
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = []
        mock_get_extractor.return_value = mock_extractor
        mock_normalize.return_value = []

        with self.settings(EXTRACTION_BACKEND='embedding'):
            record = pipeline.run('art-3', 'ypepth', 'text', [])

        self.assertEqual(record.backend, 'embedding')


class PipelineLanguageOverrideTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    @patch('topic_extraction.pipeline._get_extractor')
    def test_explicit_language_overrides_detection(self, mock_extractor):
        mock_extractor.return_value.extract.return_value = []
        record = pipeline.run(
            article_id='a1', platform='p1',
            article='Αυτό είναι ελληνικά.',  # Greek
            comments=[],
            explicit_language='de',  # but caller forces German
        )
        self.assertEqual(record.language, 'de')

    @patch('topic_extraction.pipeline._get_extractor')
    def test_taxonomy_version_stored(self, mock_extractor):
        mock_extractor.return_value.extract.return_value = []
        record = pipeline.run(
            article_id='a2', platform='p1',
            article='Hello world this is English text long enough for detection.',
            comments=[],
        )
        self.assertEqual(record.taxonomy_version, taxonomy_data.TAXONOMY_VERSION)

    @patch('topic_extraction.pipeline._get_extractor')
    def test_language_source_default_recorded_when_short(self, mock_extractor):
        mock_extractor.return_value.extract.return_value = []
        record = pipeline.run(
            article_id='a3', platform='p1',
            article='hi', comments=[],
        )
        self.assertEqual(record.language_source, 'default')

    def test_unsupported_explicit_language_raises(self):
        # Locks the docstring contract: pipeline.run propagates ValueError from
        # detect_language so the view layer (Task 15) can map to HTTP 400.
        with self.assertRaises(ValueError):
            pipeline.run(
                article_id='a4', platform='p1',
                article='text', comments=[],
                explicit_language='ko',  # not in TOPIC_LANGUAGES
            )
