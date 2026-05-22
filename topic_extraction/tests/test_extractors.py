import json
import numpy as np
from unittest.mock import patch, MagicMock
from django.test import TestCase
from topic_extraction.extractors.base import BaseExtractor, TopicResult
from topic_extraction.models import Topic
from topic_extraction.taxonomy import invalidate_taxonomy_cache
from topic_extraction.extractors.embedding import EmbeddingExtractor, EmbeddingSimilarityExtractor, _compute_passage_embedding
from topic_extraction.extractors.llm import LLMExtractor


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


class EmbeddingSimilarityExtractorTest(TestCase):
    def setUp(self):
        Topic.objects.create(slug='education_policy', label_en='Education Policy',
                             labels={'el': 'Εκπαιδευτική Πολιτική'})
        Topic.objects.create(slug='climate_change', label_en='Climate Change',
                             labels={'el': 'Κλιματική Αλλαγή'})
        invalidate_taxonomy_cache()

    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    @patch('topic_extraction.extractors.embedding.get_taxonomy_embeddings')
    @patch('topic_extraction.extractors.embedding.get_embedding_model')
    def test_returns_results_from_similarity_alone(
        self, mock_emb_model_fn, mock_taxonomy_fn, mock_hf_pipeline
    ):
        topics = list(Topic.objects.all())
        taxonomy_embs = np.array([[1.0, 0.0], [0.0, 1.0]])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.95, 0.05]])
        mock_emb_model_fn.return_value = mock_model

        extractor = EmbeddingSimilarityExtractor()
        results = extractor.extract(
            article='Teachers face hiring challenges.', comments=[], language='en'
        )

        labels = [r.label for r in results]
        self.assertIn('Education Policy', labels)
        # Critical: zero-shot pipeline is never invoked by the similarity-only extractor.
        mock_hf_pipeline.assert_not_called()

    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    @patch('topic_extraction.extractors.embedding.get_taxonomy_embeddings')
    @patch('topic_extraction.extractors.embedding.get_embedding_model')
    def test_filters_below_threshold(
        self, mock_emb_model_fn, mock_taxonomy_fn, mock_hf_pipeline
    ):
        topics = list(Topic.objects.all())
        # Passage embedding orthogonal to both taxonomy axes → cos sim = 0.
        taxonomy_embs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.0, 0.0, 1.0]])
        mock_emb_model_fn.return_value = mock_model

        extractor = EmbeddingSimilarityExtractor()
        results = extractor.extract(article='unrelated', comments=[], language='en')

        self.assertEqual(results, [])
        mock_hf_pipeline.assert_not_called()

    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    @patch('topic_extraction.extractors.embedding.get_taxonomy_embeddings')
    @patch('topic_extraction.extractors.embedding.get_embedding_model')
    def test_results_carry_both_raw_cosine_and_z_score(
        self, mock_emb_model_fn, mock_taxonomy_fn, mock_hf_pipeline
    ):
        # Three topics with one clear winner — verifies z-score normalisation
        # picks the distinctive leaf and that both raw and z-score are exposed.
        Topic.objects.create(slug='education_funding', label_en='Education Funding',
                             labels={'el': 'Χρηματοδότηση Εκπαίδευσης'})
        topics = list(Topic.objects.all())
        invalidate_taxonomy_cache()

        # Three taxonomy axes; passage close to axis 0, mid-distant from 1+2.
        taxonomy_embs = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = MagicMock()
        # passage = [0.95, 0.30, 0.05] (close to axis 0, weak signal on the others)
        mock_model.encode.return_value = np.array([[0.95, 0.30, 0.05]])
        mock_emb_model_fn.return_value = mock_model

        extractor = EmbeddingSimilarityExtractor()
        results = extractor.extract(
            article='Teachers face hiring challenges.', comments=[], language='en'
        )

        # At least one result, sorted by z-score descending — the strongest match wins.
        self.assertGreater(len(results), 0)
        # Each TopicResult exposes both the raw cosine (raw_score) and the z-score (score).
        for r in results:
            self.assertIsNotNone(r.raw_score, f'raw_score missing on {r.label}')
            self.assertIsInstance(r.raw_score, float)
            self.assertIsInstance(r.score, float)
            # raw_score is in cosine space [-1, 1]; z-score is normalised, can be any real.
            self.assertGreaterEqual(r.raw_score, -1.0)
            self.assertLessEqual(r.raw_score, 1.0)
        # The top result should have a higher z-score than any other, and its raw_score
        # should be the maximum raw cosine seen (axis 0).
        top = results[0]
        self.assertEqual(top.score, max(r.score for r in results))
        # The top z-score should be positive (above the article's mean).
        self.assertGreater(top.score, 0)
        mock_hf_pipeline.assert_not_called()

    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    @patch('topic_extraction.extractors.embedding.get_taxonomy_embeddings')
    @patch('topic_extraction.extractors.embedding.get_embedding_model')
    def test_z_score_threshold_drops_flat_distributions(
        self, mock_emb_model_fn, mock_taxonomy_fn, mock_hf_pipeline
    ):
        # When all leaves score within < 1σ of the article's own mean (a "flat"
        # distribution), z-score filtering returns zero results — this is the
        # zero-match signal we want.
        topics = list(Topic.objects.all())
        # Passage embedding equidistant from both taxonomy axes → identical cos sims.
        taxonomy_embs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        mock_taxonomy_fn.return_value = (topics, taxonomy_embs)

        mock_model = MagicMock()
        # equal projection onto both axes → both raw_scores are identical → stdev=0 → z=0.
        mock_model.encode.return_value = np.array([[1.0, 1.0, 0.0]])
        mock_emb_model_fn.return_value = mock_model

        extractor = EmbeddingSimilarityExtractor()
        results = extractor.extract(article='ambiguous text', comments=[], language='en')

        # All leaves at z=0 are below the default z-threshold (>= 1.0) — zero match.
        self.assertEqual(results, [])
        mock_hf_pipeline.assert_not_called()


