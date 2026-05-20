from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase
from topic_extraction.models import ArticleTopic
from topic_extraction import taxonomy_data


class RecomputeTopicsTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_writes_new_row_with_current_taxonomy_version(self):
        ArticleTopic.objects.create(
            article_id='a1', platform='p1', language='en',
            raw_topics=[{'label': 'Education Policy', 'score': 0.9}],
            normalized=[{'topic_id': 'education_policy', 'score': 0.9}],
            backend='embedding', taxonomy_version='2026-01-01-1',
        )
        call_command('recompute_topics')
        rows = ArticleTopic.objects.filter(article_id='a1').order_by('-computed_at')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows.first().taxonomy_version, taxonomy_data.TAXONOMY_VERSION)

    def test_skips_empty_raw_topics(self):
        ArticleTopic.objects.create(
            article_id='a2', platform='p1', language='en',
            raw_topics=[], normalized=[], backend='embedding',
        )
        out = StringIO()
        call_command('recompute_topics', stdout=out)
        # Only one row should exist — the original; no new row was written.
        self.assertEqual(ArticleTopic.objects.filter(article_id='a2').count(), 1)
        self.assertIn('skipped', out.getvalue().lower())

    @patch('topic_extraction.management.commands.recompute_topics.normalize')
    def test_no_matches_writes_empty_normalized(self, mock_normalize):
        # When normalize() returns [] (no raw topic clears the threshold against the
        # current taxonomy), the command should still write a new row with
        # normalized=[], recording that the row was reconsidered. We mock normalize
        # directly so the test exercises the empty-result integration path without
        # depending on embedding-similarity thresholds (which are taxonomy-content-
        # sensitive and would make this test fragile).
        mock_normalize.return_value = []
        ArticleTopic.objects.create(
            article_id='a3', platform='p1', language='en',
            raw_topics=[{'label': 'some stored label', 'score': 0.5}],
            normalized=[], backend='embedding',
        )
        call_command('recompute_topics')
        rows = ArticleTopic.objects.filter(article_id='a3').order_by('-computed_at')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows.first().normalized, [])

    def test_platform_filter(self):
        ArticleTopic.objects.create(
            article_id='a4', platform='p_keep', language='en',
            raw_topics=[{'label': 'Education', 'score': 0.9}],
            normalized=[], backend='embedding',
        )
        ArticleTopic.objects.create(
            article_id='a5', platform='p_skip', language='en',
            raw_topics=[{'label': 'Education', 'score': 0.9}],
            normalized=[], backend='embedding',
        )
        call_command('recompute_topics', platform='p_keep')
        self.assertEqual(ArticleTopic.objects.filter(article_id='a4').count(), 2)
        self.assertEqual(ArticleTopic.objects.filter(article_id='a5').count(), 1)

    def test_carries_forward_stored_metadata(self):
        # The new row must preserve raw_topics, language, language_source, backend
        # from the source row unchanged. Only normalized + taxonomy_version + id +
        # computed_at are fresh on the new row.
        ArticleTopic.objects.create(
            article_id='a6', platform='p1', language='el',
            language_source='explicit',
            raw_topics=[{'label': 'Educational Policy', 'score': 0.91}],
            normalized=[], backend='llm',
            taxonomy_version='2026-01-01-1',
        )
        call_command('recompute_topics')
        new_row = ArticleTopic.objects.filter(article_id='a6').order_by('-computed_at').first()
        # Carry-forward fields preserved
        self.assertEqual(new_row.raw_topics, [{'label': 'Educational Policy', 'score': 0.91}])
        self.assertEqual(new_row.language, 'el')
        self.assertEqual(new_row.language_source, 'explicit')
        self.assertEqual(new_row.backend, 'llm')
        # Fresh fields bumped
        self.assertEqual(new_row.taxonomy_version, taxonomy_data.TAXONOMY_VERSION)
        self.assertNotEqual(new_row.taxonomy_version, '2026-01-01-1')

    @patch('topic_extraction.management.commands.recompute_topics.normalize')
    def test_normalized_payload_preserves_raw_score(self, mock_normalize):
        # Setup: create an ArticleTopic with normalized carrying raw_score.
        from topic_extraction.normalizer import NormalizedTopic
        mock_normalize.return_value = [
            NormalizedTopic(topic_id='education_policy', score=0.85)
        ]
        ArticleTopic.objects.create(
            article_id='rs1', platform='p1', language='en',
            raw_topics=[{'label': 'Education Policy', 'score': 0.9}],
            normalized=[{'topic_id': 'education_policy', 'score': 0.9, 'raw_score': 0.42}],
            backend='embedding_similarity', taxonomy_version='2026-01-01-1',
        )
        call_command('recompute_topics')
        new_row = ArticleTopic.objects.filter(article_id='rs1').order_by('-computed_at').first()
        self.assertEqual(len(new_row.normalized), 1)
        self.assertAlmostEqual(new_row.normalized[0]['raw_score'], 0.42)
        self.assertEqual(new_row.normalized[0]['topic_id'], 'education_policy')

    @patch('topic_extraction.management.commands.recompute_topics.normalize')
    def test_failed_row_does_not_abort_loop(self, mock_normalize):
        # Per-row isolation: if normalize() throws on one row, the loop continues
        # and the failure is logged. The summary should report `failed: 1`.
        # Targets iterate newest-first, so side_effect order matches creation reversed:
        # first call serves 'ok' (created second → newer), second call serves 'boom'.
        mock_normalize.side_effect = [[], RuntimeError('synthetic boom')]
        ArticleTopic.objects.create(
            article_id='boom', platform='p1', language='en',
            raw_topics=[{'label': 'x', 'score': 0.5}],
            normalized=[], backend='embedding',
        )
        ArticleTopic.objects.create(
            article_id='ok', platform='p1', language='en',
            raw_topics=[{'label': 'y', 'score': 0.5}],
            normalized=[], backend='embedding',
        )
        out, err = StringIO(), StringIO()
        call_command('recompute_topics', stdout=out, stderr=err)
        # The failing row stays at 1 original; the OK row gets a new write (2 total).
        self.assertEqual(ArticleTopic.objects.filter(article_id='boom').count(), 1)
        self.assertEqual(ArticleTopic.objects.filter(article_id='ok').count(), 2)
        self.assertIn('FAILED', err.getvalue())
        self.assertIn('failed: 1', out.getvalue())
