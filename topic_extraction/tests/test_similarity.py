import numpy as np
from django.core.management import call_command
from django.test import TestCase
from topic_extraction.models import ArticleEmbedding, ArticleTopic, Topic


def _make_embedding(platform, article_id, language, vector, model_name='mpnet'):
    """Convenience: create an ArticleEmbedding with a Python list vector."""
    return ArticleEmbedding.objects.create(
        platform=platform,
        article_id=article_id,
        language=language,
        vector=list(vector),  # ensure JSONField gets a list, not np.ndarray
        embedding_model_name=model_name,
    )


def _make_topic_row(article_id, platform, language, slugs):
    """Convenience: create an ArticleTopic with a normalized list of slugs."""
    return ArticleTopic.objects.create(
        article_id=article_id,
        platform=platform,
        language=language,
        language_source='detected',
        raw_topics=[],
        normalized=[{'topic_id': s, 'score': 1.0, 'raw_score': 0.8} for s in slugs],
        backend='embedding_similarity',
        taxonomy_version='test',
    )


class FindSimilarHappyPathTest(TestCase):
    def setUp(self):
        # Source plus candidates in the same (opengov, en) bucket.
        # Vectors hand-crafted so distances are predictable.
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0, 0.0])
        _make_embedding('opengov', 'near', 'en', [0.9, 0.1, 0.0])
        _make_embedding('opengov', 'far', 'en', [0.0, 1.0, 0.0])
        _make_embedding('opengov', 'medium', 'en', [0.7, 0.7, 0.0])

    def test_returns_ranked_list_excluding_source(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10)
        ids = [r.article_id for r in results]
        self.assertNotIn('src', ids)
        self.assertEqual(ids[0], 'near')

    def test_respects_k_parameter(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=2)
        self.assertEqual(len(results), 2)

    def test_k_larger_than_pool(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=100)
        self.assertEqual(len(results), 3)

    def test_results_include_required_fields(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=1)
        r = results[0]
        self.assertTrue(hasattr(r, 'platform'))
        self.assertTrue(hasattr(r, 'article_id'))
        self.assertTrue(hasattr(r, 'language'))
        self.assertTrue(hasattr(r, 'raw_score'))
        self.assertTrue(hasattr(r, 'z_score'))

    def test_raw_score_rounded_to_4_decimals(self):
        """raw_score is round(float(cosine), 4). The view/serializer can rely
        on at most 4 decimal places in the JSON payload."""
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=1)
        r = results[0]
        # Format to a fixed-width string to inspect decimals.
        formatted = f'{r.raw_score:.10f}'.rstrip('0').rstrip('.')
        decimals = formatted.split('.')[1] if '.' in formatted else ''
        self.assertLessEqual(len(decimals), 4, f'raw_score has more than 4 decimals: {r.raw_score}')


class FindSimilarMissingSourceTest(TestCase):
    def test_raises_source_not_found(self):
        from topic_extraction.similarity import find_similar, SourceNotFoundError
        with self.assertRaises(SourceNotFoundError):
            find_similar('opengov', 'does-not-exist', k=10)


class FindSimilarLanguageFilterTest(TestCase):
    def setUp(self):
        _make_embedding('opengov', 'src', 'el', [1.0, 0.0])
        _make_embedding('opengov', 'same_lang', 'el', [0.9, 0.1])
        _make_embedding('opengov', 'diff_lang', 'en', [0.95, 0.05])

    def test_filters_to_source_language_only(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10)
        ids = [r.article_id for r in results]
        self.assertEqual(ids, ['same_lang'])
        self.assertNotIn('diff_lang', ids)


class FindSimilarModelNameFilterTest(TestCase):
    def setUp(self):
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0], model_name='mpnet')
        _make_embedding('opengov', 'same_model', 'en', [0.9, 0.1], model_name='mpnet')
        _make_embedding('opengov', 'diff_model', 'en', [0.95, 0.05], model_name='e5-base')

    def test_filters_to_source_model_space_only(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10)
        ids = [r.article_id for r in results]
        self.assertEqual(ids, ['same_model'])
        self.assertNotIn('diff_model', ids)


class FindSimilarPlatformFilterTest(TestCase):
    def setUp(self):
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0])
        _make_embedding('opengov', 'same_platform', 'en', [0.9, 0.1])
        _make_embedding('bridge', 'src', 'en', [1.0, 0.0])
        _make_embedding('bridge', 'other_platform', 'en', [0.95, 0.05])

    def test_filters_to_source_platform_only(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10)
        ids = [r.article_id for r in results]
        self.assertIn('same_platform', ids)
        self.assertNotIn('other_platform', ids)


class FindSimilarTopicSlugFilterTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0, 0.0])
        _make_embedding('opengov', 'housing_match', 'en', [0.9, 0.1, 0.0])
        _make_embedding('opengov', 'education_match', 'en', [0.95, 0.05, 0.0])
        _make_embedding('opengov', 'no_topics', 'en', [0.85, 0.15, 0.0])

        _make_topic_row('src', 'opengov', 'en', ['housing'])
        _make_topic_row('housing_match', 'opengov', 'en', ['housing'])
        _make_topic_row('education_match', 'opengov', 'en', ['education_policy'])
        # 'no_topics' has no ArticleTopic row at all.

    def test_leaf_slug_filters_to_matching_articles(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10, topic_slug='housing')
        ids = [r.article_id for r in results]
        self.assertEqual(ids, ['housing_match'])

    def test_parent_slug_expands_to_active_leaves(self):
        # 'housing_urban' is a parent; should match all articles tagged with
        # ANY leaf under that parent (including 'housing').
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10, topic_slug='housing_urban')
        ids = [r.article_id for r in results]
        self.assertIn('housing_match', ids)

    def test_deactivated_slug_returns_empty(self):
        housing = Topic.objects.get(slug='housing')
        housing.is_active = False
        housing.save()
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10, topic_slug='housing')
        self.assertEqual(results, [])

    def test_unknown_slug_raises(self):
        from topic_extraction.similarity import find_similar, UnknownTopicSlugError
        with self.assertRaises(UnknownTopicSlugError):
            find_similar('opengov', 'src', k=10, topic_slug='does-not-exist')

    def test_articles_with_empty_normalized_filtered_out(self):
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10, topic_slug='housing')
        ids = [r.article_id for r in results]
        self.assertNotIn('no_topics', ids)


class FindSimilarEmptyPoolTest(TestCase):
    def test_returns_empty_list(self):
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0])
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10)
        self.assertEqual(results, [])


class FindSimilarZScoreTest(TestCase):
    def test_small_pool_returns_z_score_none(self):
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0])
        _make_embedding('opengov', 'c1', 'en', [0.9, 0.1])
        _make_embedding('opengov', 'c2', 'en', [0.8, 0.2])
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=10)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIsNone(r.z_score)
            self.assertIsNotNone(r.raw_score)

    def test_large_pool_returns_z_score_populated(self):
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0])
        for i in range(12):
            _make_embedding('opengov', f'c{i}', 'en', [0.5 + 0.01 * i, 0.5 - 0.01 * i])
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=12)
        for r in results:
            self.assertIsNotNone(r.z_score)


class FindSimilarDegenerateStdTest(TestCase):
    """When all candidates are identically close to the source, std == 0
    and the code path sets z_score to 0.0 for every result instead of None.
    The threshold (pool >= 10) still applies."""

    def test_identical_candidates_zero_std_pool_ge_10(self):
        # Source plus 12 candidates with identical vectors — all cosine
        # similarities to source are exactly 1.0, so std == 0 in float32.
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0])
        for i in range(12):
            _make_embedding('opengov', f'c{i}', 'en', [1.0, 0.0])
        from topic_extraction.similarity import find_similar
        results = find_similar('opengov', 'src', k=12)
        self.assertEqual(len(results), 12)
        for r in results:
            # std == 0 path: z_score is 0.0, NOT None.
            self.assertEqual(r.z_score, 0.0)
            # raw_score is the identical cosine value (1.0 for these vectors).
            self.assertIsNotNone(r.raw_score)


class FindSimilarStabilityTest(TestCase):
    def setUp(self):
        _make_embedding('opengov', 'src', 'en', [1.0, 0.0])
        _make_embedding('opengov', 'c1', 'en', [0.9, 0.1])
        _make_embedding('opengov', 'c2', 'en', [0.5, 0.5])
        _make_embedding('opengov', 'c3', 'en', [0.95, 0.05])

    def test_same_input_same_output(self):
        from topic_extraction.similarity import find_similar
        r1 = find_similar('opengov', 'src', k=10)
        r2 = find_similar('opengov', 'src', k=10)
        ids1 = [r.article_id for r in r1]
        ids2 = [r.article_id for r in r2]
        self.assertEqual(ids1, ids2)
