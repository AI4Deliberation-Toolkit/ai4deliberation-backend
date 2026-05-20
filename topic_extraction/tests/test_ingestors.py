import os
import tempfile
from django.test import TestCase
from topic_extraction.ingestors.base import BaseIngestor, Conversation


class ConversationTest(TestCase):
    def test_conversation_fields(self):
        c = Conversation(
            article_id='art-1',
            platform='ypepth',
            article='Article text',
            comments=['comment 1', 'comment 2'],
        )
        self.assertEqual(c.article_id, 'art-1')
        self.assertEqual(c.platform, 'ypepth')
        self.assertEqual(len(c.comments), 2)

    def test_conversation_defaults_empty_comments(self):
        c = Conversation(article_id='art-1', platform='ypepth', article='text')
        self.assertEqual(c.comments, [])

    def test_base_ingestor_is_abstract(self):
        with self.assertRaises(TypeError):
            BaseIngestor()


# Path to the sample file checked into resources/ (unversioned, available locally)
SAMPLE_XLS = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'resources', 'ypepth_comments_4.xls'
)


class XLSIngestorTest(TestCase):
    def test_loads_conversations_from_ypepth_file(self):
        if not os.path.exists(SAMPLE_XLS):
            self.skipTest('Sample XLS file not available')
        from topic_extraction.ingestors.xls import XLSIngestor
        ingestor = XLSIngestor(platform='ypepth')
        conversations = ingestor.load(SAMPLE_XLS)
        self.assertGreater(len(conversations), 0)
        first = conversations[0]
        self.assertEqual(first.platform, 'ypepth')
        self.assertIsInstance(first.article_id, str)
        self.assertIsInstance(first.article, str)
        self.assertIsInstance(first.comments, list)
        self.assertGreater(len(first.comments), 0)

    def test_groups_comments_by_article(self):
        if not os.path.exists(SAMPLE_XLS):
            self.skipTest('Sample XLS file not available')
        from topic_extraction.ingestors.xls import XLSIngestor
        ingestor = XLSIngestor(platform='ypepth')
        conversations = ingestor.load(SAMPLE_XLS)
        # Each conversation should be a distinct article
        article_ids = [c.article_id for c in conversations]
        self.assertEqual(len(article_ids), len(set(article_ids)))

    def test_skips_empty_rows(self):
        if not os.path.exists(SAMPLE_XLS):
            self.skipTest('Sample XLS file not available')
        from topic_extraction.ingestors.xls import XLSIngestor
        ingestor = XLSIngestor(platform='ypepth')
        conversations = ingestor.load(SAMPLE_XLS)
        for conv in conversations:
            self.assertTrue(conv.article_id.strip())
            for comment in conv.comments:
                self.assertTrue(comment.strip())


