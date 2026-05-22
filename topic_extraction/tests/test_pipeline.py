import numpy as np
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
        mock_extractor = MagicMock(spec=['extract'])
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
            mock_instance = MagicMock(spec=['extract'])
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
        mock_llm = MagicMock(spec=['extract'])
        mock_llm.extract.side_effect = ValueError('LLM parse error')
        mock_get_extractor.return_value = mock_llm
        mock_normalize.return_value = []

        with patch('topic_extraction.extractors.embedding.EmbeddingExtractor') as mock_emb_cls:
            mock_emb = MagicMock()
            mock_emb.extract_with_embedding.return_value = ([], None)
            mock_emb_cls.return_value = mock_emb
            payload = pipeline.extract('art-y', 'opengov', 'text', [])

        mock_emb.extract_with_embedding.assert_called_once()
        self.assertEqual(payload['backend'], 'embedding')





class PipelineRunTest(TestCase):
    def setUp(self):
        Topic.objects.create(slug='education_policy', label_en='Education Policy', labels={})

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline._get_extractor')
    @patch('topic_extraction.pipeline.detect_language')
    def test_creates_article_topic_record(self, mock_detect, mock_get_extractor, mock_normalize):
        mock_detect.return_value = ('el', 'detected')
        mock_extractor = MagicMock(spec=['extract'])
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
        mock_llm = MagicMock(spec=['extract'])
        mock_llm.extract.side_effect = ValueError('LLM parse error')
        mock_get_extractor.return_value = mock_llm
        mock_normalize.return_value = []

        with patch('topic_extraction.extractors.embedding.EmbeddingExtractor') as mock_emb_cls:
            mock_emb = MagicMock()
            mock_emb.extract_with_embedding.return_value = (
                [TopicResult(label='Education Policy', score=0.6)],
                None,
            )
            mock_emb_cls.return_value = mock_emb

            record = pipeline.run('art-2', 'ypepth', 'Article text', [])

        mock_emb.extract_with_embedding.assert_called_once()
        self.assertIsInstance(record, ArticleTopic)
        self.assertEqual(record.backend, 'embedding')

    @patch('topic_extraction.pipeline.normalize')
    @patch('topic_extraction.pipeline._get_extractor')
    @patch('topic_extraction.pipeline.detect_language')
    def test_stores_backend_used(self, mock_detect, mock_get_extractor, mock_normalize):
        mock_detect.return_value = ('en', 'default')
        mock_extractor = MagicMock(spec=['extract'])
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
        mock_extractor.return_value = MagicMock(spec=['extract'])
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
        mock_extractor.return_value = MagicMock(spec=['extract'])
        mock_extractor.return_value.extract.return_value = []
        record = pipeline.run(
            article_id='a2', platform='p1',
            article='Hello world this is English text long enough for detection.',
            comments=[],
        )
        self.assertEqual(record.taxonomy_version, taxonomy_data.TAXONOMY_VERSION)

    @patch('topic_extraction.pipeline._get_extractor')
    def test_language_source_default_recorded_when_short(self, mock_extractor):
        mock_extractor.return_value = MagicMock(spec=['extract'])
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


