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
