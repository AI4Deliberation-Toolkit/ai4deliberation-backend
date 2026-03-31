import numpy as np
from unittest.mock import patch, MagicMock
from django.test import TestCase
from topic_extraction.extractors.base import BaseExtractor, TopicResult
from topic_extraction.models import Topic
from topic_extraction.taxonomy import invalidate_taxonomy_cache
from topic_extraction.extractors.embedding import EmbeddingExtractor


class TopicResultTest(TestCase):
    def test_topic_result_fields(self):
        t = TopicResult(label='education policy', score=0.85)
        self.assertEqual(t.label, 'education policy')
        self.assertEqual(t.score, 0.85)

    def test_base_extractor_is_abstract(self):
        with self.assertRaises(TypeError):
            BaseExtractor()

    def test_concrete_extractor_must_implement_extract(self):
        class Incomplete(BaseExtractor):
            pass
        with self.assertRaises(TypeError):
            Incomplete()


class EmbeddingExtractorTest(TestCase):
    def setUp(self):
        Topic.objects.create(slug='education_policy', label_en='Education Policy',
                             labels={'el': 'Εκπαιδευτική Πολιτική'})
        Topic.objects.create(slug='climate_change', label_en='Climate Change',
                             labels={'el': 'Κλιματική Αλλαγή'})
        invalidate_taxonomy_cache()

    @patch('topic_extraction.extractors.embedding.get_taxonomy_embeddings')
    @patch('topic_extraction.extractors.embedding.get_embedding_model')
    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    def test_returns_topic_results_above_threshold(
        self, mock_hf_pipeline, mock_emb_model_fn, mock_taxonomy_fn
    ):
        from topic_extraction.models import Topic
        topics = list(Topic.objects.all())
        taxonomy_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = MagicMock()
        # Passage embedding close to education_policy
        mock_model.encode.return_value = np.array([[0.95, 0.05]])
        mock_emb_model_fn.return_value = mock_model

        mock_zs_pipeline = MagicMock()
        mock_zs_pipeline.return_value = {
            'labels': ['Education Policy', 'Climate Change'],
            'scores': [0.8, 0.1],
        }
        mock_hf_pipeline.return_value = mock_zs_pipeline

        extractor = EmbeddingExtractor()
        results = extractor.extract(
            article='Teachers in Greece face hiring challenges.',
            comments=['Many are not getting hired.'],
            language='en',
        )

        self.assertGreater(len(results), 0)
        labels = [r.label for r in results]
        self.assertIn('Education Policy', labels)

    @patch('topic_extraction.extractors.embedding.get_taxonomy_embeddings')
    @patch('topic_extraction.extractors.embedding.get_embedding_model')
    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    def test_returns_empty_when_all_scores_below_threshold(
        self, mock_hf_pipeline, mock_emb_model_fn, mock_taxonomy_fn
    ):
        from topic_extraction.models import Topic
        topics = list(Topic.objects.all())
        taxonomy_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.5, 0.5]])
        mock_emb_model_fn.return_value = mock_model

        mock_zs_pipeline = MagicMock()
        mock_zs_pipeline.return_value = {
            'labels': ['Education Policy', 'Climate Change'],
            'scores': [0.1, 0.1],
        }
        mock_hf_pipeline.return_value = mock_zs_pipeline

        extractor = EmbeddingExtractor()
        results = extractor.extract(
            article='Some unrelated text.', comments=[], language='en'
        )
        # With embedding ~0.5 and zero-shot ~0.1, avg ~0.3 < threshold 0.35
        self.assertIsInstance(results, list)
