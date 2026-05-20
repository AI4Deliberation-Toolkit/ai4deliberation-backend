import datetime as dt
import os
import tempfile

from django.test import TestCase

from topic_extraction.corpus_sampler import SampledArticle, sample_articles


def _build_parquet(path, consultations):
    """Write a small opengov-shaped parquet for tests.

    consultations is a list of dicts: {consultation_id, start_date (datetime), articles}.
    Each article: {article_id, title, body_text}.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = []
    for c in consultations:
        rows.append({
            'consultation_id': c['consultation_id'],
            'start_date': c['start_date'],
            'articles': [
                {
                    'article_id': a['article_id'],
                    'title': a.get('title', ''),
                    'body_text': a.get('body_text', ''),
                }
                for a in c['articles']
            ],
        })
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


class SampleArticlesTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.parquet_path = os.path.join(self.tmpdir.name, 'corpus.parquet')

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make_corpus(self, articles_per_year):
        """Build a parquet with the given count of articles per year (dict[year]->count)."""
        consultations = []
        cid = 0
        aid = 0
        for year, count in articles_per_year.items():
            cid += 1
            articles = []
            for _ in range(count):
                aid += 1
                articles.append({
                    'article_id': aid,
                    'title': f'Article {aid}',
                    'body_text': f'Body {aid}',
                })
            consultations.append({
                'consultation_id': cid,
                'start_date': dt.datetime(year, 6, 15),
                'articles': articles,
            })
        _build_parquet(self.parquet_path, consultations)

    def test_returns_requested_sample_size_when_enough_available(self):
        self._make_corpus({2022: 50, 2023: 50, 2024: 50, 2025: 50, 2026: 50})
        sample = sample_articles(
            self.parquet_path,
            sample_size=100, year_min=2022, year_max=2026, seed=42,
        )
        self.assertEqual(len(sample), 100)

    def test_stratifies_evenly_across_years(self):
        self._make_corpus({2022: 50, 2023: 50, 2024: 50, 2025: 50, 2026: 50})
        sample = sample_articles(
            self.parquet_path,
            sample_size=100, year_min=2022, year_max=2026, seed=42,
        )
        per_year = {2022: 0, 2023: 0, 2024: 0, 2025: 0, 2026: 0}
        for art in sample:
            per_year[art.year] += 1
        self.assertEqual(per_year, {2022: 20, 2023: 20, 2024: 20, 2025: 20, 2026: 20})

    def test_excludes_articles_outside_year_window(self):
        self._make_corpus({2020: 50, 2024: 50})
        sample = sample_articles(
            self.parquet_path,
            sample_size=20, year_min=2022, year_max=2026, seed=42,
        )
        for art in sample:
            self.assertGreaterEqual(art.year, 2022)
            self.assertLessEqual(art.year, 2026)
            self.assertEqual(art.year, 2024)

    def test_deterministic_under_same_seed(self):
        self._make_corpus({2024: 50, 2025: 50})
        s1 = sample_articles(self.parquet_path, sample_size=20, year_min=2024, year_max=2025, seed=42)
        s2 = sample_articles(self.parquet_path, sample_size=20, year_min=2024, year_max=2025, seed=42)
        self.assertEqual([a.key for a in s1], [a.key for a in s2])

    def test_different_seed_gives_different_sample(self):
        self._make_corpus({2024: 50, 2025: 50})
        s1 = sample_articles(self.parquet_path, sample_size=20, year_min=2024, year_max=2025, seed=42)
        s2 = sample_articles(self.parquet_path, sample_size=20, year_min=2024, year_max=2025, seed=99)
        self.assertNotEqual([a.key for a in s1], [a.key for a in s2])

    def test_takes_all_available_when_year_underpopulated(self):
        self._make_corpus({2024: 5, 2025: 50, 2026: 50})
        sample = sample_articles(
            self.parquet_path,
            sample_size=60, year_min=2024, year_max=2026, seed=42,
        )
        per_year = {2024: 0, 2025: 0, 2026: 0}
        for art in sample:
            per_year[art.year] += 1
        # Year 2024 has only 5 articles — must take all 5
        self.assertEqual(per_year[2024], 5)
        # Remaining 55 distributed across 2025/2026
        self.assertEqual(per_year[2025] + per_year[2026], 55)

    def test_sampled_articles_carry_content(self):
        self._make_corpus({2024: 10})
        sample = sample_articles(
            self.parquet_path,
            sample_size=5, year_min=2024, year_max=2024, seed=42,
        )
        for art in sample:
            self.assertTrue(art.title.startswith('Article '))
            self.assertTrue(art.body_text.startswith('Body '))

    def test_sample_keys_are_unique(self):
        self._make_corpus({2024: 100, 2025: 100})
        sample = sample_articles(
            self.parquet_path,
            sample_size=50, year_min=2024, year_max=2025, seed=42,
        )
        keys = [a.key for a in sample]
        self.assertEqual(len(keys), len(set(keys)))

    def test_skips_articles_with_empty_title_and_body(self):
        consultations = [{
            'consultation_id': 1,
            'start_date': dt.datetime(2024, 6, 15),
            'articles': [
                {'article_id': 1, 'title': '', 'body_text': ''},
                {'article_id': 2, 'title': 'Real', 'body_text': 'Body'},
            ],
        }]
        _build_parquet(self.parquet_path, consultations)
        sample = sample_articles(
            self.parquet_path,
            sample_size=10, year_min=2024, year_max=2024, seed=42,
        )
        self.assertEqual(len(sample), 1)
        self.assertEqual(sample[0].article_id, 2)


class SampledArticleTest(TestCase):
    def test_key_format(self):
        a = SampledArticle(consultation_id=42, article_id=99, year=2024, title='t', body_text='b')
        self.assertEqual(a.key, '42:99')
