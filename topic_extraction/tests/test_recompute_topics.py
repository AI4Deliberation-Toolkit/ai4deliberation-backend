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
