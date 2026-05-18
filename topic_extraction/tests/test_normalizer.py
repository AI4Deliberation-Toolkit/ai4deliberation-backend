import numpy as np
from unittest.mock import patch, MagicMock
from django.test import TestCase
from topic_extraction.models import Topic
from topic_extraction.taxonomy import get_taxonomy_embeddings, invalidate_taxonomy_cache
from topic_extraction.extractors.base import TopicResult
from topic_extraction.normalizer import normalize, NormalizedTopic


class TaxonomyTest(TestCase):
    def setUp(self):
        parent = Topic.objects.create(slug='governance', label_en='Governance', labels={})
        Topic.objects.create(slug='education_policy', label_en='Education Policy',
                             labels={'el': 'Εκπαιδευτική Πολιτική'}, parent=parent)
        Topic.objects.create(slug='climate_change', label_en='Climate Change',
                             labels={'el': 'Κλιματική Αλλαγή'}, parent=parent)
        invalidate_taxonomy_cache()

    @patch('topic_extraction.taxonomy.get_embedding_model')
    def test_returns_topics_and_embeddings(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
        mock_get_model.return_value = mock_model

        topics, embeddings = get_taxonomy_embeddings('el')

        self.assertEqual(len(topics), 2)
        self.assertEqual(embeddings.shape, (2, 2))

    @patch('topic_extraction.taxonomy.get_embedding_model')
    def test_uses_translated_labels_when_available(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.zeros((2, 2))
        mock_get_model.return_value = mock_model

        get_taxonomy_embeddings('el')

        called_labels = mock_model.encode.call_args[0][0]
        self.assertIn('Εκπαιδευτική Πολιτική', called_labels)
        self.assertIn('Κλιματική Αλλαγή', called_labels)

    @patch('topic_extraction.taxonomy.get_embedding_model')
    def test_falls_back_to_english_when_no_translation(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.zeros((2, 2))
        mock_get_model.return_value = mock_model

        get_taxonomy_embeddings('fr')  # No French translations in setUp

        called_labels = mock_model.encode.call_args[0][0]
        self.assertIn('Education Policy', called_labels)

    @patch('topic_extraction.taxonomy.get_embedding_model')
    def test_caches_result_for_same_language(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.zeros((2, 2))
        mock_get_model.return_value = mock_model

        get_taxonomy_embeddings('el')
        get_taxonomy_embeddings('el')

        self.assertEqual(mock_model.encode.call_count, 1)


class NormalizerTest(TestCase):
    def setUp(self):
        parent = Topic.objects.create(slug='governance', label_en='Governance', labels={})
        Topic.objects.create(slug='education_policy', label_en='Education Policy',
                             labels={'el': 'Εκπαιδευτική Πολιτική'}, parent=parent)
        Topic.objects.create(slug='climate_change', label_en='Climate Change',
                             labels={'el': 'Κλιματική Αλλαγή'}, parent=parent)
        invalidate_taxonomy_cache()

    @patch('topic_extraction.normalizer.get_taxonomy_embeddings')
    @patch('topic_extraction.normalizer.get_embedding_model')
    def test_maps_raw_topic_to_nearest_taxonomy_node(self, mock_model_fn, mock_taxonomy_fn):
        from topic_extraction.models import Topic
        topics = list(Topic.objects.filter(parent__isnull=False))
        # education_policy embedding
        taxonomy_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = mock_model_fn.return_value
        # Raw topic embedding close to education_policy
        mock_model.encode.return_value = np.array([[0.99, 0.01]])

        raw = [TopicResult(label='Εκπαιδευτική Πολιτική', score=0.9)]
        result = normalize(raw, language='el')

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].topic_id, 'education_policy')

    @patch('topic_extraction.normalizer.get_taxonomy_embeddings')
    @patch('topic_extraction.normalizer.get_embedding_model')
    def test_deduplicates_same_taxonomy_node(self, mock_model_fn, mock_taxonomy_fn):
        from topic_extraction.models import Topic
        topics = list(Topic.objects.filter(parent__isnull=False))
        taxonomy_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = mock_model_fn.return_value
        # Both raw topics map to education_policy; keep the higher score
        mock_model.encode.return_value = np.array([[0.99, 0.01], [0.95, 0.05]])

        raw = [TopicResult(label='edu', score=0.9), TopicResult(label='education', score=0.7)]
        result = normalize(raw, language='el')

        slugs = [r.topic_id for r in result]
        self.assertEqual(slugs.count('education_policy'), 1)
        matched = next(r for r in result if r.topic_id == 'education_policy')
        self.assertEqual(matched.score, 0.9)

    @patch('topic_extraction.normalizer.get_taxonomy_embeddings')
    @patch('topic_extraction.normalizer.get_embedding_model')
    def test_returns_empty_list_for_empty_input(self, mock_model_fn, mock_taxonomy_fn):
        result = normalize([], language='el')
        self.assertEqual(result, [])
        mock_model_fn.assert_not_called()

    @patch('topic_extraction.normalizer.get_taxonomy_embeddings')
    @patch('topic_extraction.normalizer.get_embedding_model')
    def test_filters_below_threshold(self, mock_model_fn, mock_taxonomy_fn):
        from topic_extraction.models import Topic
        topics = list(Topic.objects.filter(parent__isnull=False))
        taxonomy_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = mock_model_fn.return_value
        # Score will be ~0.1 (low similarity) - both embeddings are close to zero
        mock_model.encode.return_value = np.array([[0.1, 0.1]])

        raw = [TopicResult(label='something unrelated', score=0.9)]
        result = normalize(raw, language='el', threshold=0.8)

        self.assertEqual(result, [])
