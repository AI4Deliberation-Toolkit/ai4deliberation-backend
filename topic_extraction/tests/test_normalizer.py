import numpy as np
from unittest.mock import patch, MagicMock
from django.test import TestCase
from topic_extraction.models import Topic
from topic_extraction.taxonomy import get_taxonomy_embeddings, invalidate_taxonomy_cache


class TaxonomyTest(TestCase):
    def setUp(self):
        Topic.objects.create(slug='education_policy', label_en='Education Policy',
                             labels={'el': 'Εκπαιδευτική Πολιτική'})
        Topic.objects.create(slug='climate_change', label_en='Climate Change',
                             labels={'el': 'Κλιματική Αλλαγή'})
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
