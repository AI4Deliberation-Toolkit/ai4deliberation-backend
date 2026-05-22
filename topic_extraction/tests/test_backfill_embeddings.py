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


class BackfillPlatformFilterTest(BackfillEmbeddingsBaseTest):
    def test_platform_filter_excludes_non_matching_platform(self):
        # Add an ArticleTopic for a different platform.
        ArticleTopic.objects.create(
            article_id='a1', platform='bridge', language='el',
            language_source='detected',
            raw_topics=[], normalized=[],
            backend='embedding_similarity', taxonomy_version='test',
        )
        # Mock ingestor yields a1 on both opengov and bridge.
        mock_ingestor_module = MagicMock()
        mock_ingestor_module.iter_articles.return_value = iter([
            {'platform': 'opengov', 'article_id': 'a1', 'article': 'text', 'comments': []},
            {'platform': 'bridge', 'article_id': 'a1', 'article': 'other', 'comments': []},
        ])

        def fake_emb(article, comments, language):
            return np.array([0.1, 0.2, 0.3])

        with patch('topic_extraction.management.commands.backfill_embeddings._get_ingestor',
                   return_value=mock_ingestor_module):
            with patch('topic_extraction.management.commands.backfill_embeddings._compute_passage_embedding',
                       side_effect=fake_emb):
                call_command('backfill_embeddings', '--source', 'opengov', '--platform', 'opengov')

        # Only the opengov article should have been embedded.
        self.assertTrue(ArticleEmbedding.objects.filter(platform='opengov', article_id='a1').exists())
        self.assertFalse(ArticleEmbedding.objects.filter(platform='bridge', article_id='a1').exists())


class BackfillLanguageFilterTest(BackfillEmbeddingsBaseTest):
    def test_language_filter_excludes_non_matching_language(self):
        # Override a1's language to 'en' so we can test filtering by language.
        ArticleTopic.objects.filter(article_id='a1').update(language='en')
        # a2 stays 'el'. Running with --language el should only embed a2.
        self._run_with_mocks('--source', 'opengov', '--language', 'el')
        # a2 (el) was embedded; a1 (en) was not.
        self.assertTrue(ArticleEmbedding.objects.filter(article_id='a2').exists())
        self.assertFalse(ArticleEmbedding.objects.filter(article_id='a1').exists())


class BackfillPerRowExceptionTest(BackfillEmbeddingsBaseTest):
    def test_per_row_failure_continues_and_counts_failed(self):
        """If _compute_passage_embedding raises for one article, the other
        articles still process and the summary reports failed: 1."""
        mock_ingestor_module = MagicMock()
        mock_ingestor_module.iter_articles.return_value = iter([
            {'platform': 'opengov', 'article_id': 'a1', 'article': 'good', 'comments': []},
            {'platform': 'opengov', 'article_id': 'a2', 'article': 'bad', 'comments': []},
        ])

        def fake_emb_with_one_failure(article, comments, language):
            if article == 'bad':
                raise RuntimeError('synthetic failure')
            return np.array([0.1, 0.2, 0.3])

        out = io.StringIO()
        err = io.StringIO()
        with patch('topic_extraction.management.commands.backfill_embeddings._get_ingestor',
                   return_value=mock_ingestor_module):
            with patch('topic_extraction.management.commands.backfill_embeddings._compute_passage_embedding',
                       side_effect=fake_emb_with_one_failure):
                call_command('backfill_embeddings', '--source', 'opengov', stdout=out, stderr=err)

        output = out.getvalue()
        self.assertIn('Created: 1', output)
        self.assertIn('failed: 1', output)
        # The good article was still embedded.
        self.assertTrue(ArticleEmbedding.objects.filter(article_id='a1').exists())
        # The bad article was not.
        self.assertFalse(ArticleEmbedding.objects.filter(article_id='a2').exists())
        # Failure was logged to stderr.
        self.assertIn('FAILED', err.getvalue())
        self.assertIn('a2', err.getvalue())


class BackfillZeroMatchesWarningTest(TestCase):
    """When iteration yields articles but no ArticleTopic rows match, surface
    a NOTE to stderr — most likely cause is an article_id format mismatch
    between the ingestor's synthesis and what API clients have written."""

    def test_warns_when_iterated_articles_but_zero_match(self):
        # No ArticleTopic rows exist. Ingestor yields 2 articles.
        mock_ingestor_module = MagicMock()
        mock_ingestor_module.iter_articles.return_value = iter([
            {'platform': 'opengov', 'article_id': 'a1', 'article': 'x', 'comments': []},
            {'platform': 'opengov', 'article_id': 'a2', 'article': 'y', 'comments': []},
        ])

        out = io.StringIO()
        err = io.StringIO()
        with patch('topic_extraction.management.commands.backfill_embeddings._get_ingestor',
                   return_value=mock_ingestor_module):
            call_command('backfill_embeddings', '--source', 'opengov',
                         stdout=out, stderr=err)

        stderr_text = err.getvalue()
        self.assertIn('NOTE', stderr_text)
        self.assertIn('0 ArticleTopic rows matched', stderr_text)
        self.assertIn("'opengov'", stderr_text)
        self.assertIn('Created: 0', out.getvalue())
        self.assertIn('skipped (no ArticleTopic): 2', out.getvalue())

    def test_no_warning_when_at_least_one_match(self):
        # One ArticleTopic exists; one match expected → no warning.
        ArticleTopic.objects.create(
            article_id='a1', platform='opengov', language='el',
            language_source='detected',
            raw_topics=[], normalized=[],
            backend='embedding_similarity', taxonomy_version='test',
        )
        mock_ingestor_module = MagicMock()
        mock_ingestor_module.iter_articles.return_value = iter([
            {'platform': 'opengov', 'article_id': 'a1', 'article': 'x', 'comments': []},
        ])

        def fake_emb(article, comments, language):
            return np.array([0.1, 0.2, 0.3])

        err = io.StringIO()
        with patch('topic_extraction.management.commands.backfill_embeddings._get_ingestor',
                   return_value=mock_ingestor_module):
            with patch('topic_extraction.management.commands.backfill_embeddings._compute_passage_embedding',
                       side_effect=fake_emb):
                call_command('backfill_embeddings', '--source', 'opengov', stderr=err)

        self.assertNotIn('NOTE', err.getvalue())

    def test_no_warning_when_zero_iterated(self):
        # Ingestor yields nothing → zero matches AND zero skips → no warning
        # (warning condition requires skipped_no_articletopic > 0).
        mock_ingestor_module = MagicMock()
        mock_ingestor_module.iter_articles.return_value = iter([])

        err = io.StringIO()
        with patch('topic_extraction.management.commands.backfill_embeddings._get_ingestor',
                   return_value=mock_ingestor_module):
            call_command('backfill_embeddings', '--source', 'opengov', stderr=err)

        self.assertNotIn('NOTE', err.getvalue())
