import os
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