class PipelineArticleEmbeddingIntegrationTest(TestCase):
    """Verifies the Phase-4 integration: pipeline.run writes both ArticleTopic
    AND ArticleEmbedding atomically when the extractor produces an embedding."""

    def setUp(self):
        from django.core.management import call_command
        call_command('seed_taxonomy')

    @patch('topic_extraction.pipeline.detect_language')
    @patch('topic_extraction.pipeline._get_extractor')
    def test_writes_both_articletopic_and_articleembedding(self, mock_get_extractor, mock_detect):
        from topic_extraction.models import ArticleTopic, ArticleEmbedding
        from topic_extraction.extractors.base import TopicResult

        mock_detect.return_value = ('en', 'detected')
        mock_extractor = MagicMock()
        mock_extractor.extract_with_embedding.return_value = (
            [TopicResult(label='education', score=2.0, raw_score=0.85)],
            np.array([0.1, 0.2, 0.3]),
        )
        mock_get_extractor.return_value = mock_extractor

        record = pipeline.run(
            article_id='art-1',
            platform='opengov',
            article='education policy text',
            comments=[],
        )

        # ArticleTopic was written.
        self.assertEqual(ArticleTopic.objects.filter(article_id='art-1').count(), 1)
        # ArticleEmbedding was written.
        emb = ArticleEmbedding.objects.get(platform='opengov', article_id='art-1')
        self.assertEqual(emb.vector, [0.1, 0.2, 0.3])
        self.assertEqual(emb.language, 'en')

    @patch('topic_extraction.pipeline.detect_language')
    @patch('topic_extraction.pipeline._get_extractor')
    def test_llm_backend_writes_only_articletopic_no_embedding(self, mock_get_extractor, mock_detect):
        from topic_extraction.models import ArticleTopic, ArticleEmbedding
        from topic_extraction.extractors.base import TopicResult

        mock_detect.return_value = ('en', 'detected')
        # LLM extractor mock — no extract_with_embedding attribute.
        mock_extractor = MagicMock(spec=['extract'])  # spec restricts attributes
        mock_extractor.extract.return_value = [
            TopicResult(label='education', score=0.85)
        ]
        mock_get_extractor.return_value = mock_extractor

        pipeline.run(
            article_id='art-2',
            platform='opengov',
            article='education policy text',
            comments=[],
            backend='llm',
        )

        # ArticleTopic written; ArticleEmbedding NOT written.
        self.assertEqual(ArticleTopic.objects.filter(article_id='art-2').count(), 1)
        self.assertEqual(ArticleEmbedding.objects.filter(article_id='art-2').count(), 0)

    @patch('topic_extraction.pipeline.detect_language')
    @patch('topic_extraction.pipeline._get_extractor')
    def test_transactional_rollback_on_articletopic_failure(self, mock_get_extractor, mock_detect):
        """If ArticleTopic.create fails (e.g., DB constraint), neither row
        should persist."""
        from topic_extraction.models import ArticleTopic, ArticleEmbedding
        from topic_extraction.extractors.base import TopicResult
        from unittest.mock import patch as up

        mock_detect.return_value = ('en', 'detected')
        mock_extractor = MagicMock()
        mock_extractor.extract_with_embedding.return_value = (
            [TopicResult(label='education', score=2.0, raw_score=0.85)],
            np.array([0.1, 0.2, 0.3]),
        )
        mock_get_extractor.return_value = mock_extractor

        with up.object(ArticleTopic.objects, 'create', side_effect=Exception('forced')):
            with self.assertRaises(Exception):
                pipeline.run(
                    article_id='art-3',
                    platform='opengov',
                    article='text',
                    comments=[],
                )

        # Neither row persists (transaction rolled back).
        self.assertEqual(ArticleTopic.objects.filter(article_id='art-3').count(), 0)
        self.assertEqual(ArticleEmbedding.objects.filter(article_id='art-3').count(), 0)

    @patch('topic_extraction.pipeline.detect_language')
    @patch('topic_extraction.pipeline._get_extractor')
    def test_reextraction_appends_articletopic_upserts_articleembedding(self, mock_get_extractor, mock_detect):
        from topic_extraction.models import ArticleTopic, ArticleEmbedding
        from topic_extraction.extractors.base import TopicResult

        mock_detect.return_value = ('en', 'detected')
        mock_extractor = MagicMock()
        mock_extractor.extract_with_embedding.return_value = (
            [TopicResult(label='education', score=2.0, raw_score=0.85)],
            np.array([0.1, 0.2, 0.3]),
        )
        mock_get_extractor.return_value = mock_extractor

        # First extraction.
        pipeline.run(article_id='art-4', platform='opengov', article='v1', comments=[])
        first_ae = ArticleEmbedding.objects.get(platform='opengov', article_id='art-4')
        first_ae_id = first_ae.id

        # Second extraction with different vector.
        mock_extractor.extract_with_embedding.return_value = (
            [TopicResult(label='education', score=2.5, raw_score=0.90)],
            np.array([0.5, 0.6, 0.7]),
        )
        pipeline.run(article_id='art-4', platform='opengov', article='v2', comments=[])

        # ArticleTopic: 2 rows (append-only).
        self.assertEqual(ArticleTopic.objects.filter(article_id='art-4').count(), 2)
        # ArticleEmbedding: 1 row, UPSERTed.
        self.assertEqual(ArticleEmbedding.objects.filter(article_id='art-4').count(), 1)
        ae = ArticleEmbedding.objects.get(platform='opengov', article_id='art-4')
        self.assertEqual(ae.id, first_ae_id)  # Same PK.
        self.assertEqual(ae.vector, [0.5, 0.6, 0.7])  # New vector.