class LLMExtractorTest(TestCase):
    def _make_pipeline_mock(self, json_output: str):
        mock_pipeline = MagicMock()
        prompt_placeholder = 'PROMPT'
        mock_pipeline.return_value = [{'generated_text': prompt_placeholder + json_output}]
        return mock_pipeline, prompt_placeholder

    @patch('topic_extraction.extractors.llm.pipeline')
    def test_parses_valid_json_response(self, mock_pipeline_fn):
        json_body = '[{"label": "Εκπαιδευτική Πολιτική", "score": 0.9}]'
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{'generated_text': 'PROMPT' + json_body}]
        mock_pipeline_fn.return_value = mock_pipe

        extractor = LLMExtractor()
        extractor._pipeline = mock_pipe

        with patch.object(extractor, '_build_prompt', return_value='PROMPT'):
            results = extractor.extract('article text', ['comment'], language='el')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].label, 'Εκπαιδευτική Πολιτική')
        self.assertAlmostEqual(results[0].score, 0.9)

    @patch('topic_extraction.extractors.llm.pipeline')
    def test_raises_on_invalid_json(self, mock_pipeline_fn):
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{'generated_text': 'PROMPTnot valid json at all'}]
        mock_pipeline_fn.return_value = mock_pipe

        extractor = LLMExtractor()
        extractor._pipeline = mock_pipe

        with patch.object(extractor, '_build_prompt', return_value='PROMPT'):
            with self.assertRaises(ValueError):
                extractor.extract('article', [], language='el')

    @patch('topic_extraction.extractors.llm.pipeline')
    def test_skips_items_missing_required_fields(self, mock_pipeline_fn):
        json_body = '[{"label": "Good Topic", "score": 0.8}, {"label": "Missing Score"}]'
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{'generated_text': 'PROMPT' + json_body}]
        mock_pipeline_fn.return_value = mock_pipe

        extractor = LLMExtractor()
        extractor._pipeline = mock_pipe

        with patch.object(extractor, '_build_prompt', return_value='PROMPT'):
            results = extractor.extract('article', [], language='en')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].label, 'Good Topic')


class ComputePassageEmbeddingTest(TestCase):
    """Tests the shared helper that produces the per-article passage embedding.
    Used by both EmbeddingSimilarityExtractor (live writes) and
    backfill_embeddings (bulk writes). The bit-identical contract is tested
    in Task 3 via EmbeddingSimilarityExtractor.extract_with_embedding."""

    def test_returns_numpy_array(self):
        vec = _compute_passage_embedding('hello world', [], 'en')
        self.assertIsInstance(vec, np.ndarray)

    def test_shape_matches_mpnet_dimension(self):
        # paraphrase-multilingual-mpnet-base-v2 produces 768-dim vectors.
        vec = _compute_passage_embedding('hello world', [], 'en')
        self.assertEqual(vec.shape, (768,))

    def test_deterministic_for_same_input(self):
        vec1 = _compute_passage_embedding('hello world', [], 'en')
        vec2 = _compute_passage_embedding('hello world', [], 'en')
        # mpnet on the same input + normalize_embeddings=True is deterministic.
        np.testing.assert_array_equal(vec1, vec2)

    def test_includes_first_20_comments(self):
        # Verify the helper concatenates article + first 20 comments (matching
        # the existing _compute_similarity_scores semantics).
        article = 'main article text'
        comments = [f'comment {i}' for i in range(25)]  # 25 comments

        vec_with_first_20 = _compute_passage_embedding(article, comments, 'en')
        vec_with_explicit_first_20 = _compute_passage_embedding(article, comments[:20], 'en')
        np.testing.assert_array_equal(vec_with_first_20, vec_with_explicit_first_20)

        # 21st+ comments should NOT affect the embedding.
        vec_with_first_20_only = _compute_passage_embedding(article, comments[:20], 'en')
        np.testing.assert_array_equal(vec_with_first_20, vec_with_first_20_only)

    def test_empty_comments_works(self):
        vec = _compute_passage_embedding('article only', [], 'en')
        self.assertEqual(vec.shape, (768,))

    def test_returns_l2_normalized_vector(self):
        """Locks down the `normalize_embeddings=True` contract that the docstring
        promises and that Tasks 3/8 (extractor + backfill) rely on for cosine
        ranking. If normalization is ever dropped, cosine similarity becomes
        unbounded and ranking degrades silently — this test catches the regression."""
        vec = _compute_passage_embedding('hello world', [], 'en')
        self.assertAlmostEqual(float(np.linalg.norm(vec)), 1.0, places=5)


