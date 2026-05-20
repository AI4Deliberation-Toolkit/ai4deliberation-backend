import datetime as dt
import json
import os
import tempfile
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


def _build_parquet(path, consultations):
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


def _fake_extract_payload(article_id, **kwargs):
    return {
        'article_id': article_id,
        'platform': 'opengov',
        'language': 'el',
        'language_source': 'detected',
        'raw_topics': [{'label': 'Foo', 'score': 0.9}],
        'normalized': [{'topic_id': 'foo', 'score': 0.9}],
        'backend': 'embedding',
        'taxonomy_version': 'v1',
    }


class CorpusPassNewRunTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.tmpdir.name, 'corpus.parquet')
        self.output_dir = os.path.join(self.tmpdir.name, 'out')
        _build_parquet(self.source, [
            {'consultation_id': 1, 'start_date': dt.datetime(2024, 6, 15), 'articles': [
                {'article_id': 10, 'title': 'A1', 'body_text': 'B1'},
                {'article_id': 11, 'title': 'A2', 'body_text': 'B2'},
                {'article_id': 12, 'title': 'A3', 'body_text': 'B3'},
            ]},
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    def _find_run_files(self):
        files = os.listdir(self.output_dir)
        jsonl = [f for f in files if f.endswith('.jsonl')]
        manifest = [f for f in files if f.endswith('.manifest.json')]
        return jsonl, manifest

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_creates_jsonl_and_manifest(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        out = StringIO()
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=3, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=out,
        )
        jsonl_files, manifest_files = self._find_run_files()
        self.assertEqual(len(jsonl_files), 1)
        self.assertEqual(len(manifest_files), 1)

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_jsonl_contains_one_line_per_sampled_article(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=3, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=StringIO(),
        )
        jsonl_files, _ = self._find_run_files()
        with open(os.path.join(self.output_dir, jsonl_files[0]), 'r') as f:
            lines = [line for line in f if line.strip()]
        self.assertEqual(len(lines), 3)

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_jsonl_line_has_expected_fields(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=3, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=StringIO(),
        )
        jsonl_files, _ = self._find_run_files()
        with open(os.path.join(self.output_dir, jsonl_files[0]), 'r') as f:
            line = json.loads(f.readline())
        for field in ('consultation_id', 'article_id', 'year', 'extracted_at',
                      'language', 'raw_topics', 'normalized', 'backend',
                      'taxonomy_version'):
            self.assertIn(field, line)

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_manifest_records_run_parameters(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=3, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=StringIO(),
        )
        _, manifest_files = self._find_run_files()
        manifest = json.loads(
            open(os.path.join(self.output_dir, manifest_files[0])).read()
        )
        self.assertEqual(manifest['sample_size'], 3)
        self.assertEqual(manifest['year_min'], 2024)
        self.assertEqual(manifest['year_max'], 2024)
        self.assertEqual(manifest['seed'], 42)
        self.assertIn('created_at', manifest)
        self.assertIn('sampled_keys', manifest)
        self.assertEqual(len(manifest['sampled_keys']), 3)

    def test_missing_source_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command(
                'corpus_pass',
                source=os.path.join(self.tmpdir.name, 'nonexistent.parquet'),
                stdout=StringIO(),
            )

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_calls_pipeline_extract_for_each_sampled_article(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=3, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=StringIO(),
        )
        self.assertEqual(mock_extract.call_count, 3)

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_default_backend_is_embedding_similarity(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=1, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=StringIO(),
        )
        # pipeline.extract receives backend='embedding_similarity' by default.
        _, kwargs = mock_extract.call_args
        self.assertEqual(kwargs.get('backend'), 'embedding_similarity')

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_backend_flag_is_passed_through(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=1, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            backend='embedding',
            stdout=StringIO(),
        )
        _, kwargs = mock_extract.call_args
        self.assertEqual(kwargs.get('backend'), 'embedding')

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_manifest_records_backend(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=1, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=StringIO(),
        )
        _, manifest_files = self._find_run_files()
        with open(os.path.join(self.output_dir, manifest_files[0]), 'r') as f:
            manifest = json.load(f)
        self.assertEqual(manifest.get('backend'), 'embedding_similarity')

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_max_articles_caps_processing(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=3, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            max_articles=2,
            stdout=StringIO(),
        )
        self.assertEqual(mock_extract.call_count, 2)
        jsonl_files, _ = self._find_run_files()
        with open(os.path.join(self.output_dir, jsonl_files[0]), 'r') as f:
            lines = [line for line in f if line.strip()]
        self.assertEqual(len(lines), 2)

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_resume_after_max_articles_processes_remainder(self, mock_extract):
        # Smoke-style first run: cap at 2 of 3.
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=3, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            max_articles=2,
            stdout=StringIO(),
        )
        jsonl_files, _ = self._find_run_files()
        jsonl_path = os.path.join(self.output_dir, jsonl_files[0])

        mock_extract.reset_mock()
        # Resume — should process the remaining 1.
        call_command(
            'corpus_pass',
            source=self.source,
            resume=jsonl_path,
            stdout=StringIO(),
        )
        self.assertEqual(mock_extract.call_count, 1)
        with open(jsonl_path, 'r') as f:
            lines = [line for line in f if line.strip()]
        self.assertEqual(len(lines), 3)

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_does_not_persist_to_article_topic_table(self, mock_extract):
        from topic_extraction.models import ArticleTopic
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        before = ArticleTopic.objects.count()
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=3, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=StringIO(),
        )
        after = ArticleTopic.objects.count()
        self.assertEqual(before, after)


class CorpusPassResumeTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.tmpdir.name, 'corpus.parquet')
        self.output_dir = os.path.join(self.tmpdir.name, 'out')
        _build_parquet(self.source, [
            {'consultation_id': 1, 'start_date': dt.datetime(2024, 6, 15), 'articles': [
                {'article_id': i, 'title': f'A{i}', 'body_text': f'B{i}'} for i in range(10, 16)
            ]},
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_resume_skips_already_processed_articles(self, mock_extract):
        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        # First run — process all 6 articles
        call_command(
            'corpus_pass',
            source=self.source,
            sample_size=6, year_min=2024, year_max=2024,
            seed=42, output_dir=self.output_dir,
            stdout=StringIO(),
        )
        first_call_count = mock_extract.call_count
        self.assertEqual(first_call_count, 6)

        jsonl_files = [f for f in os.listdir(self.output_dir) if f.endswith('.jsonl')]
        jsonl_path = os.path.join(self.output_dir, jsonl_files[0])

        # Resume run — nothing left to process
        mock_extract.reset_mock()
        call_command(
            'corpus_pass',
            source=self.source,
            resume=jsonl_path,
            stdout=StringIO(),
        )
        self.assertEqual(mock_extract.call_count, 0)

    @patch('topic_extraction.management.commands.corpus_pass.pipeline.extract')
    def test_resume_continues_from_partial_jsonl(self, mock_extract):
        # Simulate a partial run by manually creating a JSONL with 2 of 6 articles done.
        os.makedirs(self.output_dir, exist_ok=True)
        ts = '20260519T120000'
        jsonl_path = os.path.join(self.output_dir, f'corpus_run_{ts}.jsonl')
        manifest_path = os.path.join(self.output_dir, f'corpus_run_{ts}.manifest.json')

        from topic_extraction.corpus_sampler import sample_articles
        sampled = sample_articles(self.source, sample_size=6, year_min=2024, year_max=2024, seed=42)

        manifest = {
            'source': os.path.abspath(self.source),
            'sample_size': 6, 'year_min': 2024, 'year_max': 2024, 'seed': 42,
            'created_at': '2026-05-19T12:00:00Z',
            'sampled_keys': [a.key for a in sampled],
        }
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        # Write 2 of the 6 expected lines, mirroring the command's flat output shape.
        with open(jsonl_path, 'w') as f:
            for art in sampled[:2]:
                payload = _fake_extract_payload(art.key)
                f.write(json.dumps({
                    'consultation_id': art.consultation_id,
                    'article_id': art.article_id,
                    'year': art.year,
                    'extracted_at': '2026-05-19T12:00:00Z',
                    'language': payload['language'],
                    'language_source': payload['language_source'],
                    'raw_topics': payload['raw_topics'],
                    'normalized': payload['normalized'],
                    'backend': payload['backend'],
                    'taxonomy_version': payload['taxonomy_version'],
                }) + '\n')

        mock_extract.side_effect = lambda article_id, **kw: _fake_extract_payload(article_id, **kw)
        call_command(
            'corpus_pass',
            source=self.source,
            resume=jsonl_path,
            stdout=StringIO(),
        )
        self.assertEqual(mock_extract.call_count, 4)

        # Final JSONL should have all 6 lines.
        with open(jsonl_path, 'r') as f:
            lines = [line for line in f if line.strip()]
        self.assertEqual(len(lines), 6)
