import io
from unittest.mock import patch, MagicMock
import numpy as np

from django.core.management import call_command, CommandError
from django.test import TestCase

from topic_extraction.models import ArticleTopic, ArticleEmbedding


class BackfillEmbeddingsBaseTest(TestCase):
    """Base class with mocked ingestor and embedding helper. Real production
    data flow: ingest creates ArticleTopic, then backfill creates
    ArticleEmbedding."""

    def setUp(self):
        ArticleTopic.objects.create(
            article_id='a1', platform='opengov', language='el',
            language_source='detected',
            raw_topics=[], normalized=[],
            backend='embedding_similarity', taxonomy_version='test',
        )
        ArticleTopic.objects.create(
            article_id='a2', platform='opengov', language='el',
            language_source='detected',
            raw_topics=[], normalized=[],
            backend='embedding_similarity', taxonomy_version='test',
        )

    def _run_with_mocks(self, *args, **kwargs):
        """Run backfill_embeddings with both the ingestor and helper mocked."""
        mock_ingestor_module = MagicMock()
        mock_ingestor_module.iter_articles.return_value = iter([
            {'platform': 'opengov', 'article_id': 'a1', 'article': 'text 1', 'comments': []},
            {'platform': 'opengov', 'article_id': 'a2', 'article': 'text 2', 'comments': []},
            {'platform': 'opengov', 'article_id': 'unmatched', 'article': 'no row', 'comments': []},
        ])

        def fake_emb(article, comments, language):
            return np.array([hash(article) % 100 / 100.0, 0.0, 0.0])

        out = io.StringIO()
        with patch('topic_extraction.management.commands.backfill_embeddings._get_ingestor',
                   return_value=mock_ingestor_module):
            with patch('topic_extraction.management.commands.backfill_embeddings._compute_passage_embedding',
                       side_effect=fake_emb):
                call_command('backfill_embeddings', *args, **kwargs, stdout=out)
        return out.getvalue()


class BackfillHappyPathTest(BackfillEmbeddingsBaseTest):
    def test_creates_embeddings_for_matched_articles(self):
        self._run_with_mocks('--source', 'opengov')
        self.assertEqual(ArticleEmbedding.objects.count(), 2)
        ae1 = ArticleEmbedding.objects.get(platform='opengov', article_id='a1')
        self.assertEqual(ae1.language, 'el')
        self.assertEqual(len(ae1.vector), 3)

    def test_skips_articles_with_no_articletopic(self):
        output = self._run_with_mocks('--source', 'opengov')
        self.assertFalse(
            ArticleEmbedding.objects.filter(article_id='unmatched').exists()
        )
        self.assertIn('skipped (no ArticleTopic): 1', output)

    def test_summary_output(self):
        output = self._run_with_mocks('--source', 'opengov')
        self.assertIn('Created: 2', output)


class BackfillOnlyMissingTest(BackfillEmbeddingsBaseTest):
    def test_skips_existing_rows(self):
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='a1', language='el',
            vector=[9.9, 9.9, 9.9], embedding_model_name='old',
        )
        self._run_with_mocks('--source', 'opengov', '--only-missing')
        ae1 = ArticleEmbedding.objects.get(platform='opengov', article_id='a1')
        self.assertEqual(ae1.vector, [9.9, 9.9, 9.9])
        self.assertTrue(
            ArticleEmbedding.objects.filter(article_id='a2').exists()
        )

    def test_without_only_missing_overwrites(self):
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='a1', language='el',
            vector=[9.9, 9.9, 9.9], embedding_model_name='old',
        )
        self._run_with_mocks('--source', 'opengov')
        ae1 = ArticleEmbedding.objects.get(platform='opengov', article_id='a1')
        self.assertNotEqual(ae1.vector, [9.9, 9.9, 9.9])


class BackfillModelNameStampTest(BackfillEmbeddingsBaseTest):
    def test_stamps_current_setting(self):
        from django.conf import settings
        self._run_with_mocks('--source', 'opengov')
        ae1 = ArticleEmbedding.objects.get(platform='opengov', article_id='a1')
        self.assertEqual(ae1.embedding_model_name, settings.EMBEDDING_MODEL_NAME)


class BackfillWhereModelFilterTest(BackfillEmbeddingsBaseTest):
    def test_only_processes_rows_matching_where_model(self):
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='a1', language='el',
            vector=[0.1], embedding_model_name='old_model',
        )
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='a2', language='el',
            vector=[0.2], embedding_model_name='new_model',
        )
        self._run_with_mocks('--source', 'opengov', '--where-model', 'old_model')
        ae1 = ArticleEmbedding.objects.get(platform='opengov', article_id='a1')
        self.assertNotEqual(ae1.vector, [0.1])
        ae2 = ArticleEmbedding.objects.get(platform='opengov', article_id='a2')
        self.assertEqual(ae2.vector, [0.2])


class BackfillUnknownSourceTest(TestCase):
    def test_unknown_source_raises(self):
        with self.assertRaises(CommandError):
            call_command('backfill_embeddings', '--source', 'no-such-platform')


class BackfillEndToEndParityTest(TestCase):
    """End-to-end: pipeline.run extracts an article; backfill_embeddings over
    the same source article produces an identical ArticleEmbedding vector.
    Verifies the bit-identical invariant in the integrated environment.

    Heavy: loads the real model. Kept in this file rather than the
    helper-test file so its slow nature is contained to one place."""

    def setUp(self):
        from django.core.management import call_command as cmd
        cmd('seed_taxonomy')

    def test_extract_and_backfill_produce_identical_vector(self):
        from topic_extraction import pipeline
        from topic_extraction.models import ArticleEmbedding

        pipeline.run(
            article_id='parity-test',
            platform='opengov',
            article='education policy in Greece',
            comments=[],
        )
        live_emb = ArticleEmbedding.objects.get(
            platform='opengov', article_id='parity-test'
        )
        live_vec = list(live_emb.vector)

        mock_ingestor = MagicMock()
        mock_ingestor.iter_articles.return_value = iter([
            {
                'platform': 'opengov',
                'article_id': 'parity-test',
                'article': 'education policy in Greece',
                'comments': [],
            },
        ])
        with patch('topic_extraction.management.commands.backfill_embeddings._get_ingestor',
                   return_value=mock_ingestor):
            call_command('backfill_embeddings', '--source', 'opengov')

        backfilled = ArticleEmbedding.objects.get(
            platform='opengov', article_id='parity-test'
        )
        np.testing.assert_array_equal(
            np.array(live_vec),
            np.array(backfilled.vector),
        )