class ExtractWithEmbeddingTest(TestCase):
    """Verifies the bit-identical invariant between extract_with_embedding
    and _compute_passage_embedding — load-bearing for backfill parity."""

    def setUp(self):
        # The embedding extractors compute against the taxonomy, so they
        # need at least one active Topic in the DB to score against.
        from django.core.management import call_command
        call_command('seed_taxonomy')
        invalidate_taxonomy_cache()

    def test_similarity_extract_with_embedding_returns_tuple(self):
        from topic_extraction.extractors.embedding import EmbeddingSimilarityExtractor
        extractor = EmbeddingSimilarityExtractor()
        result = extractor.extract_with_embedding('test article', [], 'en')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        topics, vector = result
        self.assertIsInstance(topics, list)
        self.assertIsInstance(vector, np.ndarray)

    def test_similarity_extract_with_embedding_vector_matches_helper(self):
        """The bit-identical invariant: extract_with_embedding's returned
        vector must equal _compute_passage_embedding for the same input.
        Otherwise live extraction and backfill produce divergent vectors and
        cosine ranking becomes incoherent."""
        from topic_extraction.extractors.embedding import (
            EmbeddingSimilarityExtractor, _compute_passage_embedding,
        )
        article = 'test article'
        comments = ['comment one', 'comment two']
        language = 'en'

        extractor = EmbeddingSimilarityExtractor()
        _, vec_from_extractor = extractor.extract_with_embedding(article, comments, language)
        vec_from_helper = _compute_passage_embedding(article, comments, language)

        np.testing.assert_array_equal(vec_from_extractor, vec_from_helper)

    def test_similarity_extract_wrapper_preserves_interface(self):
        """The existing extract() method must still return just topics —
        backwards-compat for any direct callers."""
        from topic_extraction.extractors.embedding import EmbeddingSimilarityExtractor
        extractor = EmbeddingSimilarityExtractor()
        result = extractor.extract('test article', [], 'en')
        self.assertIsInstance(result, list)
        # Each item should be a TopicResult, not a vector.
        from topic_extraction.extractors.base import TopicResult
        for item in result:
            self.assertIsInstance(item, TopicResult)

    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    def test_full_extractor_extract_with_embedding_returns_tuple(self, mock_hf_pipeline):
        """Same contract on EmbeddingExtractor (the zero-shot one)."""
        mock_zs_pipeline = MagicMock()
        mock_zs_pipeline.side_effect = lambda text, labels, **kw: {
            'labels': labels, 'scores': [0.5] * len(labels)
        }
        mock_hf_pipeline.return_value = mock_zs_pipeline

        from topic_extraction.extractors.embedding import EmbeddingExtractor
        extractor = EmbeddingExtractor()
        result = extractor.extract_with_embedding('test article', [], 'en')
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    def test_full_extractor_extract_with_embedding_vector_matches_helper(self, mock_hf_pipeline):
        """Same bit-identical invariant on EmbeddingExtractor."""
        mock_zs_pipeline = MagicMock()
        mock_zs_pipeline.side_effect = lambda text, labels, **kw: {
            'labels': labels, 'scores': [0.5] * len(labels)
        }
        mock_hf_pipeline.return_value = mock_zs_pipeline

        from topic_extraction.extractors.embedding import (
            EmbeddingExtractor, _compute_passage_embedding,
        )
        article = 'another test'
        comments = []
        extractor = EmbeddingExtractor()
        _, vec_from_extractor = extractor.extract_with_embedding(article, comments, 'en')
        vec_from_helper = _compute_passage_embedding(article, comments, 'en')
        np.testing.assert_array_equal(vec_from_extractor, vec_from_helper)

    @patch('topic_extraction.extractors.embedding.hf_pipeline')
    def test_full_extractor_extract_wrapper_preserves_interface(self, mock_hf_pipeline):
        """The existing extract() method on EmbeddingExtractor must still
        return just topics."""
        mock_zs_pipeline = MagicMock()
        mock_zs_pipeline.side_effect = lambda text, labels, **kw: {
            'labels': labels, 'scores': [0.5] * len(labels)
        }
        mock_hf_pipeline.return_value = mock_zs_pipeline

        from topic_extraction.extractors.embedding import EmbeddingExtractor
        from topic_extraction.extractors.base import TopicResult
        extractor = EmbeddingExtractor()
        result = extractor.extract('another test', [], 'en')
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIsInstance(item, TopicResult)