def _build_opengov_parquet(path, consultations):
    """Write a parquet file mirroring the opengov_deliberations_v2 schema.

    consultations is a list of dicts with keys: consultation_id, articles.
    Each article dict has: article_id, title, body_text.
    Other schema fields are filled with defaults to keep tests focused.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = []
    for c in consultations:
        rows.append({
            'consultation_id': c['consultation_id'],
            'post_id': c.get('post_id', str(c['consultation_id'])),
            'url': c.get('url', ''),
            'title': c.get('title', ''),
            'start_minister_message': c.get('start_minister_message', ''),
            'end_minister_message': c.get('end_minister_message', ''),
            'ministry': {
                'ministry_id': c.get('ministry_id', 1),
                'code': c.get('ministry_code', 'min'),
                'name': c.get('ministry_name', ''),
                'url': c.get('ministry_url', ''),
            },
            'articles': [
                {
                    'article_id': a['article_id'],
                    'title': a.get('title', ''),
                    'url': a.get('url', ''),
                    'body_text': a.get('body_text', ''),
                    'comments': a.get('comments', []),
                }
                for a in c['articles']
            ],
        })
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


class OpengovIngestorTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.parquet_path = os.path.join(self.tmpdir.name, 'opengov.parquet')

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_loads_one_conversation_per_article(self):
        _build_opengov_parquet(self.parquet_path, [
            {'consultation_id': 1, 'articles': [
                {'article_id': 10, 'title': 'A1', 'body_text': 'body1'},
                {'article_id': 11, 'title': 'A2', 'body_text': 'body2'},
            ]},
            {'consultation_id': 2, 'articles': [
                {'article_id': 20, 'title': 'B1', 'body_text': 'body3'},
            ]},
        ])
        from topic_extraction.ingestors.opengov import OpengovIngestor
        ingestor = OpengovIngestor(platform='opengov')
        conversations = ingestor.load(self.parquet_path)
        self.assertEqual(len(conversations), 3)

    def test_article_id_combines_consultation_and_article(self):
        _build_opengov_parquet(self.parquet_path, [
            {'consultation_id': 42, 'articles': [
                {'article_id': 99, 'title': 'T', 'body_text': 'B'},
            ]},
        ])
        from topic_extraction.ingestors.opengov import OpengovIngestor
        ingestor = OpengovIngestor(platform='opengov')
        conversations = ingestor.load(self.parquet_path)
        self.assertEqual(conversations[0].article_id, '42:99')

    def test_article_text_concatenates_title_and_body(self):
        _build_opengov_parquet(self.parquet_path, [
            {'consultation_id': 1, 'articles': [
                {'article_id': 10, 'title': 'Άρθρο 1', 'body_text': 'Το κείμενο'},
            ]},
        ])
        from topic_extraction.ingestors.opengov import OpengovIngestor
        ingestor = OpengovIngestor(platform='opengov')
        conversations = ingestor.load(self.parquet_path)
        self.assertIn('Άρθρο 1', conversations[0].article)
        self.assertIn('Το κείμενο', conversations[0].article)

    def test_comments_are_empty(self):
        _build_opengov_parquet(self.parquet_path, [
            {'consultation_id': 1, 'articles': [
                {'article_id': 10, 'title': 'T', 'body_text': 'B', 'comments': [
                    {'comment_row_id': 1, 'content': 'ignored', 'date': None},
                ]},
            ]},
        ])
        from topic_extraction.ingestors.opengov import OpengovIngestor
        ingestor = OpengovIngestor(platform='opengov')
        conversations = ingestor.load(self.parquet_path)
        self.assertEqual(conversations[0].comments, [])

    def test_platform_tag_propagates(self):
        _build_opengov_parquet(self.parquet_path, [
            {'consultation_id': 1, 'articles': [
                {'article_id': 10, 'title': 'T', 'body_text': 'B'},
            ]},
        ])
        from topic_extraction.ingestors.opengov import OpengovIngestor
        ingestor = OpengovIngestor(platform='opengov')
        conversations = ingestor.load(self.parquet_path)
        self.assertEqual(conversations[0].platform, 'opengov')

    def test_skips_articles_with_empty_title_and_body(self):
        _build_opengov_parquet(self.parquet_path, [
            {'consultation_id': 1, 'articles': [
                {'article_id': 10, 'title': '', 'body_text': ''},
                {'article_id': 11, 'title': 'real', 'body_text': 'body'},
                {'article_id': 12, 'title': '   ', 'body_text': '\n\t'},
            ]},
        ])
        from topic_extraction.ingestors.opengov import OpengovIngestor
        ingestor = OpengovIngestor(platform='opengov')
        conversations = ingestor.load(self.parquet_path)
        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0].article_id, '1:11')

    def test_missing_source_raises(self):
        from topic_extraction.ingestors.opengov import OpengovIngestor
        ingestor = OpengovIngestor(platform='opengov')
        with self.assertRaises(FileNotFoundError):
            ingestor.load(os.path.join(self.tmpdir.name, 'nonexistent.parquet'))
